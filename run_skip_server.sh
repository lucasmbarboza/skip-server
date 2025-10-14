#!/bin/bash
# Script para executar o SKIP Server

set -e

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

# Verifica se está no diretório correto
if [ ! -f "skip_server.py" ]; then
    log_error "skip_server.py não encontrado"
    log_error "Execute este script no diretório do SKIP Server"
    exit 1
fi

# Verifica se o ambiente virtual existe
if [ ! -d "venv" ]; then
    log_error "Ambiente virtual não encontrado"
    log_info "Criando ambiente virtual..."
    
    # Tenta criar o ambiente virtual
    if python3 -m venv venv; then
        log_info "Ambiente virtual criado com sucesso"
        
        # Ativa e instala dependências
        source venv/bin/activate
        log_info "Atualizando pip..."
        pip install --upgrade pip
        
        if [ -f "requirements.txt" ]; then
            log_info "Instalando dependências..."
            pip install -r requirements.txt
        else
            log_info "Instalando Flask..."
            pip install flask
        fi
        deactivate
        log_info "Dependências instaladas"
    else
        log_error "Falha ao criar ambiente virtual"
        log_info "Execute: ./setup_skip.sh"
        exit 1
    fi
fi

# Verifica se o arquivo de ativação existe
if [ ! -f "venv/bin/activate" ]; then
    log_error "Arquivo venv/bin/activate não encontrado"
    log_error "Ambiente virtual pode estar corrompido"
    log_info "Removendo ambiente virtual corrompido..."
    rm -rf venv
    log_info "Execute novamente este script ou ./setup_skip.sh"
    exit 1
fi

log_info "Iniciando SKIP Server..."
log_info "Para parar o servidor: Ctrl+C"
echo ""

# Ativa o ambiente virtual e executa o servidor
source venv/bin/activate

# Verifica se python está disponível no venv
if ! command -v python &> /dev/null; then
    log_error "Python não encontrado no ambiente virtual"
    deactivate
    exit 1
fi

# Verifica se Flask está instalado
if ! python -c "import flask" 2>/dev/null; then
    log_error "Flask não está instalado no ambiente virtual"
    log_info "Instalando Flask..."
    pip install flask
fi

# Executa o servidor
python skip_server.py