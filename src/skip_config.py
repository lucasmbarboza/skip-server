# SKIP Server Configuration
# RFC SKIP Implementation Settings

import os


class SKIPConfig:
    """
    Configuração do servidor SKIP conforme RFC SKIP
    """

    # Configurações básicas do servidor
    HOST = '0.0.0.0'  # Bind em todas as interfaces para aceitar conexões do Docker
    PORT = 8080  # Porta interna (stunnel faz proxy para 8443)
    DEBUG = False

    # Configurações do Key Provider
    LOCAL_SYSTEM_ID = os.getenv('SKIP_LOCAL_SYSTEM_ID', 'KP_QuIIN_Server')
    REMOTE_SYSTEM_IDS = [
        os.getenv('SKIP_REMOTE_SYSTEM_ID', 'KP_QuIIN_Client'),
    ]

    # Algoritmos suportados (RFC SKIP Table 1)
    TLS_ALGORITHM = "TLS_DHE_PSK_WITH_AES_256_CBC_SHA384"

    # Configurações de chave
    DEFAULT_KEY_SIZE = 256  # bits
    DEFAULT_ENTROPY_SIZE = 256  # bits
    MIN_KEY_SIZE = 128  # bits
    MAX_KEY_SIZE = 512  # bits

    # Configurações de segurança
    ENABLE_KEY_ZEROIZATION = True  # Zeroizar chaves após uso
    MAX_STORED_KEYS = 1000  # Limite de chaves em memória
    KEY_EXPIRY_SECONDS = 3600  # Expiração de chaves não utilizadas

    # Configurações de logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "/var/log/skip/skip_server.log"

    # Configurações de Sincronização entre Key Providers
    MYSQL_ROOT_PASSWORD = os.getenv(
        'MYSQL_ROOT_PASSWORD', 'your_root_password_here')
    # Nome do seu banco de dados
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'my_database_name')
    # Nome do usuário do banco de dados
    MYSQL_USER = os.getenv('MYSQL_USER', 'my_user')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'my_user_password_here')
    # Host do banco de dados
    MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
    # Porta do banco de dados
    MYSQL_PORT = os.getenv('MYSQL_PORT', 3306)

    QRNG_API_KEY = os.getenv('QRNG_API_KEY',  ',U-2g704XW7N8h4,2Mniaac7Qwe+tCD6O1>isjZV<KF0UB!}ipv,>(}5!038[}K+')
    # Validação de configuração

    @classmethod
    def validate(cls):
        """Valida a configuração"""
        errors = []

        if cls.DEFAULT_KEY_SIZE < cls.MIN_KEY_SIZE:
            errors.append("DEFAULT_KEY_SIZE deve ser >= MIN_KEY_SIZE")

        if cls.DEFAULT_KEY_SIZE > cls.MAX_KEY_SIZE:
            errors.append("DEFAULT_KEY_SIZE deve ser <= MAX_KEY_SIZE")

        if not cls.LOCAL_SYSTEM_ID:
            errors.append("LOCAL_SYSTEM_ID não pode estar vazio")

        if not cls.REMOTE_SYSTEM_IDS:
            errors.append("REMOTE_SYSTEM_IDS deve conter pelo menos um ID")

        return errors

    @classmethod
    def get_capabilities_response(cls):
        """Retorna a resposta padrão para /capabilities"""
        return {
            "entropy": True,
            "key": True,
            "algorithm": 'pqc',
            "localSystemID": cls.LOCAL_SYSTEM_ID,
            "remoteSystemID": cls.REMOTE_SYSTEM_IDS
        }

# Configurações específicas do ambiente


class DevelopmentConfig(SKIPConfig):
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(SKIPConfig):
    DEBUG = False
    LOG_LEVEL = "WARNING"
    MAX_STORED_KEYS = 10000

# Seleção de configuração baseada na variável de ambiente


def get_config():
    env = os.environ.get('SKIP_ENV', 'development').lower()

    if env == 'production':
        return ProductionConfig
    else:
        return DevelopmentConfig
