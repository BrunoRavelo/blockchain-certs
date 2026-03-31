// ──────────────────────────────────────────────────────────
// app.js — Dashboard Blockchain Certs
// Sprint 2B: PoA + títulos universitarios
// ──────────────────────────────────────────────────────────

let lastHeight  = 0;
let currentTxHash = null;  // TX hash activo en el verificador

// ──────────────────────────────────────────────────────────
// Loop principal (cada 3s)
// ──────────────────────────────────────────────────────────

async function updateData() {
    try {
        const [status, chain, peers, mempool] = await Promise.all([
            fetch('/api/status').then(r => r.json()),
            fetch('/api/chain').then(r => r.json()),
            fetch('/api/peers').then(r => r.json()),
            fetch('/api/mempool').then(r => r.json()),
        ]);

        updateWallet(status);
        updateChain(chain);
        updatePeers(peers);
        updateMempool(mempool);
        updateHeader(status, chain);
        updateValidatorStatus(status);
        updateAddressDropdown();

        // Secciones específicas por rol
        if (NODE_ROLE === 'graduate') {
            loadMyCredentials(status.address);
        }
        if (NODE_ROLE === 'issuer') {
            loadPendingTitles();
            loadAllTitles();
            updateEgresadoDropdown();
        }

    } catch (err) {
        console.error('Error actualizando dashboard:', err);
    }
}

// ──────────────────────────────────────────────────────────
// Wallet
// ──────────────────────────────────────────────────────────

function updateWallet(status) {
    setText('wallet-address', status.address || '-');
    setText('wallet-balance', status.balance != null
        ? status.balance.toFixed(2) : '-');

    const roleLabels = {
        'issuer':    '📋 Secretaría (Emisor autorizado)',
        'validator': '✅ Validador autorizado',
        'graduate':  '🎓 Egresado',
        'full':      '👁 Nodo completo (solo lectura)',
    };
    setText('node-role-label', roleLabels[status.node_role] || status.node_role || '-');
}

// ──────────────────────────────────────────────────────────
// Header
// ──────────────────────────────────────────────────────────

function updateHeader(status, chain) {
    setText('chain-badge', `Altura: ${chain.height}`);
}

// ──────────────────────────────────────────────────────────
// Estado del validador PoA
// ──────────────────────────────────────────────────────────

function updateValidatorStatus(status) {
    const label = document.getElementById('validator-status-label');
    if (!label) return;

    if (status.is_validator) {
        const active = status.mining_mode === 'validator_auto';
        label.textContent  = active ? '⚡ Activo — produciendo bloques' : '⏸ En pausa';
        label.style.color  = active ? '#2e7d32' : '#888';
    } else {
        label.textContent = 'No autorizado en esta red';
        label.style.color = '#c62828';
    }

    setText('blocks-mined', status.blocks_mined ?? 0);
}

// ──────────────────────────────────────────────────────────
// Blockchain
// ──────────────────────────────────────────────────────────

function updateChain(chain) {
    setText('chain-height', chain.height);
    setText('latest-hash',  chain.latest_hash || '-');

    const newHeight = chain.height;
    if (lastHeight > 0 && newHeight > lastHeight) {
        showNotification(`✅ Nuevo bloque #${newHeight - 1} confirmado`);
    }
    lastHeight = newHeight;

    const list = document.getElementById('blocks-list');
    if (!list) return;

    if (!chain.blocks || chain.blocks.length === 0) {
        list.innerHTML = '<div class="empty">Solo el bloque génesis</div>';
        return;
    }

    list.innerHTML = chain.blocks.map(b => `
        <div class="block-item">
            <div class="block-header-row">
                <span class="block-height">#${b.height}</span>
                <span class="block-hash monospace">${b.hash}</span>
                <span class="block-txs">${b.txs} TX${b.txs !== 1 ? 's' : ''}</span>
                <span class="block-sigs">🔑 ${b.firmas || 0} firma(s)</span>
            </div>
            <div class="block-meta">
                <span>${formatTime(b.timestamp)}</span>
                <button onclick="showVerifyModal('${b.full_hash}', ${b.height})"
                        class="btn-verify">🔎 Verificar</button>
            </div>
        </div>
    `).join('');
}

