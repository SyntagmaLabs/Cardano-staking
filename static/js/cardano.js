/**
 * cardano.js — Cardano Staking Dashboard
 *
 * Fetches /api/cardano/summary and /api/cardano/wallets on load.
 */

'use strict';
 
// ── State ──────────────────────────────────────────────────────────────────
let _summary      = null;
let _wallets      = [];
let _activeEntity = '';
 
// ── Formatting helpers ─────────────────────────────────────────────────────
function fmtADA(val, decimals = 0) {
  if (val == null || isNaN(val)) return '—';
  const n = Number(val);
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return n.toFixed(decimals);
}
 
function fmtNum(val) {
  if (val == null) return '—';
  return Number(val).toLocaleString();
}
 
function shortAddr(addr) {
  if (!addr || addr.length < 20) return addr || '—';
  return addr.slice(0, 12) + '…' + addr.slice(-8);
}
 
function poolDisplay(poolId, poolName) {
  if (poolName && poolName.trim().length > 0 && poolName !== poolId) {
    return poolName.trim();
  }
  if (!poolId) return '—';
  return poolId.slice(0, 16) + '…';
}
 
// Safe setter — silently skips if the element doesn't exist on this page
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}
 
// ── Render stat strip ──────────────────────────────────────────────────────
function renderStats(totals) {
  setText('s-total-wallets', fmtNum(totals.wallet_count));
  setText('s-staking-count', fmtNum(totals.staking_count));
 
  const pct = totals.wallet_count > 0
    ? ((totals.staking_count / totals.wallet_count) * 100).toFixed(0) + '%'
    : '—';
  setText('s-staking-pct',    pct + ' staking');
  setText('s-total-stake',    '₳ ' + fmtADA(totals.total_stake_ada));
  setText('s-total-rewards',  '₳ ' + fmtADA(totals.total_rewards_ada));
  setText('s-live-stake',     '₳ ' + fmtADA(totals.total_live_ada));
  setText('s-unique-pools',   fmtNum(totals.unique_pools));
  setText('s-unique-stakes',  fmtNum(totals.unique_stake_keys));
}
 
// ── Render entity list ─────────────────────────────────────────────────────
function renderEntities(entities) {
  const container = document.getElementById('entity-list');
  if (!container) return;
  if (!entities || !Object.keys(entities).length) {
    container.innerHTML = '<div class="ada-no-data">No entity data</div>';
    return;
  }
 
  const sel = document.getElementById('entity-filter');
  if (sel) {
    sel.innerHTML = '<option value="">All Entities</option>';
    Object.keys(entities).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    });
  }
 
  container.innerHTML = Object.entries(entities).map(([name, e]) => {
    const stakingPct = e.wallet_count > 0
      ? (e.staking_count / e.wallet_count) * 100 : 0;
    const badgeCls = e.staking_count > 0 ? 'ada-badge-active' : 'ada-badge-inactive';
    const badgeTxt = `${e.staking_count}/${e.wallet_count} staking`;
 
    const uniqueStakes = new Set(
      (e.wallets || []).map(w => w.stake_address).filter(Boolean)
    ).size;
    const stakeNote = uniqueStakes > 0 && uniqueStakes < e.wallet_count
      ? `<span style="color:var(--muted);font-size:0.65rem;margin-left:6px">(${uniqueStakes} stake key${uniqueStakes !== 1 ? 's' : ''})</span>`
      : '';
 
    return `
    <div class="ada-entity-item" data-entity="${name}"
         onclick="setEntityFilter('${name.replace(/'/g, "\\'")}')">
      <span class="ada-entity-badge ${badgeCls}">${badgeTxt}</span>
      <div class="ada-entity-name">${name}${stakeNote}</div>
      <div class="ada-entity-meta">
        <div class="ada-entity-stat">
          <span class="ada-entity-stat-label">Controlled ADA</span>
          <span class="ada-entity-stat-val">₳ ${fmtADA(e.total_stake_ada)}</span>
        </div>
        <div class="ada-entity-stat">
          <span class="ada-entity-stat-label">Rewards</span>
          <span class="ada-entity-stat-val">₳ ${fmtADA(e.total_rewards_ada)}</span>
        </div>
        <div class="ada-entity-stat">
          <span class="ada-entity-stat-label">Live Stake</span>
          <span class="ada-entity-stat-val">₳ ${fmtADA(e.total_live_ada)}</span>
        </div>
        ${e.pools && e.pools.length ? `
        <div class="ada-entity-stat">
          <span class="ada-entity-stat-label">Pools</span>
          <span class="ada-entity-stat-val">${e.pools.length}</span>
        </div>` : ''}
      </div>
      <div class="ada-entity-staking-bar">
        <div class="ada-entity-staking-fill" style="width:${stakingPct.toFixed(1)}%"></div>
      </div>
    </div>`;
  }).join('');
}
 
