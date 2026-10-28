"""Cliente local: TLS verificado, port-forward e tokens apenas em memória."""
import contextlib
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import time

OC = ['oc', '--request-timeout=30s']
if os.environ.get('OC_CONTEXT'):
    OC += ['--context', os.environ['OC_CONTEXT']]

def oc(*args, stdin=None):
    return subprocess.check_output(OC + list(args), input=stdin, text=True).strip()

def apply(obj):
    subprocess.run(OC + ['apply', '-f', '-'], input=json.dumps(obj), text=True, check=True, stdout=subprocess.DEVNULL)

class VaultError(RuntimeError):
    def __init__(self, status, path):
        super().__init__(f'Vault HTTP {status} em {path}; confira permissões e configuração, sem imprimir credenciais')
        self.status = status

@contextlib.contextmanager
def connection():
    server = oc('whoami', '--show-server')
    if server != 'https://api.crc.testing:6443':
        raise RuntimeError('Este perfil exige CRC; confira contexto e servidor')
    ca = oc('-n', 'vault', 'get', 'configmap/vault-service-ca', '-o', 'jsonpath={.data.service-ca\\.crt}')
    context = ssl.create_default_context(cadata=ca)
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    process = subprocess.Popen(OC + ['-n','vault','port-forward','svc/vault',f'{port}:8200','--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', port), 0.2).close(); break
            except OSError:
                if process.poll() is not None: raise RuntimeError('Port-forward não iniciou')
                time.sleep(0.2)
        def call(method, path, data=None, token=None):
            client = http.client.HTTPConnection('vault.vault.svc', timeout=30)
            client.sock = context.wrap_socket(socket.create_connection(('127.0.0.1',port),20),server_hostname='vault.vault.svc')
            headers = {'Content-Type':'application/json'}
            if token: headers['X-Vault-Token'] = token
            client.request(method, '/v1/' + path, body=None if data is None else json.dumps(data), headers=headers)
            response = client.getresponse(); body = response.read(); client.close()
            if response.status not in [200,204]: raise VaultError(response.status,path)
            return json.loads(body) if body else {}
        yield call
    finally:
        process.terminate(); process.wait(timeout=5)

def login(call, role='operator', namespace='vault', account='vault-operator', audience='vault://operator'):
    jwt = oc('-n',namespace,'create','token',account,'--audience='+audience,'--duration=10m')
    return call('POST','auth/kubernetes/login',{'role':role,'jwt':jwt})['auth']['client_token']
