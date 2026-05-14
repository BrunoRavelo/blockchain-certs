// global.js — Explorador Público Blockchain Certs
// Sprint 3B: PoA + verificación de títulos

let lastMaxHeight  = 0;
let currentTxHash  = null;

// ──────────────────────────────────────────────────────────
// Loop principal
// ──────────────────────────────────────────────────────────

async function updateAll() {
    try {
        const network = await fetch('/api/network').then(r => r.json());
        updateSeedBadge(network.seed_online);
        updateSummary(network.summary);
        updateNodesTable(network.nodes, network.summary.max_height);
        updateRefreshBadge();
    } catch (err) {
        console.error('Error actualizando red:', err);
        document.getElementById('refresh-badge').textContent = '⚠ Error';
    }
}

async function updateChain() {
    try {
        const data = await fetch('/api/chain?count=10').then(r => r.json());
        if (data.blocks && data.blocks.length > 0) {
            renderChainVisual(data.blocks, data.height);
            updateLatestBlockInfo(data.blocks[0]);
            const src = document.getElementById('chain-source');
            if (src) src.textContent = `fuente: ${data.node || '-'}`;
        }
    } catch (err) {
        console.error('Error cargando cadena:', err);
    }
}

// ──────────────────────────────────────────────────────────
// Resumen de la red
// ──────────────────────────────────────────────────────────

function updateSeedBadge(online) {
    const el = document.getElementById('seed-badge');
    if (!el) return;
    el.textContent       = online ? '🟢 Seed online' : '🔴 Seed offline';
    el.style.background  = online ? '#e8f5e9' : '#fce4ec';
}

function updateRefreshBadge() {
    const el = document.getElementById('refresh-badge');
    if (el) el.textContent = `Actualizado: ${new Date().toLocaleTimeString()}`;
}

function updateSummary(s) {
    setText('s-total-nodes', s.total_nodes);
    setText('s-online',      s.online_nodes);
    setText('s-offline',     s.offline_nodes);
    setText('s-height',      s.max_height);
    setText('s-out-sync',    s.out_of_sync);
    setText('s-mempool',     s.total_mempool);
    setText('s-validators',  s.issuers_active);

    if (lastMaxHeight > 0 && s.max_height > lastMaxHeight) {
        showNotification(`✅ Nuevo bloque #${s.max_height - 1} confirmado en la red`);
        updateChain();
    }
    lastMaxHeight = s.max_height;
}

// ──────────────────────────────────────────────────────────
// Cadena visual
// ──────────────────────────────────────────────────────────

function renderChainVisual(blocks, totalHeight) {
    const container = document.getElementById('chain-visual');
    if (!container) return;

    const ordered = [...blocks].reverse();

    const items = ordered.map((b, i) => {
        const isLatest  = i === ordered.length - 1;
        const isGenesis = b.height === 0;
        const txLabel   = b.txs === 1 ? '1 TX' : `${b.txs} TXs`;
        const sigsLabel = `🔑 ${b.firmas || 0} firma(s)`;

        return `
            ${i > 0 ? '<div class="chain-arrow">→</div>' : ''}
            <div class="chain-block ${isLatest ? 'chain-block-latest' : ''} ${isGenesis ? 'chain-block-genesis' : ''}"
                 onclick="showBlockDetail('${b.full_hash}')"
                 title="Click para ver detalle">
                <div class="cb-height">#${b.height}</div>
                <div class="cb-hash monospace">${b.hash}</div>
                <div class="cb-meta">
                    <span class="cb-txs">${txLabel}</span>
                    <span class="cb-sigs">${sigsLabel}</span>
                </div>
                <div class="cb-time">${formatTime(b.timestamp)}</div>
            </div>`;
    }).join('');

    const hiddenCount = totalHeight - blocks.length;
    const prefix = hiddenCount > 0
        ? `<div class="chain-ellipsis">... ${hiddenCount} bloques anteriores</div>
           <div class="chain-arrow">→</div>`
        : '';

    container.innerHTML = prefix + items;
    container.scrollLeft = container.scrollWidth;
}

function updateLatestBlockInfo(block) {
    const panel = document.getElementById('latest-block-info');
    if (!panel) return;
    panel.style.display = 'block';
    setText('lb-height', `#${block.height}`);
    setText('lb-hash',   block.full_hash || block.hash);
    setText('lb-sigs',   `${block.firmas || 0} validador(es)`);
    setText('lb-txs',    block.txs);
    setText('lb-time',   formatTime(block.timestamp));
}

// ──────────────────────────────────────────────────────────
// Detalle de bloque
// ──────────────────────────────────────────────────────────

async function showBlockDetail(fullHash) {
    const panel = document.getElementById('block-detail-panel');
    if (!panel) return;
    panel.classList.remove('hidden');
    document.getElementById('bd-tx-list').innerHTML =
        '<div class="empty">Cargando...</div>';
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const block = await fetch(`/api/block/${fullHash}`).then(r => r.json());
        if (block.error) {
            document.getElementById('bd-tx-list').innerHTML =
                `<div class="empty">Error: ${block.error}</div>`;
            return;
        }

        const heightEl = document.getElementById('bd-height');
        if (heightEl) heightEl.textContent = `#${block.height ?? ''}`;

        setText('bd-hash',      block.hash);
        setText('bd-prev-hash', block.prev_hash);
        setText('bd-merkle',    block.merkle_root);
        setText('bd-sigs',      block.firmas
            ? `${block.firmas.length} firma(s): ${block.firmas.map(a => a.slice(0,12)+'...').join(', ')}`
            : '—');
        setText('bd-target',    block.target || '—');
        setText('bd-timestamp', block.timestamp
            ? new Date(block.timestamp * 1000).toLocaleString() : '—');

        const countEl = document.getElementById('bd-tx-count');
        if (countEl) {
            countEl.textContent =
                `${block.tx_count} TX${block.tx_count !== 1 ? 's' : ''}`;
        }

        const txList = document.getElementById('bd-tx-list');
        if (!block.txs || block.txs.length === 0) {
            txList.innerHTML = '<div class="empty">Sin transacciones</div>';
            return;
        }

        txList.innerHTML = block.txs.map(tx => {
            const isTitulo  = tx.tipo === 'titulo_universitario';
            const typeLabel = isTitulo
                ? '🎓 TÍTULO'
                : tx.type === 'coinbase' ? '⛏ COINBASE' : '↔ TX';
            const badgeClass = isTitulo
                ? 'badge-titulo'
                : tx.type === 'coinbase' ? 'badge-coinbase' : 'badge-normal';

            return `
                <div class="tx-detail-item ${isTitulo ? 'tx-titulo' : tx.type === 'coinbase' ? 'tx-coinbase' : ''}">
                    <div class="tx-detail-header">
                        <span class="tx-type-badge ${badgeClass}">${typeLabel}</span>
                        <span class="tx-amount-big">${tx.amount} coin(s)</span>
                    </div>
                    <div class="tx-detail-body">
                        <div class="tx-flow">
                            <span class="tx-addr-label">De:</span>
                            <span class="tx-addr monospace">${tx.from}</span>
                        </div>
                        <div class="tx-arrow-big">↓</div>
                        <div class="tx-flow">
                            <span class="tx-addr-label">Para:</span>
                            <span class="tx-addr monospace">${tx.to}</span>
                        </div>
                    </div>
                    <div class="tx-detail-footer">
                        <span class="tx-id-label">TXID:</span>
                        <span class="tx-id monospace">${tx.txid}</span>
                    </div>
                </div>`;
        }).join('');

    } catch (e) {
        document.getElementById('bd-tx-list').innerHTML =
            `<div class="empty">Error: ${e.message}</div>`;
    }
}

function closeBlockDetail() {
    const panel = document.getElementById('block-detail-panel');
    if (panel) panel.classList.add('hidden');
}

// ──────────────────────────────────────────────────────────
// Tabla de nodos
// ──────────────────────────────────────────────────────────

function updateNodesTable(nodes, maxHeight) {
    const tbody = document.getElementById('nodes-tbody');
    if (!tbody) return;

    if (!nodes || nodes.length === 0) {
        tbody.innerHTML =
            '<tr><td colspan="9" class="empty">Sin nodos en el seed</td></tr>';
        return;
    }

    const roleLabels = {
        'issuer':    '📋 Secretaría',
        'validator': '✅ Validador',
        'graduate':  '🎓 Egresado',
        'full':      '👁 Completo',
    };

    tbody.innerHTML = nodes.map(node => {
        const online   = node.online;
        const lag      = maxHeight - node.chain_height;
        const inSync   = lag <= 2;
        const syncIcon = !online ? '⬛' : inSync ? '✅' : lag <= 5 ? '⚠️' : '🔴';
        const syncText = !online ? '-' : inSync ? 'Sync' : `−${lag}`;
        const isIssuer = node.is_issuer || false;
        const rowClass = !online ? 'row-offline' : !inSync ? 'row-desynced' : '';
        const role        = roleLabels[node.node_role] || node.node_role || '-';

        return `
            <tr class="${rowClass}">
                <td class="node-id">${node.node_id || '-'}</td>
                <td>${online ? role : '-'}</td>
                <td>${online
                    ? '<span class="dot green">●</span> Online'
                    : '<span class="dot red">●</span> Offline'}</td>
                <td class="monospace">${online ? node.chain_height : '-'}</td>
                <td>${syncIcon} <span class="${inSync ? 'sync-ok' : 'sync-lag'}">${syncText}</span></td>
                <td>${online ? node.peers_count : '-'}</td>
                <td>${online ? node.mempool_count : '-'}</td>
                <td>${online ? (isIssuer ? '⚡ Emisor' : '—') : '-'}</td>
                <td>${online
                    ? `<a href="http://${window.location.hostname}:${node.dashboard_port}"
                          target="_blank" class="link">:${node.dashboard_port}</a>`
                    : '-'}</td>
            </tr>`;
    }).join('');
}

