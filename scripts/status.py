#!/usr/bin/env python3
"""Consulta estado e mounts, sem imprimir tokens ou material de chave."""
from vault_api import connection, login
with connection() as call:
    sealed=call('GET','sys/seal-status')
    print('Inicializado:',sealed['initialized'],'Selado:',sealed['sealed'])
    if not sealed['sealed']:
        token=login(call)
        mounts=call('GET','sys/mounts',token=token)['data']
        print('PKI:',', '.join(sorted(k for k,v in mounts.items() if v['type']=='pki')))
