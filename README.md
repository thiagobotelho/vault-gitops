# Vault GitOps

Vault Community no OpenShift para guardar secrets e emitir certificados X.509 com o mecanismo PKI. O perfil CRC usa uma instância, armazenamento Raft persistente, HTTPS e auditoria. Não fornece alta disponibilidade: réplicas no mesmo nó não eliminam a falha desse nó.

## Começar

1. Leia [arquitetura e componentes](docs/ARQUITETURA.md).
2. Siga [instalação e bootstrap](docs/INSTALACAO.md).
3. Use [console, acesso e recuperação](docs/OPERACAO.md).
4. Consulte [emissão de certificados](docs/PKI.md).

| Caminho | Responsabilidade |
|---|---|
| helm/values-crc.yaml | Valores do chart oficial; configuração de servidor, volumes e recursos |
| helm/chart.lock.yaml | Referência do chart e versão do servidor |
| base/vault-rendered.yaml | Recursos gerados do chart, usados pelo Kustomize/Argo CD |
| base/ | Namespace, confiança HTTPS, Route, acesso de rede e monitoramento |
| overlays/desenvolvimento | Entrada de implantação no CRC |
| scripts/bootstrap-pki.py | Inicialização/deslacramento e configuração idempotente da PKI existente |
| scripts/admin-token.py | Token curto para operação/console, emitido por identidade Kubernetes |

O [cert-manager-gitops](https://github.com/thiagobotelho/cert-manager-gitops) mantém Operator, Issuer e istio-csr. O [service-mesh-gitops](https://github.com/thiagobotelho/service-mesh-gitops) mantém o plano de controle. Applications opcionais ficam em [argocd-gitops](https://github.com/thiagobotelho/argocd-gitops). Nenhum token, chave de CA ou chave de recuperação deve entrar no Git.

## Validação local

```bash
python3 -m pip install PyYAML==6.0.3
python3 tests/validate.py
bash scripts/render.sh --check
```

O primeiro comando instala a dependência de validação; use uma venv. O teste renderiza e verifica contratos locais. Ele não inicializa o Vault nem comprova emissão no cluster. Testes de integração são descritos no procedimento e suas evidências ficam fora dos repositórios.
