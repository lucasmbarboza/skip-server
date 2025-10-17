from flask import Flask, request, jsonify, make_response
import secrets
import uuid
import logging
from datetime import datetime, timedelta
from skip_config import get_config

# Essa é uma implementação simplificada de um servidor SKIP toda a parte de sincronização de chaves entre os KP deve ser implementada a parte. Por simplicidade as chaves aqui são geradas a biblioteque secrets e armazenadas em memória. Em um ambiente de produção, seria necessário um armazenamento persistente e seguro, além de mecanismos de sincronização entre múltiplos Key Providers.

# passar para o código original
from models import db, Key  # Importa db e modelo Key
import sqlalchemy as sa


app = Flask(__name__)
# Carregar configuração
config = get_config()
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+mysqlconnector://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}'

db.init_app(app)

with app.app_context():
    db.create_all()


# Configurar logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar sincronizador
synchronizer = None
sync_loop = None


def json_response(data, status_code=200):
    """
    Cria resposta JSON com charset UTF-8 adequadamente configurado
    """
    response = make_response(jsonify(data), status_code)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


def cleanup_expired_keys():
    """Remove chaves expiradas da memória"""
    current_time = datetime.now()

    try:
        db.session.query(Key).filter(
            Key.created_at < current_time -
            timedelta(seconds=config.KEY_EXPIRY_SECONDS)
        ).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Erro ao remover chaves expiradas do banco de dados: {e}")


@app.before_request
def before_request():
    """Executado antes de cada requisição"""
    cleanup_expired_keys()
    logger.debug(
        f"Requisição: {request.method} {request.path} - {request.args}")


@app.after_request
def after_request(response):
    """Executado após cada requisição"""
    logger.debug(f"Resposta: {response.status_code}")
    return response

# Endpoint adicional para verificação de saúde (não obrigatório pela RFC)


