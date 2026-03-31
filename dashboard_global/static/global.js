// Dashboard Global — lógica completa Sprint 9.1
// Cadena visual + detalle de bloques clickeables

let lastMaxHeight = 0;
let chainRefreshInterval = null;

async function updateAll() {
    try {
        const [network, orch] = await Promise.all([
            fetch('/api/network').then(r => r.json()),
            fetch('/api/orchestrator').then(r => r.json()),
        ]);
        updateSeedBadge(network.seed_online);
        updateSummary(network.summary);
        updateNodesTable(network.nodes, network.summary.max_height);
        updateOrchestrator(orch);
        updateRefreshBadge();
    } catch (err) {
        console.error('Error actualizando red:', err);
        document.getElementById('refresh-badge').textContent = '⚠ Error de conexión';
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

function updateSeedBadge(online) {
    const el = document.getElementById('seed-badge');
    if (!el) return;
    el.textContent = online ? '🟢 Seed online' : '🔴 Seed offline';
    el.style.background = online ? '#e8f5e9' : '#fce4ec';
}

function updateRefreshBadge() {
    const el = document.getElementById('refresh-badge');
    if (!el) return;
    el.textContent = `Actualizado: ${new Date().toLocaleTimeString()}`;
}

function updateSummary(s) {
    setText('s-total-nodes', s.total_nodes);
    setText('s-online',      s.online_nodes);
    setText('s-offline',     s.offline_nodes);
    setText('s-height',      s.max_height);
    setText('s-out-sync',    s.out_of_sync);
    setText('s-mempool',     s.total_mempool);
    setText('s-mined',       s.total_mined);
    setText('s-mining-auto', s.mining_auto);

    // Mining control section
    setText('mining-auto-count', `${s.mining_auto} / ${s.online_nodes}`);
    const statusEl = document.getElementById('mining-global-status');
    if (statusEl) {
        if (s.mining_auto === s.online_nodes && s.online_nodes > 0) {
            statusEl.textContent = '⚙ Todos en AUTO';
            statusEl.style.color = '#2e7d32';
        } else if (s.mining_auto === 0) {
            statusEl.textContent = '🖐 Todos en MANUAL';
            statusEl.style.color = '#1565c0';
        } else {
            statusEl.textContent = '⚡ Mixto';
            statusEl.style.color = '#e65100';
        }
    }

    if (lastMaxHeight > 0 && s.max_height > lastMaxHeight) {
        showNotification(`¡Nuevo bloque #${s.max_height - 1} confirmado en la red!`);
        updateChain();
    }
    lastMaxHeight = s.max_height;

    const outCard = document.getElementById('s-out-sync')?.closest('.summary-card');
    if (outCard) outCard.style.background = s.out_of_sync > 0 ? '#fff3e0' : '';
}

function renderChainVisual(blocks, totalHeight) {
    const container = document.getElementById('chain-visual');
    if (!container) return;
    const ordered = [...blocks].reverse();
    const items = ordered.map((b, i) => {
        const isLatest  = i === ordered.length - 1;
        const isGenesis = b.height === 0;
        const txLabel   = b.txs === 1 ? '1 TX' : `${b.txs} TXs`;
        const minerShort = b.mined_by ? b.mined_by.slice(0, 8) + '...' : 'génesis';
        return `
            ${i > 0 ? '<div class="chain-arrow">→</div>' : ''}
            <div class="chain-block ${isLatest ? 'chain-block-latest' : ''} ${isGenesis ? 'chain-block-genesis' : ''}"
                 onclick="showBlockDetail('${b.full_hash}')" title="Click para ver detalle">
                <div class="cb-height">#${b.height}</div>
                <div class="cb-hash monospace">${b.hash}</div>
                <div class="cb-meta">
                    <span class="cb-txs">${txLabel}</span>
                    <span class="cb-miner">⛏ ${minerShort}</span>
                </div>
                <div class="cb-time">${formatTime(b.timestamp)}</div>
            </div>`;
    }).join('');
    const hiddenCount = totalHeight - blocks.length;
    const prefix = hiddenCount > 0
        ? `<div class="chain-ellipsis">... ${hiddenCount} bloques anteriores</div><div class="chain-arrow">→</div>`
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
    setText('lb-nonce',  (block.nonce || 0).toLocaleString());
    setText('lb-txs',    block.txs);
    setText('lb-miner',  block.mined_by || '-');
    setText('lb-time',   formatTime(block.timestamp));
}

async function showBlockDetail(fullHash) {
    const panel = document.getElementById('block-detail-panel');
    if (!panel) return;
    panel.classList.remove('hidden');
    document.getElementById('bd-tx-list').innerHTML = '<div class="empty">Cargando...</div>';
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    try {
        const block = await fetch(`/api/block/${fullHash}`).then(r => r.json());
        if (block.error) {
            document.getElementById('bd-tx-list').innerHTML = `<div class="empty">Error: ${block.error}</div>`;
            return;
        }
        const heightEl = document.getElementById('bd-height');
        if (heightEl) heightEl.textContent = `#${block.height ?? ''}`;
        setText('bd-hash',       block.hash);
        setText('bd-prev-hash',  block.prev_hash);
        setText('bd-merkle',     block.merkle_root);
        setText('bd-nonce',      (block.nonce || 0).toLocaleString());
        setText('bd-target',     block.target || block.difficulty || '-');
        setText('bd-timestamp',  block.timestamp ? new Date(block.timestamp * 1000).toLocaleString() : '-');
        const countEl = document.getElementById('bd-tx-count');
        if (countEl) countEl.textContent = `${block.tx_count} TX${block.tx_count !== 1 ? 's' : ''}`;
        const txList = document.getElementById('bd-tx-list');
        if (!block.txs || block.txs.length === 0) {
            txList.innerHTML = '<div class="empty">Sin transacciones</div>';
            return;
        }
        txList.innerHTML = block.txs.map(tx => `
            <div class="tx-detail-item ${tx.type === 'coinbase' ? 'tx-coinbase' : ''}">
                <div class="tx-detail-header">
                    <span class="tx-type-badge ${tx.type === 'coinbase' ? 'badge-coinbase' : 'badge-normal'}">
                        ${tx.type === 'coinbase' ? '⛏ COINBASE' : '↔ TX'}
                    </span>
                    <span class="tx-amount-big">${tx.amount} coins</span>
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
            </div>`).join('');
    } catch (e) {
        document.getElementById('bd-tx-list').innerHTML = `<div class="empty">Error al cargar: ${e.message}</div>`;
    }
}

function closeBlockDetail() {
    const panel = document.getElementById('block-detail-panel');
    if (panel) panel.classList.add('hidden');
}

function updateNodesTable(nodes, maxHeight) {
    const tbody = document.getElementById('nodes-tbody');
    if (!tbody) return;

    if (!nodes || nodes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="empty">Sin nodos registrados en el seed</td></tr>';
        return;
    }

    // Fork detection: nodos online en max_height con distinto latest_hash
    const atTop = nodes.filter(n => n.online && n.chain_height === maxHeight);
    const hashes = new Set(atTop.map(n => n.latest_hash).filter(Boolean));
    const hasFork = hashes.size > 1;

    tbody.innerHTML = nodes.map(node => {
        const online     = node.online;
        const lag        = maxHeight - node.chain_height;
        const inSync     = lag <= 2;
        const miningMode = node.mining_mode || '-';
        const isFork     = hasFork && online && node.chain_height === maxHeight;

        const syncIcon = !online ? '⬛' : inSync ? '✅' : lag <= 5 ? '⚠️' : '🔴';
        const syncText = !online ? '-' : inSync ? 'Sync' : `−${lag}`;
        const modeLabel = miningMode === 'auto' ? '⚙ Auto' : miningMode === 'manual' ? '🖐 Manual' : '-';
        const forkBadge = isFork ? ' <span class="fork-badge">⚡ FORK</span>' : '';
        const rowClass  = !online ? 'row-offline' : isFork ? 'row-fork' : !inSync ? 'row-desynced' : '';

        return `
            <tr class="${rowClass}">
                <td class="node-id">${node.node_id || '-'}${forkBadge}</td>
                <td>${online ? '<span class="dot green">●</span> Online' : '<span class="dot red">●</span> Offline'}</td>
                <td class="monospace">${online ? node.chain_height : '-'}</td>
                <td>${syncIcon} <span class="${inSync ? 'sync-ok' : 'sync-lag'}">${syncText}</span></td>
                <td class="balance">${online ? node.balance.toFixed(2) : '-'}</td>
                <td>${online ? node.peers_count : '-'}</td>
                <td>${online ? node.mempool_count : '-'}</td>
                <td>${online ? modeLabel : '-'}</td>
                <td>${online ? node.blocks_mined : '-'}</td>
                <td>${online ? `<a href="http://${window.location.hostname}:${node.dashboard_port}" target="_blank" class="link">:${node.dashboard_port}</a>` : '-'}</td>
            </tr>`;
    }).join('');

    if (hasFork) showNotification('⚡ Fork detectado — dos nodos con distinto bloque en la misma altura');
}

function updateOrchestrator(orch) {
    if (!orch || !orch.available) return;
    const mode   = orch.mode || 'manual';
    const labels = { auto: '⚙ Automático', manual: '🖐 Manual' };
    const colors = { auto: '#2e7d32', manual: '#1565c0' };
    const modeEl = document.getElementById('orch-mode');
    if (modeEl) {
        modeEl.textContent  = labels[mode] || mode;
        modeEl.style.color  = colors[mode] || '#333';
        modeEl.style.fontWeight = '600';
    }
    setText('orch-sent',   orch.txs_sent   || 0);
    setText('orch-failed', orch.txs_failed || 0);
    setText('orch-rate',   orch.success_rate != null ? (orch.success_rate * 100).toFixed(1) + '%' : '-');
    ['auto', 'manual'].forEach(m => {
        const btn = document.getElementById(`btn-orch-${m}`);
        if (btn) btn.classList.toggle('active', m === mode);
    });
}

async function setOrchMode(mode) {
    try {
        await fetch(`/api/orchestrator/${mode}`, { method: 'POST' });
        await updateAll();
        showNotification(`TXs automáticas: ${mode === 'auto' ? 'activadas' : 'pausadas'}`);
    } catch (e) {
        console.error('Error cambiando modo orquestador:', e);
    }
}

async function setAllMining(mode) {
    try {
        const res  = await fetch(`/api/mining/all/${mode}`, { method: 'POST' });
        const data = await res.json();
        const label = mode === 'auto' ? 'AUTO' : 'MANUAL';
        showNotification(`Minado ${label} aplicado: ${data.nodes_ok} nodos OK, ${data.nodes_failed} fallidos`);
        await updateAll();
    } catch (e) {
        console.error('Error cambiando modo de minado:', e);
    }
}

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

document.addEventListener('DOMContentLoaded', () => {
    updateAll();
    setInterval(updateAll, 3000);
    updateChain();
    setInterval(updateChain, 5000);
});
