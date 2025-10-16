#!/bin/bash
# SKIP Server Simple Test via stunnel4
# Testa conexão básica com o servidor SKIP através do stunnel4

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
SKIP_HOST="localhost"
SKIP_PORT="8443"
BASE_URL="https://${SKIP_HOST}:${SKIP_PORT}"

# Função para log colorido
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Função para fazer requisição HTTP via openssl s_client com PSK
make_psk_request() {
    local path="$1"
    local psk_identity="skip-client"
    local psk_key=$(grep "^${psk_identity}:" psk.txt | cut -d: -f2)
    
    if [ -z "$psk_key" ]; then
        log_error "PSK não encontrada para identidade: $psk_identity"
        return 1
    fi
    
    # Criar requisição HTTP
    local http_request="GET $path HTTP/1.1\r\nHost: $SKIP_HOST:$SKIP_PORT\r\nConnection: close\r\n\r\n"
    
    # Fazer conexão com PSK
    echo -e "$http_request" | timeout 10 openssl s_client \
        -connect "$SKIP_HOST:$SKIP_PORT" \
        -psk "$psk_key" \
        -psk_identity "$psk_identity" \
        -quiet -no_ign_eof 2>/dev/null
}

# Função para testar endpoint com PSK
test_endpoint() {
    local test_name="$1"
    local path="$2"
    
    log_info "Testando: $test_name"
    
    # Fazer requisição via openssl s_client
    response=$(make_psk_request "$path")
    
    if [ $? -ne 0 ] || [ -z "$response" ]; then
        log_error "$test_name - Falha na conexão PSK"
        return 1
    fi
    
    # Extrair status HTTP e corpo da resposta
    http_line=$(echo "$response" | grep "^HTTP" | head -1)
    status_code=$(echo "$http_line" | awk '{print $2}')
    
    echo "  HTTP Response: $http_line"
    
    # Extrair corpo JSON (após linha em branco)
    body=$(echo "$response" | sed -n '/^$/,$p' | tail -n +2)
    
    if [ -n "$body" ]; then
        echo "  Body: $body"
    fi
    
    if [ "$status_code" = "200" ]; then
        log_success "$test_name - OK"
    else
        log_warning "$test_name - Status: $status_code"
    fi
    
    echo
}

# Verificar dependências
check_dependencies() {
    local missing_deps=0
    
    if ! command -v openssl >/dev/null 2>&1; then
        log_error "openssl não encontrado"
        echo "  Instale com: sudo apt install openssl (Ubuntu/Debian)"
        missing_deps=1
    fi
    
    if ! command -v timeout >/dev/null 2>&1; then
        log_warning "timeout não encontrado - usando alternativas"
    fi
    
    # Verificar se o arquivo PSK existe
    if [ ! -f "psk.txt" ]; then
        log_error "Arquivo psk.txt não encontrado"
        echo "  Crie o arquivo com: echo 'skip-client:deadbeefcafebabe1234567890abcdef' > psk.txt"
        missing_deps=1
    fi
    
    if [ $missing_deps -eq 1 ]; then
        log_error "Dependências faltando. Instale e tente novamente."
        exit 1
    fi
}

# Header do script
echo "=========================================="
echo "  SKIP Server Simple Test via stunnel4"
echo "=========================================="
echo "Target: $BASE_URL"
echo "Date: $(date)"
echo

# Verificar dependências
check_dependencies

# Verificar se o stunnel4 está respondendo
log_info "1. Testando conectividade na porta $SKIP_PORT..."
if command -v nc >/dev/null 2>&1; then
    # Usar netcat se disponível
    if timeout 5 nc -z $SKIP_HOST $SKIP_PORT 2>/dev/null; then
        log_success "Porta $SKIP_PORT está aberta (nc)"
    else
        log_error "Porta $SKIP_PORT não está acessível"
        log_info "Verifique se stunnel4 está rodando"
        exit 1
    fi
