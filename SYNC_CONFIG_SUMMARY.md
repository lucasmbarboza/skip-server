# Configuração de Sincronização SKIP Server

## Resumo das Configurações Aplicadas

### Arquitetura
- **Servidor interno**: HTTP na porta 8080 (localhost)
- **Proxy TLS**: stunnel4 na porta 8443 (externa)
- **Sincronização**: HTTPS via stunnel na porta 8443

### Fluxo de Comunicação
```
Peer SKIP ←→ [Port 8443 - stunnel4 - TLS PSK] ←→ [Port 8080 - Flask HTTP] ←→ SKIP Server
```

### Configurações Aplicadas

#### skip_config.py
- `SYNC_USE_HTTPS = True` - Usar HTTPS para sincronização
- `SYNC_PORT = 8443` - Porta para comunicação entre peers
- `SSL_VERIFY_PEER = False` - Não verificar certificados válidos
- `SSL_CHECK_HOSTNAME = False` - Não verificar hostname
- `STUNNEL_ACCEPT_PORT = 8443` - Porta externa stunnel

#### skip_sync.py
- Configuração SSL context sem verificação de certificados
- Suporte para HTTPS via stunnel
- Retry logic com tratamento específico para erros SSL
- Headers de identificação SKIP

#### stunnel.conf
- Aceita conexões na porta 8443
- Proxy para localhost:8080
- TLS PSK com algoritmos RFC SKIP compliant
- Apenas TLS 1.2 permitido

#### psk.txt
- Pre-Shared Keys para autenticação TLS PSK
- Formato: `CLIENT_ID:HEX_KEY`

### Benefícios
✅ **Sem certificados válidos**: Desenvolvimento simplificado
✅ **TLS PSK**: Segurança conforme RFC SKIP
✅ **Porta única**: Todas as conexões via 8443
✅ **stunnel proxy**: Terminação TLS externa ao Flask
✅ **Compatibilidade**: Protocolo HTTPS padrão

### Como Usar
1. Configure peers no `skip_config.py` com porta 8443
2. Adicione PSK no arquivo `psk.txt`
3. Execute stunnel4 com a configuração fornecida
4. Execute o servidor SKIP na porta 8080
5. Peers se conectam na porta 8443 (HTTPS)

### Exemplo de Configuração de Peer
```python
SYNC_PEERS = [
    {
        "system_id": "KP_QuIIN_Backup",
        "endpoint": "192.168.1.100",
        "port": 8443,  # Porta HTTPS via stunnel
        "shared_secret": "your_shared_secret_here"
    }
]
```