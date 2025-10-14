#!/bin/bash
# SKIP Server Enhanced Setup Script
# RFC SKIP compliant configuration

set -e

echo "=== SKIP Server Setup - RFC Compliant ==="

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Função para verificar se o stunnel4 está instalado
check_stunnel() {
    if ! command -v stunnel4 &> /dev/null; then
        log_error "stunnel4 não está instalado"
        log_info "Instalando stunnel4..."
        sudo apt-get update
        sudo apt-get install -y stunnel4
    else
        log_info "stunnel4 já está instalado"
    fi
}

# Função para configurar diretórios de log
setup_directories() {
    log_info "Configurando diretórios..."
    
    # Diretório de logs do SKIP
    sudo mkdir -p /var/log/skip
    sudo chown $(whoami):$(whoami) /var/log/skip
    
    # Diretório de logs do stunnel
    sudo mkdir -p /var/log/stunnel4
    sudo chown stunnel4:stunnel4 /var/log/stunnel4 2>/dev/null || true
    
    # Diretório de PID do stunnel
    sudo mkdir -p /var/run/stunnel4
    sudo chown stunnel4:stunnel4 /var/run/stunnel4 2>/dev/null || true
}

# Função para validar o arquivo PSK
validate_psk() {
    log_info "Validando arquivo PSK..."
    
    if [ ! -f "psk.txt" ]; then
        log_error "Arquivo psk.txt não encontrado"
        exit 1
    fi
    
    # Verifica se há pelo menos uma entrada PSK válida
    if ! grep -E "^[^#][^:]+:[a-fA-F0-9]{64}$" psk.txt > /dev/null; then
        log_warn "Nenhuma entrada PSK válida (256-bit) encontrada em psk.txt"
        log_info "Gerando PSK de exemplo..."
        echo "# Auto-generated PSK entry" >> psk.txt
        echo "auto_generated:$(openssl rand -hex 32)" >> psk.txt
    fi
}

# Função para configurar stunnel4
setup_stunnel() {
    log_info "Configurando stunnel4..."
    
    # Habilita o stunnel4
    echo "ENABLED=1" | sudo tee /etc/default/stunnel4 > /dev/null
    
    # Copia a configuração
    if [ -f "stunnel.conf" ]; then
        sudo cp stunnel.conf /etc/stunnel/stunnel.conf
        log_info "Configuração do stunnel copiada para /etc/stunnel/stunnel.conf"
    else
        log_error "Arquivo stunnel.conf não encontrado"
        exit 1
    fi
    
    # Copia o arquivo PSK
    sudo cp psk.txt /etc/stunnel/psk.txt
    sudo chmod 600 /etc/stunnel/psk.txt
    sudo chown stunnel4:stunnel4 /etc/stunnel/psk.txt 2>/dev/null || true
    log_info "Arquivo PSK copiado e protegido"
}

# Função para verificar dependências Python
check_python_deps() {
    log_info "Verificando dependências Python..."
    
    # Verifica se python3-venv está disponível
    if ! python3 -c "import venv" 2>/dev/null; then
        log_info "Instalando python3-venv..."
        sudo apt-get update
        sudo apt-get install -y python3-venv python3-full
    fi
    
    # Cria ambiente virtual se não existir
    if [ ! -d "venv" ]; then
        log_info "Criando ambiente virtual..."
        python3 -m venv venv
        log_info "Ambiente virtual criado"
    fi
    
    # Ativa o ambiente virtual
    source venv/bin/activate
    log_info "Ambiente virtual ativado"
    
    # Atualiza pip no ambiente virtual
    pip install --upgrade pip
    
    # Instala dependências do requirements.txt se existir
    if [ -f "requirements.txt" ]; then
        log_info "Instalando dependências do requirements.txt..."
        pip install -r requirements.txt
        log_info "Dependências instaladas com sucesso"
    else
        log_warn "Arquivo requirements.txt não encontrado"
        log_info "Instalando Flask manualmente..."
        pip install flask
    fi
    
    # Verifica se as dependências foram instaladas corretamente
    if ! python -c "import flask" 2>/dev/null; then
        log_error "Falha ao instalar Flask"
        exit 1
    else
        log_info "Flask instalado e funcionando"
    fi
    
    # Verifica se módulo secrets está disponível (Python 3.6+)
    if ! python -c "import secrets" 2>/dev/null; then
        log_warn "Módulo secrets não disponível (Python < 3.6)"
        log_warn "Considere atualizar para Python 3.6 ou superior"
    else
        log_info "Módulo secrets disponível"
    fi
    
    # Desativa o ambiente virtual
    deactivate
    log_info "Ambiente virtual configurado"
}

# Função para validar configuração
validate_config() {
    log_info "Validando configuração SKIP..."
    
    if [ -f "skip_config.py" ]; then
        python3 -c "
from skip_config import get_config
config = get_config()
errors = config.validate()
if errors:
    print('Erros de configuração:')
    for error in errors:
        print(f'  - {error}')
    exit(1)
else:
    print('Configuração válida')
"
    fi
}

# Função para testar a configuração
test_config() {
    log_info "Testando configuração do stunnel..."
    
    # Testa a configuração do stunnel
    if sudo stunnel4 -test /etc/stunnel/stunnel.conf; then
        log_info "Configuração do stunnel válida"
    else
        log_error "Configuração do stunnel inválida"
        exit 1
    fi
}

# Função para iniciar serviços
start_services() {
    log_info "Iniciando serviços..."
    
    # Reinicia o stunnel4
    sudo systemctl restart stunnel4
    
    if sudo systemctl is-active --quiet stunnel4; then
        log_info "stunnel4 iniciado com sucesso"
    else
        log_error "Falha ao iniciar stunnel4"
        sudo systemctl status stunnel4
        exit 1
    fi
}

# Função para mostrar status
show_status() {
    log_info "Status dos serviços:"
    echo "stunnel4: $(sudo systemctl is-active stunnel4)"
    
    log_info "Portas em uso:"
    sudo netstat -tlnp | grep -E ":(443|8080)" || log_warn "Nenhuma porta SKIP detectada"
    
    log_info "Logs disponíveis em:"
    echo "  - stunnel: /var/log/stunnel4/"
    echo "  - SKIP: /var/log/skip/"
    
    log_info "Para iniciar o servidor SKIP:"
    echo "  1. Ative o ambiente virtual: source venv/bin/activate"
    echo "  2. Execute o servidor: python skip_server.py"
    echo "  3. Para desativar o ambiente virtual: deactivate"
    echo ""
    log_info "Endpoint HTTPS: https://localhost:443/"
}

# Execução principal
main() {
    log_info "Iniciando setup do SKIP Server..."
    
    check_stunnel
    setup_directories
    validate_psk
    check_python_deps
    validate_config
    setup_stunnel
    test_config
    start_services
    show_status
    
    log_info "Setup concluído com sucesso!"
    log_info ""
    log_info "INSTRUÇÕES PARA INICIAR O SERVIDOR:"
    log_info "1. cd $(pwd)"
    log_info "2. source venv/bin/activate"
    log_info "3. python skip_server.py"
}
}

# Executa se chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi