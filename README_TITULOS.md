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
| Universidad Anáhuac México | Emite títulos y sella bloques (PoA manual) | :9002 |
| Verificador | Observa la red, solo lectura | :9003 |
| Bruno Rosas | Egresado — ve y descarga su credencial | :9004 |
| Ana López | Egresado — ve y descarga su credencial | :9005 |
| Carlos Méndez | Egresado — ve y descarga su credencial | :9006 |
| Explorador público | Dashboard global de toda la red | :9000 |

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

| Puerto P2P | Dashboard | Nodo | Rol |
|---|---|---|---|
| :8888 | — | Seed node | Descubrimiento de peers |
| :8002 | :9002 | Universidad Anáhuac México | issuer |
| :8003 | :9003 | Verificador | observer |
| :8004 | :9004 | Bruno Rosas | graduate |
| :8005 | :9005 | Ana López | graduate |
| :8006 | :9006 | Carlos Méndez | graduate |
| — | :9000 | Explorador público | global explorer |

Esperar hasta ver `Conectando nodos..... listo.` en consola (aprox. 10 segundos).

Para detener: `Ctrl+C`

---

## Flujo del demo — paso a paso

### Paso 1 — Abrir el dashboard de la institución

Abrir **http://localhost:9002** (Universidad Anáhuac México).

Al arrancar, la consola imprime las wallets de cada nodo. Las wallets de los
egresados también aparecen en el dropdown del formulario de emisión.

---

### Paso 2 — Emitir un Certificado Total de Estudios

En la sección **"Emitir Certificado Total de Estudios"**:

| Campo | Descripción |
|---|---|
| Nombre completo | Nombre del egresado |
| Matrícula | Número de matrícula |
| Fecha de egreso | Fecha de titulación |
| Licenciatura | Seleccionar del desplegable |
| Wallet del egresado | Escribir o seleccionar del dropdown |

Hacer clic en **"Registrar en blockchain"**.

Aparecerá el **TX Hash** — confirmar que la TX entró al mempool.

---

### Paso 3 — Sellar el bloque (PoA manual)

En la misma pantalla de Anáhuac (:9002), hacer clic en **"🔒 Sellar bloque"**.

Aparecerá la **Tarjeta Sello Digital** con:
- Número de bloque confirmado
- Nombre de la institución que firmó
- Dirección (wallet) del emisor
- **Firma digital Ed25519** (64 bytes en hexadecimal)
- Indicador "✅ Firma criptográficamente verificada"

El bloque se propaga automáticamente a todos los nodos de la red.

---

### Paso 4 — Ver la credencial (Egresado)

Abrir el dashboard del egresado correspondiente, por ejemplo
**http://localhost:9004** (Bruno Rosas).

En la sección **"Mis Credenciales"** aparecerá el título confirmado con:
- Tipo de certificado y nombre de la carrera
- Institución y nombre del egresado
- Número de bloque y validadores
- TX Hash para compartir
- Botón **"⬇ Descargar certificado PDF"** — genera un diploma informativo

---

### Paso 5 — Verificar el título (desde cualquier nodo)

En cualquier dashboard, ir a la sección **"Verificar Certificado"**:

1. Pegar el TX Hash del Paso 2
2. Hacer clic en **"Verificar"**
3. Ver los datos del título verificados directamente en la cadena

La verificación es instantánea y no requiere contactar a la institución.

---

### Paso 6 — Explorador público

Abrir **http://localhost:9000** para ver el estado global de la red:
- Todos los bloques de la cadena con sus firmas
- Estado de los nodos
- Verificación de cualquier TX hash

---

## Conceptos blockchain demostrados

| Concepto | Dónde se ve en el demo |
|---|---|
| **Inmutabilidad** | El título no puede modificarse sin invalidar el hash de la TX |
| **Firma digital Ed25519** | La institución firma cada título con su llave privada |
| **Proof of Authority (PoA)** | Solo validadores autorizados producen bloques |
| **Firma del bloque visible** | La tarjeta "Sello Digital" muestra la firma hex en pantalla |
| **Árbol de Merkle** | El bloque incluye la raíz Merkle de todas sus TXs |
| **Verificación sin intermediarios** | El verificador consulta directamente la cadena |
| **Red P2P** | Los bloques se propagan automáticamente entre los nodos |
| **PDF informativo** | El egresado descarga un diploma; la validez reside en el TX hash |

---

## Diferencias con Bitcoin (educativo)

| Aspecto | Bitcoin | Este demo |
|---|---|---|
| Consenso | Proof of Work (puzzle SHA256) | Proof of Authority (firma Ed25519) |
| Quién valida | Cualquier minero con suficiente poder | Solo validadores autorizados |
| Cuándo se produce el bloque | Cuando se resuelve el puzzle | Cuando el issuer hace clic en "Sellar" |
| Incentivo del validador | Recompensa económica (BTC) | Institucional (la universidad opera su nodo) |
| Uso de los tokens | Moneda de intercambio | Representan un título académico |
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
├── Nodo Anáhuac (:8002 P2P · :9002 Dashboard)
│   ├── Rol: issuer
│   ├── Emite TXs de Certificado Total de Estudios
│   ├── Produce bloques PoA de forma MANUAL
│   └── Dashboard con formulario de emisión + Sello Digital
│
├── Nodo Verificador (:8003 P2P · :9003 Dashboard)
│   ├── Rol: validator (solo lectura)
│   └── Propaga y verifica bloques entrantes
│
├── Nodo Bruno Rosas (:8004 P2P · :9004 Dashboard)
├── Nodo Ana López   (:8005 P2P · :9005 Dashboard)
├── Nodo Carlos Méndez (:8006 P2P · :9006 Dashboard)
│   ├── Rol: graduate
│   ├── Reciben TXs de título en su wallet
│   └── Dashboard con "Mis Credenciales" + descarga de PDF
│
└── Explorador público (:9000)
    └── Vista global de la red, bloques y verificación
```

### Flujo de una TX de título

```
Institución (Anáhuac)
  → build_titulo_tx()       crea TX con metadatos + SHA256(nombre|carrera|…)
  → tx.sign(wallet)         firma Ed25519 de la institución
  → mempool                 TX entra al pool de pendientes

Institución hace clic en "Sellar bloque"
  → produce_block_poa()     construye bloque + firma el hash del bloque
  → Tarjeta Sello Digital   muestra firma Ed25519 al evaluador
  → broadcast_block()       propaga a todos los nodos P2P
  → cadena confirmada       TX ya no puede modificarse

Verificador / Empleador
  → /api/title/lookup/txhash   busca la TX en la cadena
  → resultado en segundos      sin llamar a nadie
```

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| Firma digital | Ed25519 (library: cryptography) |
| Red P2P | WebSockets (library: websockets) |
| Dashboard | Flask + Jinja2 |
| Hash | SHA256 doble (igual que Bitcoin) |
| Árbol de Merkle | Implementación propia |
| Direcciones | Base58Check (compatible con Bitcoin) |
| PDF | ReportLab |

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

---

## Estado del proyecto

### Funcionalidades completadas

- Consenso PoA completo (producción y validación de bloques)
- Emisión de Certificado Total de Estudios con firma Ed25519
- Tarjeta "Sello Digital" con firma hexadecimal visible al sellar bloques
- Carreras reales de la Universidad Anáhuac México
- 3 egresados con wallets independientes
- Nodo Verificador como observador de solo lectura
- Verificación de certificados por TX hash
- Descarga de PDF estilo diploma (informativo)
- Dashboard global como explorador público
- Propagación P2P entre todos los nodos

### Posibles mejoras futuras

- Quórum 2-de-2 (actualmente QUORUM_REQUIRED = 1)
- Tests automatizados
