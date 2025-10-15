# SKIP Server - RFC Compliant Implementation

Este é um servidor de implementação do **Secure Key Integration Protocol (SKIP)** conforme especificado no draft RFC SKIP.

## Visão Geral

O SKIP é um protocolo que permite a dois participantes obter de forma segura uma chave de um Key Provider independente, fornecendo resistência quântica para protocolos de canal seguro existentes.

## Arquitetura

```
Cliente                                    Servidor
+----------------+                        +----------------+
|   Encryptor    |<-- HTTPS/TLS PSK -->  |   Encryptor    |
|      |         |                       |      |         |
|   SKIP API     |                       |   SKIP API     |
|      |         |                       |      |         |
| Key Provider   |<-- Sincronização -->  | Key Provider   |
+----------------+                        +----------------+
```

## ✨ Nova Funcionalidade: Sincronização entre Key Providers

O servidor SKIP agora inclui um sistema robusto de sincronização entre múltiplos Key Providers, implementando as diretrizes do RFC SKIP para distribuição segura de chaves.

### 🔄 Características da Sincronização

- **Sincronização Automática**: Chaves são automaticamente replicadas entre peers configurados
- **Heartbeat Monitoring**: Monitoramento contínuo do status dos peers
- **Criptografia End-to-End**: Todas as comunicações entre KPs são criptografadas
- **Autenticação HMAC**: Assinatura digital de todas as mensagens
- **Tolerância a Falhas**: Retry automático e detecção de peers offline
- **Health Monitoring**: Endpoints dedicados para monitoramento do sistema

### 🛡️ Segurança da Sincronização

- **Chaves Compartilhadas**: Cada peer usa uma chave pré-compartilhada única
- **Proteção contra Replay**: Validação de timestamp nas mensagens
- **Criptografia Fernet**: Criptografia simétrica para dados de chave
- **Zeroização Automática**: Chaves são removidas da memória após uso

## Endpoints RFC SKIP

### 1. GET /capabilities
Retorna as capacidades do Key Provider.

**Resposta:**
```json
{
    "entropy": true,
    "key": true,
    "algorithm": "TLS_DHE_PSK_WITH_AES_256_CBC_SHA384",
    "localSystemID": "KP_QuIIN_Server",
    "remoteSystemID": ["KP_QuIIN_Client", "KP_*_Test"]
}
```

### 2. GET /key?remoteSystemID=<id>&size=<bits>
Gera uma nova chave e retorna key + keyId.

**Parâmetros:**
- `remoteSystemID`: ID do sistema remoto (obrigatório)
- `size`: Tamanho da chave em bits (opcional, padrão: 256)

**Resposta:**
```json
{
    "keyId": "1726e9ae76234fb1dd1283d4dca1911e1f93864d70f3069e",
    "key": "ad229dfb8a276e74c1f3b6c09349a69fb2fed73c541270663f0e5cbbfb031670"
}
```

### 3. GET /key/{keyId}?remoteSystemID=<id>
Recupera uma chave específica pelo keyId.

**Resposta:**
```json
{
    "keyId": "1726e9ae76234fb1dd1283d4dca1911e1f93864d70f3069e",
    "key": "ad229dfb8a276e74c1f3b6c09349a69fb2fed73c541270663f0e5cbbfb031670"
}
```

### 4. GET /entropy?minentropy=<bits>
Retorna entropia aleatória.

**Parâmetros:**
- `minentropy`: Quantidade de entropia em bits (opcional, padrão: 256)

**Resposta:**
```json
{
   "randomStr": "AD229DFB8A276E74C1F3B6C09349A69FB2FED73C541270663F0E5CBBFB031670",
   "minentropy": 256
}
```

## 🔄 Endpoints de Sincronização

### 1. POST /sync
Endpoint interno para comunicação entre Key Providers.

**Uso:** Recebe mensagens de sincronização de outros KPs (heartbeat, chaves, capabilities)

### 2. GET /status/sync
Retorna o status da sincronização.

**Resposta:**
```json
{
    "sync_enabled": true,
    "local_system_id": "KP_QuIIN_Server",
    "peer_count": 2,
    "peers": {
        "KP_QuIIN_Backup": {
            "endpoint": "192.168.1.100:8443",
            "status": "online",
            "last_heartbeat": 1634567890.123
        }
    }
}
```

### 3. GET /status/health
Health check com informações de sincronização.

