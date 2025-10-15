#!/bin/bash
# Script de diagnóstico para problemas de sincronização SKIP

echo "=== SKIP Sync Diagnostics ==="
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

check_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Função para testar conectividade com um endpoint
test_connectivity() {
    local host="$1"
    local port="$2"
    local protocol="$3"
    
    echo "Testando $protocol://$host:$port"
    
    # Teste de TCP connectivity
    if timeout 5 nc -z "$host" "$port" 2>/dev/null; then
        check_ok "TCP connectivity: $host:$port"
    else
        check_fail "TCP connectivity: $host:$port"
        return 1
    fi
    
    # Teste HTTP/HTTPS
    if command -v curl &> /dev/null; then
        local url="$protocol://$host:$port/capabilities"
        local curl_opts=""
        
        if [ "$protocol" = "https" ]; then
            curl_opts="-k --tlsv1.2 --tls-max 1.2"
        fi
        
        if timeout 10 curl -s $curl_opts "$url" >/dev/null 2>&1; then
            check_ok "$protocol connectivity: $host:$port"
        else
            check_fail "$protocol connectivity: $host:$port"
            
            # Detalhar erro HTTPS
            if [ "$protocol" = "https" ]; then
                echo "  Detalhes do erro HTTPS:"
                timeout 10 curl -v $curl_opts "$url" 2>&1 | grep -E "(SSL|TLS|error|failed)" | head -3
            fi
        fi
    fi
}

# Função para testar certificados SSL
test_ssl_handshake() {
    local host="$1"
    local port="$2"
    
    echo ""
    echo "Testando handshake SSL/TLS com $host:$port"
    
    if command -v openssl &> /dev/null; then
        # Teste handshake TLS 1.2
        echo "q" | timeout 10 openssl s_client -connect "$host:$port" -tls1_2 -quiet 2>&1 | \
        if grep -q "Verify return code: 0"; then
            check_ok "TLS 1.2 handshake successful"
        else
            check_fail "TLS 1.2 handshake failed"
            echo "  Detalhes:"
            echo "q" | timeout 5 openssl s_client -connect "$host:$port" -tls1_2 2>&1 | \
            grep -E "(error|alert|failed|Verify return code)" | head -3
        fi
        
        # Mostrar ciphers disponíveis
        echo ""
        echo "Ciphers suportados pelo servidor:"
        echo "q" | timeout 5 openssl s_client -connect "$host:$port" -cipher 'ALL' 2>/dev/null | \
        grep "Cipher is" | head -5
        
    else
        check_warn "OpenSSL não disponível para teste detalhado"
    fi
}

echo "1. Verificando dependências..."

# Verificar ferramentas necessárias
for tool in nc curl openssl python3; do
    if command -v "$tool" &> /dev/null; then
        check_ok "$tool instalado"
    else
        check_fail "$tool não encontrado"
    fi
done

echo ""
echo "2. Verificando configuração local..."

# Verificar arquivos de configuração
if [ -f "skip_config.py" ]; then
    check_ok "skip_config.py encontrado"
    
    # Extrair configurações de sync
    if python3 -c "
from skip_config import get_config
config = get_config()
print(f'LOCAL_SYSTEM_ID: {config.LOCAL_SYSTEM_ID}')
print(f'SYNC_ENABLED: {config.SYNC_ENABLED}')
print(f'SYNC_PORT: {config.SYNC_PORT}')
print(f'ALLOW_HTTP_FALLBACK: {getattr(config, \"ALLOW_HTTP_FALLBACK\", False)}')
print(f'SSL_VERIFY_PEER: {getattr(config, \"SSL_VERIFY_PEER\", True)}')
" 2>/dev/null; then
        check_ok "Configuração carregada com sucesso"
    else
        check_fail "Erro ao carregar configuração"
    fi
else
    check_fail "skip_config.py não encontrado"
fi

echo ""
echo "3. Verificando portas locais..."

# Verificar se portas estão em uso
for port in 8080 8443 443; do
    if netstat -tlnp 2>/dev/null | grep ":$port " >/dev/null; then
        check_ok "Porta $port em uso"
        # Mostrar processo usando a porta
        process=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | head -1)
        echo "  Processo: $process"
    else
        check_warn "Porta $port não está em uso"
    fi
done

echo ""
echo "4. Testando conectividade com peers..."

# Verificar peers configurados
if [ -f "skip_config.py" ]; then
    python3 -c "
from skip_config import get_config
config = get_config()
peers = getattr(config, 'SYNC_PEERS', [])
if peers:
    print('Peers configurados:')
    for peer in peers:
        print(f\"  {peer.get('system_id', 'Unknown')}: {peer.get('endpoint', 'Unknown')}:{peer.get('port', 'Unknown')}\")
else:
    print('Nenhum peer configurado')
" 2>/dev/null
fi

# Testar conectividade com endpoints comuns
echo ""
echo "Testando endpoints de exemplo:"

# Endpoint de exemplo (ajustar conforme necessário)
test_connectivity "192.168.1.198" "8443" "https"
test_connectivity "192.168.1.198" "8443" "http"

echo ""
echo "5. Verificando logs de sincronização..."

# Verificar logs recentes
if [ -f "/var/log/skip/skip_server.log" ]; then
    check_ok "Log file encontrado"
    echo "Últimas 5 linhas relacionadas a sync:"
    tail -50 /var/log/skip/skip_server.log | grep -i "sync\|peer\|ssl\|tls" | tail -5
else
    check_warn "Log file não encontrado"
fi

echo ""
echo "6. Teste de handshake SSL detalhado..."

# Testar SSL handshake com peer
test_ssl_handshake "192.168.1.198" "8443"

echo ""
echo "=== Sugestões de solução ==="
echo ""
echo "Para problemas de SSL handshake:"
echo "  1. Verificar se ambos os peers usam TLS 1.2"
echo "  2. Confirmar ciphers compatíveis (PSK)"
echo "  3. Verificar certificados se usando modo certificado"
echo "  4. Temporariamente usar ALLOW_HTTP_FALLBACK = True"
echo ""
echo "Para problemas de conectividade:"
echo "  1. Verificar firewall e portas abertas"
echo "  2. Confirmar IPs e portas dos peers"
echo "  3. Testar conectividade básica: nc -z <host> <port>"
echo ""
echo "Para debug detalhado:"
echo "  1. Verificar logs: tail -f /var/log/skip/skip_server.log"
echo "  2. Aumentar log level para DEBUG"
echo "  3. Usar wireshark para analisar tráfego"