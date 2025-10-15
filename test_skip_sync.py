#!/usr/bin/env python3
"""
Script de teste para sincronização SKIP
Demonstra como testar a funcionalidade de sincronização entre servidores SKIP
"""

import asyncio
import aiohttp
import json
import sys
import time
import argparse
from datetime import datetime


class SKIPSyncTester:
    """Classe para testar a sincronização entre servidores SKIP"""

    def __init__(self, primary_url, secondary_url=None):
        self.primary_url = primary_url.rstrip('/')
        self.secondary_url = secondary_url.rstrip(
            '/') if secondary_url else None

    async def test_capabilities(self, url):
        """Testa o endpoint de capabilities"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/capabilities") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ Capabilities de {url}:")
                        print(
                            f"  Local System ID: {data.get('localSystemID')}")
                        print(
                            f"  Remote System IDs: {data.get('remoteSystemID')}")
                        print(f"  Algoritmo: {data.get('algorithm')}")
                        return True
                    else:
                        print(
                            f"✗ Erro ao obter capabilities de {url}: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Exceção ao testar capabilities de {url}: {e}")
            return False

    async def test_health(self, url):
        """Testa o endpoint de health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/status/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ Health check de {url}:")
                        print(f"  Status: {data.get('status')}")
                        print(
                            f"  Chaves armazenadas: {data.get('stored_keys')}")
                        print(
                            f"  Sincronização habilitada: {data.get('sync_enabled')}")
                        if data.get('sync_enabled'):
                            print(
                                f"  Peers online: {data.get('online_peers', 0)}/{data.get('sync_peers', 0)}")
                        return True
                    else:
                        print(
                            f"✗ Erro no health check de {url}: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Exceção no health check de {url}: {e}")
            return False

    async def test_sync_status(self, url):
        """Testa o endpoint de status de sincronização"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/status/sync") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ Status de sincronização de {url}:")
                        print(
                            f"  Sincronização habilitada: {data.get('sync_enabled')}")
                        print(
                            f"  System ID local: {data.get('local_system_id')}")
                        print(f"  Número de peers: {data.get('peer_count')}")

                        if data.get('peers'):
                            print("  Peers:")
                            for peer_id, peer_info in data['peers'].items():
                                status = peer_info.get('status', 'unknown')
                                endpoint = peer_info.get('endpoint', 'unknown')
                                last_hb = peer_info.get('last_heartbeat')
                                hb_str = f" (último heartbeat: {datetime.fromtimestamp(last_hb).strftime('%H:%M:%S')})" if last_hb else ""
                                print(
                                    f"    {peer_id}: {status} @ {endpoint}{hb_str}")
                        return True
                    else:
                        print(
                            f"✗ Erro no status de sincronização de {url}: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Exceção no status de sincronização de {url}: {e}")
            return False

    async def test_key_generation_and_sync(self):
        """Testa geração de chave e sincronização"""
        if not self.secondary_url:
            print("⚠ Teste de sincronização requer dois servidores")
            return False

        print("\n=== Teste de Geração e Sincronização de Chaves ===")

        try:
            # 1. Gerar chave no servidor primário
            async with aiohttp.ClientSession() as session:
                params = {
                    'remoteSystemID': 'KP_Test_Client',
                    'size': '256'
                }
                async with session.get(f"{self.primary_url}/key", params=params) as response:
                    if response.status == 200:
                        key_data = await response.json()
                        key_id = key_data['keyId']
                        key_value = key_data['key']
                        print(f"✓ Chave gerada no servidor primário:")
                        print(f"  Key ID: {key_id}")
                        print(f"  Key: {key_value[:16]}...{key_value[-16:]}")
                    else:
                        print(f"✗ Erro ao gerar chave: {response.status}")
                        return False

            # 2. Aguardar sincronização
            print("⏳ Aguardando sincronização (5 segundos)...")
            await asyncio.sleep(5)

            # 3. Tentar recuperar chave no servidor secundário
            async with aiohttp.ClientSession() as session:
                params = {'remoteSystemID': 'KP_Test_Primary'}
                async with session.get(f"{self.secondary_url}/key/{key_id}", params=params) as response:
                    if response.status == 200:
                        synced_key_data = await response.json()
                        synced_key_value = synced_key_data['key']

                        if synced_key_value == key_value:
                            print(
                                "✓ Sincronização bem-sucedida! Chaves idênticas nos dois servidores.")
                            return True
                        else:
                            print("✗ Sincronização falhou! Chaves diferentes.")
                            return False
                    else:
                        print(
                            f"✗ Chave não encontrada no servidor secundário: {response.status}")
                        return False

        except Exception as e:
            print(f"✗ Exceção no teste de sincronização: {e}")
            return False

    async def test_entropy(self, url):
        """Testa geração de entropia"""
        try:
            async with aiohttp.ClientSession() as session:
                params = {'minentropy': '128'}
                async with session.get(f"{url}/entropy", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        entropy = data['randomStr']
                        bits = data['minentropy']
                        print(f"✓ Entropia gerada de {url}:")
                        print(f"  Bits: {bits}")
                        print(f"  Valor: {entropy[:32]}...")
                        return True
                    else:
                        print(
                            f"✗ Erro ao gerar entropia de {url}: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Exceção ao testar entropia de {url}: {e}")
            return False

    async def run_comprehensive_test(self):
        """Executa todos os testes"""
        print("=== TESTE ABRANGENTE DE SINCRONIZAÇÃO SKIP ===")
        print(f"Servidor Primário: {self.primary_url}")
        if self.secondary_url:
            print(f"Servidor Secundário: {self.secondary_url}")
        print()

        results = []

        # Teste de capabilities
        print("1. Testando capabilities...")
        results.append(await self.test_capabilities(self.primary_url))
        if self.secondary_url:
            results.append(await self.test_capabilities(self.secondary_url))
        print()

        # Teste de health
        print("2. Testando health check...")
        results.append(await self.test_health(self.primary_url))
        if self.secondary_url:
            results.append(await self.test_health(self.secondary_url))
        print()

        # Teste de status de sincronização
        print("3. Testando status de sincronização...")
        results.append(await self.test_sync_status(self.primary_url))
        if self.secondary_url:
            results.append(await self.test_sync_status(self.secondary_url))
        print()

        # Teste de entropia
        print("4. Testando geração de entropia...")
        results.append(await self.test_entropy(self.primary_url))
        if self.secondary_url:
            results.append(await self.test_entropy(self.secondary_url))
        print()

        # Teste de sincronização (se dois servidores disponíveis)
        if self.secondary_url:
            print("5. Testando sincronização de chaves...")
            results.append(await self.test_key_generation_and_sync())
            print()

        # Resumo
        passed = sum(results)
        total = len(results)
        print(f"=== RESUMO DOS TESTES ===")
        print(f"Testes passaram: {passed}/{total}")

        if passed == total:
            print("✓ Todos os testes passaram! Sistema funcionando corretamente.")
            return True
        else:
            print("✗ Alguns testes falharam. Verifique a configuração e logs.")
            return False


async def main():
    parser = argparse.ArgumentParser(
        description='Testador de sincronização SKIP')
    parser.add_argument(
        'primary_url', help='URL do servidor SKIP primário (ex: https://localhost:443)')
    parser.add_argument(
        '--secondary', help='URL do servidor SKIP secundário para teste de sincronização')
    parser.add_argument('--test', choices=['all', 'capabilities', 'health', 'sync', 'entropy'],
                        default='all', help='Tipo de teste a executar')

    args = parser.parse_args()

    tester = SKIPSyncTester(args.primary_url, args.secondary)

    if args.test == 'all':
        success = await tester.run_comprehensive_test()
    elif args.test == 'capabilities':
        success = await tester.test_capabilities(args.primary_url)
    elif args.test == 'health':
        success = await tester.test_health(args.primary_url)
    elif args.test == 'sync':
        success = await tester.test_sync_status(args.primary_url)
    elif args.test == 'entropy':
        success = await tester.test_entropy(args.primary_url)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