// ──────────────────────────────────────────────────────────
// Peers
// ──────────────────────────────────────────────────────────

function updatePeers(peers) {
    setText('peers-count', peers.length);
    const list = document.getElementById('peers-list');
    if (!list) return;
    list.innerHTML = peers.length === 0
        ? '<li class="empty">Sin peers conectados</li>'
        : peers.map(p => `<li><span class="peer-dot">●</span> ${p.address}</li>`).join('');
}

// ──────────────────────────────────────────────────────────
// Mempool
// ──────────────────────────────────────────────────────────

function updateMempool(mempool) {
    setText('mempool-count', mempool.length);
    const list = document.getElementById('mempool-list');
    if (!list) return;

    list.innerHTML = mempool.length === 0
        ? '<div class="empty">Sin transacciones pendientes</div>'
        : mempool.map(tx => `
            <div class="tx-item">
                <div class="tx-hash">${tx.txid}
                    ${tx.tipo ? `<span class="tx-tipo-badge">${tx.tipo}</span>` : ''}
                </div>
                <div class="tx-details">
                    <span class="tx-addr">${tx.from} → ${tx.to}</span>
                    <span class="tx-amount">${tx.amount} coins</span>
                </div>
            </div>
        `).join('');
}

// ──────────────────────────────────────────────────────────
// Dropdowns de addresses
// ──────────────────────────────────────────────────────────

async function updateAddressDropdown() {
    try {
        const addresses = await fetch('/api/addresses').then(r => r.json());
        const select    = document.getElementById('address-select');
        if (!select) return;
        const current = select.value;
        select.innerHTML = '<option value="">— conocidos —</option>' +
            addresses.map(a =>
                `<option value="${a.wallet_address}">${a.node_id}: ${a.wallet_address.slice(0,14)}...</option>`
            ).join('');
        if (current) select.value = current;
    } catch (e) { /* seed no disponible */ }
}

async function updateEgresadoDropdown() {
    try {
        const addresses = await fetch('/api/addresses').then(r => r.json());
        const select    = document.getElementById('t-address-select');
        if (!select) return;
        select.innerHTML = '<option value="">— conocidos —</option>' +
            addresses.map(a =>
                `<option value="${a.wallet_address}">${a.node_id}: ${a.wallet_address.slice(0,14)}...</option>`
            ).join('');
    } catch (e) { /* seed no disponible */ }
}

function fillAddress(value) {
    if (value) document.getElementById('to_address').value = value;
}

function fillEgresadoAddress(value) {
    if (value) document.getElementById('t-wallet').value = value;
}

// ──────────────────────────────────────────────────────────
// EMITIR TÍTULO (rol: issuer)
// ──────────────────────────────────────────────────────────

