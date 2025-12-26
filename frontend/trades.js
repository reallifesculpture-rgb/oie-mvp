/**
 * OIE Trade History
 * Polls /api/v1/trades for trade history data
 */

const API_BASE = window.location.origin;
const POLL_INTERVAL = 2000;

// State
const state = {
    trades: [],
    stats: null,
    connected: false,
    error: null
};

let pollingInterval = null;

// DOM Elements
const elements = {
    symbolSelect: null,
    actionFilter: null,
    todayOnly: null,
    statusBadge: null,
    tradesBody: null,
    statTotal: null,
    statWinning: null,
    statLosing: null,
    statWinrate: null,
    statPnl: null,
    statNet: null
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    elements.symbolSelect = document.getElementById('symbol-select');
    elements.actionFilter = document.getElementById('action-filter');
    elements.todayOnly = document.getElementById('today-only');
    elements.statusBadge = document.getElementById('status-badge');
    elements.tradesBody = document.getElementById('trades-body');
    elements.statTotal = document.getElementById('stat-total');
    elements.statWinning = document.getElementById('stat-winning');
    elements.statLosing = document.getElementById('stat-losing');
    elements.statWinrate = document.getElementById('stat-winrate');
    elements.statPnl = document.getElementById('stat-pnl');
    elements.statNet = document.getElementById('stat-net');

    // Event listeners
    elements.symbolSelect.addEventListener('change', fetchTrades);
    elements.actionFilter.addEventListener('change', renderTable);
    elements.todayOnly.addEventListener('change', fetchTrades);

    // Start polling
    startPolling();
});

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    fetchTrades();
    fetchStats();
    pollingInterval = setInterval(() => {
        fetchTrades();
        fetchStats();
    }, POLL_INTERVAL);
}

async function fetchTrades() {
    try {
        const symbol = elements.symbolSelect.value;
        const todayOnly = elements.todayOnly.checked;
        const params = new URLSearchParams({ limit: '200' });

        if (symbol) {
            params.set('symbol', symbol);
        }
        if (todayOnly) {
            params.set('today', 'true');
        }

        const resp = await fetch(`${API_BASE}/api/v1/trades?${params}`);

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();

        if (!data.ok) {
            throw new Error(data.error || 'Unknown error');
        }

        updateStatus(true);
        state.trades = data.trades || [];
        renderTable();

    } catch (err) {
        console.error('Fetch error:', err);
        updateStatus(false, err.message);
    }
}

async function fetchStats() {
    try {
        const symbol = elements.symbolSelect.value;
        const params = symbol ? `?symbol=${symbol}` : '';

        const resp = await fetch(`${API_BASE}/api/v1/trades/stats${params}`);
        if (!resp.ok) return;

        const data = await resp.json();
        if (!data.ok) return;

        state.stats = data.stats;
        renderStats();

    } catch (err) {
        console.error('Stats fetch error:', err);
    }
}

function updateStatus(connected, errorMsg = null) {
    state.connected = connected;
    state.error = errorMsg;

    if (connected) {
        elements.statusBadge.textContent = 'Connected';
        elements.statusBadge.className = 'status-badge connected';
    } else {
        elements.statusBadge.textContent = errorMsg ? `Error: ${errorMsg}` : 'Disconnected';
        elements.statusBadge.className = 'status-badge error';
    }
}

function renderStats() {
    if (!state.stats) return;

    const todayOnly = elements.todayOnly.checked;
    const stats = todayOnly ? state.stats.today : state.stats.all_time;

    if (!stats) return;

    elements.statTotal.textContent = stats.total_trades || 0;
    elements.statWinning.textContent = stats.winning_trades || 0;
    elements.statLosing.textContent = stats.losing_trades || 0;
    elements.statWinrate.textContent = (stats.win_rate || 0).toFixed(1) + '%';

    const pnl = stats.total_pnl || 0;
    elements.statPnl.textContent = formatPrice(pnl);
    elements.statPnl.className = 'stat-value ' + (pnl >= 0 ? 'winning' : 'losing');

    const net = stats.net_pnl || 0;
    elements.statNet.textContent = formatPrice(net);
    elements.statNet.className = 'stat-value ' + (net >= 0 ? 'winning' : 'losing');
}

function renderTable() {
    const actionFilter = elements.actionFilter.value;

    let filtered = state.trades;
    if (actionFilter) {
        filtered = filtered.filter(t => t.action === actionFilter);
    }

    if (filtered.length === 0) {
        elements.tradesBody.innerHTML = '<tr class="empty-row"><td colspan="9">No trades found</td></tr>';
        return;
    }

    elements.tradesBody.innerHTML = filtered.map(trade => {
        const time = formatTime(trade.ts);
        const symbol = trade.symbol || '-';
        const side = trade.side || '-';
        const action = trade.action || '-';
        const qty = trade.qty != null ? trade.qty.toFixed(4) : '-';
        const entry = trade.entry_price != null ? formatPrice(trade.entry_price) : '-';
        const exit = trade.exit_price != null ? formatPrice(trade.exit_price) : '-';
        const pnl = trade.pnl || 0;
        const reason = truncate(trade.reason || '-', 30);

        const sideClass = side === 'BUY' ? 'buy' : 'sell';
        const actionClass = getActionClass(action);
        const pnlClass = pnl > 0 ? 'winning' : (pnl < 0 ? 'losing' : '');

        return `
            <tr>
                <td class="time">${time}</td>
                <td class="symbol">${symbol.replace('USDT', '')}</td>
                <td class="side ${sideClass}">${side}</td>
                <td class="action ${actionClass}">${action}</td>
                <td class="qty">${qty}</td>
                <td class="price">${entry}</td>
                <td class="price">${exit}</td>
                <td class="pnl ${pnlClass}">${pnl !== 0 ? formatPrice(pnl) : '-'}</td>
                <td class="reason" title="${trade.reason || ''}">${reason}</td>
            </tr>
        `;
    }).join('');
}

function formatTime(ts) {
    if (!ts) return '-';
    try {
        const date = new Date(ts);
        return date.toLocaleString('en-GB', {
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch {
        return ts;
    }
}

function formatPrice(value) {
    if (value == null) return '-';
    const prefix = value >= 0 ? '+' : '';
    if (Math.abs(value) >= 1000) {
        return prefix + '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return prefix + '$' + value.toFixed(4);
}

function truncate(str, maxLen) {
    if (!str || str.length <= maxLen) return str;
    return str.substring(0, maxLen - 3) + '...';
}

function getActionClass(action) {
    if (!action) return '';
    switch (action) {
        case 'OPEN': return 'open';
        case 'CLOSE': return 'close';
        case 'STOP_LOSS': return 'stop-loss';
        case 'TAKE_PROFIT': return 'take-profit';
        default: return '';
    }
}
