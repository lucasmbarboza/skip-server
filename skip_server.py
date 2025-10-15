from flask import Flask, request, jsonify
import secrets
import uuid
import logging
import os
import asyncio
import threading
from datetime import datetime, timedelta
from skip_config import get_config
from skip_sync import SKIPSynchronizer

# Essa é uma implementação simplificada de um servidor SKIP toda a parte de sincronização de chaves entre os KP deve ser implementada a parte. Por simplicidade as chaves aqui são geradas a biblioteque secrets e armazenadas em memória. Em um ambiente de produção, seria necessário um armazenamento persistente e seguro, além de mecanismos de sincronização entre múltiplos Key Providers.

app = Flask(__name__)

# Carregar configuração
config = get_config()

# Configurar logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Simulação de dados do Key Provider
KP_DATA = {
    "localSystemID": config.LOCAL_SYSTEM_ID,
    "remoteSystemIDs": config.REMOTE_SYSTEM_IDS,
    "algorithm": config.TLS_ALGORITHM,
    "keys": {},  # Storage para as chaves geradas
    "key_timestamps": {}  # Timestamps para expiração
}

# Inicializar sincronizador
synchronizer = None
sync_loop = None


def init_synchronizer():
    """Inicializa o sistema de sincronização"""
    global synchronizer, sync_loop

    if not config.SYNC_ENABLED:
        logger.info("Sincronização desabilitada")
        return

    try:
        synchronizer = SKIPSynchronizer(config, KP_DATA)

        # Configurar peers da configuração
        for peer_config in config.SYNC_PEERS:
            synchronizer.add_peer(
                peer_config["system_id"],
                peer_config["endpoint"],
                peer_config["port"],
                peer_config["shared_secret"]
            )

        # Criar e iniciar loop de sincronização em thread separada
        def run_sync_loop():
            sync_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(sync_loop)

            # Iniciar sincronização no contexto do novo event loop
            sync_loop.run_until_complete(start_sync_tasks())

        async def start_sync_tasks():
            # Iniciar sincronização usando método assíncrono
            await synchronizer.async_start_sync()
            
            # Manter o loop rodando indefinidamente
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                synchronizer.stop_sync()
                raise

        sync_thread = threading.Thread(target=run_sync_loop, daemon=True)
        sync_thread.start()

        logger.info("Sistema de sincronização inicializado")

    except Exception as e:
        logger.error(f"Erro ao inicializar sincronização: {e}")
        synchronizer = None


