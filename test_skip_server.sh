#!/bin/bash
# SKIP Server Test Suite
# Testes de conformidade com RFC SKIP

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configurações
SKIP_URL="https://localhost:443"
CURL_OPTS="-k -s -w %{http_code}"

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Função para fazer requisições e verificar códigos HTTP
test_endpoint() {
    local endpoint="$1"
    local expected_code="$2"
    local description="$3"
    
    log_test "$description"
    
    local response=$(curl $CURL_OPTS "$SKIP_URL$endpoint" 2>/dev/null)
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" = "$expected_code" ]; then
        log_pass "HTTP $http_code - $description"
        if [ ! -z "$body" ] && [ "$body" != "000" ]; then
            echo "Response: $body" | jq . 2>/dev/null || echo "Response: $body"
        fi
        return 0
    else
        log_fail "HTTP $http_code (esperado $expected_code) - $description"
        if [ ! -z "$body" ]; then
            echo "Response: $body"
        fi
        return 1
    fi
}

# Função para verificar se o servidor está rodando
check_server() {
    log_info "Verificando se o servidor SKIP está acessível..."
    
    if curl -k -s --connect-timeout 5 "$SKIP_URL/capabilities" > /dev/null 2>&1; then
        log_pass "Servidor SKIP acessível em $SKIP_URL"
        return 0
    else
        log_fail "Servidor SKIP não acessível em $SKIP_URL"
        log_info "Certifique-se de que:"
        log_info "  1. stunnel4 está rodando (sudo systemctl status stunnel4)"
        log_info "  2. skip_server.py está rodando (python3 skip_server.py)"
        log_info "  3. Porta 443 está aberta"
        return 1
    fi
}

# Teste 1: GET /capabilities
test_capabilities() {
    echo
    log_info "=== Teste 1: GET /capabilities ==="
    
    if test_endpoint "/capabilities" "200" "Obter capacidades do KP"; then
        # Verificar campos obrigatórios na resposta
        local response=$(curl -k -s "$SKIP_URL/capabilities" | jq .)
        
        for field in "entropy" "key" "algorithm" "localSystemID" "remoteSystemID"; do
            if echo "$response" | jq -e ".$field" > /dev/null 2>&1; then
                log_pass "Campo '$field' presente na resposta"
            else
                log_fail "Campo '$field' ausente na resposta"
            fi
        done
    fi
}

# Teste 2: GET /key com parâmetros válidos
test_key_generation() {
    echo
    log_info "=== Teste 2: GET /key (geração de nova chave) ==="
    
    test_endpoint "/key?remoteSystemID=KP_QuIIN_Client" "200" "Gerar nova chave"
    test_endpoint "/key?remoteSystemID=KP_QuIIN_Client&size=256" "200" "Gerar chave de 256 bits"
    test_endpoint "/key?remoteSystemID=KP_QuIIN_Client&size=128" "200" "Gerar chave de 128 bits"
}

# Teste 3: GET /key com parâmetros inválidos
test_key_generation_errors() {
    echo
    log_info "=== Teste 3: GET /key (casos de erro) ==="
    
    test_endpoint "/key" "400" "Erro: remoteSystemID ausente"
    test_endpoint "/key?remoteSystemID=InvalidSystem" "400" "Erro: remoteSystemID inválido"
}

# Teste 4: GET /key/{keyId}
test_key_retrieval() {
    echo
    log_info "=== Teste 4: GET /key/{keyId} (recuperação de chave) ==="
    
    # Primeiro gera uma chave para obter um keyId válido
    local response=$(curl -k -s "$SKIP_URL/key?remoteSystemID=KP_QuIIN_Client")
    local keyId=$(echo "$response" | jq -r '.keyId' 2>/dev/null)
    
    if [ "$keyId" != "null" ] && [ ! -z "$keyId" ]; then
        log_info "KeyId obtido: $keyId"
        test_endpoint "/key/$keyId?remoteSystemID=KP_QuIIN_Client" "200" "Recuperar chave por keyId"
        
        # Tentar recuperar a mesma chave novamente (deve falhar pois foi zeroizada)
        test_endpoint "/key/$keyId?remoteSystemID=KP_QuIIN_Client" "400" "Erro: chave já foi zeroizada"
    else
        log_fail "Não foi possível obter keyId para teste de recuperação"
    fi
}

