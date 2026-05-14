# Blockchain Certs — Títulos Universitarios en Blockchain

Demo académico de un sistema de expedición y verificación de títulos
universitarios usando tecnología blockchain con consenso Proof of Authority (PoA).

---

## Contexto del proyecto

Este sistema replica el modelo implementado por el MIT con su proyecto
**Blockcerts** (2017), adaptado como demo educativo. La idea central es que
un título universitario registrado en blockchain puede ser verificado por
cualquier empleador en segundos, sin intermediarios y sin posibilidad de fraude.

### Actores del sistema

| Actor | Rol | Dashboard |
|---|---|---|
| Secretaría Académica | Emite títulos firmados criptográficamente | :9001 |
| COPAES (Acreditador) | Co-valida bloques como organismo independiente | :9002 |
| Egresado | Recibe y comparte sus credenciales | :9003 |
| Empleador | Verifica autenticidad sin contactar a la institución | cualquier nodo |

---

## Requisitos

- Python 3.11 o superior
- Las dependencias del archivo `requirements.txt`

```bash
# Verificar versión de Python
python --version

# Instalar dependencias (con el entorno virtual activado)
pip install -r requirements.txt
```

---

## Instalación

```bash
# 1. Clonar o descomprimir el proyecto
cd blockchain-certs

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Arranque del demo

```bash
# Con el entorno virtual activado, desde la raíz del proyecto:
python launcher_titulos.py
```

El launcher levanta automáticamente:
- Seed node en `:8888`
- Secretaría Académica en P2P `:8001` · Dashboard `:9001`
- COPAES en P2P `:8002` · Dashboard `:9002`
- Egresado en P2P `:8003` · Dashboard `:9003`

Esperar hasta ver `Conectando nodos..... listo.` en consola (aprox. 8 segundos).

Para detener: `Ctrl+C`

---

## Flujo del demo — paso a paso

### Paso 1 — Copiar la address del egresado

Al arrancar, la consola imprime las addresses de cada nodo:

```
  [Egresado: Bruno Rosas]
    Address:   1Abc123...
    Dashboard: http://localhost:9003
