#!/usr/bin/env python3
"""Validação estática: composição, contratos de segurança e links locais."""
from pathlib import Path
import re
import subprocess
import yaml
root=Path(__file__).resolve().parents[1]
rendered=[]
for p in root.rglob('kustomization.yaml'):
    docs=[x for x in yaml.safe_load_all(subprocess.check_output(['kubectl','kustomize',str(p.parent)],text=True)) if x]
    keys=[(x['apiVersion'],x['kind'],x['metadata'].get('namespace'),x['metadata']['name']) for x in docs]
    assert len(keys)==len(set(keys)),p
    rendered+=docs
for p in root.rglob('*.md'):
    if '.git' in p.parts:continue
    for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if ':' not in link and not link.startswith('#'):assert (p.parent/link.split('#')[0]).exists(),(p,link)
for obj in rendered:
    if obj['kind']=='Secret':raise AssertionError('Secrets gerados pertencem ao bootstrap, não ao Git')
    if obj['kind']=='ClusterRoleBinding':assert obj['roleRef']['name']!='cluster-admin'
    if obj['kind']=='StatefulSet':
        assert obj['spec']['replicas']==1
        for c in obj['spec']['template']['spec']['containers']:
            assert 'sha256:' in c['image']
            assert not c.get('securityContext',{}).get('privileged',False)
            assert c['securityContext']['allowPrivilegeEscalation'] is False
            names=[e['name'] for e in c.get('env',[])];assert len(names)==len(set(names))
    if obj['kind']=='Issuer':
        v=obj['spec']['vault'];assert v['server'].startswith('https://')
        assert 'serviceAccountRef' in v['auth']['kubernetes']
        assert 'secretRef' not in v['auth']['kubernetes']
    if obj['kind']=='IstioCSR':
        assert obj['metadata']['name']=='default'
        assert obj['spec']['istioCSRConfig']['istioDataPlaneNamespaceSelector']=='istio-discovery=mesh-vault'
print('PASS: composição Kustomize, contratos e links')
