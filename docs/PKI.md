# Emitir certificados

## Pelo cert-manager

Este é o caminho declarativo recomendado para um servidor Kubernetes: uma Certificate define DNS, validade, chave e Secret de destino. O Issuer consulta o Vault e o cert-manager mantém renovação e rotação.

No checkout cert-manager-gitops:

```bash
oc apply -f examples/certificate.yaml
oc -n istio-vault-system wait certificate/vault-demo --for=condition=Ready --timeout=120s
oc -n istio-vault-system get certificate vault-demo
oc -n istio-vault-system get secret vault-demo-tls -o 'jsonpath={.data.tls\.crt}'   | base64 -d | openssl x509 -noout -issuer -subject -dates
```

O último comando mostra somente o certificado público. A chave privada fica no Secret; não exporte o objeto inteiro para tickets ou para o Git. A aplicação precisa montar o Secret e suportar recarga, ou ter reinício controlado: renovar o Secret não reinicia automaticamente qualquer aplicação.

## Por CSR/API Vault

Para estudar a assinatura diretamente, gere a chave privada fora do checkout e envie ao Vault somente uma CSR. O mecanismo PKI também possui operação issue, que devolve uma chave privada; não use essa resposta em logs ou exemplos públicos.

A policy do operador permite a role lab-server sob pki-mesh. Essa role aceita subdomínios de lab.internal por até uma hora. Na console, navegue em pki-mesh → roles → lab-server e use a assinatura de CSR; ajuste os nomes conforme as permissões, sem liberar allow_any_name como atalho.

## Certificados do mesh

O agente Istio gera a chave e solicita certificado ao istio-csr. Não se cria uma Certificate manual por pod. O agente/proxy usa SDS para obter e renovar a identidade; ela contém uma URI como spiffe://cluster.local/ns/mesh-vault-lab/sa/sleep.

A validade é curta e a cadeia deve terminar na raiz pública esperada. Para verificação completa, use scripts/verify-certificates.py no projeto cert-manager-gitops. O teste compara cadeia e SAN; conferir apenas o nome do emissor não comprova confiança.
