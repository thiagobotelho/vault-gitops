#!/usr/bin/env python3
"""Inicializa/deslacra Vault e configura PKI do laboratório sem imprimir secrets."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from vault_api import apply, connection, login, oc, VaultError

parser=argparse.ArgumentParser()
parser.add_argument('--backup',required=True,help='Arquivo .age fora do checkout')
parser.add_argument('--recipient-file',help='Chave pública age/SSH para inicialização')
parser.add_argument('--identity',help='Identidade age/SSH para recuperar um Vault inicializado')
parser.add_argument('--unseal-only',action='store_true')
a=parser.parse_args()
backup=Path(a.backup).expanduser().resolve()
repo=Path(__file__).resolve().parents[1]
if backup.is_relative_to(repo):raise SystemExit('O backup deve ficar fora do checkout')
age=os.environ.get('AGE_BIN') or shutil.which('age')
if not age:raise SystemExit('Instale age antes de inicializar; nenhuma chave será criada sem backup cifrado')
with connection() as v:
    initialized=v('GET','sys/init')['initialized']
    if not initialized:
        if not a.recipient_file or backup.exists():raise SystemExit('Informe chave pública e um caminho novo de backup')
        if not Path(a.recipient_file).expanduser().is_file():raise SystemExit('Chave pública ausente')
        data=v('PUT','sys/init',{'secret_shares':3,'secret_threshold':2})
        backup.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:
            subprocess.run([age,'-R',str(Path(a.recipient_file).expanduser())],input=json.dumps(data).encode(),stdout=f,check=True)
        print('Backup cifrado gravado em',backup)
    else:
        if not a.identity or not backup.is_file():raise SystemExit('Vault inicializado: informe backup cifrado e --identity')
        data=json.loads(subprocess.check_output([age,'-d','-i',str(Path(a.identity).expanduser()),str(backup)]))
    if v('GET','sys/seal-status')['sealed']:
        for key in data['keys_base64'][:2]:v('PUT','sys/unseal',{'key':key})
    assert not v('GET','sys/seal-status')['sealed']
    if a.unseal_only:
        print('PASS: Vault deslacrado');raise SystemExit(0)
    root=data['root_token']; initial_root=True
    for attempt in range(30):
        try:
            v('GET','auth/token/lookup-self',token=root); break
        except VaultError as error:
            if error.status in [401,403]:
                root=login(v); initial_root=False; break
            if error.status not in [500,503] or attempt == 29: raise
            time.sleep(1)
    def call(method,path,payload=None):return v(method,path,payload,root)
    mounts=call('GET','sys/mounts')['data']
    for mount,ttl in [('pki-root','43800h'),('pki-mesh','8760h')]:
        if mount+'/' not in mounts:call('POST','sys/mounts/'+mount,{'type':'pki','config':{'max_lease_ttl':ttl}})
    try:root_ca=call('GET','pki-root/cert/ca')['data']['certificate']
    except VaultError:
        root_ca=call('POST','pki-root/root/generate/internal',{'common_name':'Laboratorio Root CA','ttl':'43800h','key_type':'ec','key_bits':256})['data']['certificate']
    try:call('GET','pki-mesh/cert/ca')
    except VaultError:
        csr=call('POST','pki-mesh/intermediate/generate/internal',{'common_name':'Laboratorio Mesh Intermediate CA','key_type':'ec','key_bits':256})['data']['csr']
        certificate=call('POST','pki-root/root/sign-intermediate',{'csr':csr,'ttl':'8760h','format':'pem_bundle'})['data']['certificate']
        call('POST','pki-mesh/intermediate/set-signed',{'certificate':certificate})
    role={'allowed_domains':['lab.internal','istio-vault-system.svc','istio-csr-vault.svc'], 'allow_subdomains':True,'allow_bare_domains':True,'allow_localhost':False,'allow_ip_sans':False,'allowed_uri_sans':['spiffe://cluster.local/ns/mesh-vault-lab/sa/*','spiffe://cluster.local/ns/istio-vault-system/sa/*'],'require_cn':False,'key_type':'any','ttl':'1h','max_ttl':'1h'}
    call('POST','pki-mesh/roles/mesh-vault',role)
    call('POST','pki-mesh/roles/lab-server',{'allowed_domains':['lab.internal'],'allow_subdomains':True,'allow_bare_domains':False,'allow_ip_sans':False,'ttl':'1h','max_ttl':'1h'})
    if initial_root:
        auth=call('GET','sys/auth')['data']
        if 'kubernetes/' not in auth:call('POST','sys/auth/kubernetes',{'type':'kubernetes'})
        call('POST','auth/kubernetes/config',{'kubernetes_host':'https://kubernetes.default.svc:443'})
        call('PUT','sys/policies/acl/mesh-sign',{'policy':'path "pki-mesh/sign/mesh-vault" { capabilities = ["update"] }\npath "pki-mesh/cert/ca" { capabilities = ["read"] }'})
        call('POST','auth/kubernetes/role/mesh-vault',{'bound_service_account_names':['vault-issuer'],'bound_service_account_namespaces':['istio-vault-system'],'audience':'vault://mesh-vault','token_policies':['mesh-sign'],'token_ttl':'5m','token_max_ttl':'10m'})
        policy='''path "pki-root/*" { capabilities = ["create","read","update","delete","list"] }
path "pki-mesh/*" { capabilities = ["create","read","update","delete","list"] }
path "sys/health" { capabilities = ["read"] }
path "sys/mounts" { capabilities = ["read"] }
path "sys/audit" { capabilities = ["read","list"] }
path "auth/token/create" { capabilities = ["update"] }
'''
        call('PUT','sys/policies/acl/pki-lab-admin',{'policy':policy})
        call('POST','auth/kubernetes/role/operator',{'bound_service_account_names':['vault-operator'],'bound_service_account_namespaces':['vault'],'audience':'vault://operator','token_policies':['pki-lab-admin'],'token_ttl':'15m','token_max_ttl':'1h'})
        if 'file/' not in call('GET','sys/audit')['data']:call('PUT','sys/audit/file',{'type':'file','options':{'file_path':'/vault/audit/audit.log'}})
        if 'stdout/' not in call('GET','sys/audit')['data']:call('PUT','sys/audit/stdout',{'type':'file','options':{'file_path':'stdout'}})
    # Public trust data only; generated outside Git and reconciled by this helper.
    for ns in ['istio-vault-system','istio-csr-vault']:
        apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'istio-discovery':'mesh-vault','observability':'enabled'}}})
    apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'vault-mesh-root','namespace':'istio-csr-vault'},'data':{'root-cert.pem':root_ca}})
    ca=oc('-n','vault','get','configmap/vault-service-ca','-o','jsonpath={.data.service-ca\\.crt}')
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'vault-server-ca','namespace':'istio-vault-system'},'type':'Opaque','stringData':{'ca.crt':ca}})
    if initial_root:call('POST','auth/token/revoke-self')
    data=None;root=None
    print('PASS: PKI e autenticação configuradas; root inicial revogado quando usado')
