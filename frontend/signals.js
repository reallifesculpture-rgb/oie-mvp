/**
 * OIE Signals Monitor
 * Polls /api/v1/signals/history for live signal data
 */

const API_BASE = window.location.origin;
const POLL_INTERVAL = 1000;
const MAX_SIGNALS = 50;

// State
const state = {
    signals: [],
    seenIds: new Set(),
    connected: false,
    error: null,
    stats: { total: 0, executed: 0, ignored: 0, blocked: 0 }
};

let pollingInterval = null;

// DOM Elements
const elements = {
    symbolSelect: null,
    decisionFilter: null,
    statusBadge: null,
    signalsBody: null,
    statTotal: null,
    statExecuted: null,
    statIgnored: null,
    statBlocked: null
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    elements.symbolSelect = document.getElementById('symbol-select');
    elements.decisionFilter = document.getElementById('decision-filter');
    elements.statusBadge = document.getElementById('status-badge');
    elements.signalsBody = document.getElementById('signals-body');
    elements.statTotal = document.getElementById('stat-total');
    elements.statExecuted = document.getElementById('stat-executed');
    elements.statIgnored = document.getElementById('stat-ignored');
    elements.statBlocked = document.getElementById('stat-blocked');

    // Event listeners
    elements.symbolSelect.addEventListener('change', () => {
        state.signals = [];
        state.seenIds.clear();
        renderTable();
        fetchSignals();
    });

    elements.decisionFilter.addEventListener('change', renderTable);

    // Start polling
    startPolling();
});

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    fetchSignals();
    pollingInterval = setInterval(fetchSignals, POLL_INTERVAL);
}

async function fetchSignals() {
    try {
        const symbol = elements.symbolSelect.value;
        const params = new URLSearchParams({ limit: '100' });

        if (symbol !== 'ALL') {
            params.set('symbol', symbol);
        }

        const resp = await fetch(`${API_BASE}/api/v1/signals/history?${params}`);

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();

        if (!data.ok) {
            throw new Error(data.error || 'Unknown error');
        }

        updateStatus(true);
        processSignals(data.signals || []);
        updateStats(data.signals || []);

    } catch (err) {
        console.error('Fetch error:', err);
        updateStatus(false, err.message);
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

function processSignals(signals) {
    // Add new signals that we haven't seen yet
    for (const signal of signals) {
        const id = signal.id || `${signal.ts}_${signal.symbol}_${signal.signal_type}`;

        if (state.seenIds.has(id)) continue;

        state.seenIds.add(id);
        state.signals.push(signal);
    }

    // Sort by timestamp descending (newest first) - ALWAYS sort for consistent display
    state.signals.sort((a, b) => {
        const tsA = a.ts || '';
        const tsB = b.ts || '';
        return tsB.localeCompare(tsA);  // Descending order (newest first)
    });

    // Keep only MAX_SIGNALS (remove oldest from end)
    if (state.signals.length > MAX_SIGNALS) {
        const removed = state.signals.splice(MAX_SIGNALS);
        for (const sig of removed) {
            const id = sig.id || `${sig.ts}_${sig.symbol}_${sig.signal_type}`;
            state.seenIds.delete(id);
        }
    }

    renderTable();
}

function updateStats(signals) {
    const stats = { total: signals.length, executed: 0, ignored: 0, blocked: 0 };

    for (const sig of signals) {
        const decision = (sig.decision || '').toUpperCase();
        if (decision === 'EXECUTED') stats.executed++;
        else if (decision === 'IGNORED') stats.ignored++;
        else if (decision === 'BLOCKED') stats.blocked++;
    }

    elements.statTotal.textContent = stats.total;
    elements.statExecuted.textContent = stats.executed;
    elements.statIgnored.textContent = stats.ignored;
    elements.statBlocked.textContent = stats.blocked;
}

function renderTable() {
    const decisionFilter = elements.decisionFilter.value.toUpperCase();

    let filtered = state.signals;
    if (decisionFilter) {
        filtered = filtered.filter(s => (s.decision || '').toUpperCase() === decisionFilter);
    }

    if (filtered.length === 0) {
        elements.signalsBody.innerHTML = '<tr class="empty-row"><td colspan="9">No signals yet...</td></tr>';
        return;
    }

    elements.signalsBody.innerHTML = filtered.map(signal => {
        const time = formatTime(signal.ts);
        const symbol = signal.symbol || '-';
        const signalType = signal.signal_type || '-';
        const strength = signal.strength != null ? (signal.strength * 100).toFixed(0) + '%' : '-';
        const delta = signal.delta != null ? signal.delta.toFixed(1) : '-';
        const ifi = signal.ifi != null ? signal.ifi.toFixed(2) : '-';
        const vortex = signal.vortex != null ? (signal.vortex * 100).toFixed(0) + '%' : '-';
        const decision = signal.decision || '-';
        const reason = truncate(signal.reason || '-', 40);

        const signalClass = getSignalClass(signalType);
        const decisionClass = getDecisionClass(decision);

        return `
            <tr>
                <td class="time">${time}</td>
                <td class="symbol">${symbol.replace('USDT', '')}</td>
                <td class="signal ${signalClass}">${signalType}</td>
                <td class="strength">${strength}</td>
                <td class="delta">${delta}</td>
                <td class="ifi">${ifi}</td>
                <td class="vortex">${vortex}</td>
                <td class="decision ${decisionClass}">${decision}</td>
                <td class="reason" title="${signal.reason || ''}">${reason}</td>
            </tr>
        `;
    }).join('');
}

function formatTime(ts) {
    if (!ts) return '-';
    try {
        const date = new Date(ts);
        return date.toLocaleTimeString('en-GB', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch {
        return ts;
    }
}

function truncate(str, maxLen) {
    if (!str || str.length <= maxLen) return str;
    return str.substring(0, maxLen - 3) + '...';
}

function getSignalClass(type) {
    if (!type) return '';
    const t = type.toUpperCase();
    if (t === 'LONG') return 'long';
    if (t === 'SHORT') return 'short';
    return 'neutral';
}

function getDecisionClass(decision) {
    if (!decision) return '';
    const d = decision.toUpperCase();
    if (d === 'EXECUTED') return 'executed';
    if (d === 'IGNORED') return 'ignored';
    if (d === 'BLOCKED') return 'blocked';
    return '';
}
