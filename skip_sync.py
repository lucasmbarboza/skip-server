# SKIP Server Synchronization Module
# Implementa a sincronização de chaves entre Key Providers conforme RFC SKIP

import asyncio
import aiohttp
import hashlib
import hmac
import json
import logging
import ssl
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

logger = logging.getLogger(__name__)


@dataclass
class SyncMessage:
    """Mensagem de sincronização entre KPs"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: str  # 'key_sync', 'heartbeat', 'capability_exchange'
    timestamp: float
    payload: Dict
    signature: Optional[str] = None


@dataclass
class KeySyncPayload:
    """Payload para sincronização de chaves"""
    key_id: str
    key_data: str  # Encrypted key
    remote_system_id: str
    key_size: int
    created_at: float
    expires_at: float


@dataclass
class PeerKP:
    """Representação de um Key Provider peer"""
    system_id: str
    endpoint: str
    port: int
    shared_secret: str
    last_heartbeat: Optional[float] = None
    status: str = "unknown"  # unknown, online, offline, error
    capabilities: Optional[Dict] = None


class SKIPSynchronizer:
    """
    Gerenciador de sincronização para servidores SKIP
    Implementa sincronização segura de chaves entre Key Providers
    """

    def __init__(self, config, kp_data):
        self.config = config
        self.kp_data = kp_data
        self.peers: Dict[str, PeerKP] = {}
        self.sync_enabled = getattr(config, 'SYNC_ENABLED', True)
        self.sync_interval = getattr(config, 'SYNC_INTERVAL', 30)  # seconds
        self.heartbeat_interval = getattr(config, 'HEARTBEAT_INTERVAL', 10)
        self.max_retry_attempts = getattr(config, 'MAX_RETRY_ATTEMPTS', 3)
        self.sync_timeout = getattr(config, 'SYNC_TIMEOUT', 10)

        # Configurar criptografia para comunicação entre peers
        self._setup_encryption()

        # Tasks assíncronas
        self._sync_task = None
        self._heartbeat_task = None

        logger.info(
            f"SKIP Synchronizer iniciado para {self.config.LOCAL_SYSTEM_ID}")

    def _setup_encryption(self):
        """Configura criptografia para comunicação segura entre peers"""
        # Usar uma chave derivada do ID local para criptografia
        password = f"{self.config.LOCAL_SYSTEM_ID}_sync_key".encode()
        salt = b'skip_sync_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self.cipher = Fernet(key)

    def add_peer(self, system_id: str, endpoint: str, port: int, shared_secret: str):
        """Adiciona um peer KP para sincronização"""
        peer = PeerKP(
            system_id=system_id,
            endpoint=endpoint,
            port=port,
            shared_secret=shared_secret
        )
        self.peers[system_id] = peer
        logger.info(f"Peer KP adicionado: {system_id} @ {endpoint}:{port}")

    def remove_peer(self, system_id: str):
        """Remove um peer KP"""
        if system_id in self.peers:
            del self.peers[system_id]
            logger.info(f"Peer KP removido: {system_id}")

    def start_sync(self):
        """Inicia as tarefas de sincronização em background"""
        if not self.sync_enabled:
            logger.info("Sincronização desabilitada")
            return

        try:
            # Verificar se há um event loop rodando
            loop = asyncio.get_running_loop()

            if self._sync_task is None or self._sync_task.done():
                self._sync_task = loop.create_task(self._sync_loop())
                logger.info("Tarefa de sincronização iniciada")

            if self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = loop.create_task(self._heartbeat_loop())
                logger.info("Tarefa de heartbeat iniciada")

        except RuntimeError:
            # Não há event loop rodando, criar tasks será feito externamente
            logger.warning(
                "Nenhum event loop ativo encontrado para start_sync")
            pass

    async def async_start_sync(self):
        """Versão assíncrona de start_sync para uso em event loops"""
        if not self.sync_enabled:
            logger.info("Sincronização desabilitada")
            return

        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._sync_loop())
            logger.info("Tarefa de sincronização iniciada (async)")

        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Tarefa de heartbeat iniciada (async)")

    def stop_sync(self):
        """Para as tarefas de sincronização"""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            logger.info("Tarefa de sincronização parada")

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            logger.info("Tarefa de heartbeat parada")

    async def _sync_loop(self):
        """Loop principal de sincronização"""
        while True:
            try:
                await self._sync_with_peers()
                await asyncio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                logger.info("Loop de sincronização cancelado")
                break
            except Exception as e:
                logger.error(f"Erro no loop de sincronização: {e}")
                await asyncio.sleep(5)  # Wait before retry

    async def _heartbeat_loop(self):
        """Loop de heartbeat para verificar status dos peers"""
        while True:
            try:
                await self._send_heartbeats()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                logger.info("Loop de heartbeat cancelado")
                break
            except Exception as e:
                logger.error(f"Erro no loop de heartbeat: {e}")
                await asyncio.sleep(5)

    async def _sync_with_peers(self):
        """Sincroniza chaves com todos os peers"""
        tasks = []
        for peer_id, peer in self.peers.items():
            if peer.status == "online":
                task = asyncio.create_task(self._sync_with_peer(peer))
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _sync_with_peer(self, peer: PeerKP):
        """Sincroniza chaves com um peer específico"""
        try:
            # Enviar chaves pendentes para o peer
            pending_keys = self._get_pending_keys_for_peer(peer.system_id)
            for key_id, key_info in pending_keys.items():
                await self._send_key_to_peer(peer, key_id, key_info)

            # Verificar se há chaves para receber
            await self._request_keys_from_peer(peer)

        except Exception as e:
            logger.error(
                f"Erro na sincronização com peer {peer.system_id}: {e}")
            peer.status = "error"

    def _get_pending_keys_for_peer(self, peer_system_id: str) -> Dict:
        """Obtém chaves que precisam ser sincronizadas com um peer"""
        pending_keys = {}

        for key_id, key_data in self.kp_data["keys"].items():
            # Verificar se a chave é destinada a este peer
            if key_data.get("remoteSystemID") == peer_system_id:
                # Verificar se não foi sincronizada ainda
                if not key_data.get("synced", False):
                    pending_keys[key_id] = key_data

        return pending_keys

    async def _send_key_to_peer(self, peer: PeerKP, key_id: str, key_info: Dict):
        """Envia uma chave para um peer"""
        try:
            # Criar payload de sincronização
            payload = KeySyncPayload(
                key_id=key_id,
                key_data=self._encrypt_key(key_info["key"]),
                remote_system_id=self.config.LOCAL_SYSTEM_ID,
                key_size=key_info["size"],
                created_at=time.time(),
                expires_at=time.time() + self.config.KEY_EXPIRY_SECONDS
            )

            # Criar mensagem de sincronização
            message = SyncMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.config.LOCAL_SYSTEM_ID,
                receiver_id=peer.system_id,
                message_type="key_sync",
                timestamp=time.time(),
                payload=asdict(payload)
            )

            # Assinar mensagem
            message.signature = self._sign_message(message, peer.shared_secret)

            # Enviar mensagem
            success = await self._send_message_to_peer(peer, message)

            if success:
                # Marcar chave como sincronizada
                self.kp_data["keys"][key_id]["synced"] = True
                logger.info(
                    f"Chave {key_id} sincronizada com peer {peer.system_id}")
            else:
                logger.warning(
                    f"Falha ao sincronizar chave {key_id} com peer {peer.system_id}")

        except Exception as e:
            logger.error(
                f"Erro ao enviar chave para peer {peer.system_id}: {e}")

    async def _request_keys_from_peer(self, peer: PeerKP):
        """Solicita chaves de um peer (placeholder para implementação futura)"""
        # Esta funcionalidade pode ser implementada para solicitar chaves específicas
        pass

    async def _send_heartbeats(self):
        """Envia heartbeats para todos os peers"""
        tasks = []
        for peer in self.peers.values():
            task = asyncio.create_task(self._send_heartbeat_to_peer(peer))
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Atualizar status dos peers baseado nos resultados
            for i, (peer, result) in enumerate(zip(self.peers.values(), results)):
                if isinstance(result, Exception):
                    peer.status = "offline"
                    peer.last_heartbeat = None
                else:
                    peer.status = "online"
                    peer.last_heartbeat = time.time()

    async def _send_heartbeat_to_peer(self, peer: PeerKP):
        """Envia heartbeat para um peer específico"""
        message = SyncMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.config.LOCAL_SYSTEM_ID,
            receiver_id=peer.system_id,
            message_type="heartbeat",
            timestamp=time.time(),
            payload={"status": "online"}
        )

        message.signature = self._sign_message(message, peer.shared_secret)
        return await self._send_message_to_peer(peer, message)

    async def _send_message_to_peer(self, peer: PeerKP, message: SyncMessage) -> bool:
        """Envia uma mensagem para um peer via HTTPS (stunnel)"""
        # Usar HTTPS via stunnel (sem certificados válidos)
        protocol = "https" if getattr(
            self.config, 'SYNC_USE_HTTPS', True) else "http"
        url = f"{protocol}://{peer.endpoint}:{peer.port}/sync"

        # Configurar SSL context para usar HTTPS sem verificação de certificados
        ssl_context = None
        connector_kwargs = {}

        if protocol == "https":
            ssl_context = ssl.create_default_context()
            # Não verificar certificados (desenvolvimento/auto-assinados)
            ssl_context.check_hostname = getattr(
                self.config, 'SSL_CHECK_HOSTNAME', False)
            ssl_context.verify_mode = ssl.CERT_NONE if not getattr(
                self.config, 'SSL_VERIFY_PEER', False) else ssl.CERT_REQUIRED

            # Configurar versões TLS conforme configuração
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2

            connector_kwargs = {
                'ssl': ssl_context,
                'limit': 10,
                'ttl_dns_cache': 300,
                'use_dns_cache': True,
            }

        # Retry logic
        for attempt in range(self.max_retry_attempts):
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(
                        total=self.sync_timeout,
                        connect=5,
                        sock_read=self.sync_timeout
                    ),
                    connector=aiohttp.TCPConnector(
                        **connector_kwargs) if connector_kwargs else None
                ) as session:

                    # Headers para identificação
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": f"SKIP-Sync/{self.config.LOCAL_SYSTEM_ID}",
                        "X-SKIP-Version": "1.0",
                        "X-SKIP-Sender": self.config.LOCAL_SYSTEM_ID
                    }

                    async with session.post(
                        url,
                        json=asdict(message),
                        headers=headers
                    ) as response:

                        if response.status == 200:
                            logger.debug(
                                f"Mensagem enviada com sucesso para {peer.system_id}")
                            return True
                        else:
                            response_text = await response.text()
                            logger.warning(
                                f"Peer {peer.system_id} retornou status {response.status}: {response_text}")
                            return False

            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout ao comunicar com peer {peer.system_id} (tentativa {attempt + 1})")
                if attempt == self.max_retry_attempts - 1:
                    return False
                await asyncio.sleep(1 + attempt)  # Simple backoff

            except aiohttp.ClientConnectorError as e:
                logger.warning(
                    f"Erro de conexão com peer {peer.system_id} (tentativa {attempt + 1}): {e}")
                if attempt == self.max_retry_attempts - 1:
                    return False
                await asyncio.sleep(1 + attempt)

            except ssl.SSLError as e:
                logger.warning(
                    f"Erro SSL com peer {peer.system_id} (tentativa {attempt + 1}): {e}")
                if attempt == self.max_retry_attempts - 1:
                    return False
                await asyncio.sleep(1 + attempt)

            except Exception as e:
                logger.error(
                    f"Erro ao comunicar com peer {peer.system_id} (tentativa {attempt + 1}): {e}")
                if attempt == self.max_retry_attempts - 1:
                    return False
                await asyncio.sleep(1 + attempt)

        return False

    def _encrypt_key(self, key_data: str) -> str:
        """Criptografa uma chave para transmissão"""
        key_bytes = key_data.encode() if isinstance(key_data, str) else key_data
        encrypted = self.cipher.encrypt(key_bytes)
        return base64.b64encode(encrypted).decode()

    def _decrypt_key(self, encrypted_key: str) -> str:
        """Descriptografa uma chave recebida"""
        encrypted_bytes = base64.b64decode(encrypted_key.encode())
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()

    def _sign_message(self, message: SyncMessage, shared_secret: str) -> str:
        """Assina uma mensagem usando HMAC"""
        # Criar string da mensagem para assinatura (excluindo a própria assinatura)
        message_copy = SyncMessage(**asdict(message))
        message_copy.signature = None
        message_str = json.dumps(asdict(message_copy), sort_keys=True)

        # Criar HMAC
        signature = hmac.new(
            shared_secret.encode(),
            message_str.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    def verify_message_signature(self, message: SyncMessage, shared_secret: str) -> bool:
        """Verifica a assinatura de uma mensagem"""
        if not message.signature:
            return False

        expected_signature = self._sign_message(message, shared_secret)
        return hmac.compare_digest(message.signature, expected_signature)

    async def handle_incoming_message(self, message_data: Dict, sender_ip: str) -> Dict:
        """Processa mensagem recebida de um peer"""
        try:
            message = SyncMessage(**message_data)

            # Encontrar peer pelo sender_id
            peer = self.peers.get(message.sender_id)
            if not peer:
                logger.warning(
                    f"Mensagem recebida de peer desconhecido: {message.sender_id}")
                return {"status": "error", "message": "Unknown peer"}

            # Verificar assinatura
            if not self.verify_message_signature(message, peer.shared_secret):
                logger.warning(
                    f"Assinatura inválida de peer {message.sender_id}")
                return {"status": "error", "message": "Invalid signature"}

            # Verificar timestamp (proteção contra replay attacks)
            current_time = time.time()
            if abs(current_time - message.timestamp) > 300:  # 5 minutos
                logger.warning(
                    f"Mensagem expirada de peer {message.sender_id}")
                return {"status": "error", "message": "Message expired"}

            # Processar mensagem baseado no tipo
            if message.message_type == "heartbeat":
                return await self._handle_heartbeat(message, peer)
            elif message.message_type == "key_sync":
                return await self._handle_key_sync(message, peer)
            elif message.message_type == "capability_exchange":
                return await self._handle_capability_exchange(message, peer)
            else:
                logger.warning(
                    f"Tipo de mensagem desconhecido: {message.message_type}")
                return {"status": "error", "message": "Unknown message type"}

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_heartbeat(self, message: SyncMessage, peer: PeerKP) -> Dict:
        """Processa mensagem de heartbeat"""
        peer.last_heartbeat = time.time()
        peer.status = "online"
        logger.debug(f"Heartbeat recebido de {peer.system_id}")
        return {"status": "ok", "message": "Heartbeat acknowledged"}

    async def _handle_key_sync(self, message: SyncMessage, peer: PeerKP) -> Dict:
        """Processa sincronização de chave"""
        try:
            payload = KeySyncPayload(**message.payload)

            # Descriptografar chave
            decrypted_key = self._decrypt_key(payload.key_data)

            # Armazenar chave localmente
            self.kp_data["keys"][payload.key_id] = {
                "key": decrypted_key,
                "remoteSystemID": payload.remote_system_id,
                "size": payload.key_size,
                "synced": True,
                "received_from": peer.system_id
            }

            # Armazenar timestamp
            self.kp_data["key_timestamps"][payload.key_id] = datetime.fromtimestamp(
                payload.created_at)

            logger.info(
                f"Chave {payload.key_id} recebida e armazenada de peer {peer.system_id}")
            return {"status": "ok", "message": "Key synchronized"}

        except Exception as e:
            logger.error(f"Erro ao processar sincronização de chave: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_capability_exchange(self, message: SyncMessage, peer: PeerKP) -> Dict:
        """Processa troca de capabilities"""
        peer.capabilities = message.payload
        logger.info(f"Capabilities atualizadas para peer {peer.system_id}")
        return {"status": "ok", "message": "Capabilities updated"}

    def get_sync_status(self) -> Dict:
        """Retorna status da sincronização"""
        status = {
            "sync_enabled": self.sync_enabled,
            "local_system_id": self.config.LOCAL_SYSTEM_ID,
            "peer_count": len(self.peers),
            "peers": {}
        }

        for system_id, peer in self.peers.items():
            status["peers"][system_id] = {
                "endpoint": f"{peer.endpoint}:{peer.port}",
                "status": peer.status,
                "last_heartbeat": peer.last_heartbeat,
                "capabilities": peer.capabilities
            }

        return status

    def sync_key_with_peers(self, key_id: str, key_data: Dict):
        """
        Marca uma chave para sincronização com peers relevantes
        Chamado quando uma nova chave é gerada
        """
        if not self.sync_enabled:
            return

        # Marcar chave como não sincronizada
        if key_id in self.kp_data["keys"]:
            self.kp_data["keys"][key_id]["synced"] = False
            logger.debug(f"Chave {key_id} marcada para sincronização")

    def cleanup_expired_sync_data(self):
        """Remove dados de sincronização expirados"""
        current_time = time.time()

        # Remover peers offline por muito tempo
        offline_threshold = current_time - (self.heartbeat_interval * 10)

        for system_id, peer in list(self.peers.items()):
            if (peer.last_heartbeat and
                peer.last_heartbeat < offline_threshold and
                    peer.status == "offline"):
                logger.info(
                    f"Removendo peer offline há muito tempo: {system_id}")
                # Não remover automaticamente - apenas log para administrador