@app.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint de verificação de saúde do serviço
    """
    try:
        # Verificar conexão com banco de dados
        db.session.execute(sa.text('SELECT 1'))
        db_status = "ok"
    except Exception as e:
        logger.error(f"Erro na verificação de saúde do banco: {e}")
        db_status = "error"

    response = {
        "status": "ok" if db_status == "ok" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "version": "1.0.0",
        "localSystemID": config.LOCAL_SYSTEM_ID
    }

    status_code = 200 if db_status == "ok" else 503
    return json_response(response, status_code)

# Endpoint: GET /capabilities


@app.route('/capabilities', methods=['GET'])
def get_capabilities():
    """
    Retorna as capacidades do Key Provider conforme RFC SKIP Seção 4.1
    """
    logger.info("Solicitação de capabilities recebida")
    response = config.get_capabilities_response()
    return json_response(response)

# Endpoint: GET /key?remoteSystemID=<id>&size=<bits>


@app.route('/key', methods=['GET'])
def get_new_key():
    """
    Gera uma nova chave e retorna key + keyId conforme RFC SKIP Seção 4.2
    """
    remote_system_id = request.args.get('remoteSystemID')

    # RFC SKIP: remoteSystemID é obrigatório para geração de novas chaves
    if not remote_system_id:
        return json_response({"error": "remoteSystemID is required"}, 400)

    # Validar remoteSystemID
    if not _is_valid_remote_system(remote_system_id):
        return json_response({"error": "Invalid remoteSystemID"}, 400)

    try:
        # Default from config (256 bits como padrão da RFC)
        key_size = int(request.args.get('size', config.DEFAULT_KEY_SIZE))
    except ValueError:
        return json_response({"error": "Invalid size parameter"}, 400)

    # Validar tamanho da chave
    if key_size < config.MIN_KEY_SIZE or key_size > config.MAX_KEY_SIZE:
        return json_response({
            "error": f"Invalid key size. Must be between {config.MIN_KEY_SIZE} and {config.MAX_KEY_SIZE} bits"
        }, 400)

    # Verificar se é múltiplo de 8
    if key_size % 8 != 0:
        return json_response({"error": "Key size must be a multiple of 8"}, 400)

    try:
        # Gerar chave segura
        key_bytes = secrets.token_bytes(key_size // 8)
        key_hex = key_bytes.hex()

        # Gerar keyId de 128 bits (padrão RFC) em formato hex
        key_id_bytes = secrets.token_bytes(16)  # 128 bits / 8 = 16 bytes
        key_id = key_id_bytes.hex()

        new_key = Key(
            key_id=key_id,
            key=key_hex,
            remote_system_id=remote_system_id,
            size=key_size,
            created_at=datetime.now()
        )

        db.session.add(new_key)
        db.session.commit()

        logger.info(
            f"Nova chave gerada: {key_id} (size: {key_size} bits, remoteSystemID: {remote_system_id})")

        response = {
            "keyId": key_id,
            "key": key_hex
        }

        return json_response(response)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao gerar/salvar nova chave: {e}")
        return json_response({"error": "Internal server error"}, 500)

# Endpoint: GET /key/{keyId}?remoteSystemID=<id>


@app.route('/key/<key_id>', methods=['GET'])
def get_key_by_id(key_id):
    """
    Recupera uma chave específica pelo keyId conforme RFC SKIP Seção 4.2
    """
    remote_system_id = request.args.get('remoteSystemID')
    if not remote_system_id:
        return json_response({"error": "remoteSystemID is required"}, 400)

    # Validar formato do keyId (deve ser hexadecimal)
    if not key_id or len(key_id) != 32:  # 128 bits = 32 caracteres hex
        return json_response({"error": "Malformed keyId"}, 400)

    try:
        # Verificar se é hexadecimal válido
        int(key_id, 16)
    except ValueError:
        return json_response({"error": "Malformed keyId"}, 400)

    # Validar remoteSystemID
    if not _is_valid_remote_system(remote_system_id):
        return json_response({"error": "Invalid remoteSystemID"}, 400)

    try:
        # Buscar a chave no banco de dados
        key_record = db.session.get(Key, key_id)
        if key_record is None:
            return json_response({"error": "Key not found"}, 400)

        # RFC SKIP: Para sincronização entre Key Providers, permitir acesso
        # se o remoteSystemID é conhecido (está na lista de sistemas válidos)
        # A chave existe no banco compartilhado, então ambos os servidores podem acessá-la

        logger.info(
            f"Chave encontrada: criada para '{key_record.remote_system_id}', solicitada por '{remote_system_id}', servidor local '{config.LOCAL_SYSTEM_ID}'")

        response = {
            "keyId": key_record.key_id,
            "key": key_record.key
        }

        logger.info(
            f"Chave recuperada: {key_id} (remoteSystemID: {remote_system_id})")

        # Zeroiza a chave após o uso (conforme RFC SKIP Seção 4.2.2)
        if config.ENABLE_KEY_ZEROIZATION:
            try:
                db.session.delete(key_record)
                db.session.commit()
                logger.info(f"Chave zeroizada após uso: {key_id}")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erro ao zeroizar chave: {e}")
                return json_response({"error": "Internal error while trying to zeroize key"}, 500)

        return json_response(response)

    except Exception as e:
        logger.error(f"Erro ao recuperar chave {key_id}: {e}")
        # Endpoint: GET /entropy?minentropy=<bits>
        return json_response({"error": "Internal error while trying to read key"}, 500)


@app.route('/entropy', methods=['GET'])
def get_entropy():
    """
    Retorna entropia aleatória conforme RFC SKIP Seção 4.3
    """
    try:
        min_entropy = int(request.args.get(
            'minentropy', 256))  # Default 256 bits

        # Validar tamanho mínimo de entropia
        if min_entropy < 8 or min_entropy > 2048:  # Limites razoáveis
            return json_response({"error": "Invalid minentropy. Must be between 8 and 2048 bits"}, 400)

        # Verificar se é múltiplo de 8
        if min_entropy % 8 != 0:
            return json_response({"error": "minentropy must be a multiple of 8"}, 400)

        # Gera entropia aleatória
        entropy_bytes = secrets.token_bytes(min_entropy // 8)
        entropy_hex = entropy_bytes.hex().upper()

        response = {
            "randomStr": entropy_hex,
            "minentropy": min_entropy
        }

        logger.info(f"Entropia gerada: {min_entropy} bits")
        return json_response(response)

    except ValueError:
        return json_response({"error": "Invalid minentropy parameter"}, 400)
    except Exception as e:
        logger.error(f"Erro ao gerar entropia: {e}")
        return json_response({"error": "Hardware random number generator not available"}, 503)


def _is_valid_remote_system(remote_system_id):
    """
    Verifica se o remoteSystemID é válido (suporte a glob patterns)
    """
    for valid_id in config.REMOTE_SYSTEM_IDS:
        if valid_id == remote_system_id:
            return True
        # Suporte básico para glob pattern com *
        if '*' in valid_id:
            pattern = valid_id.replace('*', '.*')
            import re
            if re.match(pattern, remote_system_id):
                return True
    return False

# Tratamento de erros HTTP conforme RFC SKIP Tabela 3


@app.errorhandler(404)
def not_found(error):
    """
    RFC SKIP Tabela 3: 404 - A path that doesn't correspond to those described in Table 2 was provided
    """
    return json_response({"error": "Endpoint not found"}, 404)


@app.errorhandler(405)
def method_not_allowed(error):
    """
    RFC SKIP Tabela 3: 405 - A bad method was used. Only 'GET' is supported
    """
    return json_response({"error": "Method not allowed. Only GET is supported"}, 405)


@app.errorhandler(400)
def bad_request(error):
    """
    RFC SKIP Tabela 7: 400 - A malformed keyId was requested or the key was not found
    """
    return json_response({"error": "Bad request"}, 400)


@app.errorhandler(500)
def internal_server_error(error):
    """
    RFC SKIP Tabela 7: 500 - There was an internal error while trying to read or zeroize the key
    """
    logger.error(f"Internal server error: {error}")
    return json_response({"error": "Internal server error"}, 500)


@app.errorhandler(503)
def service_unavailable(error):
    """
    RFC SKIP Tabela 9: 503 - Hardware random number generator is not available or entropy pool doesn't have enough entropy
    """
    return json_response({"error": "Service unavailable"}, 503)


if __name__ == '__main__':
    # Validar configuração antes de iniciar
    errors = config.validate()
    if errors:
        logger.error("Erros de configuração encontrados:")
        for error in errors:
            logger.error(f"  - {error}")
        exit(1)

    logger.info(f"Iniciando SKIP Server - {config.LOCAL_SYSTEM_ID}")
    logger.info(f"Algoritmo TLS: {config.TLS_ALGORITHM}")
    logger.info(f"Sistemas remotos suportados: {config.REMOTE_SYSTEM_IDS}")

    # O TLS/PSK é gerenciado pelo stunnel4, então rodamos em modo HTTP normal
    try:
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    except KeyboardInterrupt:
        exit(1)
