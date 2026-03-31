"""
Merkle Tree (Árbol de Merkle)
Estructura de datos para resumir transacciones en un solo hash

En Bitcoin:
- Cada bloque tiene un Merkle root en su header
- Permite verificar si una TX está en un bloque sin descargar todas las TXs
- Garantiza integridad: cambiar 1 TX → cambia el Merkle root
"""

import hashlib
import json
from typing import List, Optional


class MerkleTree:
    """
    Árbol binario de hashes
    
    Ejemplo con 4 transacciones:
    
           Root (H1234)
                  
        H12           H34
                      
      H1    H2      H3    H4
                     
     TX1   TX2     TX3   TX4
    
    Propiedades:
    - Si número impar de hojas, duplica la última
    - Cada nivel combina pares: H12 = SHA256(H1 + H2)
    - Root es el hash único que representa todas las TXs
    """
    
    def __init__(self, transactions: List):
        """
        Construye árbol Merkle desde lista de transacciones
        
        Args:
            transactions: Lista de objetos Transaction
        """
        self.transactions = transactions
        self.tree = self.build_tree()
    
    def hash_transaction(self, tx) -> str:
        """
        Calcula hash de una transacción
        
        Args:
            tx: Objeto Transaction
        
        Returns:
            Hash SHA256 en hexadecimal
        """
        # Serializar transacción (sin signature para consistencia)
        tx_dict = tx.to_dict(include_signature=False)
        tx_string = json.dumps(tx_dict, sort_keys=True)
        
        # Double SHA256 (como Bitcoin)
        hash1 = hashlib.sha256(tx_string.encode()).digest()
        hash2 = hashlib.sha256(hash1).hexdigest()
        
        return hash2
    
    def build_tree(self) -> List[List[str]]:
        """
        Construye árbol completo (todos los niveles)
        
        Returns:
            Lista de niveles, cada nivel es lista de hashes
            tree[0] = nivel hojas (hashes de TXs)
            tree[-1] = nivel raíz (Merkle root)
        """
        # Caso especial: sin transacciones
        if not self.transactions:
            # Hash vacío (32 bytes de ceros)
            return [['0' * 64]]
        
        # Nivel 0: Hashes de las transacciones (hojas)
        current_level = [self.hash_transaction(tx) for tx in self.transactions]
        tree = [current_level.copy()]
        
        # Construir niveles superiores hasta llegar a la raíz
        while len(current_level) > 1:
            # Si número impar, duplicar el último (estándar Bitcoin)
            if len(current_level) % 2 != 0:
                current_level.append(current_level[-1])
            
            # Combinar pares de hashes
            next_level = []
            for i in range(0, len(current_level), 2):
                # Concatenar dos hashes hijos
                combined = current_level[i] + current_level[i + 1]
                
                # Hash del resultado (double SHA256)
                hash1 = hashlib.sha256(combined.encode()).digest()
                parent_hash = hashlib.sha256(hash1).hexdigest()
                
                next_level.append(parent_hash)
            
            tree.append(next_level)
            current_level = next_level
        
        return tree
    
    def get_root(self) -> str:
        """
        Retorna Merkle root (hash raíz del árbol)
        
        Este es el hash que va en el block header
        
        Returns:
            Hash SHA256 en hexadecimal (64 caracteres)
        """
        return self.tree[-1][0]
    
    def get_proof(self, tx_index: int) -> Optional[List[dict]]:
        """
        Genera prueba Merkle para verificar que una TX está en el árbol
        
        Prueba Merkle = lista de hashes hermanos necesarios para
        reconstruir el camino desde la hoja hasta la raíz
        
        Args:
            tx_index: Índice de la transacción (0-based)
        
        Returns:
            Lista de dicts con 'hash' y 'position' ('left' o 'right')
            None si el índice es inválido
        
        Nota: Implementación opcional para demo básico
        """
        if tx_index < 0 or tx_index >= len(self.transactions):
            return None
        
        proof = []
        index = tx_index
        
        # Recorrer niveles desde hojas hasta raíz (excluyendo raíz)
        for level_index in range(len(self.tree) - 1):
            level = self.tree[level_index]
            
            # Determinar índice del hermano (sibling)
            if index % 2 == 0:
                # Nodo par → hermano está a la derecha
                sibling_index = index + 1
                position = 'right'
            else:
                # Nodo impar → hermano está a la izquierda
                sibling_index = index - 1
                position = 'left'
            
            # Agregar hash del hermano (si existe)
            if sibling_index < len(level):
                proof.append({
                    'hash': level[sibling_index],
                    'position': position
                })
            
            # Subir al siguiente nivel
            index = index // 2
        
        return proof
    
    @staticmethod
    def verify_proof(tx_hash: str, merkle_root: str, proof: List[dict]) -> bool:
        """
        Verifica que una transacción está en el árbol usando prueba Merkle
        
        Args:
            tx_hash: Hash de la transacción a verificar
            merkle_root: Merkle root del bloque
            proof: Prueba Merkle (de get_proof)
        
        Returns:
            True si la transacción está en el árbol
        
        Nota: Implementación opcional para demo básico
        """
        current_hash = tx_hash
        
        # Reconstruir camino hacia la raíz
        for step in proof:
            sibling_hash = step['hash']
            position = step['position']
            
            # Combinar según posición
            if position == 'left':
                combined = sibling_hash + current_hash
            else:  # 'right'
                combined = current_hash + sibling_hash
            
            # Hash del resultado (double SHA256)
            hash1 = hashlib.sha256(combined.encode()).digest()
            current_hash = hashlib.sha256(hash1).hexdigest()
        
        # Verificar que llegamos a la raíz
        return current_hash == merkle_root
    
    def __repr__(self):
        return f"MerkleTree(transactions={len(self.transactions)}, root={self.get_root()[:16]}...)"