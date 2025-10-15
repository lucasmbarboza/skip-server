#!/usr/bin/env python3
"""
Script de configuração para sincronização SKIP
Facilita a configuração inicial de múltiplos Key Providers
"""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path


class SKIPSyncConfigurator:
    """Configurador para sincronização SKIP"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_template = """# Configuração gerada automaticamente para sincronização SKIP
# Gerado em: {timestamp}

from skip_config import SKIPConfig

class {class_name}(SKIPConfig):
    \"\"\"
    Configuração {env_type} para {system_id}
    \"\"\"
    
    # Identificação do Key Provider
    LOCAL_SYSTEM_ID = "{system_id}"
    
    # Sistemas remotos aceitos
    REMOTE_SYSTEM_IDS = {remote_systems}
    
    # Configurações de sincronização
    SYNC_ENABLED = True
    SYNC_INTERVAL = {sync_interval}
    HEARTBEAT_INTERVAL = {heartbeat_interval}
    MAX_RETRY_ATTEMPTS = {max_retries}
    SYNC_TIMEOUT = {sync_timeout}
    SYNC_PORT = {sync_port}
    
    # Configuração de peers
    SYNC_PEERS = {peers}
    
    # Configurações de segurança
    MAX_STORED_KEYS = {max_keys}
    KEY_EXPIRY_SECONDS = {key_expiry}
    ENABLE_KEY_ZEROIZATION = {enable_zeroization}
    
    # Configurações de ambiente
    LOG_LEVEL = "{log_level}"
    DEBUG = {debug}