elif timeout 5 bash -c "</dev/tcp/$SKIP_HOST/$SKIP_PORT" 2>/dev/null; then
    # Fallback para /dev/tcp
    log_success "Porta $SKIP_PORT está aberta (/dev/tcp)"
else
    log_error "Porta $SKIP_PORT não está acessível"
    log_info "Verifique se stunnel4 está rodando"
    exit 1
fi

# Teste básico de conexão TLS PSK
log_info "2. Testando handshake TLS PSK..."
psk_identity="skip-client"
psk_key=$(grep "^${psk_identity}:" psk.txt | cut -d: -f2)

if [ -z "$psk_key" ]; then
    log_error "PSK não encontrada no arquivo psk.txt"
    log_info "Adicione uma linha como: skip-client:deadbeefcafebabe1234567890abcdef"
    exit 1
fi

# Testar conexão PSK
test_response=$(echo -e "GET / HTTP/1.1\r\nHost: $SKIP_HOST:$SKIP_PORT\r\nConnection: close\r\n\r\n" | \
    timeout 10 openssl s_client \
    -connect "$SKIP_HOST:$SKIP_PORT" \
    -psk "$psk_key" \
    -psk_identity "$psk_identity" \
    -quiet -no_ign_eof 2>/dev/null)

if [ $? -eq 0 ] && echo "$test_response" | grep -q "HTTP"; then
    log_success "Handshake TLS PSK OK"
    http_status=$(echo "$test_response" | grep "^HTTP" | head -1)
    echo "  Response: $http_status"
else
    log_error "Falha no handshake TLS PSK"
    log_info "Verifique se:"
    log_info "  - stunnel4 está rodando com configuração PSK"
    log_info "  - psk.txt contém a chave correta"
    log_info "  - skip_server.py está rodando na porta 8080"
    exit 1
fi

# Testar endpoints básicos do SKIP
echo
log_info "=== TESTANDO ENDPOINTS SKIP ==="
echo

# Teste 1: Capabilities
test_endpoint "GET /capabilities" "/capabilities"

# Teste 2: Nova chave
test_endpoint "GET /key" "/key"

# Teste 3: Entropy
test_endpoint "GET /entropy" "/entropy"

# Teste 4: Health check
test_endpoint "GET /status/health" "/status/health"

echo
log_info "=== TESTE RÁPIDO DE PERFORMANCE ==="
echo

# Teste simples de performance - 3 requisições PSK
log_info "Fazendo 3 requisições consecutivas via PSK..."
start_time=$(date +%s)

for i in $(seq 1 3); do
    response=$(make_psk_request "/key")
    if [ $? -eq 0 ] && echo "$response" | grep -q "keyId"; then
        echo "  Requisição $i: OK"
    else
        echo "  Requisição $i: FALHA"
    fi
done

end_time=$(date +%s)
duration=$((end_time - start_time))
log_info "3 requisições PSK completadas em ${duration}s"

echo
echo "=========================================="
echo "             RESUMO"
echo "=========================================="
echo "✅ Conexão TLS PSK via stunnel4: OK"
echo "✅ Endpoints SKIP: Testados"
echo "✅ Performance básica PSK: Medida"
echo
log_success "Teste TLS PSK concluído!"
echo
log_info "=== COMANDOS MANUAIS PARA TESTE PSK ==="
echo
echo "# Para testar manualmente com openssl s_client:"
echo "echo 'GET /capabilities HTTP/1.1\r\nHost: localhost:$SKIP_PORT\r\nConnection: close\r\n\r\n' | \\"
echo "openssl s_client -psk_identity $psk_identity -psk $psk_key -connect localhost:$SKIP_PORT -quiet"
echo
echo "# Para outros endpoints, substitua /capabilities por:"
echo "#   /key, /entropy, /status/health"
echo
echo "# PSK Identity: $psk_identity"
echo "# PSK Key: $(echo $psk_key | sed 's/./*/g')"
echo