def cleanup_expired_keys():
    """Remove chaves expiradas da memória"""
    current_time = datetime.now()
    expired_keys = []

    for key_id, timestamp in KP_DATA["key_timestamps"].items():
        if current_time - timestamp > timedelta(seconds=config.KEY_EXPIRY_SECONDS):
            expired_keys.append(key_id)

    for key_id in expired_keys:
        if key_id in KP_DATA["keys"]:
            del KP_DATA["keys"][key_id]
            logger.info(f"Chave expirada removida: {key_id}")
        if key_id in KP_DATA["key_timestamps"]:
            del KP_DATA["key_timestamps"][key_id]


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
    remote_system_id = request.args.get('remoteSystemID')
    key_size = int(request.args.get('size', 256))  # Default 256 bits

    if not remote_system_id:
        return jsonify({"error": "remoteSystemID is required"}), 400

    # Verifica se o remoteSystemID é válido
    if not _is_valid_remote_system(remote_system_id):
        return jsonify({"error": "Invalid remoteSystemID"}), 400

    # Gera nova chave e keyId
    key_bytes = secrets.token_bytes(key_size // 8)
    key_hex = key_bytes.hex()
    key_id = uuid.uuid4().hex

    # Verifica limite de chaves armazenadas
    if len(KP_DATA["keys"]) >= config.MAX_STORED_KEYS:
        cleanup_expired_keys()
        if len(KP_DATA["keys"]) >= config.MAX_STORED_KEYS:
            logger.warning("Limite de chaves armazenadas atingido")
            return jsonify({"error": "Key storage limit reached"}), 500

    # Armazena a chave (simulação - em produção seria sincronizada com KP remoto)
    KP_DATA["keys"][key_id] = {
        "key": key_hex,
        "remoteSystemID": remote_system_id,
        "size": key_size
    }
    KP_DATA["key_timestamps"][key_id] = datetime.now()

    # Sincronizar chave com peers se habilitado
    if synchronizer:
        synchronizer.sync_key_with_peers(key_id, KP_DATA["keys"][key_id])

    logger.info(f"Nova chave gerada: {key_id} para {remote_system_id}")

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
    if key_id not in KP_DATA["keys"]:
        return jsonify({"error": "Key not found"}), 400

    key_data = KP_DATA["keys"][key_id]

    # Verifica se o remoteSystemID corresponde
    if key_data["remoteSystemID"] != remote_system_id:
        return jsonify({"error": "Invalid remoteSystemID for this key"}), 400

    response = {
        "keyId": key_id,
        "key": key_data["key"]
    }

    # Zeroiza a chave após o uso (conforme RFC)
    if config.ENABLE_KEY_ZEROIZATION:
        del KP_DATA["keys"][key_id]
        if key_id in KP_DATA["key_timestamps"]:
            del KP_DATA["key_timestamps"][key_id]
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


# Endpoint: POST /sync (para comunicação entre Key Providers)
@app.route('/sync', methods=['POST'])
def handle_sync():
    """
    Endpoint para receber mensagens de sincronização de outros Key Providers
    """
    if not synchronizer:
        return jsonify({"error": "Synchronization not enabled"}), 503

    try:
        message_data = request.get_json()
        if not message_data:
            return jsonify({"error": "Invalid JSON data"}), 400

        # Executar processamento assíncrono em thread
        def process_sync():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                synchronizer.handle_incoming_message(
                    message_data, request.remote_addr)
            )
            loop.close()
            return result

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(process_sync)
            result = future.result(timeout=10)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Erro no endpoint de sincronização: {e}")
        return jsonify({"error": "Internal sync error"}), 500


# Endpoint: GET /status/sync
@app.route('/status/sync', methods=['GET'])
def get_sync_status():
    """
    Retorna status da sincronização entre Key Providers
    """
    if not synchronizer:
        return jsonify({
            "sync_enabled": False,
            "message": "Synchronization not enabled"
        }), 200

    try:
        status = synchronizer.get_sync_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Erro ao obter status de sincronização: {e}")
        return jsonify({"error": "Failed to get sync status"}), 500


# Endpoint: GET /status/health
@app.route('/status/health', methods=['GET'])
def get_health_status():
    """
    Endpoint de health check para monitoramento
    """
    try:
        # Limpar chaves expiradas
        cleanup_expired_keys()

        # Verificar status básico
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "local_system_id": config.LOCAL_SYSTEM_ID,
            "stored_keys": len(KP_DATA["keys"]),
            "max_keys": config.MAX_STORED_KEYS,
            "sync_enabled": config.SYNC_ENABLED
        }

        # Adicionar informações de sincronização se habilitada
        if synchronizer:
            sync_status = synchronizer.get_sync_status()
            health_status["sync_peers"] = len(sync_status["peers"])
            health_status["online_peers"] = len([
                p for p in sync_status["peers"].values()
                if p["status"] == "online"
            ])

        return jsonify(health_status), 200

    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


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

    # Inicializar sistema de sincronização
    init_synchronizer()

    # O TLS/PSK é gerenciado pelo stunnel4, então rodamos em modo HTTP normal
    try:
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    except KeyboardInterrupt:
        logger.info("Parando servidor...")
        if synchronizer:
            synchronizer.stop_sync()
        logger.info("Servidor parado")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        if synchronizer:
            synchronizer.stop_sync()
        exit(1)