# Configuração ativa
config = {class_name}
"""

    def generate_shared_secret(self, length=64):
        """Gera uma chave compartilhada segura"""
        return secrets.token_hex(length)

    def create_peer_config(self, system_id, endpoint, port=8443, shared_secret=None):
        """Cria configuração de um peer"""
        if shared_secret is None:
            shared_secret = self.generate_shared_secret()

        return {
            "system_id": system_id,
            "endpoint": endpoint,
            "port": port,
            "shared_secret": shared_secret
        }

    def generate_config_file(self, config_data, output_file):
        """Gera arquivo de configuração Python"""
        from datetime import datetime

        # Preparar dados para template
        template_data = {
            "timestamp": datetime.now().isoformat(),
            "class_name": config_data["class_name"],
            "env_type": config_data["env_type"],
            "system_id": config_data["system_id"],
            "remote_systems": json.dumps(config_data["remote_systems"], indent=8),
            "sync_interval": config_data.get("sync_interval", 30),
            "heartbeat_interval": config_data.get("heartbeat_interval", 10),
            "max_retries": config_data.get("max_retries", 3),
            "sync_timeout": config_data.get("sync_timeout", 10),
            "sync_port": config_data.get("sync_port", 8443),
            "peers": json.dumps(config_data["peers"], indent=8),
            "max_keys": config_data.get("max_keys", 1000),
            "key_expiry": config_data.get("key_expiry", 3600),
            "enable_zeroization": config_data.get("enable_zeroization", True),
            "log_level": config_data.get("log_level", "INFO"),
            "debug": config_data.get("debug", False)
        }

        # Gerar arquivo
        config_content = self.config_template.format(**template_data)

        with open(output_file, 'w') as f:
            f.write(config_content)

        print(f"✓ Configuração gerada: {output_file}")

    def setup_primary_secondary(self, primary_id, primary_endpoint, secondary_id, secondary_endpoint):
        """Configura um par primário-secundário básico"""
        # Gerar chave compartilhada única
        shared_secret = self.generate_shared_secret()

        # Configuração do primário
        primary_config = {
            "class_name": "PrimaryConfig",
            "env_type": "primário",
            "system_id": primary_id,
            "remote_systems": [f"{secondary_id}", "KP_Client_*", "KP_Test_*"],
            "peers": [self.create_peer_config(secondary_id, secondary_endpoint, 8443, shared_secret)],
            "sync_interval": 30,
            "heartbeat_interval": 10
        }

        # Configuração do secundário
        secondary_config = {
            "class_name": "SecondaryConfig",
            "env_type": "secundário",
            "system_id": secondary_id,
            "remote_systems": [f"{primary_id}", "KP_Client_*", "KP_Test_*"],
            "peers": [self.create_peer_config(primary_id, primary_endpoint, 8443, shared_secret)],
            "sync_interval": 30,
            "heartbeat_interval": 10
        }

        # Gerar arquivos
        self.generate_config_file(
            primary_config, f"skip_config_{primary_id.lower()}.py")
        self.generate_config_file(
            secondary_config, f"skip_config_{secondary_id.lower()}.py")

        print(f"\n🔑 Chave compartilhada gerada: {shared_secret}")
        print("⚠️  IMPORTANTE: Mantenha esta chave segura e configurada em ambos os servidores!")

        return shared_secret

    def setup_cluster(self, nodes):
        """Configura um cluster de múltiplos nós"""
        # Gerar chaves compartilhadas para cada par
        shared_secrets = {}

        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes[i+1:], i+1):
                pair_key = f"{node1['id']}-{node2['id']}"
                shared_secrets[pair_key] = self.generate_shared_secret()

        # Gerar configuração para cada nó
        for node in nodes:
            peers = []
            remote_systems = []

            for other_node in nodes:
                if other_node['id'] != node['id']:
                    # Encontrar chave compartilhada
                    pair_key1 = f"{node['id']}-{other_node['id']}"
                    pair_key2 = f"{other_node['id']}-{node['id']}"
                    shared_secret = shared_secrets.get(
                        pair_key1) or shared_secrets.get(pair_key2)

                    peers.append(self.create_peer_config(
                        other_node['id'],
                        other_node['endpoint'],
                        other_node.get('port', 8443),
                        shared_secret
                    ))

                    remote_systems.append(other_node['id'])

            # Adicionar sistemas cliente padrão
            remote_systems.extend(["KP_Client_*", "KP_Test_*", "KP_Mobile_*"])

            config = {
                "class_name": f"{node['id'].replace('_', '')}Config",
                "env_type": "cluster",
                "system_id": node['id'],
                "remote_systems": remote_systems,
                "peers": peers,
                "sync_interval": 15,  # Mais frequente para cluster
                "heartbeat_interval": 5,
                "max_keys": node.get('max_keys', 5000),
                "key_expiry": node.get('key_expiry', 1800)
            }

            filename = f"skip_config_{node['id'].lower()}.py"
            self.generate_config_file(config, filename)

        # Salvar resumo das chaves
        with open("cluster_shared_secrets.json", 'w') as f:
            json.dump(shared_secrets, f, indent=2)

        print(f"\n🔑 Chaves compartilhadas salvas em: cluster_shared_secrets.json")
        print("⚠️  IMPORTANTE: Distribua as chaves adequadas para cada nó!")

    def interactive_setup(self):
        """Setup interativo para configuração"""
        print("=== Configurador Interativo de Sincronização SKIP ===\n")

        setup_type = input(
            "Tipo de setup (1=Par Primário/Secundário, 2=Cluster): ")

        if setup_type == "1":
            print("\n--- Configuração Primário/Secundário ---")
            primary_id = input(
                "ID do servidor primário (ex: KP_QuIIN_Primary): ")
            primary_endpoint = input(
                "Endpoint do primário (ex: 192.168.1.10): ")
            secondary_id = input(
                "ID do servidor secundário (ex: KP_QuIIN_Backup): ")
            secondary_endpoint = input(
                "Endpoint do secundário (ex: 192.168.1.20): ")

            self.setup_primary_secondary(
                primary_id, primary_endpoint, secondary_id, secondary_endpoint)

        elif setup_type == "2":
            print("\n--- Configuração de Cluster ---")
            num_nodes = int(input("Número de nós no cluster: "))

            nodes = []
            for i in range(num_nodes):
                print(f"\nNó {i+1}:")
                node_id = input(f"  ID do nó (ex: KP_Node_{i+1}): ")
                endpoint = input(f"  Endpoint (ex: 192.168.1.{10+i}): ")
                port = input(f"  Porta (default 8443): ") or "8443"

                nodes.append({
                    "id": node_id,
                    "endpoint": endpoint,
                    "port": int(port)
                })

            self.setup_cluster(nodes)

        else:
            print("Opção inválida!")
            return

        print("\n✅ Configuração concluída!")
        print("\nPróximos passos:")
        print("1. Copie os arquivos de configuração para os respectivos servidores")
        print("2. Atualize skip_config.py para importar a configuração correta")
        print("3. Instale as dependências: pip install -r requirements.txt")
        print("4. Reinicie os servidores SKIP")
        print("5. Teste com: python3 test_skip_sync.py")


def main():
    parser = argparse.ArgumentParser(
        description='Configurador de sincronização SKIP')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Modo interativo')
    parser.add_argument('--primary-id', help='ID do servidor primário')
    parser.add_argument('--primary-endpoint',
                        help='Endpoint do servidor primário')
    parser.add_argument('--secondary-id', help='ID do servidor secundário')
    parser.add_argument('--secondary-endpoint',
                        help='Endpoint do servidor secundário')
    parser.add_argument('--cluster-config',
                        help='Arquivo JSON com configuração de cluster')

    args = parser.parse_args()

    configurator = SKIPSyncConfigurator()

    if args.interactive:
        configurator.interactive_setup()
    elif args.primary_id and args.primary_endpoint and args.secondary_id and args.secondary_endpoint:
        configurator.setup_primary_secondary(
            args.primary_id, args.primary_endpoint,
            args.secondary_id, args.secondary_endpoint
        )
    elif args.cluster_config:
        with open(args.cluster_config) as f:
            cluster_data = json.load(f)
        configurator.setup_cluster(cluster_data['nodes'])
    else:
        print("Use --interactive ou forneça parâmetros específicos")
        print("Exemplo: python3 setup_skip_sync.py --primary-id KP_Primary --primary-endpoint 192.168.1.10 --secondary-id KP_Backup --secondary-endpoint 192.168.1.20")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
