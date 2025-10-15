# Arquivo de configuração de exemplo para sincronização SKIP
# Copie para skip_sync_config.py e ajuste conforme seu ambiente

from skip_config import SKIPConfig


class ProductionSyncConfig(SKIPConfig):
    """
    Configuração de produção com sincronização habilitada
    """

    # Key Provider principal
    LOCAL_SYSTEM_ID = "KP_QuIIN_Primary"

    # Sistemas remotos que podem solicitar chaves
    REMOTE_SYSTEM_IDS = [
        "KP_QuIIN_Client",
        "KP_QuIIN_Mobile",
        "KP_Test_*",
        "KP_Dev_*"
    ]

    # Configurações de sincronização
    SYNC_ENABLED = True
    SYNC_INTERVAL = 15  # Sincronizar a cada 15 segundos
    HEARTBEAT_INTERVAL = 5  # Heartbeat a cada 5 segundos
    MAX_RETRY_ATTEMPTS = 5
    SYNC_TIMEOUT = 15
    SYNC_PORT = 8443

    # Configuração de peers para sincronização
    SYNC_PEERS = [
        {
            "system_id": "KP_QuIIN_Backup",
            "endpoint": "192.168.1.100",
            "port": 8443,
            "shared_secret": "backup_server_shared_secret_256bit_key_here"
        },
        {
            "system_id": "KP_QuIIN_DR",
            "endpoint": "10.0.1.50",
            "port": 8443,
            "shared_secret": "disaster_recovery_shared_secret_256bit_key"
        }
    ]

    # Configurações de segurança aprimoradas
    MAX_STORED_KEYS = 5000
    KEY_EXPIRY_SECONDS = 1800  # 30 minutos
    ENABLE_KEY_ZEROIZATION = True

    # Logging para produção
    LOG_LEVEL = "INFO"
    DEBUG = False


class DevelopmentSyncConfig(SKIPConfig):
    """
    Configuração de desenvolvimento com sincronização para teste
    """

    LOCAL_SYSTEM_ID = "KP_Dev_Node1"

    REMOTE_SYSTEM_IDS = [
        "KP_Dev_Client",
        "KP_Test_*"
    ]

    # Sincronização mais frequente para desenvolvimento
    SYNC_ENABLED = True
    SYNC_INTERVAL = 10
    HEARTBEAT_INTERVAL = 3
    MAX_RETRY_ATTEMPTS = 3
    SYNC_TIMEOUT = 5
    SYNC_PORT = 8443

    # Peer de desenvolvimento local
    SYNC_PEERS = [
        {
            "system_id": "KP_Dev_Node2",
            "endpoint": "localhost",
            "port": 8444,  # Porta diferente para teste local
            "shared_secret": "dev_test_shared_secret_for_development_only"
        }
    ]

    # Configurações para desenvolvimento
    MAX_STORED_KEYS = 100
    KEY_EXPIRY_SECONDS = 300  # 5 minutos para teste
    LOG_LEVEL = "DEBUG"
    DEBUG = True


class DisasterRecoveryConfig(SKIPConfig):
    """
    Configuração especializada para site de disaster recovery
    """

    LOCAL_SYSTEM_ID = "KP_QuIIN_DR_Site"

    # Aceitar conexões de múltiplos sites
    REMOTE_SYSTEM_IDS = [
        "KP_QuIIN_*",
        "KP_Backup_*",
        "KP_Emergency_*"
    ]

    # Configurações otimizadas para DR
    SYNC_ENABLED = True
    SYNC_INTERVAL = 5  # Sincronização mais agressiva
    HEARTBEAT_INTERVAL = 2
    MAX_RETRY_ATTEMPTS = 10  # Mais tentativas
    SYNC_TIMEOUT = 20  # Timeout maior para links instáveis
    SYNC_PORT = 8443

    # Múltiplos peers para redundância
    SYNC_PEERS = [
        {
            "system_id": "KP_QuIIN_Primary",
            "endpoint": "primary.skip.company.com",
            "port": 8443,
            "shared_secret": "primary_to_dr_shared_secret_key_here"
        },
        {
            "system_id": "KP_QuIIN_Backup",
            "endpoint": "backup.skip.company.com",
            "port": 8443,
            "shared_secret": "backup_to_dr_shared_secret_key_here"
        }
    ]

    # Configurações de alta disponibilidade
    MAX_STORED_KEYS = 10000
    KEY_EXPIRY_SECONDS = 3600  # 1 hora
    ENABLE_KEY_ZEROIZATION = False  # Manter chaves para DR

    LOG_LEVEL = "WARNING"  # Menos logs para performance
    DEBUG = False


# Mapeamento de configurações por ambiente
SYNC_CONFIGS = {
    "production": ProductionSyncConfig,
    "development": DevelopmentSyncConfig,
    "disaster_recovery": DisasterRecoveryConfig
}


def get_sync_config(env_name="development"):
    """
    Retorna a configuração apropriada para o ambiente
    """
    return SYNC_CONFIGS.get(env_name, DevelopmentSyncConfig)


# Instruções de uso:
#
# 1. Copie este arquivo para skip_sync_config.py
# 2. Ajuste as configurações conforme seu ambiente
# 3. Defina a variável de ambiente SKIP_SYNC_ENV:
#    - export SKIP_SYNC_ENV=production
#    - export SKIP_SYNC_ENV=development
#    - export SKIP_SYNC_ENV=disaster_recovery
# 4. Modifique skip_config.py para usar get_sync_config()
#
# Exemplo de modificação em skip_config.py:
#
# def get_config():
#     env = os.environ.get('SKIP_ENV', 'development').lower()
#     sync_env = os.environ.get('SKIP_SYNC_ENV', env)
#
#     if sync_env in ['production', 'disaster_recovery']:
#         from skip_sync_config import get_sync_config
#         return get_sync_config(sync_env)
#     else:
#         return DevelopmentConfig
