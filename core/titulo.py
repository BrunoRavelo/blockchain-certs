"""
Lógica de negocio para títulos universitarios en blockchain.

Este módulo es el único lugar donde vive la lógica específica
de los diplomas — el resto del sistema (blockchain, red, wallet)
no sabe nada sobre títulos.

Funciones principales:
- build_titulo_tx()    → crea una TX de título lista para firmar
- validate_titulo_tx() → valida reglas de negocio antes del mempool
- get_titulos_by_wallet() → consulta títulos de un egresado
- verify_document()    → verifica autenticidad de un PDF
"""

import hashlib
from core.transaction import Transaction
import config


# Campos obligatorios en data de una TX de título
CAMPOS_REQUERIDOS = [
    "tipo",
    "nombre",
    "matricula",
    "carrera",
    "institucion",
    "rvoe",
    "fecha",
    "hash_doc",
]


def build_titulo_tx(
    secretaria_wallet,
    egresado_address: str,
    nombre:       str,
    matricula:    str,
    carrera:      str,
    fecha:        str,
    rvoe:         str,
    pdf_bytes:    bytes,
    institucion:  str = None,
) -> Transaction:
    """
    Construye una TX de título universitario correctamente formada.

    El hash SHA256 del PDF se calcula aquí — el archivo nunca va
    a la cadena, solo su huella digital. Esto es suficiente para
    que cualquier empleador pueda verificar la autenticidad del
    documento que el egresado le proporcionó.

    Args:
        secretaria_wallet: Wallet del emisor autorizado (secretaría)
        egresado_address:  Address de la wallet del egresado
        nombre:            Nombre completo del egresado
        matricula:         Matrícula del egresado
        carrera:           Nombre de la carrera / programa
        fecha:             Fecha de titulación (string, ej: "2025-03-15")
        rvoe:              Clave RVOE de la institución
        pdf_bytes:         Contenido del PDF del título (para calcular hash)
        institucion:       Nombre de la institución (default: config.NOMBRE_INSTITUCION)

    Returns:
        Transaction firmada lista para agregar al mempool.
    """
    if institucion is None:
        institucion = config.NOMBRE_INSTITUCION

    hash_doc = hashlib.sha256(pdf_bytes).hexdigest()

    tx = Transaction(
        from_address = secretaria_wallet.address,
        to_address   = egresado_address,
        amount       = 1,
        data = {
            "tipo":        "titulo_universitario",
            "nombre":      nombre,
            "matricula":   matricula,
            "carrera":     carrera,
            "institucion": institucion,
            "rvoe":        rvoe,
            "fecha":       fecha,
            "hash_doc":    hash_doc,
        }
    )
    tx.sign(secretaria_wallet)
    return tx


def validate_titulo_tx(tx: Transaction, blockchain) -> tuple:
    """
    Valida reglas de negocio de una TX de título.

    Esta validación se llama ANTES de agregar la TX al mempool,
    complementando la validación criptográfica de Transaction.is_valid().

    Returns:
        (True, "")          si la TX es válida
        (False, "mensaje")  si hay un error de negocio
    """
    # Si no es un título, no aplican estas reglas
    if tx.data.get("tipo") != "titulo_universitario":
        return True, ""

    # Campos obligatorios presentes y no vacíos
    for campo in CAMPOS_REQUERIDOS:
        if not tx.data.get(campo):
            return False, f"Campo requerido faltante o vacío: {campo}"

    # Solo issuers autorizados pueden emitir títulos
    if tx.from_address not in config.AUTHORIZED_ISSUERS:
        return False, (
            f"Wallet no autorizada para emitir títulos. "
            f"Address: {tx.from_address[:16]}..."
        )

    # hash_doc debe ser SHA256 hex válido (64 caracteres hexadecimales)
    hash_doc = tx.data.get("hash_doc", "")
    if len(hash_doc) != 64 or not all(c in "0123456789abcdef" for c in hash_doc):
        return False, "hash_doc inválido — debe ser SHA256 hex de 64 caracteres"

    # Prevenir duplicados: misma matrícula + mismo RVOE ya confirmados en cadena
    matricula = tx.data["matricula"]
    rvoe      = tx.data["rvoe"]
    for block in blockchain.chain:
        for t in block.transactions:
            if (t.data.get("matricula") == matricula and
                    t.data.get("rvoe") == rvoe and
                    t.data.get("tipo") == "titulo_universitario"):
                return False, (
                    f"Ya existe un título confirmado para matrícula "
                    f"'{matricula}' con RVOE '{rvoe}'"
                )

    return True, ""


