# Console, diagnóstico e recuperação

## Acessar a console

Abra https://vault.apps-crc.testing/ui/. A Route reencrypt usa TLS no navegador e no trecho router→Vault. O certificado externo é o do ingresso OpenShift; a confiança usada pelo cert-manager para o Service é outra.

Na console, selecione o método Token. Um operador com permissão de criar token da ServiceAccount vault-operator pode obter um token curto:

```bash
python3 scripts/admin-token.py
```

A saída desse comando é uma **credencial** para copiar na console: não cole em issues, chats, documentação ou CI. O programa não grava token em disco. O perfil não configura login OIDC da console; essa integração deve ser cadastrada separadamente se desejada.

A console permite navegar pelas PKIs, certificados e roles conforme a policy. A configuração desejada continua nos scripts/manifests; alterações manuais na console precisam ser reconciliadas na fonte responsável.

## Deslacrar após reinício

Sem auto-unseal externo, um reinício do processo exige deslacramento. Use a identidade privada correspondente ao destinatário do backup:

```bash
python3 scripts/bootstrap-pki.py   --identity "$HOME/.ssh/id_ed25519"   --backup "$HOME/.local/state/vault-lab/bootstrap.age"   --unseal-only
python3 scripts/status.py
```

Não reinicialize um Vault que já possui dados nem exclua PVCs para corrigir estado lacrado. A perda de shares/identidade de decriptação pode impedir recuperação. O backup age não é backup do banco Raft: preserve snapshots e o material de recuperação de forma independente.

## Investigar por etapa

| Sintoma | Conferir |
|---|---|
| ImagePullBackOff | Imagem/digest e acesso ao registry; referência docker.io explícita |
| Pod Running, não pronto | sys/seal-status; inicialização/deslacramento |
| Issuer não pronto | Service Vault, CA HTTPS, RoleBinding TokenRequest, role e audience Kubernetes |
| CertificateRequest recusado | DNS/URI SAN, TTL e policy da role de assinatura |
| Proxy sem certificado | IstioCSR, CertificateRequest, raiz distribuída e endereço da CA |
| HTTP 403 no mesh | AuthorizationPolicy e response_code_details do proxy |

```bash
oc -n vault get pods,pvc,svc,route
oc -n istio-vault-system get issuer,certificate,certificaterequest
oc -n istio-csr-vault get istiocsr,pods
```

## Auditoria e métricas

Auditoria é habilitada em stdout e em /vault/audit/audit.log no PVC próprio, com HMAC dos campos sensíveis pelo mecanismo padrão do Vault. No Logging, filtre namespace vault e o container vault para chamadas PKI/autenticação. Não habilite log_raw para facilitar diagnóstico. Defina retenção/rotação e capacidade do arquivo antes de ampliar o uso; o perfil não instala um serviço de arquivamento externo.

O ServiceMonitor consulta /v1/sys/metrics com TLS validado no Prometheus Apps. O endpoint de métricas permite leitura sem token, restrita pela NetworkPolicy aos consumidores autorizados no namespace. Uma série ausente não deve ser interpretada como zero. Grafana/Prometheus mostram métricas; a console Vault administra a PKI.

Certificados de serviço renovados pelo OpenShift e mudanças da Service CA exigem verificar recarga do servidor e atualizar a cópia de confiança do Issuer. Reexecute o bootstrap com backup/identidade para sincronizar a confiança pública; planeje o reinício/deslacramento quando necessário.

## Reversão

Remova primeiro workloads dependentes; depois a integração mesh/istio-csr e Issuer. Preserve snapshots e shares antes de remover o servidor. Evite apagar o Operator cert-manager enquanto houver certificados/consumidores. As Applications opcionais não habilitam prune automático.