// ──────────────────────────────────────────────────────────
// Verificación de títulos
// ──────────────────────────────────────────────────────────

async function lookupTitle() {
    const txHash    = document.getElementById('v-txhash').value.trim();
    const resultDiv = document.getElementById('title-lookup-result');

    if (!txHash) {
        resultDiv.innerHTML =
            '<div class="g-result-error">Ingresa un TX hash</div>';
        return;
    }

    resultDiv.innerHTML =
        '<div class="g-result-pending">🔍 Buscando en la cadena...</div>';
    document.getElementById('doc-verify-section').classList.add('hidden');

    try {
        const res  = await fetch(`/api/title/lookup/${txHash}`);
        const data = await res.json();

        if (!data.encontrado) {
            resultDiv.innerHTML =
                `<div class="g-result-error">❌ TX no encontrada en la cadena</div>`;
            return;
        }

        const d    = data.datos;
        const sigs = (data.firmas_validadores || []).length;

        resultDiv.innerHTML = `
            <div class="g-verified-card">
                <div class="g-verified-header">
                    <span class="g-verified-badge">✅ TÍTULO VERIFICADO</span>
                    <span class="g-verified-block">Bloque #${data.bloque}</span>
                </div>
                <div class="g-verified-grid">
                    <span class="g-vg-label">Nombre</span>       <span>${d.nombre}</span>
                    <span class="g-vg-label">Matrícula</span>    <span>${d.matricula}</span>
                    <span class="g-vg-label">Carrera</span>      <span>${d.carrera}</span>
                    <span class="g-vg-label">Institución</span>  <span>${d.institucion}</span>
                    <span class="g-vg-label">Fecha</span>        <span>${d.fecha}</span>
                </div>
                <div class="g-verified-sigs">
                    🔑 Firmado por ${sigs} validador(es) autorizado(s)
                </div>
                <div class="g-verified-hash">
                    <span class="g-vg-label">Hash del documento registrado:</span>
                    <code>${d.hash_doc}</code>
                </div>
            </div>`;

        currentTxHash = txHash;
        document.getElementById('doc-verify-section').classList.remove('hidden');

    } catch (e) {
        resultDiv.innerHTML =
            `<div class="g-result-error">❌ Error: ${e.message}</div>`;
    }
}

function clearVerifyResult() {
    const r = document.getElementById('title-lookup-result');
    if (r) r.innerHTML = '';
    const d = document.getElementById('doc-verify-section');
    if (d) d.classList.add('hidden');
}

async function verifyDocument() {
    const file = document.getElementById('v-pdf').files[0];
    if (!file || !currentTxHash) return;

    const resultDiv = document.getElementById('doc-verify-result');
    resultDiv.innerHTML =
        '<div class="g-result-pending">⏳ Calculando hash del documento...</div>';

    const form = new FormData();
    form.append('tx_hash',     currentTxHash);
    form.append('archivo_pdf', file);

    try {
        const res    = await fetch('/api/title/verify_doc',
                                   { method: 'POST', body: form });
        const result = await res.json();

        if (result.valido) {
            resultDiv.innerHTML = `
                <div class="g-result-success">
                    <div class="g-result-title">✅ DOCUMENTO AUTÉNTICO</div>
                    <div>El PDF coincide exactamente con el registrado en blockchain.</div>
                    <div class="g-hash-row">
                        <span class="g-vg-label">Hash verificado:</span>
                        <code>${result.hash_calculado}</code>
                    </div>
                </div>`;
        } else if (result.error) {
            resultDiv.innerHTML =
                `<div class="g-result-error">❌ ${result.error}</div>`;
        } else {
            resultDiv.innerHTML = `
                <div class="g-result-error">
                    <div class="g-result-title">❌ DOCUMENTO NO COINCIDE</div>
                    <div>El archivo fue modificado o no corresponde a este título.</div>
                    <div class="g-hash-row">
                        <span class="g-vg-label">Esperado:</span>
                        <code>${result.hash_registrado}</code>
                    </div>
                    <div class="g-hash-row">
                        <span class="g-vg-label">Recibido:</span>
                        <code>${result.hash_calculado}</code>
                    </div>
                </div>`;
        }
    } catch (e) {
        resultDiv.innerHTML =
            `<div class="g-result-error">❌ Error: ${e.message}</div>`;
    }
}

// ──────────────────────────────────────────────────────────
// Utilidades
// ──────────────────────────────────────────────────────────

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatTime(timestamp) {
    if (!timestamp) return '-';
    return new Date(timestamp * 1000).toLocaleTimeString();
}

function showNotification(msg) {
    const el = document.getElementById('notification');
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 4000);
}

// ──────────────────────────────────────────────────────────
// Inicialización
// ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    updateAll();
    setInterval(updateAll, 3000);
    updateChain();
    setInterval(updateChain, 5000);
});