# Teste 5: GET /entropy
test_entropy() {
    echo
    log_info "=== Teste 5: GET /entropy ==="
    
    test_endpoint "/entropy" "200" "Obter entropia padrão (256 bits)"
    test_endpoint "/entropy?minentropy=128" "200" "Obter entropia de 128 bits"
    test_endpoint "/entropy?minentropy=512" "200" "Obter entropia de 512 bits"
}

# Teste 6: Endpoints inválidos
test_invalid_endpoints() {
    echo
    log_info "=== Teste 6: Endpoints inválidos ==="
    
    test_endpoint "/invalid" "404" "Erro: endpoint inexistente"
    test_endpoint "/key" "400" "Erro: parâmetros ausentes" # POST method
}

# Teste 7: Métodos HTTP inválidos
test_invalid_methods() {
    echo
    log_info "=== Teste 7: Métodos HTTP inválidos ==="
    
    local response=$(curl -k -s -w %{http_code} -X POST "$SKIP_URL/capabilities" 2>/dev/null)
    local http_code="${response: -3}"
    
    if [ "$http_code" = "405" ]; then
        log_pass "HTTP 405 - Método POST rejeitado corretamente"
    else
        log_fail "HTTP $http_code (esperado 405) - Método POST deveria ser rejeitado"
    fi
}

# Teste completo de fluxo SKIP
test_skip_flow() {
    echo
    log_info "=== Teste 8: Fluxo SKIP Completo ==="
    
    # 1. Obter capabilities
    log_test "Passo 1: Obter capabilities"
    local caps_response=$(curl -k -s "$SKIP_URL/capabilities")
    local local_system_id=$(echo "$caps_response" | jq -r '.localSystemID' 2>/dev/null)
    local remote_systems=$(echo "$caps_response" | jq -r '.remoteSystemID[]' 2>/dev/null | head -1)
    
    if [ ! -z "$local_system_id" ] && [ "$local_system_id" != "null" ]; then
        log_pass "LocalSystemID: $local_system_id"
    else
        log_fail "Não foi possível obter localSystemID"
        return 1
    fi
    
    # 2. Gerar nova chave
    log_test "Passo 2: Gerar nova chave"
    local key_response=$(curl -k -s "$SKIP_URL/key?remoteSystemID=$remote_systems")
    local keyId=$(echo "$key_response" | jq -r '.keyId' 2>/dev/null)
    local key=$(echo "$key_response" | jq -r '.key' 2>/dev/null)
    
    if [ ! -z "$keyId" ] && [ "$keyId" != "null" ]; then
        log_pass "KeyId gerado: ${keyId:0:16}..."
        log_pass "Key gerado: ${key:0:16}... (${#key} chars)"
    else
        log_fail "Não foi possível gerar chave"
        return 1
    fi
    
    # 3. Recuperar chave pelo keyId
    log_test "Passo 3: Recuperar chave pelo keyId"
    local retrieved_response=$(curl -k -s "$SKIP_URL/key/$keyId?remoteSystemID=$remote_systems")
    local retrieved_key=$(echo "$retrieved_response" | jq -r '.key' 2>/dev/null)
    
    if [ "$retrieved_key" = "$key" ]; then
        log_pass "Chave recuperada corretamente"
    else
        log_fail "Chave recuperada não corresponde à chave original"
    fi
}

# Função principal
run_tests() {
    echo "=== SKIP Server Test Suite ==="
    echo "RFC SKIP Compliance Tests"
    echo "=========================="
    
    # Verificar dependências
    if ! command -v jq &> /dev/null; then
        log_info "Instalando jq para parsing JSON..."
        sudo apt-get update && sudo apt-get install -y jq
    fi
    
    # Verificar servidor
    if ! check_server; then
        exit 1
    fi
    
    local total_tests=0
    local passed_tests=0
    
    # Executar testes
    for test_func in test_capabilities test_key_generation test_key_generation_errors test_key_retrieval test_entropy test_invalid_endpoints test_invalid_methods test_skip_flow; do
        if $test_func; then
            ((passed_tests++))
        fi
        ((total_tests++))
        sleep 1
    done
    
    echo
    echo "=========================="
    echo "Resultados dos Testes:"
    echo "Total: $total_tests"
    echo "Passou: $passed_tests"
    echo "Falhou: $((total_tests - passed_tests))"
    
    if [ $passed_tests -eq $total_tests ]; then
        log_pass "Todos os testes passaram! ✓"
        exit 0
    else
        log_fail "Alguns testes falharam! ✗"
        exit 1
    fi
}

# Executar se chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_tests "$@"
fi