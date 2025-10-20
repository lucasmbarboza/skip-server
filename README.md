# SKIP Server - Implementação RFC Compliant

[![RFC SKIP](https://img.shields.io/badge/RFC-SKIP%20draft--cisco--skip--02-blue)](https://datatracker.ietf.org/doc/draft-cisco-skip/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker)](https://www.docker.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql)](https://www.mysql.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python)](https://www.python.org/)

Este é um servidor de implementação completa do **Secure Key Integration Protocol (SKIP)** conforme especificado no **draft-cisco-skip-02** da IETF.

## Visão Geral

O SKIP é um protocolo que permite a dois participantes (encryptors) obter de forma segura chaves de Key Providers independentes, fornecendo resistência quântica para protocolos de canal seguro existentes como IKEv2, TLS e MACsec.

### Principais Características

- **RFC Compliant**: 100% em conformidade com draft-cisco-skip-02
- **Banco de Dados Compartilhado**: Persistência MySQL para múltiplos Key Providers
- **Docker Ready**: Containerização completa com MySQL
- **Quantum Resistant**: Geração de chaves criptograficamente seguras
- **Observabilidade**: Logs detalhados e endpoint de monitoramento
- **Produção Ready**: TLS 1.2/1.3 com autenticação PSK/Certificado

## Arquitetura

```text
        Location A                                 Location B
+------------------------+              +------------------------+
|   +----------------+   |              |   +----------------+   |
|   |   Encryptor    |   |   IKEv2/     |   |   Encryptor    |   |
|   |   (Alice)      |==================|   |    (Bob)       |   |
|   +----------------+   |   TLS/IPsec  |   +----------------+   |
|           |            |              |           |            |
|      SKIP |            |              |      SKIP |            |
|           |            |              |           |            |
|   +----------------+   |              |   +----------------+   |
|   | Key Provider   |   |              |   | Key Provider   |   |
|   |   (Alice)      |   |              |   |    (Bob)       |   |
|   +----------------+   |              |   +----------------+   |
+------------------------+              +------------------------+
           |                                           |
           +-------------------+   +-------------------+
                               |   |
                        +-------------+
                        |   MySQL     |
                        | (Shared DB) |
                        +-------------+
```

### Componentes

- **Encryptor**: Cliente que solicita chaves (IKEv2, TLS, MACsec, etc.)
- **Key Provider**: Servidor SKIP que gerencia chaves
- **MySQL Database**: Banco de dados compartilhado para persistência
- **stunnel4**: Terminação TLS com autenticação PSK/Certificado

## Funcionalidade: Banco de Dados Compartilhado

O servidor SKIP utiliza um banco de dados MySQL compartilhado entre múltiplos Key Providers, permitindo que chaves geradas por um KP sejam acessadas por outro KP autorizado.

### Características do Compartilhamento

- **Banco Centralizado**: MySQL compartilhado entre todos os Key Providers
- **Acesso Controlado**: Validação de remoteSystemID para autorização
- **Persistência**: Chaves armazenadas com metadados (tamanho, timestamp, etc.)
- **Cleanup Automático**: Remoção de chaves expiradas
- **Zeroização**: Chaves podem ser removidas após uso (configurável)

## Endpoints RFC SKIP

### 1. GET /capabilities

Retorna as capacidades do Key Provider conforme RFC SKIP Seção 4.1.

**Resposta:**

```json
{
    "entropy": true,
    "key": true,
    "algorithm": "pqc",
    "localSystemID": "KP_QuIIN_Server",
    "remoteSystemID": ["KP_QuIIN_Client", "192_168_*"]
}
```

### 2. GET /key?remoteSystemID=&lt;id&gt;&size=&lt;bits&gt;

Gera uma nova chave e retorna key + keyId conforme RFC SKIP Seção 4.2.

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

**Comportamento:**
- Chave é armazenada no banco MySQL com `remote_system_id`
- keyId é gerado como 128 bits (32 caracteres hex)
- Validação de remoteSystemID contra lista configurada

### 3. GET /key/{keyId}?remoteSystemID=&lt;id&gt;

Recupera uma chave específica pelo keyId conforme RFC SKIP Seção 4.2.

**Resposta:**

```json
{
    "keyId": "1726e9ae76234fb1dd1283d4dca1911e1f93864d70f3069e",
    "key": "ad229dfb8a276e74c1f3b6c09349a69fb2fed73c541270663f0e5cbbfb031670"
}
```

**Comportamento:**
- Busca chave no banco MySQL compartilhado
- Permite acesso se remoteSystemID é válido (sem restrição de direção)
- Zeroiza chave após uso se configurado

### 4. GET /entropy?minentropy=&lt;bits&gt;

Retorna entropia aleatória conforme RFC SKIP Seção 4.3.

**Parâmetros:**

- `minentropy`: Quantidade de entropia em bits (opcional, padrão: 256)

**Resposta:**

```json
{
   "randomStr": "AD229DFB8A276E74C1F3B6C09349A69FB2FED73C541270663F0E5CBBFB031670",
   "minentropy": 256
}
```

## Endpoints Adicionais

### GET /health

Endpoint de verificação de saúde do serviço.

**Resposta:**

```json
{
    "status": "ok",
    "timestamp": "2025-10-20T10:30:00Z",
    "database": "ok",
    "version": "1.0.0",
    "localSystemID": "KP_QuIIN_Server"
}
```

**Comportamento:**
- Verifica conectividade com MySQL
- Retorna status 503 se banco estiver indisponível
- Inclui informações do sistema local

## Configuração TLS

Conforme RFC SKIP Tabela 1, suportamos:

| Modo | TLS Version | Cipher Suite | Requirement |
|------|-------------|--------------|-------------|
| PSK | TLS 1.2 | TLS_DHE_PSK_WITH_AES_256_CBC_SHA384 | RECOMMENDED |
| PSK | TLS 1.2 | TLS_DHE_PSK_WITH_AES_256_CBC_SHA | RECOMMENDED |
| Certificate/PSK | TLS 1.3 | TLS_AES_256_GCM_SHA384 | REQUIRED |

## Instalação e Configuração

### Pré-requisitos

- **Docker & Docker Compose**: Para containerização
- **MySQL 8.0**: Banco de dados (pode ser externo)
- **stunnel4**: Para terminação TLS (necessário no host)

### Instalação com Docker (Recomendado)

#### 1. Instalar stunnel4 no Host

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install stunnel4

# Configurar stunnel4
sudo cp stunnel.conf /etc/stunnel/stunnel.conf
sudo cp psk.txt /etc/stunnel/psk.txt
sudo chmod 600 /etc/stunnel/psk.txt

# Habilitar stunnel4
echo "ENABLED=1" | sudo tee /etc/default/stunnel4
sudo systemctl restart stunnel4
```

#### 2. Clone e Configure

```bash
git clone <repository>
cd "SKIP Server"

# Edite as variáveis de ambiente no docker-compose.yml
# Todas as configurações estão na seção 'environment'
```

#### 3. Execute com Docker Compose

```bash
# Antes de iniciar, configure as variáveis no docker-compose.yml:
# - MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
# - SKIP_LOCAL_SYSTEM_ID, SKIP_REMOTE_SYSTEM_ID_1

# Inicie os serviços
docker compose up -d --build

# Verifique os logs
docker compose logs -f skip_server

# Teste a conectividade TLS via stunnel4
curl -k "https://localhost:8443/capabilities"

# Teste direto no container (sem TLS)
curl -k "http://localhost:8080/capabilities"
```

#### 4. Configuração de Variáveis de Ambiente

Todas as configurações são definidas diretamente no `docker-compose.yml`:

```yaml
# docker-compose.yml
services:
  skip_server:
    network_mode: host  # Permite acesso ao MySQL no host
    environment:
      - FLASK_ENV=development
      - SKIP_LOCAL_SYSTEM_ID=KP_QuIIN_Server
      - SKIP_REMOTE_SYSTEM_ID_1=KP_QuIIN_Client
      - MYSQL_HOST=127.0.0.1
      - MYSQL_DATABASE=my_database_name
      - MYSQL_USER=my_user
      - MYSQL_PASSWORD=my_user_password_here
```

**Importante**: 
- Edite estas variáveis no `docker-compose.yml` antes de executar o container
- O stunnel4 roda no host e redireciona HTTPS (8443) para HTTP no container (8080)

### Instalação Manual

#### 1. Instalar Dependências

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip stunnel4 mysql-client

# Instalar dependências Python
pip3 install -r requirements.txt
```

**Nota**: O `stunnel4` é um pacote do sistema Linux para terminação TLS, não uma dependência Python.

#### 2. Configurar MySQL

```sql
-- Criar banco de dados e usuário
CREATE DATABASE skip_keys;
CREATE USER 'skip_user'@'%' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON skip_keys.* TO 'skip_user'@'%';
FLUSH PRIVILEGES;
```

**Nota**: As tabelas são criadas automaticamente pelo `skip_server.py` na primeira execução através do SQLAlchemy (`db.create_all()`).

#### 3. Configurar stunnel4

```bash
# Copiar configurações
sudo cp stunnel.conf /etc/stunnel/stunnel.conf
sudo cp psk.txt /etc/stunnel/psk.txt
sudo chmod 600 /etc/stunnel/psk.txt

# Habilitar stunnel4
echo "ENABLED=1" | sudo tee /etc/default/stunnel4
sudo systemctl restart stunnel4
```

#### 4. Iniciar Servidor

```bash
# Desenvolvimento
export SKIP_ENV=development
python3 src/skip_server.py

# Produção
export SKIP_ENV=production
python3 src/skip_server.py
```

**Nota**: O servidor inicializa automaticamente as tabelas do banco de dados na primeira execução.

## Configuração

### Configuração via docker-compose.yml

O servidor é configurado através das variáveis de ambiente definidas no `docker-compose.yml`:

```yaml
environment:
  # Configurações básicas
  - FLASK_ENV=development
  - SKIP_LOCAL_SYSTEM_ID=KP_QuIIN_Server
  - SKIP_REMOTE_SYSTEM_ID_1=KP_QuIIN_Client
  
  # Configurações do MySQL
  - MYSQL_HOST=127.0.0.1
  - MYSQL_DATABASE=my_database_name
  - MYSQL_USER=my_user
  - MYSQL_PASSWORD=my_user_password_here
  - MYSQL_ROOT_PASSWORD=your_root_password_here
```

Para instalação manual (sem Docker), estas mesmas variáveis podem ser exportadas no shell.

### Arquivo skip_config.py

As configurações principais estão em `src/skip_config.py`:

```python
class SKIPConfig:
    # Configurações do Key Provider
    LOCAL_SYSTEM_ID = os.getenv('SKIP_LOCAL_SYSTEM_ID', 'KP_QuIIN_Server')
    REMOTE_SYSTEM_IDS = [
        os.getenv('SKIP_REMOTE_SYSTEM_ID_1', 'KP_QuIIN_Client'),
    ]
    
    # Configurações de chave
    DEFAULT_KEY_SIZE = 256  # bits
    MIN_KEY_SIZE = 128      # bits
    MAX_KEY_SIZE = 512      # bits
    
    # Zeroização de chaves
    ENABLE_KEY_ZEROIZATION = True
```

## Estrutura de Arquivos

```text
SKIP Server/
├── src/
│   ├── skip_server.py          # Servidor principal SKIP
│   ├── skip_config.py          # Configurações
│   ├── models.py               # Modelos de banco de dados
│   └── Dockerfile              # Imagem do container
├── docker-compose.yml          # Orquestração do container
├── stunnel.conf                # Configuração TLS/PSK
├── psk.txt                     # Chaves pré-compartilhadas
├── test_rfc_compliance.py      # Testes de conformidade RFC
├── test_specific_issue.py      # Testes de problemas específicos
├── RFC_COMPLIANCE.md           # Relatório de conformidade
└── README.md                   # Este arquivo
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
- **SKIP Server:** Logs do container via `docker compose logs`
- **MySQL:** Logs de consulta do banco de dados (configurável)

## Testes e Validação

### Testes Automatizados

```bash
# Teste completo de conformidade RFC
python3 test_rfc_compliance.py

# Teste do problema específico resolvido
python3 test_specific_issue.py

# Teste de sincronização
python3 test_skip_sync.py
```

### Testes Manuais via cURL

```bash
# Teste de capabilities
curl -k "http://localhost:8080/capabilities"

# Gerar nova chave
curl -k "http://localhost:8080/key?remoteSystemID=192_168_71_25&size=256"

# Recuperar chave por ID
curl -k "http://localhost:8080/key/YOUR_KEY_ID?remoteSystemID=192_168_71_15"

# Gerar entropia
curl -k "http://localhost:8080/entropy?minentropy=128"

# Health check
curl -k "http://localhost:8080/health"
```

### Monitoramento e Debug

```bash
# Ver logs do container
docker compose logs -f skip_server

# Verificar banco de dados
docker exec -it mysql_container mysql -u skip_user -p skip_keys

# Query de debug das chaves
SELECT key_id, remote_system_id, size, created_at FROM `keys` ORDER BY created_at DESC LIMIT 10;

# Verificar conectividade TLS
openssl s_client -connect localhost:8443 -psk_identity cisco -psk YOUR_PSK_KEY
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

## Solução de Problemas

### Problemas Comuns

1. **Erro 400 na recuperação de chave**: Verifique a configuração do remoteSystemID e banco de dados
2. **Problemas de rede Docker**: Certifique-se que `network_mode: host` para MySQL externo
3. **Falha na conexão TLS**: Verifique a configuração do stunnel4 e arquivo PSK
4. **Conexão com banco de dados**: Verifique credenciais MySQL e acesso de rede


## Desenvolvimento

### Configuração de Desenvolvimento

```bash
export SKIP_ENV=development
export SKIP_DEBUG=true
python3 src/skip_server.py
```

### Configuração de Produção

```bash
export SKIP_ENV=production
export SKIP_DEBUG=false
python3 src/skip_server.py
```

## Referências

- **RFC SKIP:** draft-cisco-skip-02
- **RFC 8784:** IKEv2 PPK Extension
- **RFC 8446:** TLS 1.3
- **RFC 9110:** HTTP Semantics

## Licença

Este projeto implementa especificações públicas do IETF e está disponível para uso conforme as diretrizes de implementação de RFCs.