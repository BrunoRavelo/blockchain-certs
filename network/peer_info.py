"""
Información de peers para gossip protocol
"""

from datetime import datetime
from typing import Optional


class PeerInfo:
    """
    Información sobre un peer conocido (conectado o no)
    Similar a CAddress en Bitcoin
    """
    
    def __init__(self, host: str, port: int, node_id: Optional[str] = None):
        self.host = host
        self.port = port
        self.node_id = node_id
        
        # Timestamps
        self.first_seen = datetime.now().timestamp()
        self.last_seen = datetime.now().timestamp()
        self.last_attempt = None
        
        # Estado
        self.is_connected = False
        self.connection_failures = 0
        
    def to_dict(self) -> dict:
        """Serializa para enviar por red"""
        return {
            'host': self.host,
            'port': self.port,
            'node_id': self.node_id,
            'last_seen': self.last_seen
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'PeerInfo':
        """Deserializa desde mensaje de red"""
        peer = PeerInfo(data['host'], data['port'], data.get('node_id'))
        peer.last_seen = data.get('last_seen', datetime.now().timestamp())
        return peer
    
    def mark_seen(self):
        """Actualiza timestamp de última vez visto"""
        self.last_seen = datetime.now().timestamp()
    
    def mark_attempt(self):
        """Marca intento de conexión"""
        self.last_attempt = datetime.now().timestamp()
    
    def mark_failure(self):
        """Marca fallo de conexión"""
        self.connection_failures += 1
        self.is_connected = False
    
    def mark_connected(self):
        """Marca como conectado exitosamente"""
        self.is_connected = True
        self.connection_failures = 0
        self.mark_seen()
    
    def mark_disconnected(self):
        """Marca como desconectado"""
        self.is_connected = False
    
    def get_address(self) -> str:
        """Retorna dirección en formato host:port"""
        return f"{self.host}:{self.port}"
    
    def __repr__(self):
        status = "CONNECTED" if self.is_connected else "KNOWN"
        return f"PeerInfo({self.get_address()}, {status}, failures={self.connection_failures})"