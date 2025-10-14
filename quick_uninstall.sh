#!/bin/bash
# Script de remoção rápida do SKIP Server (sem confirmações)

echo "=== SKIP Server - Remoção Rápida ==="

# Para serviços
sudo systemctl stop stunnel4 2>/dev/null || true
pkill -f "skip_server.py" 2>/dev/null || true

# Remove ambiente virtual
rm -rf venv

# Desabilita stunnel4
echo "ENABLED=0" | sudo tee /etc/default/stunnel4 > /dev/null 2>&1 || true

# Remove configurações
sudo rm -f /etc/stunnel/stunnel.conf 2>/dev/null || true
sudo rm -f /etc/stunnel/psk.txt 2>/dev/null || true

# Remove logs
sudo rm -rf /var/log/stunnel4/* 2>/dev/null || true
sudo rm -rf /var/log/skip 2>/dev/null || true
sudo rm -rf /var/run/stunnel4/* 2>/dev/null || true

# Remove arquivos temporários
rm -rf __pycache__ *.pyc .pytest_cache htmlcov .coverage *.log *.pid 2>/dev/null || true

echo "✓ SKIP Server removido rapidamente"
echo "✓ Para remoção completa com opções, use: ./uninstall_skip.sh"