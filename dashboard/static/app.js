// app.js — Blockchain Certs Dashboard

let lastHeight = 0;

// ──────────────────────────────────────────────────────────
// Loop principal
// ──────────────────────────────────────────────────────────

async function updateData() {
    try {
        const [status, chain, peers] = await Promise.all([
            fetch('/api/status').then(r => r.json()),
            fetch('/api/chain').then(r => r.json()),
            fetch('/api/peers').then(r => r.json()),
        ]);

        updateWallet(status);
        updateChain(chain);
        updatePeers(peers);
        updateHeader(chain);

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
// Wallet e identidad
// ──────────────────────────────────────────────────────────

function updateWallet(status) {
    setText('wallet-address', status.address || '-');

    const roleLabels = {
        'issuer':    '📋 Institución Emisora (puede sellar bloques)',
        'observer':  '🔍 Verificador — Solo lectura',
        'graduate':  '🎓 Egresado',
        'full':      '👁 Nodo de auditoría',
    };
    setText('node-role-label',  roleLabels[status.node_role] || status.node_role || '-');
    setText('institucion-label', status.institucion || '-');

    // Credenciales para egresado
    const credEl = document.getElementById('credential-count');
    if (credEl) {
        credEl.textContent = status.credential_count ?? '-';
    }
}

function updateHeader(chain) {
    setText('chain-badge', `Altura: ${chain.height ?? '-'}`);
}

// ──────────────────────────────────────────────────────────
// Blockchain
// ──────────────────────────────────────────────────────────

function updateChain(chain) {
    setText('chain-height', chain.height ?? '-');
    setText('latest-hash',  chain.latest_hash || '-');

    const newHeight = chain.height ?? 0;
    if (lastHeight > 0 && newHeight > lastHeight) {
        showNotification(`✅ Nuevo bloque #${newHeight - 1} confirmado en la cadena`);
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
                <span class="block-sigs">🔑 ${b.firmas || 0}</span>
            </div>
            <div class="block-meta">
                <span>${formatTime(b.timestamp)}</span>
                <button onclick="showVerifyModal('${b.full_hash}', ${b.height})" class="btn-verify">
                    🔎 Verificar
                </button>
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
        ? '<li class="empty">Sin peers conectados aún</li>'
        : peers.map(p => `<li><span class="peer-dot">●</span> ${p.address}</li>`).join('');
}

// ──────────────────────────────────────────────────────────
// Dropdown de egresados conocidos
// ──────────────────────────────────────────────────────────

async function updateEgresadoDropdown() {
    try {
        const addresses = await fetch('/api/addresses').then(r => r.json());
        const select    = document.getElementById('t-address-select');
        if (!select) return;

        // Filtrar: solo mostrar nodos que NO son issuers ni validators
        // (en la práctica, mostrar todos los conocidos y dejar que el usuario elija)
        const current = select.value;
        select.innerHTML = '<option value="">— conocidos —</option>' +
            addresses.map(a =>
                `<option value="${a.wallet_address}">
                    ${a.node_id}: ${a.wallet_address.slice(0, 12)}...
                </option>`
            ).join('');
        if (current) select.value = current;
    } catch (e) { /* seed no disponible todavía */ }
}

function fillEgresadoAddress(value) {
    if (value) {
        const input = document.getElementById('t-wallet');
        if (input) input.value = value;
    }
}

// ──────────────────────────────────────────────────────────
// Emitir certificado (issuer)
// ──────────────────────────────────────────────────────────

async function issueTitle() {
    const resultBox = document.getElementById('issue-result');
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = '<div class="result-pending">⏳ Procesando...</div>';

    const form = new FormData();
    form.append('nombre',           document.getElementById('t-nombre').value.trim());
    form.append('matricula',        document.getElementById('t-matricula').value.trim());
    form.append('carrera',          document.getElementById('t-carrera').value);
    form.append('fecha',            document.getElementById('t-fecha').value);
    form.append('egresado_address', document.getElementById('t-wallet').value.trim());

    try {
        const res  = await fetch('/api/title/issue', { method: 'POST', body: form });
        const data = await res.json();

        if (res.ok) {
            resultBox.innerHTML = `
                <div class="result-success">
                    <div class="result-title">✅ Certificado registrado en el mempool</div>
                    <div class="result-row">
                        <span class="result-label">TX Hash</span>
                        <code class="result-hash">${data.tx_hash}</code>
                        <button class="btn-copy-sm" onclick="copyText('${data.tx_hash}')">Copiar</button>
                    </div>
                    <div class="result-note">⚠️ ${data.mensaje}</div>
                </div>`;
            ['t-nombre','t-matricula','t-fecha','t-wallet'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
        } else {
            resultBox.innerHTML = `<div class="result-error">❌ ${data.error}</div>`;
        }
    } catch (e) {
        resultBox.innerHTML = `<div class="result-error">❌ Error: ${e.message}</div>`;
    }
}

// ──────────────────────────────────────────────────────────
// Sellar bloque (issuer)
// ──────────────────────────────────────────────────────────

async function sealBlock() {
    const resultDiv = document.getElementById('seal-result');
    const btn       = document.getElementById('btn-seal');

    if (btn) btn.disabled = true;
    if (resultDiv) resultDiv.innerHTML = '<div class="result-pending">🔒 Sellando bloque...</div>';

    try {
        const res  = await fetch('/api/mine/once', { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
            const addr      = data.validator_address || '';
            const addrShort = addr.slice(0, 8) + '...' + addr.slice(-6);
            if (resultDiv) resultDiv.innerHTML = `
                <div class="seal-card">
                    <div class="seal-card-header">
                        <span class="seal-icon">🔏</span>
                        <span class="seal-title">BLOQUE #${data.bloque_num} SELLADO</span>
                    </div>
                    <div class="seal-meta">
                        <span>🏛 ${data.validator_name}</span>
                        <span>📦 ${data.tx_count} certificado(s) incluido(s)</span>
                    </div>
                    <div class="seal-addr">Emisor: <code>${addrShort}</code></div>
                    <div class="seal-sig-box">
                        <div class="seal-sig-label">FIRMA DIGITAL Ed25519</div>
                        <code class="seal-sig-code">${data.firma_hex}...</code>
                    </div>
                    <div class="seal-verified-badge">✅ Firma criptográficamente verificada</div>
                </div>`;
        } else {
            if (resultDiv) resultDiv.innerHTML =
                `<div class="result-error">❌ ${data.error}</div>`;
        }
    } catch (e) {
        if (resultDiv) resultDiv.innerHTML =
            `<div class="result-error">❌ Error: ${e.message}</div>`;
    } finally {
        setTimeout(() => { if (btn) btn.disabled = false; }, 8000);
    }
}

// ──────────────────────────────────────────────────────────
// Pendientes y emitidos (issuer)
// ──────────────────────────────────────────────────────────

async function loadPendingTitles() {
    try {
        const pending = await fetch('/api/title/pending').then(r => r.json());
        const list    = document.getElementById('pending-list');
        if (!list) return;

        if (!pending.length) {
            list.innerHTML = '<div class="empty">Sin certificados pendientes</div>';
            return;
        }
        list.innerHTML = pending.map(t => `
            <div class="title-pending-item">
                <span class="title-name">${t.nombre}</span>
                <span class="title-carrera">${t.carrera}</span>
                <span class="badge-pending">⏳ ${t.tipo_certificado || 'Título'}</span>
            </div>
        `).join('');
    } catch (e) {}
}

async function loadAllTitles() {
    try {
        const titles = await fetch('/api/title/all').then(r => r.json());
        const list   = document.getElementById('all-titles-list');
        if (!list) return;

        if (!titles.length) {
            list.innerHTML = '<div class="empty">Sin certificados emitidos aún</div>';
            return;
        }
        list.innerHTML = titles.map(t => `
            <div class="title-confirmed-item">
                <div class="title-confirmed-header">
                    <span class="title-name">${t.nombre}</span>
                    <span class="badge-confirmed">✅ ${t.tipo_certificado || 'Título'}</span>
                </div>
                <div class="title-confirmed-meta">
                    <span>${t.carrera}</span>
                    <span>Mat. ${t.matricula}</span>
                    <span>Bloque #${t.bloque}</span>
                </div>
                <div class="title-hash-row">
                    <code>${t.tx_hash.slice(0, 24)}...</code>
                    <button class="btn-copy-sm" onclick="copyText('${t.tx_hash}')">Copiar TX</button>
                </div>
            </div>
        `).join('');
    } catch (e) {}
}

// ──────────────────────────────────────────────────────────
// Mis credenciales (graduate)
// ──────────────────────────────────────────────────────────

async function loadMyCredentials(myAddress) {
    if (!myAddress) return;
    try {
        const titles    = await fetch(`/api/title/by_wallet/${myAddress}`).then(r => r.json());
        const container = document.getElementById('mis-credenciales');
        if (!container) return;

        if (!titles.length) {
            container.innerHTML =
                '<div class="empty">No hay credenciales registradas en esta wallet todavía.</div>';
            return;
        }

        container.innerHTML = titles.map(t => `
            <div class="credential-card">
                <div class="cred-verified-badge">✅ Verificado en blockchain</div>
                <div class="cred-tipo">${t.tipo_certificado || 'Título Universitario'}</div>
                <div class="cred-title-name">${t.carrera}</div>
                <div class="cred-holder">${t.nombre}</div>
                <div class="cred-meta">
                    <span>🏛 ${t.institucion}</span>
                    <span>📅 ${t.fecha}</span>
                </div>
                <div class="cred-chain-info">
                    Bloque #${t.bloque} ·
                    ${t.firmas_validadores.length} validador(es)
                </div>
                <div class="cred-hash-row">
                    <span class="cred-hash-label">TX Hash:</span>
                    <code class="cred-hash">${t.tx_hash}</code>
                    <button class="btn-copy-sm" onclick="copyText('${t.tx_hash}')">Copiar</button>
                </div>
                <div class="cred-download-row">
                    <a href="/api/title/${t.tx_hash}/pdf" download class="btn-download-pdf">
                        ⬇ Descargar certificado PDF
                    </a>
                </div>
            </div>
        `).join('');
    } catch (e) {
        const container = document.getElementById('mis-credenciales');
        if (container) container.innerHTML = '<div class="empty">Error cargando credenciales</div>';
    }
}

// ──────────────────────────────────────────────────────────
// Verificar título / PDF
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
            return;
        }

        const d    = data.datos;
        const sigs = (data.firmas_validadores || []).length;

        resultDiv.innerHTML = `
            <div class="verified-title-card">
                <div class="verified-header">
                    <span class="verified-badge">✅ CERTIFICADO VERIFICADO</span>
                    <span class="verified-block">Bloque #${data.bloque}</span>
                </div>
                <div class="verified-tipo">${d.tipo_certificado || 'Título Universitario'}</div>
                <div class="verified-grid">
                    <span class="vg-label">Nombre</span>       <span>${d.nombre}</span>
                    <span class="vg-label">Matrícula</span>    <span>${d.matricula}</span>
                    <span class="vg-label">Programa</span>     <span>${d.carrera}</span>
                    <span class="vg-label">Institución</span>  <span>${d.institucion}</span>
                    <span class="vg-label">Fecha</span>        <span>${d.fecha}</span>
                </div>
                <div class="verified-sigs">🔑 Firmado por ${sigs} institución(es) autorizada(s)</div>
                <div class="verified-hash">
                    <span class="vg-label">Hash del documento:</span>
                    <code>${d.hash_doc}</code>
                </div>
            </div>`;

    } catch (e) {
        resultDiv.innerHTML = `<div class="result-error">❌ Error: ${e.message}</div>`;
    }
}

// ──────────────────────────────────────────────────────────
// Modal verificación de bloque
// ──────────────────────────────────────────────────────────

async function showVerifyModal(fullHash, height) {
    const modal = document.getElementById('verify-modal');
    if (!modal) return;
    setText('verify-block-height', `#${height}`);
    document.getElementById('verify-results').innerHTML =
        '<div class="empty">Verificando...</div>';
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

function closeVerifyModal() {
    document.getElementById('verify-modal')?.classList.add('hidden');
}

// ──────────────────────────────────────────────────────────
// Utilidades
// ──────────────────────────────────────────────────────────

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function copyAddress() {
    const address = document.getElementById('wallet-address')?.textContent;
    if (address) {
        navigator.clipboard.writeText(address)
            .then(() => showNotification('Address copiada'));
    }
}

function copyText(text) {
    navigator.clipboard.writeText(text)
        .then(() => showNotification('Copiado al portapapeles'));
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
