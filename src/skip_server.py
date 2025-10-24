import os
from flask import Flask, request, jsonify, make_response
import secrets
import logging
from datetime import datetime, timedelta
from skip_config import get_config

# This is a simplified implementation of a SKIP server. The entire key synchronization part between KPs must be implemented separately. For simplicity, keys here are generated using the secrets library and stored in memory. In a production environment, persistent and secure storage would be necessary, along with synchronization mechanisms between multiple Key Providers.

# Import OpenTelemetry configuration
from otel_config import setup_otel, get_tracer, get_logger, instrument_flask_app, create_custom_log_handler

# move to original code
from models import db, Key  # Import db and Key model
import sqlalchemy as sa

# Setup OpenTelemetry early
config = get_config()
setup_otel(service_name=config.LOCAL_SYSTEM_ID, service_version="1.0.0")

app = Flask(__name__)

# Instrument Flask AFTER creating the app
instrument_flask_app(app)
# Load configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+mysqlconnector://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}'

db.init_app(app)

with app.app_context():
    db.create_all()


# Configure logging with OpenTelemetry
log_format = f'%(asctime)s - [{config.LOCAL_SYSTEM_ID}] - %(name)s - %(levelname)s - %(message)s'

# Create logs directory if it doesn't exist (for local backup)
log_dir = '/app/logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, 'skip.logs')

# Get OTEL-enabled logger
logger = get_logger(__name__)
tracer = get_tracer(__name__)
logger.setLevel(getattr(logging, config.LOG_LEVEL))

# File handler (for Splunk)
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
file_handler.setFormatter(logging.Formatter(log_format))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
console_handler.setFormatter(logging.Formatter(log_format))

# OTEL trace log handler (sends logs as trace events)
otel_log_handler = create_custom_log_handler()
otel_log_handler.setLevel(getattr(logging, config.LOG_LEVEL))

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.addHandler(otel_log_handler)

# Configure root logger for other modules (without OTEL handler to avoid noise)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=log_format,
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler()
        # Note: Not adding OTEL handler to root logger to avoid capturing internal logs
    ]
)

# Initialize synchronizer
synchronizer = None
sync_loop = None


def json_response(data, status_code=200):
    """
    Creates JSON response with properly configured UTF-8 charset
    """
    response = make_response(jsonify(data), status_code)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


def cleanup_expired_keys():
    """Remove expired keys from memory"""
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
            f"Error removing expired keys from database: {e}")


@app.before_request
def before_request():
    """Executed before each request"""
    cleanup_expired_keys()
    # Get the endpoint/route that was matched (if available)
    endpoint = request.endpoint if request.endpoint else "unknown"
    logger.debug(
        f"REQUEST | method={request.method} | path={request.path} | endpoint={endpoint} | args={request.args} | remote_addr={request.remote_addr}")


@app.after_request
def after_request(response):
    """Executed after each request"""
    # Get response data for logging (only for non-binary content)
    response_data = ""
    try:
        if response.content_type and 'application/json' in response.content_type:
            response_data = response.get_data(as_text=True)
            # Limit response data length for logging (avoid huge logs)
            if len(response_data) > 500:
                response_data = response_data[:500] + "..."
        else:
            response_data = f"[{response.content_type}]"
    except Exception:
        response_data = "[binary-data]"

    logger.debug(
        f"RESPONSE | status_code={response.status_code} | content_length={response.content_length} | endpoint={request.endpoint if request.endpoint else 'unknown'}")
    return response

# Additional endpoint for service health check (not required by RFC)