def get_titulos_by_wallet(blockchain, wallet_address: str) -> list:
    """
    Busca todos los títulos confirmados emitidos a una wallet.

    Solo devuelve títulos que ya están en bloques confirmados —
    los pendientes en el mempool no se incluyen aquí.

    Args:
        blockchain:     Instancia de Blockchain
        wallet_address: Address del egresado

    Returns:
        Lista de dicts con datos del título + metadatos del bloque.
    """
    titulos = []
    for block in blockchain.chain:
        for tx in block.transactions:
            if (tx.data.get("tipo") == "titulo_universitario" and
                    tx.to_address == wallet_address):
                titulos.append({
                    "tx_hash":            tx.hash(),
                    "bloque":             blockchain.chain.index(block),
                    "timestamp_bloque":   block.header.timestamp,
                    "firmas_validadores": list(block.header.signatures.keys()),
                    **tx.data,
                })
    return titulos


def get_all_titulos(blockchain) -> list:
    """
    Devuelve todos los títulos confirmados en la cadena.
    Útil para el dashboard del issuer / vista de administración.
    """
    titulos = []
    for block in blockchain.chain:
        for tx in block.transactions:
            if tx.data.get("tipo") == "titulo_universitario":
                titulos.append({
                    "tx_hash":            tx.hash(),
                    "bloque":             blockchain.chain.index(block),
                    "timestamp_bloque":   block.header.timestamp,
                    "egresado_address":   tx.to_address,
                    "firmas_validadores": list(block.header.signatures.keys()),
                    **tx.data,
                })
    return titulos


def get_titulos_pendientes(blockchain) -> list:
    """
    Devuelve títulos en el mempool (aún no confirmados en un bloque).
    """
    return [
        {
            "tx_hash":  tx.hash(),
            "estado":   "pendiente",
            **tx.data,
        }
        for tx in blockchain.mempool
        if tx.data.get("tipo") == "titulo_universitario"
    ]


def verify_document(blockchain, tx_hash: str, pdf_bytes: bytes) -> dict:
    """
    Verifica que un PDF corresponde al hash registrado en una TX de título.

    Este es el flujo del empleador:
    1. El egresado le da su TX hash y su PDF
    2. El empleador busca el TX hash en la cadena (lookup_title)
    3. El empleador sube el PDF aquí para confirmar autenticidad
    4. El sistema calcula SHA256(pdf) y lo compara con hash_doc en la TX

    Si coincide → el documento es auténtico e inalterado.
    Si no coincide → el documento fue modificado o es una falsificación.

    Args:
        blockchain: Instancia de Blockchain
        tx_hash:    Hash de la TX de título a verificar
        pdf_bytes:  Bytes del PDF proporcionado por el egresado

    Returns:
        Dict con resultado de la verificación y metadatos del título.
    """
    # Buscar la TX en la cadena
    for block in blockchain.chain:
        for tx in block.transactions:
            if tx.hash() == tx_hash:
                if tx.data.get("tipo") != "titulo_universitario":
                    return {
                        "valido": False,
                        "error":  "La TX no corresponde a un título universitario",
                    }

                hash_calculado  = hashlib.sha256(pdf_bytes).hexdigest()
                hash_registrado = tx.data.get("hash_doc", "")
                coincide        = hash_calculado == hash_registrado

                return {
                    "valido":             coincide,
                    "tx_hash":            tx_hash,
                    "hash_calculado":     hash_calculado,
                    "hash_registrado":    hash_registrado,
                    "datos_titulo":       tx.data,
                    "bloque":             blockchain.chain.index(block),
                    "timestamp_bloque":   block.header.timestamp,
                    "firmas_validadores": list(block.header.signatures.keys()),
                }

    return {
        "valido": False,
        "error":  f"TX no encontrada en la cadena: {tx_hash[:16]}...",
    }