async function issueTitle() {
    const resultBox = document.getElementById('issue-result');
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = '<div class="result-pending">⏳ Procesando...</div>';

    const form = new FormData();
    form.append('nombre',            document.getElementById('t-nombre').value.trim());
    form.append('matricula',         document.getElementById('t-matricula').value.trim());
    form.append('carrera',           document.getElementById('t-carrera').value.trim());
    form.append('rvoe',              document.getElementById('t-rvoe').value.trim());
    form.append('fecha',             document.getElementById('t-fecha').value);
    form.append('egresado_address',  document.getElementById('t-wallet').value.trim());

    const pdfFile = document.getElementById('t-pdf').files[0];
    if (pdfFile) form.append('archivo_pdf', pdfFile);

    try {
        const res  = await fetch('/api/title/issue', { method: 'POST', body: form });
        const data = await res.json();

        if (res.ok) {
            resultBox.innerHTML = `
                <div class="result-success">
                    <div class="result-title">✅ Título registrado en el mempool</div>
                    <div class="result-row">
                        <span class="result-label">TX Hash</span>
                        <code class="result-hash">${data.tx_hash}</code>
                        <button class="btn-copy-sm" onclick="copyText('${data.tx_hash}')">Copiar</button>
                    </div>
                    <div class="result-row">
                        <span class="result-label">Hash del PDF</span>
                        <code class="result-hash">${data.hash_doc}</code>
                    </div>
                    <div class="result-note">${data.mensaje}</div>
                </div>`;
            // Limpiar form
            ['t-nombre','t-matricula','t-carrera','t-rvoe','t-fecha','t-wallet'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
        } else {
            resultBox.innerHTML = `<div class="result-error">❌ ${data.error}</div>`;
        }
    } catch (e) {
        resultBox.innerHTML = `<div class="result-error">❌ Error de conexión: ${e.message}</div>`;
    }
}

// ──────────────────────────────────────────────────────────
// PENDIENTES Y EMITIDOS (rol: issuer)
// ──────────────────────────────────────────────────────────

async function loadPendingTitles() {
    try {
        const pending = await fetch('/api/title/pending').then(r => r.json());
        const list    = document.getElementById('pending-list');
        if (!list) return;

        if (!pending.length) {
            list.innerHTML = '<div class="empty">Sin títulos pendientes</div>';
            return;
        }
        list.innerHTML = pending.map(t => `
            <div class="title-pending-item">
                <span class="title-name">${t.nombre}</span>
                <span class="title-carrera">${t.carrera}</span>
                <span class="title-mat">Mat. ${t.matricula}</span>
                <span class="badge-pending">⏳ Pendiente</span>
            </div>
        `).join('');
    } catch (e) { /* silencioso */ }
}

async function loadAllTitles() {
    try {
        const titles = await fetch('/api/title/all').then(r => r.json());
        const list   = document.getElementById('all-titles-list');
        if (!list) return;

        if (!titles.length) {
            list.innerHTML = '<div class="empty">Sin títulos confirmados aún</div>';
            return;
        }
        list.innerHTML = titles.map(t => `
            <div class="title-confirmed-item">
                <div class="title-confirmed-header">
                    <span class="title-name">${t.nombre}</span>
                    <span class="badge-confirmed">✅ Confirmado</span>
                </div>
                <div class="title-confirmed-meta">
                    <span>${t.carrera}</span>
                    <span>Mat. ${t.matricula}</span>
                    <span>Bloque #${t.bloque}</span>
                </div>
                <div class="title-hash-row">
                    <code>${t.tx_hash.slice(0,24)}...</code>
                    <button class="btn-copy-sm" onclick="copyText('${t.tx_hash}')">Copiar TX</button>
                </div>
            </div>
        `).join('');
    } catch (e) { /* silencioso */ }
}

// ──────────────────────────────────────────────────────────
// MIS CREDENCIALES (rol: graduate)
// ──────────────────────────────────────────────────────────

async function loadMyCredentials(myAddress) {
    if (!myAddress) return;
    try {
        const titles    = await fetch(`/api/title/by_wallet/${myAddress}`).then(r => r.json());
        const container = document.getElementById('mis-credenciales');
        if (!container) return;

        if (!titles.length) {
            container.innerHTML = '<div class="empty">No hay credenciales registradas en esta wallet todavía.</div>';
            return;
        }

        container.innerHTML = titles.map(t => `
            <div class="credential-card">
                <div class="cred-verified-badge">✅ Verificado en blockchain</div>
                <div class="cred-title-name">${t.carrera}</div>
                <div class="cred-holder">${t.nombre}</div>
                <div class="cred-meta">
                    <span>🏛 ${t.institucion}</span>
                    <span>📋 RVOE: ${t.rvoe}</span>
                    <span>📅 ${t.fecha}</span>
                </div>
                <div class="cred-chain-info">
                    Bloque #${t.bloque} · ${t.firmas_validadores.length} validador(es)
                </div>
                <div class="cred-hash-row">
                    <span class="cred-hash-label">TX Hash:</span>
                    <code class="cred-hash">${t.tx_hash}</code>
                    <button class="btn-copy-sm" onclick="copyText('${t.tx_hash}')">Copiar</button>
                </div>
            </div>
        `).join('');
    } catch (e) { /* silencioso */ }
}

// ──────────────────────────────────────────────────────────
// VERIFICAR TÍTULO (todos los roles)
// ──────────────────────────────────────────────────────────

async function lookupTitle() {
    const txHash    = document.getElementById('v-txhash').value.trim();
    const resultDiv = document.getElementById('title-lookup-result');
    if (!txHash) {
        resultDiv.innerHTML = '<div class="result-error">Ingresa un TX hash</div>';
        return;
    }

    resultDiv.innerHTML = '<div class="result-pending">🔍 Buscando en la cadena...</div>';

    try {
        const res  = await fetch(`/api/title/lookup/${txHash}`);
        const data = await res.json();

        if (!data.encontrado) {
            resultDiv.innerHTML = `<div class="result-error">❌ TX no encontrada en la cadena</div>`;
            document.getElementById('doc-verify-section').classList.add('hidden');
            return;
        }

        const d    = data.datos;
        const sigs = data.firmas_validadores.length;

        resultDiv.innerHTML = `
            <div class="verified-title-card">
                <div class="verified-header">
                    <span class="verified-badge">✅ TÍTULO VERIFICADO</span>
                    <span class="verified-block">Bloque #${data.bloque}</span>
                </div>
                <div class="verified-grid">
                    <span class="vg-label">Nombre</span>      <span>${d.nombre}</span>
                    <span class="vg-label">Matrícula</span>   <span>${d.matricula}</span>
                    <span class="vg-label">Carrera</span>     <span>${d.carrera}</span>
                    <span class="vg-label">Institución</span> <span>${d.institucion}</span>
                    <span class="vg-label">RVOE</span>        <span>${d.rvoe}</span>
                    <span class="vg-label">Fecha</span>       <span>${d.fecha}</span>
                </div>
                <div class="verified-sigs">🔑 Firmado por ${sigs} validador(es) autorizado(s)</div>
                <div class="verified-hash">
                    <span class="vg-label">Hash del documento registrado:</span>
                    <code>${d.hash_doc}</code>
                </div>
            </div>`;

        currentTxHash = txHash;
        document.getElementById('doc-verify-section').classList.remove('hidden');

    } catch (e) {
        resultDiv.innerHTML = `<div class="result-error">❌ Error: ${e.message}</div>`;
    }
}

async function verifyDocument() {
    const file = document.getElementById('v-pdf').files[0];
    if (!file || !currentTxHash) return;

    const resultDiv = document.getElementById('doc-verify-result');
    resultDiv.innerHTML = '<div class="result-pending">⏳ Calculando hash del documento...</div>';

    const form = new FormData();
    form.append('tx_hash',     currentTxHash);
    form.append('archivo_pdf', file);

    try {
        const res    = await fetch('/api/title/verify_doc', { method: 'POST', body: form });
        const result = await res.json();

        if (result.valido) {
            resultDiv.innerHTML = `
                <div class="result-success">
                    <div class="result-title">✅ DOCUMENTO AUTÉNTICO</div>
                    <div>El PDF proporcionado coincide exactamente con el registrado en blockchain.</div>
                    <div class="hash-compare">
                        <div><span class="vg-label">Hash calculado:</span>
                             <code>${result.hash_calculado}</code></div>
                    </div>
                </div>`;
        } else if (result.error) {
            resultDiv.innerHTML = `<div class="result-error">❌ ${result.error}</div>`;
        } else {
            resultDiv.innerHTML = `
                <div class="result-error">
                    <div class="result-title">❌ DOCUMENTO NO COINCIDE</div>
                    <div>El archivo fue modificado o no corresponde a este título.</div>
                    <div class="hash-compare">
                        <div><span class="vg-label">Esperado:</span>
                             <code>${result.hash_registrado}</code></div>
                        <div><span class="vg-label">Recibido:</span>
                             <code>${result.hash_calculado}</code></div>
                    </div>
                </div>`;
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="result-error">❌ Error: ${e.message}</div>`;
    }
}

// ──────────────────────────────────────────────────────────
// Control del validador
// ──────────────────────────────────────────────────────────

async function mineOnce() {
    try {
        const res  = await fetch('/api/mine/once', { method: 'POST' });
        const data = await res.json();
        if (data.error) showNotification('Error: ' + data.error);
        else showNotification('⚡ Bloque PoA producido');
    } catch (e) {
        showNotification('Error al producir bloque');
    }
}

// ──────────────────────────────────────────────────────────
// Modal: Vista previa de TX
// ──────────────────────────────────────────────────────────

async function previewTx() {
    const toAddress = document.getElementById('to_address').value.trim();
    const amount    = document.getElementById('amount').value;
    if (!toAddress || !amount) {
        showNotification('Completa destinatario y cantidad');
        return;
    }
    try {
        const res  = await fetch('/api/tx/preview', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ to_address: toAddress, amount: parseFloat(amount) }),
        });
        const data = await res.json();
        if (data.error) { showNotification('Error: ' + data.error); return; }

        setText('prev-from',   data.from);
        setText('prev-to',     data.to);
        setText('prev-amount', `${data.amount} coins`);
        setText('prev-txid',   data.txid);
        setText('prev-sig',    data.signature);
        const validEl = document.getElementById('prev-valid');
        if (validEl) {
            validEl.textContent = data.valid ? '✅ Válida' : '❌ Inválida';
            validEl.style.color = data.valid ? '#2e7d32' : '#c62828';
        }
        document.getElementById('tx-preview-modal').classList.remove('hidden');
    } catch (e) {
        showNotification('Error al generar vista previa');
    }
}

function closeTxPreview()  { document.getElementById('tx-preview-modal').classList.add('hidden'); }
function confirmTx()       { closeTxPreview(); document.getElementById('tx-form').submit(); }

// ──────────────────────────────────────────────────────────
// Modal: Verificación de bloque
// ──────────────────────────────────────────────────────────

async function showVerifyModal(fullHash, height) {
    const modal = document.getElementById('verify-modal');
    if (!modal) return;
    setText('verify-block-height', `#${height}`);
    document.getElementById('verify-results').innerHTML = '<div class="empty">Verificando...</div>';
    modal.classList.remove('hidden');

    try {
        const data = await fetch(`/api/block/${fullHash}/verify`).then(r => r.json());
        if (data.error) {
            document.getElementById('verify-results').innerHTML =
                `<div class="empty">Error: ${data.error}</div>`;
            return;
        }

        const rows = Object.values(data.checks).map(c => `
            <div class="check-row ${c.ok ? 'verify-result-ok' : 'verify-result-fail'}">
                <span class="check-icon">${c.ok ? '✅' : '❌'}</span>
                <div class="check-info">
                    <div class="check-label">${c.label}</div>
                    <div class="check-detail">${c.detail}</div>
                </div>
            </div>
        `).join('');

        const summary = data.all_valid
            ? '<div class="verify-all-ok">✅ Bloque completamente válido</div>'
            : '<div class="verify-all-fail">❌ Bloque con errores</div>';

        document.getElementById('verify-results').innerHTML = rows + summary;
    } catch (e) {
        document.getElementById('verify-results').innerHTML =
            `<div class="empty">Error: ${e.message}</div>`;
    }
}

function closeVerifyModal() { document.getElementById('verify-modal').classList.add('hidden'); }

// ──────────────────────────────────────────────────────────
// Utilidades
// ──────────────────────────────────────────────────────────

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function copyAddress() {
    const address = document.getElementById('wallet-address').textContent;
    navigator.clipboard.writeText(address).then(() => {
        showNotification('Address copiada al portapapeles');
    });
}

function copyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copiado al portapapeles');
    });
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    return new Date(timestamp * 1000).toLocaleTimeString();
}

function showNotification(msg) {
    const el = document.getElementById('block-notification');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 4000);
}

// ──────────────────────────────────────────────────────────
// Inicialización
// ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    updateData();
    setInterval(updateData, 3000);
});