// ── Render pool list ───────────────────────────────────────────────────────
function renderPools(pools) {
  const container = document.getElementById('pool-list');
  if (!container) return;
  if (!pools || !pools.length) {
    container.innerHTML = '<div class="ada-no-data">No pool data</div>';
    return;
  }
 
  const maxStake = Math.max(...pools.map(p => p.total_stake_ada), 1);
 
  container.innerHTML = pools.slice(0, 8).map(p => {
    const barPct  = ((p.total_stake_ada / maxStake) * 100).toFixed(1);
    const name    = poolDisplay(p.pool_id, p.pool_name);
    const shortId = p.pool_id ? p.pool_id.slice(0, 12) + '…' : '';
 
    return `
    <div class="ada-pool-row">
      <div>
        <div class="ada-pool-name">${name}</div>
        <div class="ada-pool-id-short">${shortId}</div>
      </div>
      <div class="ada-pool-wallets">${p.wallet_count} wallet${p.wallet_count !== 1 ? 's' : ''}</div>
      <div class="ada-pool-stake">₳ ${fmtADA(p.total_stake_ada, 2)}</div>
      <div class="ada-pool-bar-col">
        <div class="ada-pool-bar-bg">
          <div class="ada-pool-bar-fill" style="width:${barPct}%"></div>
        </div>
      </div>
    </div>`;
  }).join('');
}
 
// ── Render wallet table ────────────────────────────────────────────────────
function renderWallets(wallets) {
  const tbody        = document.getElementById('wallet-tbody');
  const countLabel   = document.getElementById('wallet-count-label');
  const showingLabel = document.getElementById('wallet-showing-label');
  if (!tbody) return;
 
  if (!wallets || !wallets.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="ada-no-data">No wallet data available</td></tr>';
    return;
  }
 
  const entityFilter = document.getElementById('entity-filter');
  const addrSearch   = document.getElementById('addr-search');
  const entityVal    = entityFilter ? entityFilter.value : '';
  const searchVal    = addrSearch   ? addrSearch.value.toLowerCase().trim() : '';
 
  let filtered = wallets;
  if (entityVal)  filtered = filtered.filter(w => w.entity_name === entityVal);
  if (searchVal)  filtered = filtered.filter(w =>
    (w.address || '').toLowerCase().includes(searchVal) ||
    (w.stake_address || '').toLowerCase().includes(searchVal)
  );
 
  if (countLabel)   countLabel.textContent   = `${wallets.length} wallets`;
  if (showingLabel) showingLabel.textContent = filtered.length < wallets.length ? `Showing ${filtered.length}` : '';
 
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="ada-no-data">No wallets match filter</td></tr>';
    return;
  }
 
  tbody.innerHTML = filtered.map(w => {
    const statusCls   = w.staked ? 'ada-status-staking' : 'ada-status-inactive';
    const statusTxt   = w.staked ? 'Staking' : (w.active ? 'Active' : 'Inactive');
    const explorerUrl = `https://cardanoscan.io/address/${w.address}`;
    const poolLabel   = poolDisplay(w.pool_id, w.pool_name);
 
    return `
    <tr>
      <td><div class="ada-entity-tag" title="${w.entity_name}">${w.entity_name}</div></td>
      <td class="ada-td-addr">
        <a href="${explorerUrl}" target="_blank" rel="noopener"
           title="${w.address}">${shortAddr(w.address)}</a>
      </td>
      <td class="ada-td-num">₳ ${fmtADA(w.balance_ada, 2)}</td>
      <td class="ada-td-num" style="color:var(--teal)">₳ ${fmtADA(w.rewards_ada, 2)}</td>
      <td class="ada-td-num" style="color:#6699ff">₳ ${fmtADA(w.live_stake_ada, 2)}</td>
      <td>
        ${w.pool_id
          ? `<span class="ada-pool-tag" title="${w.pool_id}">${poolLabel}</span>`
          : '<span style="color:var(--dim)">—</span>'}
      </td>
      <td>
        <span class="ada-status-dot ${statusCls}"></span>
        <span style="color:var(--text2);font-size:0.72rem">${statusTxt}</span>
        ${w.active_epoch ? `<span style="color:var(--dim);font-size:0.65rem;margin-left:4px">e${w.active_epoch}</span>` : ''}
      </td>
    </tr>`;
  }).join('');
}
 
