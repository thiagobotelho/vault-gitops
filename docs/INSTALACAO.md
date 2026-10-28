# Instalar no CRC

## Pré-requisitos

CRC autenticado em oc, Git, kubectl/Kustomize, Python 3.10+, age e uma chave pública age ou SSH com identidade privada recuperável. Helm é necessário para regenerar o chart; a aplicação dos manifests versionados usa somente Kustomize. Instale o cert-manager Operator conforme o README do projeto correspondente antes de configurar a integração.

O perfil usa namespace vault, domínio apps-crc.testing e a StorageClass padrão. Revise recursos, DNS e capacidade do provisionador. O hostpath do CRC pode anunciar uma capacidade de PV diferente do pedido e não representa reserva física isolada.

## Instalar o servidor

```bash
oc whoami
oc whoami --show-server
oc apply -k overlays/desenvolvimento
oc -n vault get pods,pvc,svc,route
oc -n vault wait pod/vault-0 --for=jsonpath='{.status.phase}'=Running --timeout=180s
```

Antes da inicialização, Running com Ready=False é esperado: o Vault ainda está lacrado. Não altere a readiness para tratar um servidor lacrado como pronto.

## Inicializar e configurar PKI

Escolha um diretório privado fora do checkout. O script exige age, grava um backup cifrado antes de prosseguir e não imprime as chaves. Nunca substitua o backup de uma instância por outro arquivo sem identificar a origem.

```bash
python3 scripts/bootstrap-pki.py   --recipient-file "$HOME/.ssh/id_ed25519.pub"   --backup "$HOME/.local/state/vault-lab/bootstrap.age"
python3 scripts/status.py
oc -n vault wait pod/vault-0 --for=condition=Ready --timeout=120s
```

O bootstrap cria três shares com limiar dois, deslacra, cria raiz/intermediária, roles, autenticação Kubernetes e auditoria. O root token inicial é revogado ao concluir. O arquivo cifrado contém os shares e o token inicial já revogado; sua chave privada de decriptação precisa ser preservada separadamente.

Neste laboratório, os três shares estão no mesmo arquivo cifrado: isso protege o armazenamento, mas não estabelece custódia por pessoas distintas. Não use esse arranjo como desenho de custódia para ambientes críticos.

O script também publica **confiança pública**, fora do Git: vault-server-ca em istio-vault-system e vault-mesh-root em istio-csr-vault. Esses namespaces são necessários para o próximo estágio. As chaves das CAs não são exportadas.

## Integrar

Siga a [integração Vault do cert-manager](https://github.com/thiagobotelho/cert-manager-gitops/blob/main/docs/INTEGRACAO-MESH.md). Ela instala Issuer e istio-csr; depois vem o plano de controle e os workloads de teste. Esse guia é a fonte da sequência entre os repositórios.

## Instalação opcional pelo Argo CD

No checkout argocd-gitops:

```bash
oc apply -k optional/vault
oc apply -k optional/cert-manager
```

Aguarde o servidor Running e faça o bootstrap manual acima. Em seguida, aplique optional/pki nesse checkout para registrar as integrações e o mesh isolado. O Argo CD não deslacra o Vault. O prune fica desabilitado: remover a Application não deve ser usado como atalho para apagar estado de PKI.

## Regenerar o chart

Edite helm/values-crc.yaml e execute scripts/render.sh. O lock registra versão e SHA256 do pacote. A imagem usa referência totalmente qualificada e digest. Revise o diff de base/vault-rendered.yaml e valide antes de publicar; não altere apenas o arquivo gerado.
