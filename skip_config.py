# SKIP Server Configuration
# RFC SKIP Implementation Settings

import os


class SKIPConfig:
    """
    Configuração do servidor SKIP conforme RFC SKIP
    """

    # Configurações básicas do servidor
    HOST = '127.0.0.1'  # Bind interno - TLS terminado pelo stunnel
    PORT = 8080
    DEBUG = False

    # Configurações do Key Provider
    LOCAL_SYSTEM_ID = "KP_QuIIN_Server"
    REMOTE_SYSTEM_IDS = [
        "KP_QuIIN_Client",
        "KP_*_Test",
        "KP_Development_*"
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

    # Configurações TLS/Stunnel
    STUNNEL_ACCEPT_PORT = 443
    STUNNEL_BACKEND_PORT = PORT
    PSK_FILE = "psk.txt"

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
            "algorithm": cls.TLS_ALGORITHM,
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