// ── Entity filter interaction ──────────────────────────────────────────────
function setEntityFilter(name) {
  _activeEntity = (_activeEntity === name) ? '' : name;
  const sel = document.getElementById('entity-filter');
  if (sel) sel.value = _activeEntity;
  document.querySelectorAll('.ada-entity-item').forEach(el => {
    el.classList.toggle('active', el.dataset.entity === _activeEntity);
  });
  renderWallets(_wallets);
}
 
function filterWallets() {
  const sel = document.getElementById('entity-filter');
  _activeEntity = sel ? sel.value : '';
  document.querySelectorAll('.ada-entity-item').forEach(el => {
    el.classList.toggle('active', el.dataset.entity === _activeEntity);
  });
  renderWallets(_wallets);
}
 
// ── Manual refresh ─────────────────────────────────────────────────────────
async function triggerRefresh() {
  const btn = document.getElementById('ada-refresh-btn');
  if (btn) { btn.classList.add('spinning'); btn.disabled = true; }
  try {
    const res  = await fetch('/api/cardano/refresh');
    const data = await res.json();
    if (data.error) alert('Refresh failed: ' + data.error);
    else await loadData();
  } catch (e) {
    alert('Refresh error: ' + e.message);
  } finally {
    if (btn) { btn.classList.remove('spinning'); btn.disabled = false; }
  }
}
 
// ── Main data load ─────────────────────────────────────────────────────────
async function loadData() {
  // Only run on the Cardano page
  if (!document.getElementById('entity-list')) return;
 
  try {
    const [sumRes, walRes] = await Promise.all([
      fetch('/api/cardano/summary'),
      fetch('/api/cardano/wallets'),
    ]);
 
    if (sumRes.status === 503) {
      setText('entity-list', '');
      const el = document.getElementById('entity-list');
      if (el) el.innerHTML = '<div class="ada-error">Data initialising — check BLOCKFROST_API_KEY is set, then use Refresh.</div>';
      const pl = document.getElementById('pool-list');
      if (pl) pl.innerHTML = '<div class="ada-error">No data yet.</div>';
      const tb = document.getElementById('wallet-tbody');
      if (tb) tb.innerHTML = '<tr><td colspan="7" class="ada-no-data">No data yet — configure BLOCKFROST_API_KEY and click Refresh.</td></tr>';
      return;
    }
 
    _summary = await sumRes.json();
    _wallets = await walRes.json();
 
    if (_summary.error) {
      const el = document.getElementById('entity-list');
      if (el) el.innerHTML = `<div class="ada-error">${_summary.error}</div>`;
      return;
    }
 
    if (_summary.updated_at) {
      const d = new Date(_summary.updated_at);
      setText('ada-updated', 'Updated ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    }
 
    renderStats(_summary.totals || {});
    renderEntities(_summary.entities || {});
    renderPools(_summary.pools || []);
    renderWallets(_wallets);
 
  } catch (e) {
    console.error('Cardano data load error:', e);
    const el = document.getElementById('entity-list');
    if (el) el.innerHTML = `<div class="ada-error">Load error: ${e.message}</div>`;
  }
}
 
document.addEventListener('DOMContentLoaded', loadData);
 