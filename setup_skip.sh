#!/bin/bash
# SKIP Server Docker Setup Script
# RFC SKIP compliant configuration with Docker Compose

set -e

echo "=== SKIP Server Docker Setup - RFC Compliant ==="

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

# Função para verificar se o Docker está instalado
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker não está instalado"
        log_info "Para instalar o Docker, visite: https://docs.docker.com/get-docker/"
        exit 1
    else
        log_info "Docker está instalado: $(docker --version)"
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose não está instalado"
        log_info "Para instalar o Docker Compose, visite: https://docs.docker.com/compose/install/"
        exit 1
    else
        if command -v docker-compose &> /dev/null; then
            log_info "Docker Compose está instalado: $(docker-compose --version)"
        else
            log_info "Docker Compose (plugin) está instalado: $(docker compose version)"
        fi
    fi
    
    # Verifica se o Docker daemon está rodando
    if ! docker info &> /dev/null; then
        log_error "Docker daemon não está rodando"
        log_info "Execute: sudo systemctl start docker"
        exit 1
    fi
}

# Função para verificar se o stunnel4 está instalado (mantido para compatibilidade)
check_stunnel() {
    log_info "stunnel4 será gerenciado pelo container Docker"
    log_warn "Esta configuração usa Docker - stunnel4 não é necessário no host"
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
###
# Função para verificar dependências Python
check_python_deps() {
    log_info "Verificando dependências Python..."
    
    # Verifica se python3-venv está disponível
    if ! python3 -c "import venv" 2>/dev/null; then
        log_info "Instalando python3-venv..."
        sudo apt-get update
        sudo apt-get install -y python3-venv python3-full
    fi
    
    # Remove venv existente se estiver corrompido ou incompleto
    if [ -d "venv" ]; then
        if [ ! -f "venv/bin/activate" ] || [ ! -f "venv/bin/python" ]; then
            log_warn "Ambiente virtual incompleto ou corrompido, removendo..."
            rm -rf venv
        fi
    fi
    
    # Cria ambiente virtual se não existir
    if [ ! -d "venv" ]; then
        log_info "Criando ambiente virtual..."
        python3 -m venv venv --clear
        
        # Verifica se foi criado corretamente
        if [ ! -f "venv/bin/activate" ]; then
            log_error "Falha ao criar ambiente virtual - activate não encontrado"
            exit 1
        fi
        
        if [ ! -f "venv/bin/python" ]; then
            log_error "Falha ao criar ambiente virtual - python não encontrado"
            exit 1
        fi
        
        log_info "Ambiente virtual criado com sucesso"
    fi
    
    # Ativa o ambiente virtual
    if source venv/bin/activate; then
        log_info "Ambiente virtual ativado"
    else
        log_error "Falha ao ativar ambiente virtual"
        exit 1
    fi
    
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
        # Ativa o ambiente virtual temporariamente para validação
        source venv/bin/activate
        
        python -c "
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
" || {
            deactivate
            log_warn "Erro na validação da configuração, mas continuando..."
            return 0
        }
        
        deactivate
    else
        log_warn "Arquivo skip_config.py não encontrado, pulando validação"
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
    log_info "Verificando arquivos necessários para Docker:"
    
    if [ -f "docker-compose.yml" ]; then
        echo "✓ docker-compose.yml encontrado"
    else
        log_error "docker-compose.yml não encontrado!"
        exit 1
    fi
    
    if [ -f "src/Dockerfile" ]; then
        echo "✓ src/Dockerfile encontrado"
    else
        log_error "src/Dockerfile não encontrado!"
        exit 1
    fi
    
    if [ -f "src/skip_server.py" ]; then
        echo "✓ src/skip_server.py encontrado"
    else
        log_error "src/skip_server.py não encontrado!"
        exit 1
    fi
    
    log_info "Portas que serão utilizadas:"
    echo "  - HTTP: 8080 (container interno e externo)"
    
    log_info "Para iniciar o servidor SKIP com Docker:"
    echo "  1. Construir e iniciar: docker-compose up --build"
    echo "  2. Executar em background: docker-compose up -d --build"
    echo "  3. Para parar: docker-compose down"
    echo "  4. Ver logs: docker-compose logs -f skip_server"
    echo ""
    log_info "Endpoint HTTP: http://localhost:8080/"
    log_info "Endpoints de teste:"
    echo "  - Capabilities: http://localhost:8080/capabilities"
    echo "  - Health check: http://localhost:8080/status/health"
}

# Função para testar se o Docker pode construir a imagem
test_docker_build() {
    log_info "Testando construção da imagem Docker..."
    
    if docker-compose config > /dev/null 2>&1 || docker compose config > /dev/null 2>&1; then
        log_info "✓ docker-compose.yml é válido"
    else
        log_error "docker-compose.yml contém erros"
        return 1
    fi
    
    log_info "Construção de teste concluída com sucesso"
    log_warn "Para construir e executar o container, use: docker-compose up --build"
}

# Execução principal
main() {
    log_info "Iniciando setup do SKIP Server com Docker..."
    
    check_docker
    check_stunnel
    setup_directories
    validate_psk
    test_docker_build
    # check_python_deps (não necessário com Docker)
    # validate_config (será feito pelo container)
    # setup_stunnel (será feito pelo container)
    # start_services (será feito pelo docker-compose)
    show_status
    
    log_info "Setup concluído com sucesso!"
    log_info ""
    log_info "INSTRUÇÕES PARA INICIAR O SERVIDOR COM DOCKER:"
    log_info "1. cd $(pwd)"
    log_info "2. docker-compose up --build"
    log_info ""
    log_info "COMANDOS ÚTEIS:"
    log_info "• Executar em background: docker-compose up -d --build"
    log_info "• Ver logs: docker-compose logs -f skip_server"
    log_info "• Parar container: docker-compose down"
    log_info "• Rebuild: docker-compose build --no-cache"
}


# Executa se chamado diretamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi