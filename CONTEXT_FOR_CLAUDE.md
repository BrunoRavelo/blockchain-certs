# CONTEXT_FOR_CLAUDE — Blockchain Certs
## Proyecto: Expedición y Verificación de Títulos Universitarios en Blockchain

---

## Identidad del proyecto

**Nombre del repo:** `blockchain-certs`
**Origen:** Clon de `blockchain-demo` (demo Bitcoin educativo), adaptado para caso de uso universitario real.
**Propósito académico:** Demo para evaluador universitario. Muestra cómo blockchain elimina el fraude de títulos, basado en MIT Blockcerts (2017).
**Lenguaje:** Python 3.11
**Stack:** Flask, WebSockets, Ed25519 (cryptography), SHA256, Base58Check, ReportLab (PDF)
**Entorno:** Solo local, múltiples nodos en distintos puertos de la misma máquina

---

## Cómo correr el proyecto

```bash
venv\Scripts\activate          # Windows
python launcher_titulos.py
```

**URLs del demo:**
- `:9001` — UNAM (institución emisora)
- `:9002` — Anáhuac (institución emisora)
- `:9003` — Verificador (observador/solo lectura)
- `:9004` — Bruno Rosas (egresado)
- `:9005` — Ana López (egresado)
- `:9006` — Carlos Méndez (egresado)
- `:9000` — Explorador público (dashboard global)
- `:8888` — Seed node (interno)

**Mapeo P2P → Dashboard:**
- P2P `:8001` → Dashboard `:9001` (UNAM)
- P2P `:8002` → Dashboard `:9002` (Anáhuac)
- P2P `:8003` → Dashboard `:9003` (Verificador)
- P2P `:8004` → Dashboard `:9004` (Bruno Rosas)
- P2P `:8005` → Dashboard `:9005` (Ana López)
- P2P `:8006` → Dashboard `:9006` (Carlos Méndez)

---

## Flujo del demo (para el evaluador)

```
1. Abrir :9001 (UNAM) o :9002 (Anáhuac)
2. Llenar formulario "Emitir Certificado Total de Estudios"
   - Seleccionar licenciatura del desplegable
   - Ingresar nombre, matrícula, fecha
   - Seleccionar egresado del dropdown (solo muestra graduates, no issuers)
3. Click "Registrar en blockchain" → TX va al mempool
4. Click "Sellar bloque" → bloque PoA confirmado, propagado a la red
5. Abrir :9004/:9005/:9006 → egresado ve su credencial con TX Hash
6. Egresado puede descargar PDF de certificado (botón en su dashboard)
7. Abrir :9003 o cualquier dashboard → "Verificar Certificado" con TX Hash
8. Verificación instantánea sin contactar a la institución
```

---

## Arquitectura de nodos y roles

### Roles definidos

| Rol | Quién | Puede emitir TXs | Puede sellar bloques | Ve credenciales propias |
|---|---|---|---|---|
| `issuer` | UNAM, Anáhuac | ✅ (títulos) | ✅ MANUAL | ❌ |
| `validator` | Verificador | ❌ | ❌ | ❌ |
| `graduate` | Bruno, Ana, Carlos | ❌ | ❌ | ✅ + descarga PDF |

**Puntos clave:**
- PoA es manual — el issuer hace clic en "Sellar bloque".
- El Verificador (antes COPAES) es solo lectura.
- `AUTHORIZED_VALIDATORS` solo incluye wallets de issuers.
- El rol se guarda en `node.node_role` (instancia), NO en `config.NODE_ROLE`.
- El dropdown de egresados en el formulario de emisión **filtra issuers** — solo muestra nodos graduates.

### Consenso PoA

```python
config.AUTHORIZED_VALIDATORS = [unam_wallet.address, anahuac_wallet.address]
config.VALIDATOR_PUBKEYS     = {address: pubkey_hex, ...}
config.AUTHORIZED_ISSUERS    = [unam_wallet.address, anahuac_wallet.address]
config.QUORUM_REQUIRED       = 1
```

---

## Estructura del proyecto

```
blockchain-certs/
│
├── launcher_titulos.py       ← punto de entrada; nodo observer: name='Verificador'
├── config.py                 ← sin PoW; AUTHORIZED_* poblados en runtime por launcher
├── requirements.txt          ← incluye reportlab
│
├── core/
│   ├── blockchain.py         ← usa `import config` (NO from-import) — crítico
│   ├── transaction.py        ← +campo data:dict
│   ├── wallet.py             ← +sign(bytes), +verify_from_pubkey_hex()
│   ├── titulo.py             ← lógica de negocio; rvoe opcional (''); tipo fijo
│   ├── pdf_cert.py           ← PDF informativo; paleta por institución
│   ├── block.py              ← sin target/nonce, con signatures dict
│   └── merkle.py
│
├── network/
│   ├── p2p_node.py           ← usa `import config` (NO from-import) — crítico
│   ├── seed_node.py
│   ├── seed_client.py
│   ├── protocol.py
│   └── peer_info.py
│
├── dashboard/
│   ├── app.py                ← +GET /api/title/<tx_hash>/pdf; filtro issuers en /api/addresses
│   ├── templates/dashboard.html  ← formulario simplificado (sin RVOE, sin tipo, carrera=select)
│   └── static/
│       ├── app.js            ← sin verifyDocument(); +botón descarga PDF en egresado
│       └── style.css         ← +.btn-download-pdf, +.cred-download-row
│
├── dashboard_global/
│   ├── app.py                ← sin verify_doc; summary usa issuers_active
│   ├── templates/global.html
│   └── static/
│       ├── global.js         ← usa is_issuer (antes is_validator/mining_mode)
│       └── global.css
│
└── utils/logger.py
```

**Archivos eliminados del proyecto original:** `core/pow.py`, `core/tx_orchestrator.py`

---

## Certificados — diseño actual

### Tipo único
Solo se emite **"Certificado Total de Estudios"** — hardcodeado en frontend y backend. No hay selector de tipo.

### Carreras (desplegables por institución)
```python
# dashboard/app.py — se pasa al template según `institucion` del nodo
CARRERAS_ANAHUAC = [
    'Administración y Estrategia de Negocios',
    'Derecho',
    'Psicología',
    'Ingeniería en Tecnologías de la Información y Ciberseguridad',
    'Nutrición y Ciencia de los Alimentos',
]

CARRERAS_UNAM = [
    'Derecho',
    'Medicina',
    'Ingeniería en Computación',
    'Psicología',
    'Administración',
]
```
La selección se hace por: `'Anáhuac' in institucion or 'Anahuac' in institucion`.

### Campos del formulario de emisión
- Nombre completo del egresado
- Matrícula
- Fecha de egreso
- Licenciatura (desplegable)
- Wallet del egresado (texto + dropdown de egresados conocidos)
- **SIN RVOE** — eliminado del formulario y de CAMPOS_REQUERIDOS
- **SIN selector de tipo** — siempre "Certificado Total de Estudios"
- **SIN upload de PDF** — eliminado completamente

### hash_doc
```python
# titulo.py — sin rvoe, sin PDF
cert_data = f"{nombre}|{matricula}|{carrera}|{institucion}|{fecha}|{tipo_certificado}"
hash_doc  = SHA256(cert_data.encode())
```

---

## PDF del certificado (`core/pdf_cert.py`)

- Generado bajo demanda en `GET /api/title/<tx_hash>/pdf`
- Solo accesible desde el dashboard del **egresado** (botón "⬇ Descargar certificado PDF")
- El PDF es **puramente informativo** — su hash no se almacena en blockchain
- La verificación de autenticidad se hace siempre por TX hash

### Paletas por institución
| Institución | Color primario | Color secundario |
|---|---|---|
| UNAM (default) | Azul `#003F87` | Dorado `#C8A951` |
| Anáhuac | Café `#5C2D0E` | Naranja `#E87722` |

Detección: `'Anáhuac' in institucion or 'Anahuac' in institucion` → paleta Anáhuac; cualquier otra → paleta UNAM.

---

## Cambios técnicos críticos

### BUG CRÍTICO — `from config import AUTHORIZED_*`
**NUNCA usar `from config import AUTHORIZED_VALIDATORS/ISSUERS/VALIDATOR_PUBKEYS`** en ningún módulo.
- Python copia los valores vacíos `[]` al importar. El launcher los puebla después → los módulos ven listas vacías.
- Fix aplicado en `blockchain.py` y `p2p_node.py`: usar `import config` + `config.AUTHORIZED_*`.
- Las constantes de red (MAX_OUTBOUND_CONNECTIONS, etc.) SÍ se pueden importar directamente porque no cambian en runtime.

### `core/blockchain.py`
- `import config` (no from-import) — crítico
- `produce_block_poa(validator_wallet)` — firma Ed25519, instantáneo
- `_is_valid_block_poa()` — verifica firmas + quórum + Merkle
- TXs de título saltan el check de balance en `add_transaction_to_mempool`
- Sin `get_target_hex()`, `get_estimated_block_time()`, `_last_adjustment`

### `network/p2p_node.py`
- `import config` (no from-import) — crítico
- `mine_once()` — produce bloque PoA manual
- Sin `set_mining_mode()`, `set_node_mode()`, `get_balance()`
- Sin `self.mining_mode`, `self.mining_rewards`, `self.mining_progress`
- Sin constantes `MINING_AUTO`, `MINING_MANUAL`, `VALIDATOR_AUTO`, `NODE_PAUSED`

### `dashboard/app.py`
- `/api/addresses` filtra `config.AUTHORIZED_VALIDATORS` — solo retorna graduates
- `/api/title/<tx_hash>/pdf` — genera y descarga el PDF
- Sin `api_title_verify_doc` (eliminado)
- Sin rutas stub (`/api/mine/auto`, `/api/mine/manual`, `/api/tx/*`)
- `/api/status` sin campos `mining_mode`, `mining_rewards`, `mining_progress`, `is_validator`

### `core/titulo.py`
- `rvoe` ya no está en `CAMPOS_REQUERIDOS`
- `build_titulo_tx()` tiene `rvoe=''` como default
- `tipo_certificado` default = `'Certificado Total de Estudios'`
- `hash_doc` calculado sin rvoe: `f"{nombre}|{matricula}|{carrera}|{institucion}|{fecha}|{tipo_certificado}"`

### `config.py`
- Sin `BLOCK_REWARD`, `NODE_ROLE`
- `P2P_PORT` y `DASHBOARD_PORT` siguen presentes (los usa `main.py`)

---

## Bugs corregidos (no repetir)

1. **`from config import AUTHORIZED_*`** en `blockchain.py` y `p2p_node.py` → valores vacíos congelados. Fix: `import config`.
2. **Rol en config global compartido** — `config.NODE_ROLE` sobreescrito. Fix: `node.node_role` en instancia.
3. **TX rechazada por fondos insuficientes** — TXs de título skip balance check.
4. **`dashboard_port` anunciado incorrectamente** — pasar como parámetro del constructor.
5. **Dos nodos del mismo rol imposible** — dict `wallets` usaba `role` como clave; fix: usa `name`.
6. **Institución tomada de config global** — fix: `getattr(self.node, 'institucion', '')`.
7. **`config.get('BLOCK_TIME', 10)`** — `config` es módulo. Fix: `config.BLOCK_TIME`.
8. **`config.QUORUM_REQUIRED` en Jinja2** — fix: pasar como variable explícita `quorum=`.
9. **Issuers aparecían en dropdown de egresados** — fix: filtrar `AUTHORIZED_VALIDATORS` en `/api/addresses`.
10. **`validators_active` siempre 0** — usaba `mining_mode == 'validator_auto'`; fix: `is_issuer` del nodo.

---

## Estado del desarrollo

### Completado y funcionando
- PoA completo (producción y validación de bloques)
- Emisión de Certificado Total de Estudios
- Carreras reales por institución (Anáhuac / UNAM)
- 2 instituciones emisoras con paletas de color propias en PDF
- 3 egresados con wallets independientes
- Nodo Verificador (observer) como solo-lectura
- Verificación de certificados por TX hash
- Descarga de PDF estilo diploma para egresados (informativo)
- Dashboard global como explorador público con estado real de issuers
- Propagación P2P entre nodos

### Pendiente / posibles mejoras
- Tests automatizados
- Quórum 2-de-2 (actualmente QUORUM_REQUIRED=1)

---

## Dependencias

```
flask, websockets, cryptography, pycryptodome, requests
reportlab    ← generación de PDF (pip install reportlab)
```

---

## Precedente real

**MIT Blockcerts (2017):** El MIT registra el hash del diploma en Bitcoin. El egresado comparte el hash y cualquier empleador verifica sin contactar al MIT.
**Malta (2019):** Todos los títulos universitarios registrados en blockchain pública.
**Open Badges v3 / IMS Global:** Estándar compatible con LinkedIn, Indeed, portales de empleo.
