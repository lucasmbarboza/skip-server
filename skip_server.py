from flask import Flask, request, jsonify
import secrets
import uuid
import logging
from datetime import datetime, timedelta
from skip_config import get_config

# Essa é uma implementação simplificada de um servidor SKIP toda a parte de sincronização de chaves entre os KP deve ser implementada a parte. Por simplicidade as chaves aqui são geradas a biblioteque secrets e armazenadas em memória. Em um ambiente de produção, seria necessário um armazenamento persistente e seguro, além de mecanismos de sincronização entre múltiplos Key Providers.

### passar para o código original
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


def cleanup_expired_keys():
    """Remove chaves expiradas da memória"""
    current_time = datetime.now()

    try:
        db.session.query(Key).filter(
            Key.created_at < current_time - timedelta(seconds=config.KEY_EXPIRY_SECONDS)
        ).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao remover chaves expiradas do banco de dados: {e}")


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

# Endpoint: GET /capabilities


@app.route('/capabilities', methods=['GET'])
def get_capabilities():
    """
    Retorna as capacidades do Key Provider conforme RFC SKIP Seção 4.1
    """
    logger.info("Solicitação de capabilities recebida")
    response = config.get_capabilities_response()
    return jsonify(response), 200

# Endpoint: GET /key?remoteSystemID=<id>&size=<bits>


@app.route('/key', methods=['GET'])
def get_new_key():
    """
    Gera uma nova chave e retorna key + keyId conforme RFC SKIP Seção 4.2
    """
 
    # Default from config
    key_size = int(request.args.get('size', config.DEFAULT_KEY_SIZE))

    # Validar tamanho da chave
    if key_size < config.MIN_KEY_SIZE or key_size > config.MAX_KEY_SIZE:
        return jsonify({
            "error": f"Invalid key size. Must be between {config.MIN_KEY_SIZE} and {config.MAX_KEY_SIZE} bits"
        }), 400

    # Gerar chave segura
    key_bytes = secrets.token_bytes(key_size // 8)
    key_hex = key_bytes.hex()
    key_id = uuid.uuid4().hex

    new_key = Key(
        key_id=key_id,
        key=key_hex,
        remote_system_id=config.LOCAL_SYSTEM_ID,  # Pode ser None
        size=key_size,
        created_at=datetime.now()
    )
    try:
        db.session.add(new_key)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar nova chave: {e}")
        return jsonify({"error": "Internal server error"}), 500

    logger.info(f"Nova chave gerada: {key_id} (size: {key_size})")

    response = {
        "keyId": key_id,
        "key": key_hex
    }

    return jsonify(response), 200

# Endpoint: GET /key/{keyId}?remoteSystemID=<id>


@app.route('/key/<key_id>', methods=['GET'])
def get_key_by_id(key_id):
    """
    Recupera uma chave específica pelo keyId conforme RFC SKIP Seção 4.2
    """
    remote_system_id = request.args.get('remoteSystemID')
    if not remote_system_id:
        return jsonify({"error": "remoteSystemID is required"}), 400


    # Verifica se a chave existe
    try:
        if db.session.get(Key, key_id) is None:
            return jsonify({"error": "Key not found"}), 400

        # key_data = KP_DATA["keys"][key_id]
        key_record = db.session.get(Key, key_id)
        response = {
            "keyId": key_record.key_id,
            "key": key_record.key,
        }
    except Exception as e:
        logger.error(f"Erro ao recuperar chave: {e}")
        return jsonify({"error": "Internal server error"}), 500

    if remote_system_id and key_record.remote_system_id != remote_system_id:
        return jsonify({"error": "Invalid remoteSystemID for this key"}), 400
    logger.info(f"Chave recuperada: {key_id}")

    # Zeroiza a chave após o uso (conforme RFC)
    if config.ENABLE_KEY_ZEROIZATION:
        try:
            db.session.delete(key_record)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao zeroizar chave: {e}")
            return jsonify({"error": "Internal server error"}), 500
        logger.info(f"Chave zeroizada: {key_id}")

    return jsonify(response), 200  # Endpoint: GET /entropy?minentropy=<bits>


@app.route('/entropy', methods=['GET'])
def get_entropy():
    """
    Retorna entropia aleatória conforme RFC SKIP Seção 4.3
    """
    min_entropy = int(request.args.get('minentropy', 256))  # Default 256 bits

    try:
        # Gera entropia aleatória
        entropy_bytes = secrets.token_bytes(min_entropy // 8)
        entropy_hex = entropy_bytes.hex().upper()

        response = {
            "randomStr": entropy_hex,
            "minentropy": min_entropy
        }

        return jsonify(response), 200

    except Exception:
        return jsonify({"error": "Hardware random number generator not available"}), 503


def _is_valid_remote_system(remote_system_id):
    """
    Verifica se o remoteSystemID é válido (suporte a glob patterns)
    """
    for valid_id in KP_DATA["remoteSystemIDs"]:
        if valid_id == remote_system_id:
            return True
        # Suporte básico para glob pattern com *
        if '*' in valid_id:
            pattern = valid_id.replace('*', '.*')
            import re
            if re.match(pattern, remote_system_id):
                return True
    return False

# Tratamento de erros HTTP


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed. Only GET is supported"}), 405


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