@app.route('/health', methods=['GET'])
def health_check():
    """
    Service health check endpoint
    """
    try:
        # Check database connection
        db.session.execute(sa.text('SELECT 1'))
        db_status = "ok"
    except Exception as e:
        logger.error(f"Error in database health check: {e}")
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
    Returns Key Provider capabilities according to RFC SKIP Section 4.1
    """
    logger.info("Capabilities request received")
    response = config.get_capabilities_response()
    return json_response(response)

# Endpoint: GET /key?remoteSystemID=<id>&size=<bits>


@app.route('/key', methods=['GET'])
def get_new_key():
    """
    Generates a new key and returns key + keyId according to RFC SKIP Section 4.2
    """
    remote_system_id = request.args.get('remoteSystemID')

    if not remote_system_id:
        remote_system_id = config.LOCAL_SYSTEM_ID
    # RFC SKIP: remoteSystemID is required for new key generation
    # if not remote_system_id:
    #     return json_response({"error": "remoteSystemID is required"}, 400)

    # Validar remoteSystemID
    # if not _is_valid_remote_system(remote_system_id):
    #     return json_response({"error": "Invalid remoteSystemID"}, 400)

    try:
        # Default from config (256 bits as RFC default)
        key_size = int(request.args.get('size', config.DEFAULT_KEY_SIZE))
    except ValueError:
        return json_response({"error": "Invalid size parameter"}, 400)

    # Validate key size
    if key_size < config.MIN_KEY_SIZE or key_size > config.MAX_KEY_SIZE:
        return json_response({
            "error": f"Invalid key size. Must be between {config.MIN_KEY_SIZE} and {config.MAX_KEY_SIZE} bits"
        }, 400)

    # Check if it's a multiple of 8
    if key_size % 8 != 0:
        return json_response({"error": "Key size must be a multiple of 8"}, 400)

    try:
        # Generate secure key
        key_bytes = secrets.token_bytes(key_size // 8)
        key_hex = key_bytes.hex()

        # Generate 128-bit keyId (RFC default) in hex format
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
            f"KEY_GENERATED | key_id={key_id} | size={key_size} | remote_system_id={remote_system_id} | action=generate")

        response = {
            "keyId": key_id,
            "key": key_hex
        }

        return json_response(response)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating/saving new key: {e}")
        return json_response({"error": "Internal server error"}, 500)

# Endpoint: GET /key/{keyId}?remoteSystemID=<id>


@app.route('/key/<key_id>', methods=['GET'])
def get_key_by_id(key_id):
    """
    Retrieves a specific key by keyId according to RFC SKIP Section 4.2
    """
    remote_system_id = request.args.get('remoteSystemID')
    if not remote_system_id:
        return json_response({"error": "remoteSystemID is required"}, 400)

    # Validate keyId format (must be hexadecimal)
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
        # Search for the key in the database
        key_record = db.session.get(Key, key_id)
        if key_record is None:
            return json_response({"error": "Key not found"}, 400)

        # RFC SKIP: For synchronization between Key Providers, allow access
        # if the remoteSystemID is known (is in the list of valid systems)
        # The key exists in the shared database, so both servers can access it

        logger.info(
            f"Key found: created for '{key_record.remote_system_id}', requested by '{remote_system_id}', local server '{config.LOCAL_SYSTEM_ID}'")

        response = {
            "keyId": key_record.key_id,
            "key": key_record.key
        }

        logger.info(
            f"KEY_RETRIEVED | key_id={key_id} | remote_system_id={remote_system_id} | action=retrieve")

        # Zeroize the key after use (according to RFC SKIP Section 4.2.2)
        if config.ENABLE_KEY_ZEROIZATION:
            try:
                db.session.delete(key_record)
                db.session.commit()
                logger.info(f"KEY_ZEROIZED | key_id={key_id} | action=zeroize")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error zeroizing key: {e}")
                return json_response({"error": "Internal error while trying to zeroize key"}, 500)

        return json_response(response)

    except Exception as e:
        logger.error(f"Error retrieving key {key_id}: {e}")
        # Endpoint: GET /entropy?minentropy=<bits>
        return json_response({"error": "Internal error while trying to read key"}, 500)


@app.route('/entropy', methods=['GET'])
def get_entropy():
    """
    Returns random entropy according to RFC SKIP Section 4.3
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

        logger.info(
            f"ENTROPY_GENERATED | min_entropy={min_entropy} | action=entropy")
        return json_response(response)

    except ValueError:
        return json_response({"error": "Invalid minentropy parameter"}, 400)
    except Exception as e:
        logger.error(f"Error generating entropy: {e}")
        return json_response({"error": "Hardware random number generator not available"}, 503)


def _is_valid_remote_system(remote_system_id):
    """
    Checks if remoteSystemID is valid (supports glob patterns)
    """
    for valid_id in config.REMOTE_SYSTEM_IDS:
        if valid_id == remote_system_id:
            return True
        # Basic support for glob pattern with *
        if '*' in valid_id:
            pattern = valid_id.replace('*', '.*')
            import re
            if re.match(pattern, remote_system_id):
                return True
    return False

# HTTP error handling according to RFC SKIP Table 3


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
    # Validate configuration before starting
    errors = config.validate()
    if errors:
        logger.error("Configuration errors found:")
        for error in errors:
            logger.error(f"  - {error}")
        exit(1)

    logger.info(f"Starting SKIP Server - {config.LOCAL_SYSTEM_ID}")
    logger.info(f"TLS Algorithm: {config.TLS_ALGORITHM}")
    logger.info(f"Supported remote systems: {config.REMOTE_SYSTEM_IDS}")

    # TLS/PSK is managed by stunnel4, so we run in normal HTTP mode
    try:
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    except KeyboardInterrupt:
        exit(1)
