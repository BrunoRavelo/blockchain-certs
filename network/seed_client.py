"""
Seed Client — Cliente HTTP para comunicarse con el Seed Node
Sprint 5.1: agrega announce_address() y get_addresses()

Separación de responsabilidades:
    register() / get_peers()          → lógica P2P
    announce_address() / get_addresses() → lógica de orquestador
"""

import requests
from typing import List, Optional
from utils.logger import setup_logger
from config import SEED_HOST, SEED_PORT


class SeedClient:
    """
    Cliente HTTP para el seed node.

    Uso en P2PNode:
        client = SeedClient(node_id, host, port)
        client.register()                          # al arrancar
        client.announce_address(wallet_address)    # al arrancar (separado)
        peers = client.get_peers()                 # obtener peers iniciales

    Uso en TxOrchestrator:
        client = SeedClient(...)
        addresses = client.get_addresses()         # obtener wallets para TXs
    """

    def __init__(
        self,
        node_id:   str,
        host:      str,
        port:      int,
        seed_host: str = SEED_HOST,
        seed_port: int = SEED_PORT,
    ):
        self.node_id  = node_id
        self.host     = host
        self.port     = port
        self.seed_url = f"http://{seed_host}:{seed_port}"
        self.logger   = setup_logger(node_id)

    # ──────────────────────────────────────────────
    # Lógica P2P
    # ──────────────────────────────────────────────

    def register(self) -> bool:
        """
        Registra este nodo en el seed (IP + puerto).
        Llamar al arrancar y periódicamente como keep-alive.
        NO incluye wallet_address — eso va en announce_address().

        Returns:
            True si el registro fue exitoso.
        """
        try:
            response = requests.post(
                f"{self.seed_url}/register",
                json={
                    'host':    self.host,
                    'port':    self.port,
                    'node_id': self.node_id,
                },
                timeout=5,
            )
            if response.status_code == 200:
                self.logger.info(f"[SEED] Registrado en {self.seed_url}")
                return True
            else:
                self.logger.warning(f"[SEED] Registro falló: {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            self.logger.warning(
                f"[SEED] No disponible {self.seed_url} — continuando sin seed"
            )
            return False
        except requests.exceptions.Timeout:
            self.logger.warning("[SEED] Timeout al registrar")
            return False
        except Exception as e:
            self.logger.error(f"[SEED] Error al registrar: {e}")
            return False

    def get_peers(self) -> List[dict]:
        """
        Obtiene la lista de nodos activos del seed.
        Excluye automáticamente este mismo nodo.

        Returns:
            Lista de dicts con 'host', 'port', 'node_id'.
        """
        try:
            response = requests.get(
                f"{self.seed_url}/peers",
                params={
                    'exclude_host': self.host,
                    'exclude_port': self.port,
                },
                timeout=5,
            )
            if response.status_code == 200:
                peers = response.json().get('peers', [])
                self.logger.info(f"[SEED] {len(peers)} peers obtenidos")
                return peers
            else:
                self.logger.warning(f"[SEED] get_peers falló: {response.status_code}")
                return []

        except requests.exceptions.ConnectionError:
            self.logger.warning("[SEED] Seed no disponible")
            return []
        except Exception as e:
            self.logger.error(f"[SEED] Error obteniendo peers: {e}")
            return []

    def is_seed_available(self) -> bool:
        """Verifica si el seed está activo."""
        try:
            response = requests.get(f"{self.seed_url}/health", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    # ──────────────────────────────────────────────
    # Lógica de orquestador (independiente del P2P)
    # ──────────────────────────────────────────────

    def announce_address(self, wallet_address: str, dashboard_port: int = 8000) -> bool:        
        """
        Anuncia la wallet address de este nodo al seed.

        Completamente separado de register() — el seed almacena
        estas addresses en un registro independiente.
        Si el orquestador se elimina en el futuro, esta llamada
        se quita sin afectar el registro P2P.

        Args:
            wallet_address: Address de la wallet del nodo (Base58Check).

        Returns:
            True si el anuncio fue exitoso.
        """
        try:
            response = requests.post(
                f"{self.seed_url}/announce_address",
                json={
                    'host':           self.host,
                    'port':           self.port,
                    'node_id':        self.node_id,
                    'wallet_address': wallet_address,
                    'dashboard_port': dashboard_port,
                },
                timeout=5,
            )
            if response.status_code == 200:
                self.logger.info(
                    f"[SEED] Address anunciada: {wallet_address[:16]}..."
                )
                return True
            else:
                self.logger.warning(
                    f"[SEED] announce_address falló: {response.status_code}"
                )
                return False

        except requests.exceptions.ConnectionError:
            self.logger.warning(
                "[SEED] Seed no disponible para announce_address"
            )
            return False
        except Exception as e:
            self.logger.error(f"[SEED] Error en announce_address: {e}")
            return False

    def get_addresses(
        self,
        exclude_host: Optional[str] = None,
        exclude_port: Optional[int] = None,
    ) -> List[dict]:
        """
        Obtiene todas las wallet addresses registradas en el seed.
        Usado por el TxOrchestrator para saber a quién enviar TXs.

        Args:
            exclude_host: IP a excluir de los resultados.
            exclude_port: Puerto a excluir de los resultados.

        Returns:
            Lista de dicts con 'host', 'port', 'node_id', 'wallet_address'.
            Lista vacía si el seed no está disponible.
        """
        try:
            params = {}
            if exclude_host:
                params['exclude_host'] = exclude_host
            if exclude_port:
                params['exclude_port'] = exclude_port

            response = requests.get(
                f"{self.seed_url}/addresses",
                params=params,
                timeout=5,
            )
            if response.status_code == 200:
                addresses = response.json().get('addresses', [])
                self.logger.debug(
                    f"[SEED] {len(addresses)} addresses obtenidas"
                )
                return addresses
            else:
                self.logger.warning(
                    f"[SEED] get_addresses falló: {response.status_code}"
                )
                return []

        except requests.exceptions.ConnectionError:
            self.logger.warning("[SEED] Seed no disponible para get_addresses")
            return []
        except Exception as e:
            self.logger.error(f"[SEED] Error en get_addresses: {e}")
            return []
