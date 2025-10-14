#!/bin/bash
# Script para testar e corrigir a configuração do stunnel4

echo "=== Teste e Correção do stunnel4 ==="

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Verifica se os arquivos necessários existem
log_info "Verificando arquivos de configuração..."

if [ ! -f "stunnel.conf" ]; then
    log_error "stunnel.conf não encontrado no diretório atual"
    exit 1
fi

if [ ! -f "psk.txt" ]; then
    log_error "psk.txt não encontrado no diretório atual" 
    exit 1
fi

# 2. Cria diretórios necessários
log_info "Criando diretórios necessários..."
sudo mkdir -p /var/log/stunnel4
sudo mkdir -p /var/run/stunnel4
sudo chown stunnel4:stunnel4 /var/log/stunnel4 2>/dev/null || true
sudo chown stunnel4:stunnel4 /var/run/stunnel4 2>/dev/null || true

# 3. Copia arquivos de configuração
log_info "Copiando arquivos de configuração..."
sudo cp stunnel.conf /etc/stunnel/stunnel.conf
sudo cp psk.txt /etc/stunnel/psk.txt
sudo chmod 600 /etc/stunnel/psk.txt
sudo chown stunnel4:stunnel4 /etc/stunnel/psk.txt 2>/dev/null || true

# 4. Testa a configuração
log_info "Testando configuração do stunnel..."
if sudo stunnel4 -test /etc/stunnel/stunnel.conf; then
    log_info "✓ Configuração do stunnel válida"
else
    log_error "✗ Configuração do stunnel inválida"
    log_info "Verificando logs de erro..."
    sudo tail -10 /var/log/stunnel4/stunnel.log 2>/dev/null || echo "Log não disponível"
    exit 1
fi

# 5. Habilita o stunnel4
log_info "Habilitando stunnel4..."
echo "ENABLED=1" | sudo tee /etc/default/stunnel4 > /dev/null

# 6. Reinicia o serviço
log_info "Reiniciando stunnel4..."
sudo systemctl stop stunnel4 2>/dev/null || true
sleep 2
sudo systemctl start stunnel4

# 7. Verifica status
if sudo systemctl is-active --quiet stunnel4; then
    log_info "✓ stunnel4 iniciado com sucesso"
    
    # Verifica se está escutando na porta 443
    if sudo netstat -tlnp | grep :443 > /dev/null; then
        log_info "✓ stunnel4 escutando na porta 443"
    else
        log_warn "⚠ Porta 443 não detectada"
    fi
    
else
    log_error "✗ Falha ao iniciar stunnel4"
    log_info "Status detalhado:"
    sudo systemctl status stunnel4
    log_info "Logs recentes:"
    sudo journalctl -u stunnel4 -n 10 --no-pager
    exit 1
fi

log_info "✓ stunnel4 configurado e funcionando!"
log_info ""
log_info "Para verificar logs: sudo tail -f /var/log/stunnel4/stunnel.log"
log_info "Para verificar status: sudo systemctl status stunnel4"