**Resposta:**
```json
{
    "status": "healthy",
    "timestamp": "2024-10-15T10:30:00",
    "local_system_id": "KP_QuIIN_Server",
    "stored_keys": 45,
    "max_keys": 1000,
    "sync_enabled": true,
    "sync_peers": 2,
    "online_peers": 1
}
```
```

## Configuração TLS

Conforme RFC SKIP Tabela 1, suportamos:

| Modo | TLS Version | Cipher Suite | Requirement |
|------|-------------|--------------|-------------|
| PSK | TLS 1.2 | TLS_DHE_PSK_WITH_AES_256_CBC_SHA384 | RECOMMENDED |
| PSK | TLS 1.2 | TLS_DHE_PSK_WITH_AES_256_CBC_SHA | RECOMMENDED |

## Instalação e Configuração

### 1. Requisitos

- Python 3.6+
- Flask
- stunnel4
- OpenSSL

### 2. Setup Automático

```bash
chmod +x setup_skip_enhanced.sh
./setup_skip_enhanced.sh
```

### 3. Setup Manual

1. **Instalar dependências:**
```bash
sudo apt-get update
sudo apt-get install stunnel4 python3-pip
pip3 install flask
```

2. **Configurar stunnel4:**
```bash
sudo cp stunnel.conf /etc/stunnel/stunnel.conf
sudo cp psk.txt /etc/stunnel/psk.txt
sudo chmod 600 /etc/stunnel/psk.txt
echo "ENABLED=1" | sudo tee /etc/default/stunnel4
```

3. **Iniciar serviços:**
```bash
sudo systemctl restart stunnel4
python3 skip_server.py
```

## ⚙️ Configuração de Sincronização

### Configuração Básica

Para habilitar sincronização entre Key Providers, edite `skip_config.py`:

```python
# Habilitar sincronização
SYNC_ENABLED = True
SYNC_INTERVAL = 30  # segundos
HEARTBEAT_INTERVAL = 10  # segundos

# Configurar peers
SYNC_PEERS = [
    {
        "system_id": "KP_QuIIN_Backup",
        "endpoint": "192.168.1.100",
        "port": 8443,
        "shared_secret": "sua_chave_secreta_256_bits"
    }
]
```

### Configuração Avançada

Use o arquivo `skip_sync_config.example.py` como base:

1. **Copie o arquivo de exemplo:**
```bash
cp skip_sync_config.example.py skip_sync_config.py
```

2. **Configure os ambientes:**
```bash
export SKIP_SYNC_ENV=production
```

3. **Defina peers e secrets:**
   - Cada peer deve ter uma chave compartilhada única
   - Use chaves de pelo menos 256 bits
   - Configure endpoints acessíveis

### Testando a Sincronização

Use o script de teste incluído:

```bash
# Teste básico
python3 test_skip_sync.py https://localhost:443

# Teste de sincronização entre dois servidores
python3 test_skip_sync.py https://primary:443 --secondary https://backup:443

# Teste específico
python3 test_skip_sync.py https://localhost:443 --test sync
```
```

## Estrutura de Arquivos

```
SKIP Server/
├── skip_server.py          # Servidor principal SKIP
├── skip_config.py          # Configurações
├── stunnel.conf            # Configuração TLS/PSK
├── psk.txt                 # Chaves pré-compartilhadas
├── setup_stunnel4.sh       # Setup básico
├── setup_skip_enhanced.sh  # Setup avançado
└── README.md              # Este arquivo
```

## Segurança

### TLS PSK (Pre-Shared Key)

A comunicação é protegida por TLS com chaves pré-compartilhadas conforme RFC SKIP:

- **Arquivo PSK:** `/etc/stunnel/psk.txt`
- **Formato:** `identity:key_hex`
- **Tamanho mínimo:** 256 bits (64 caracteres hex)

### Zeroização de Chaves

- Chaves são automaticamente removidas da memória após uso
- Implementa o princípio de "use once, destroy" do RFC SKIP

### Validação de SystemID

- Suporte a glob patterns (`*`, `?`, `[list]`)
- Validação de IDs remotos conforme configuração

## Logs

- **stunnel4:** `/var/log/stunnel4/skip-server.log`
- **SKIP Server:** `/var/log/skip/skip_server.log`

## Teste

### Teste de Capabilities
```bash
curl -k https://localhost:443/capabilities
```

### Teste de Nova Chave
```bash
curl -k "https://localhost:443/key?remoteSystemID=KP_QuIIN_Client&size=256"
```

### Teste de Entropia
```bash
curl -k "https://localhost:443/entropy?minentropy=128"
```

## Códigos de Status HTTP

| Código | Significado |
|--------|-------------|
| 200 | OK |
| 400 | keyId malformado ou chave não encontrada |
| 404 | Endpoint não encontrado |
| 405 | Método não permitido (apenas GET suportado) |
| 500 | Erro interno ao ler/zeroizar chave |
| 503 | Gerador de números aleatórios não disponível |

## Integração com IKEv2

O SKIP pode ser integrado com IKEv2 PPK conforme RFC 8784:

1. **Capabilities:** Troca de IDs de sistema
2. **Key Request:** Obtenção de (keyId, key)
3. **Key Exchange:** Troca de keyId via IKE_AUTH
4. **Key Retrieval:** Recuperação da chave pelo keyId

## Desenvolvimento

### Configuração de Desenvolvimento

```bash
export SKIP_ENV=development
python3 skip_server.py
```

### Configuração de Produção

```bash
export SKIP_ENV=production
python3 skip_server.py
```

## Referências

- **RFC SKIP:** draft-cisco-skip-02
- **RFC 8784:** IKEv2 PPK Extension
- **RFC 8446:** TLS 1.3
- **RFC 9110:** HTTP Semantics

## Licença

Este projeto implementa especificações públicas do IETF e está disponível para uso conforme as diretrizes de implementação de RFCs.