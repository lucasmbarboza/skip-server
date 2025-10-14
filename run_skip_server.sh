#!/bin/bash
# Script para executar o SKIP Server

# Verifica se está no diretório correto
if [ ! -f "skip_server.py" ]; then
    echo "Erro: skip_server.py não encontrado"
    echo "Execute este script no diretório do SKIP Server"
    exit 1
fi

# Verifica se o ambiente virtual existe
if [ ! -d "venv" ]; then
    echo "Erro: Ambiente virtual não encontrado"
    echo "Execute primeiro: ./setup_skip.sh"
    exit 1
fi

echo "Iniciando SKIP Server..."
echo "Para parar o servidor: Ctrl+C"
echo ""

# Ativa o ambiente virtual e executa o servidor
source venv/bin/activate
python skip_server.py