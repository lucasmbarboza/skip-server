#!/bin/bash
# Script para remover completamente o SKIP Server e suas dependências

set -e

echo "=== SKIP Server - Script de Remoção Completa ==="
echo ""
echo "ATENÇÃO: Este script irá remover:"
echo "- Ambiente virtual Python (venv/)"
echo "- Configurações do stunnel4"
echo "- Logs do SKIP Server"
echo "- Arquivos de configuração do sistema"
echo "- Serviços em execução"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Função para confirmar ação
confirm_action() {
    local message="$1"
    echo -e "${YELLOW}$message${NC}"
    read -p "Continuar? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Operação cancelada."
        exit 0
    fi
}

# Confirma a remoção
confirm_action "Deseja realmente remover TUDO relacionado ao SKIP Server?"

log_step "1. Parando serviços..."

# Para o stunnel4
if systemctl is-active --quiet stunnel4 2>/dev/null; then
    log_info "Parando stunnel4..."
    sudo systemctl stop stunnel4
    log_info "stunnel4 parado"
else
    log_info "stunnel4 já estava parado"
fi

# Para processos Python do SKIP
if pgrep -f "skip_server.py" > /dev/null; then
    log_info "Parando processos do SKIP Server..."
    pkill -f "skip_server.py" || true
    log_info "Processos do SKIP Server parados"
fi

log_step "2. Removendo ambiente virtual Python..."

if [ -d "venv" ]; then
    log_info "Removendo diretório venv/..."
    rm -rf venv
    log_info "Ambiente virtual removido"
else
    log_info "Ambiente virtual não encontrado"
fi

log_step "3. Removendo configurações do stunnel4..."

# Desabilita stunnel4
if [ -f "/etc/default/stunnel4" ]; then
    log_info "Desabilitando stunnel4..."
    echo "ENABLED=0" | sudo tee /etc/default/stunnel4 > /dev/null
    log_info "stunnel4 desabilitado"
fi

# Remove configurações do stunnel
if [ -f "/etc/stunnel/stunnel.conf" ]; then
    log_info "Removendo /etc/stunnel/stunnel.conf..."
    sudo rm -f /etc/stunnel/stunnel.conf
    log_info "Configuração do stunnel removida"
fi

if [ -f "/etc/stunnel/psk.txt" ]; then
    log_info "Removendo /etc/stunnel/psk.txt..."
    sudo rm -f /etc/stunnel/psk.txt
    log_info "Arquivo PSK removido"
fi

log_step "4. Removendo logs..."

# Remove logs do stunnel4
if [ -d "/var/log/stunnel4" ]; then
    log_info "Removendo logs do stunnel4..."
    sudo rm -rf /var/log/stunnel4/*
    log_info "Logs do stunnel4 removidos"
fi

# Remove logs do SKIP
if [ -d "/var/log/skip" ]; then
    log_info "Removendo logs do SKIP..."
    sudo rm -rf /var/log/skip
    log_info "Logs do SKIP removidos"
fi

# Remove PIDs do stunnel4
if [ -d "/var/run/stunnel4" ]; then
    log_info "Removendo PIDs do stunnel4..."
    sudo rm -rf /var/run/stunnel4/*
    log_info "PIDs do stunnel4 removidos"
fi

log_step "5. Removendo arquivos locais do projeto..."

# Lista de arquivos gerados pelo setup
local_files=(
    "*.log"
    "*.pid"
    "__pycache__"
    "*.pyc"
    ".pytest_cache"
    "htmlcov"
    ".coverage"
)

for pattern in "${local_files[@]}"; do
    if ls $pattern 2>/dev/null; then
        log_info "Removendo $pattern..."
        rm -rf $pattern
    fi
done

log_step "6. Verificando pacotes instalados..."

# Pergunta se quer remover stunnel4 completamente
echo ""
log_warn "O stunnel4 foi instalado pelo sistema de pacotes."
confirm_action "Deseja remover o stunnel4 completamente do sistema?" && {
    log_info "Removendo stunnel4..."
    sudo apt-get remove -y stunnel4
    sudo apt-get autoremove -y
    log_info "stunnel4 removido do sistema"
} || {
    log_info "stunnel4 mantido no sistema (apenas desabilitado)"
}

# Pergunta se quer remover python3-venv
echo ""
log_warn "Os pacotes python3-venv e python3-full podem ser usados por outros projetos."
confirm_action "Deseja remover python3-venv e python3-full?" && {
    log_info "Removendo python3-venv e python3-full..."
    sudo apt-get remove -y python3-venv python3-full
    sudo apt-get autoremove -y
    log_info "Pacotes Python removidos"
} || {
    log_info "Pacotes Python mantidos no sistema"
}

log_step "7. Limpeza final..."

# Remove scripts criados (opcional)
echo ""
log_warn "Scripts de setup e utilitários foram criados:"
ls -la *.sh 2>/dev/null || true
echo ""
confirm_action "Deseja remover todos os scripts (.sh)?" && {
    log_info "Removendo scripts..."
    rm -f *.sh
    log_info "Scripts removidos"
} || {
    log_info "Scripts mantidos"
}

log_step "8. Verificação final..."

# Verifica se ainda há processos relacionados
if pgrep -f "skip\|stunnel" > /dev/null; then
    log_warn "Ainda há processos relacionados em execução:"
    pgrep -af "skip\|stunnel"
else
    log_info "Nenhum processo relacionado em execução"
fi

# Verifica portas
if command -v netstat &> /dev/null; then
    if netstat -tlnp 2>/dev/null | grep -E ":(443|8080)"; then
        log_warn "Ainda há serviços usando portas 443 ou 8080"
    else
        log_info "Portas 443 e 8080 liberadas"
    fi
fi

echo ""
echo "=== Remoção Concluída ==="
log_info "✓ Serviços parados"
log_info "✓ Ambiente virtual removido"
log_info "✓ Configurações do stunnel removidas"
log_info "✓ Logs removidos"
log_info "✓ Arquivos temporários removidos"

echo ""
log_info "O SKIP Server foi completamente removido do sistema."
log_info "Arquivos de código fonte (skip_server.py, skip_config.py, etc.) foram mantidos."
echo ""
log_warn "Para remover completamente o diretório do projeto:"
echo "  cd .."
echo "  rm -rf $(basename $(pwd))"