```

Copiar esa address — se usará en el formulario de emisión.

---

### Paso 2 — Emitir un título (Secretaría)

Abrir **http://localhost:9001**

En la sección **"Emitir Título Universitario"**:

| Campo | Valor de ejemplo |
|---|---|
| Nombre completo | Bruno Rosas Hernández |
| Matrícula | 2021045 |
| Fecha de titulación | 2025-03-15 |
| Carrera | Ingeniería en Sistemas Computacionales |
| Clave RVOE | UAAN-2024-001 |
| Wallet del egresado | (pegar la address del Paso 1) |
| Archivo PDF | (cualquier PDF, opcional para el demo) |

Hacer clic en **"Emitir y registrar en blockchain"**.

Aparecerá el **TX Hash** — copiar este valor, se usará en el Paso 4.

---

### Paso 3 — Confirmar el bloque

Esperar aproximadamente **10 segundos**. El nodo validador (Secretaría o COPAES)
produce un bloque PoA automáticamente cada `BLOCK_TIME` segundos.

La consola mostrará:
```
[POA] Bloque #1 producido. TXs: 1, Firmas: 1
```

En el dashboard de la Secretaría (:9001), la sección **"Últimos bloques"**
mostrará el nuevo bloque con el indicador `🔑 1 firma(s)`.

---

### Paso 4 — Ver la credencial (Egresado)

Abrir **http://localhost:9003**

En la sección **"Mis Credenciales"** aparecerá el título confirmado con:
- Nombre de la carrera
- Institución y RVOE
- Número de bloque donde fue confirmado
- TX Hash para compartir con empleadores

---

### Paso 5 — Verificar el título (Empleador)

Abrir cualquier dashboard, por ejemplo **http://localhost:9001**

En la sección **"Verificar Título"**:

1. Pegar el TX Hash del Paso 2
2. Hacer clic en **"Buscar"**
3. Ver los datos del título verificados en cadena

Si se subió un PDF en el Paso 2:
4. Hacer clic en **"Verificar documento PDF"**
5. Subir el mismo PDF → resultado: **"✅ DOCUMENTO AUTÉNTICO"**
6. Subir un PDF diferente → resultado: **"❌ DOCUMENTO NO COINCIDE"**

Este último paso es el más impactante del demo — demuestra que cualquier
alteración del documento es detectada inmediatamente.

---

### Paso 6 — Verificar el bloque (opcional, avanzado)

En la sección **"Últimos bloques"**, hacer clic en **"🔎 Verificar"**
sobre cualquier bloque.

El modal mostrará:
- ✅ Firmas PoA — N firmas de validadores autorizados
- ✅ Merkle Root — integridad del árbol de transacciones
- ✅ Enlace prev_hash — conectividad de la cadena
- ✅ Firmas de TXs — autenticidad de cada transacción

---

## Conceptos blockchain demostrados

| Concepto | Dónde se ve en el demo |
|---|---|
| **Inmutabilidad** | El título no puede modificarse sin invalidar el hash de la TX |
| **Firma digital (Ed25519)** | La secretaría firma cada título con su llave privada |
| **Proof of Authority** | Solo validadores autorizados producen bloques |
| **Árbol de Merkle** | El bloque incluye la raíz Merkle de todas sus TXs |
| **Verificación sin intermediarios** | El empleador verifica directamente en la cadena |
| **Hash como prueba de integridad** | SHA256 del PDF detecta cualquier alteración |
| **Red P2P** | Los bloques se propagan automáticamente entre los 3 nodos |

---

## Diferencias con Bitcoin (educativo)

| Aspecto | Bitcoin | Este demo |
|---|---|---|
| Consenso | Proof of Work (puzzle SHA256) | Proof of Authority (firma Ed25519) |
| Quién valida | Cualquier minero con suficiente poder | Solo validadores autorizados |
| Incentivo del validador | Recompensa económica (BTC) | Institucional (la universidad opera su nodo) |
| Uso de los tokens | Moneda de intercambio | Representan un título académico |
| Recompensa por bloque | 3.125 BTC | 0 (sin recompensa económica) |
| Firma digital | ECDSA secp256k1 | Ed25519 (mismo concepto, algoritmo moderno) |
| Precedente real | Bitcoin (2009) | MIT Blockcerts (2017) |

---

## Arquitectura técnica

```
launcher_titulos.py
│
├── Seed node (:8888)
│   └── Registro y descubrimiento de peers (HTTP)
│
├── Nodo Secretaría (:8001 P2P · :9001 Dashboard)
│   ├── Rol: issuer + validator
│   ├── Puede emitir TXs de título
│   ├── Produce bloques PoA automáticamente
│   └── Dashboard con formulario de emisión
│
├── Nodo COPAES (:8002 P2P · :9002 Dashboard)
│   ├── Rol: validator
│   ├── Valida y propaga bloques
│   └── Dashboard de estado del validador
│
└── Nodo Egresado (:8003 P2P · :9003 Dashboard)
    ├── Rol: graduate
    ├── Recibe TXs de título en su wallet
    └── Dashboard con "Mis Credenciales"
```

### Flujo de una TX de título

```
Secretaría
  → build_titulo_tx()         crea TX con metadatos + SHA256(PDF)
  → tx.sign(wallet)           firma Ed25519 de la secretaría
  → mempool                   TX entra al pool de pendientes
  → validator_loop()          cada BLOCK_TIME segundos
  → produce_block_poa()       construye bloque + firma el hash
  → broadcast_block()         propaga a todos los nodos P2P
  → cadena confirmada         TX ya no puede modificarse

Empleador
  → /api/title/lookup/txhash  busca la TX en la cadena
  → /api/title/verify_doc     compara SHA256(PDF_recibido) vs hash_doc en TX
  → resultado en segundos     sin llamar a nadie
```

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| Firma digital | Ed25519 (library: cryptography) |
| Red P2P | WebSockets (library: websockets) |
| Dashboard | Flask |
| Hash | SHA256 doble (igual que Bitcoin) |
| Árbol de Merkle | Implementación propia |
| Direcciones | Base58Check (compatible con Bitcoin) |

---

## Referencia: MIT Blockcerts

Este demo está inspirado en el proyecto real del MIT:

> "From the beginning, one of our primary motivations has been to empower
> students to be the curators of their own credentials."
> — Mary Callahan, MIT Registrar, 2017

El MIT registra el hash del diploma en la blockchain de Bitcoin.
Cualquier empleador puede verificar la autenticidad del diploma
sin contactar al MIT, usando solo el archivo digital y la cadena pública.

Fuente: https://news.mit.edu/2017/mit-debuts-secure-digital-diploma-blockchain-technology-1017
