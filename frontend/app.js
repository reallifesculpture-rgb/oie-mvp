/**
 * OIE MVP - Multi-Symbol Trading Dashboard
 * JavaScript for LIVE paper trading UI (REST polling - no WebSocket)
 */

// ============================================
// API BASE URL - uses current origin in production
// ============================================
const API_BASE = window.location.origin;

// ============================================
// STATE
// ============================================
const state = {
    connected: false,
    symbol: 'BTCUSDT',
    timeframe: '1m',
    position: null,
    equity: 0,
    today: { trades: 0, wins: 0, losses: 0, pnl: 0 },
    allTime: { trades: 0, wins: 0, losses: 0, pnl: 0, grossProfit: 0, grossLoss: 0 },
    market: { price: 0, change: 0, delta: 0, ifi: 0, trend: '-', vortex: 'None' },
    barsCollected: 0,
    barsNeeded: 20,
    // Multi-symbol tracking
    activeSymbols: {},
    runners: {}
};

let pollingInterval = null;
const POLLING_DELAY = 1000; // 1 second

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];

// ============================================
// DOM ELEMENTS
// ============================================
const el = {
    statusBadge: document.getElementById('statusBadge'),
    connectBtn: document.getElementById('connectBtn'),
    startAllBtn: document.getElementById('startAllBtn'),
    symbolSelect: document.getElementById('symbolSelect'),
    timeframeSelect: document.getElementById('timeframeSelect'),
    marketCardsGrid: document.getElementById('marketCardsGrid'),

    noPosition: document.getElementById('noPosition'),
    positionData: document.getElementById('positionData'),
    posSide: document.getElementById('posSide'),
    posPnl: document.getElementById('posPnl'),
    posEntry: document.getElementById('posEntry'),
    posCurrent: document.getElementById('posCurrent'),
    posSL: document.getElementById('posSL'),
    posTP: document.getElementById('posTP'),

    logContainer: document.getElementById('logContainer'),
    tradeTableBody: document.getElementById('tradeTableBody'),
    noTrades: document.getElementById('noTrades'),

    todayPnl: document.getElementById('todayPnl'),
    todayTrades: document.getElementById('todayTrades'),
    todayWins: document.getElementById('todayWins'),
    todayLosses: document.getElementById('todayLosses'),
    todayWR: document.getElementById('todayWR'),

    equity: document.getElementById('equity'),
    totalTrades: document.getElementById('totalTrades'),
    totalWR: document.getElementById('totalWR'),
    profitFactor: document.getElementById('profitFactor'),
    totalPnl: document.getElementById('totalPnl'),

    lastUpdate: document.getElementById('lastUpdate'),
    currentTF: document.getElementById('currentTF')
};

// ============================================
// FORMATTERS
// ============================================
const fmt = {
    price: n => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    pct: n => (n >= 0 ? '+' : '') + n.toFixed(2) + '%',
    time: () => new Date().toLocaleTimeString('en-US', { hour12: false }),
    short: d => new Date(d).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
};

// ============================================
// UI UPDATES
// ============================================
function updateConnection(connected, status = '') {
    if (connected) {
        el.statusBadge.textContent = status || 'Connected';
        el.statusBadge.classList.add('connected');
    } else {
        el.statusBadge.textContent = status || 'Disconnected';
        el.statusBadge.classList.remove('connected');
    }
    el.connectBtn.textContent = connected ? 'Disconnect' : 'Connect';
}

function updateMarketCards() {
    let html = '';
    console.log('updateMarketCards called, SYMBOLS:', SYMBOLS);

    // Create cards for all symbols (show all, even if no data yet)
    for (const symbol of SYMBOLS) {
        const key = `${symbol}_${state.timeframe}`;
        const data = state.runners[key] || {};
        const shortSymbol = symbol.replace('USDT', '');

        const price = data.bar?.close || 0;
        const bars = data.bars_processed || 0;
        const delta = data.bar?.delta || 0;
        const ifi = data.predictive?.IFI || 0;
        const vortex = data.topology?.vortexes?.slice(-1)[0]?.direction || 'None';

        const isActive = bars >= 20;
        const isCollecting = bars > 0 && bars < 20;
        const isSelected = symbol === state.symbol;

        // Determine trend
        let trend = 'Neutral';
        let trendClass = 'neutral';
        if (delta > 10) {
            trend = 'Bullish';
            trendClass = 'bullish';
        } else if (delta < -10) {
            trend = 'Bearish';
            trendClass = 'bearish';
        }

        html += `
            <div class="market-card ${isSelected ? 'selected' : ''} ${isActive ? 'active' : ''} ${isCollecting ? 'collecting' : ''}"
                 data-symbol="${symbol}" onclick="selectSymbol('${symbol}')">
                <div class="market-card-header">
                    <span class="market-card-symbol">${shortSymbol}</span>
                    <span class="market-card-bars">${bars}/20</span>
                </div>
                <div class="market-card-price">${price > 0 ? fmt.price(price) : '--'}</div>
                <div class="market-card-stats">
                    <div class="market-card-stat">
                        <span class="market-card-stat-label">Delta</span>
                        <span class="market-card-stat-value ${delta >= 0 ? 'positive' : 'negative'}">${delta >= 0 ? '+' : ''}${delta.toFixed(1)}</span>
                    </div>
                    <div class="market-card-stat">
                        <span class="market-card-stat-label">IFI</span>
                        <span class="market-card-stat-value">${ifi.toFixed(2)}</span>
                    </div>
                    <div class="market-card-stat">
                        <span class="market-card-stat-label">Vortex</span>
                        <span class="market-card-stat-value">${vortex}</span>
                    </div>
                    <div class="market-card-stat">
                        <span class="market-card-stat-label">Trades</span>
                        <span class="market-card-stat-value">${data.stats?.total_trades || 0}</span>
                    </div>
                </div>
                <div class="market-card-trend">
                    <span class="market-card-trend-label">Trend:</span>
                    <span class="market-card-trend-value ${trendClass}">${trend}</span>
                </div>
            </div>
        `;
    }

    console.log('Generated HTML length:', html.length);
    console.log('marketCardsGrid element:', el.marketCardsGrid);
    if (el.marketCardsGrid) {
        el.marketCardsGrid.innerHTML = html;
    } else {
        console.error('marketCardsGrid element not found!');
    }
}

// Function to select a symbol by clicking on a card
function selectSymbol(symbol) {
    state.symbol = symbol;
    el.symbolSelect.value = symbol;
    addLog('', `Switched to ${symbol}`);
    updateSelectedSymbolView();
    updateMarketCards();
    startTradingWithSymbol(symbol, state.timeframe);
}

function updatePosition(pos) {
    if (pos && pos.currentPrice > 0) {
        el.noPosition.style.display = 'none';
        el.positionData.style.display = 'block';

        const isLong = pos.direction === 'long';
        el.posSide.textContent = isLong ? 'LONG' : 'SHORT';
        el.posSide.className = 'position-side ' + (isLong ? 'long' : 'short');

        el.posEntry.textContent = fmt.price(pos.entryPrice);
        el.posCurrent.textContent = fmt.price(pos.currentPrice);

        const pnl = isLong
            ? pos.currentPrice - pos.entryPrice
            : pos.entryPrice - pos.currentPrice;

        el.posPnl.textContent = (pnl >= 0 ? '+' : '') + fmt.price(pnl);
        el.posPnl.className = 'position-pnl ' + (pnl >= 0 ? 'profit' : 'loss');

        el.posSL.textContent = fmt.price(pos.stopLoss);
        el.posTP.textContent = fmt.price(pos.takeProfit);
    } else {
        el.noPosition.style.display = 'block';
        el.positionData.style.display = 'none';
    }
}


function updateTodayStats(s) {
    el.todayTrades.textContent = s.trades;
    el.todayWins.textContent = s.wins;
    el.todayLosses.textContent = s.losses;
    el.todayWR.textContent = s.trades > 0 ? Math.round(s.wins / s.trades * 100) + '%' : '0%';

    el.todayPnl.textContent = fmt.price(s.pnl);
    el.todayPnl.className = 'big-stat-value ' + (s.pnl >= 0 ? 'profit' : 'loss');
}

function updateAllTimeStats(s) {
    el.totalTrades.textContent = s.trades;
    el.totalWR.textContent = s.trades > 0 ? Math.round(s.wins / s.trades * 100) + '%' : '0%';

    const pf = s.grossLoss > 0 ? (s.grossProfit / s.grossLoss) : s.grossProfit > 0 ? 999 : 0;
    el.profitFactor.textContent = pf.toFixed(2);

    el.totalPnl.textContent = fmt.price(s.pnl);
    el.totalPnl.className = 'stat-value ' + (s.pnl >= 0 ? 'positive' : 'negative');
}

function updateEquity(e) {
    el.equity.textContent = fmt.price(e);
}

function addLog(type, message) {
    const line = document.createElement('div');
    line.className = 'log-line ' + type;
    line.textContent = `[${fmt.time()}] ${message}`;
    el.logContainer.insertBefore(line, el.logContainer.firstChild);

    while (el.logContainer.children.length > 100) {
        el.logContainer.removeChild(el.logContainer.lastChild);
    }
}

function addTrade(trade) {
    el.noTrades.style.display = 'none';

    const isLong = trade.direction === 'long' || trade.direction === 'LONG';
    const isProfit = trade.pnl >= 0;

    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${fmt.short(trade.exitTime || trade.exit_time || new Date())}</td>
        <td class="${isLong ? 'side-long' : 'side-short'}">${isLong ? 'LONG' : 'SHORT'}</td>
        <td>${fmt.price(trade.entryPrice || trade.entry_price)}</td>
        <td>${fmt.price(trade.exitPrice || trade.exit_price)}</td>
        <td class="${isProfit ? 'pnl-profit' : 'pnl-loss'}">${fmt.price(trade.pnl)}</td>
    `;
    el.tradeTableBody.insertBefore(row, el.tradeTableBody.firstChild);

    while (el.tradeTableBody.children.length > 50) {
        el.tradeTableBody.removeChild(el.tradeTableBody.lastChild);
    }
}

function updateLastUpdate() {
    el.lastUpdate.textContent = fmt.time();
}

// ============================================
// API CALLS (REST)
// ============================================
async function startTradingWithSymbol(symbol, tf) {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/trading/start?symbol=${symbol}&interval=${tf}`, { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            addLog('', `[OK] Started ${symbol} ${tf}`);
            return true;
        } else {
            addLog('error', `[ERROR] ${data.error || 'Failed to start'}`);
            return false;
        }
    } catch (e) {
        addLog('error', `[ERROR] Server not available: ${e.message}`);
        return false;
    }
}

async function startAllSymbols() {
    const tf = el.timeframeSelect.value;
    addLog('', `Starting all symbols on ${tf}...`);

    try {
        const resp = await fetch(`${API_BASE}/api/v1/trading/start-all?interval=${tf}`, { method: 'POST' });
        const data = await resp.json();

        if (data.results) {
            let started = 0;
            for (const [symbol, result] of Object.entries(data.results)) {
                if (result.success) {
                    started++;
                    addLog('', `[OK] ${symbol}: ${result.status}`);
                } else {
                    addLog('error', `[ERROR] ${symbol}: ${result.status}`);
                }
            }
            addLog('', `Started ${started}/${Object.keys(data.results).length} symbols`);
        }

    } catch (e) {
        addLog('error', `[ERROR] ${e.message}`);
    }
}

async function stopTrading() {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/trading/stop`, { method: 'POST' });
        const data = await resp.json();
        addLog('', `Trading stopped`);
        return true;
    } catch (e) {
        addLog('error', `[ERROR] ${e.message}`);
        return false;
    }
}

async function fetchTradingStatus() {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/trading/status`);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();
        return data;
    } catch (e) {
        console.error('Status fetch error:', e);
        return null;
    }
}

// ============================================
// REST POLLING (replaces WebSocket)
// ============================================
function startPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }

    // Immediate first poll
    pollStatus();

    // Start interval polling
    pollingInterval = setInterval(pollStatus, POLLING_DELAY);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

async function pollStatus() {
    const data = await fetchTradingStatus();

    if (!data) {
        // Connection lost
        if (state.connected) {
            state.connected = false;
            updateConnection(false, 'Connection Lost');
            addLog('error', 'Lost connection to server');
        }
        return;
    }

    // Update connection state
    if (!state.connected) {
        state.connected = true;
        addLog('', `[LIVE] Connected to trading server`);
    }

    updateLastUpdate();

    // Process status data
    handleStatusUpdate(data);
}

function handleStatusUpdate(data) {
    // Handle runners data
    if (data.runners) {
        // Check for new trades by comparing with previous state
        for (const [key, runner] of Object.entries(data.runners)) {
            const prevRunner = state.runners[key];

            // Check for new trades
            if (runner.stats && prevRunner?.stats) {
                if (runner.stats.total_trades > prevRunner.stats.total_trades) {
                    // New trade detected - could fetch trade details if available
                    const pnlDiff = (runner.stats.total_pnl || 0) - (prevRunner.stats.total_pnl || 0);
                    addLog(pnlDiff >= 0 ? 'long' : 'short', `[TRADE] ${key.split('_')[0]}: ${pnlDiff >= 0 ? '+' : ''}${fmt.price(pnlDiff)}`);
                }
            }

            // Log bar progress
            const bars = runner.bars_processed || 0;
            const prevBars = prevRunner?.bars_processed || 0;
            const shortSymbol = key.split('_')[0].replace('USDT', '');

            if (bars > prevBars && bars <= 20 && bars % 5 === 0) {
                addLog('', `[${shortSymbol}] Collecting bars... ${bars}/20`);
            }
            if (bars === 20 && prevBars < 20) {
                addLog('signal', `[${shortSymbol}] Ready for trading!`);
            }

            // Log new signals
            if (runner.signals && runner.signals.length > 0) {
                for (const sig of runner.signals) {
                    const conf = (sig.confidence * 100).toFixed(0);
                    if (sig.type.includes('long')) {
                        addLog('long', `[${shortSymbol}] LONG - ${sig.type} (${conf}%)`);
                    } else if (sig.type.includes('short')) {
                        addLog('short', `[${shortSymbol}] SHORT - ${sig.type} (${conf}%)`);
                    }
                }
            }
        }

        state.runners = data.runners;
        updateMarketCards();

        // Update status badge with active count
        const activeCount = Object.keys(data.runners).length;
        updateConnection(true, `LIVE (${activeCount})`);

        // Update stats for selected symbol
        const selectedKey = `${state.symbol}_${state.timeframe}`;
        if (data.runners[selectedKey]) {
            const runner = data.runners[selectedKey];
            if (runner.stats) {
                state.today.trades = runner.stats.total_trades || 0;
                state.today.wins = runner.stats.winning_trades || 0;
                state.today.losses = (runner.stats.total_trades || 0) - (runner.stats.winning_trades || 0);
                state.today.pnl = runner.stats.total_pnl || 0;
                updateTodayStats(state.today);
                updateAllTimeStats(state.today);

                // Update position
                if (runner.stats.current_position) {
                    const currentPrice = runner.bar?.close || 0;
                    state.position = {
                        direction: (runner.stats.current_position.direction || 'long').toLowerCase(),
                        entryPrice: runner.stats.current_position.entry_price || 0,
                        currentPrice: currentPrice,
                        stopLoss: runner.stats.current_position.stop_loss || 0,
                        takeProfit: runner.stats.current_position.take_profit || 0
                    };
                    updatePosition(state.position);
                } else {
                    state.position = null;
                    updatePosition(null);
                }
            }
        }
    }

    // Update equity/balance
    if (data.balance) {
        state.equity = data.balance;
        updateEquity(state.equity);
    }
}

// ============================================
// CONNECT / DISCONNECT
// ============================================
async function connect() {
    // Get selected values
    state.symbol = el.symbolSelect.value;
    state.timeframe = el.timeframeSelect.value;
    el.currentTF.textContent = state.timeframe;

    updateConnection(false, 'Connecting...');
    addLog('', `Connecting to server...`);

    // Start trading for selected symbol
    const started = await startTradingWithSymbol(state.symbol, state.timeframe);
    if (!started) {
        updateConnection(false, 'Server Offline');
        return;
    }

    // Start polling for status updates
    state.connected = true;
    startPolling();
}

function disconnect() {
    stopPolling();
    state.connected = false;
    updateConnection(false, 'Disconnected');
    addLog('', 'Disconnected');
}

// ============================================
// HELPER FUNCTIONS
// ============================================
function updateSelectedSymbolView() {
    // Update sidebar stats with data from selected symbol
    const selectedKey = `${state.symbol}_${state.timeframe}`;
    const runner = state.runners[selectedKey];

    if (runner && runner.stats) {
        state.today.trades = runner.stats.total_trades || 0;
        state.today.wins = runner.stats.winning_trades || 0;
        state.today.losses = (runner.stats.total_trades || 0) - (runner.stats.winning_trades || 0);
        state.today.pnl = runner.stats.total_pnl || 0;
        updateTodayStats(state.today);
        updateAllTimeStats(state.today);

        if (runner.stats.current_position) {
            const currentPrice = runner.bar?.close || 0;
            state.position = {
                direction: (runner.stats.current_position.direction || 'long').toLowerCase(),
                entryPrice: runner.stats.current_position.entry_price || 0,
                currentPrice: currentPrice,
                stopLoss: runner.stats.current_position.stop_loss || 0,
                takeProfit: runner.stats.current_position.take_profit || 0
            };
            updatePosition(state.position);
        } else {
            state.position = null;
            updatePosition(null);
        }
    } else {
        // Reset stats if no data
        state.today = { trades: 0, wins: 0, losses: 0, pnl: 0 };
        updateTodayStats(state.today);
        updateAllTimeStats(state.today);
        state.position = null;
        updatePosition(null);
    }
}

// ============================================
// INIT
// ============================================
el.connectBtn.addEventListener('click', () => {
    if (state.connected) {
        disconnect();
    } else {
        connect();
    }
});

el.startAllBtn.addEventListener('click', startAllSymbols);

// Symbol change handler
el.symbolSelect.addEventListener('change', async () => {
    state.symbol = el.symbolSelect.value;
    addLog('', `Switched to ${state.symbol}`);

    // Immediately update view with cached data for this symbol
    updateSelectedSymbolView();
    updateMarketCards();

    // Start trading for this symbol if not already running
    await startTradingWithSymbol(state.symbol, state.timeframe);
});

// Timeframe change handler
el.timeframeSelect.addEventListener('change', async () => {
    state.timeframe = el.timeframeSelect.value;
    el.currentTF.textContent = state.timeframe;
    addLog('', `Switched to ${state.timeframe}`);

    // Start all symbols on new timeframe
    await startAllSymbols();
});

// Initialize UI
updateConnection(false, 'Ready');
updatePosition(null);
updateTodayStats(state.today);
updateAllTimeStats(state.allTime);
updateEquity(0);
updateMarketCards();

// Auto-connect on load
addLog('', 'OIE Multi-Symbol Trading Dashboard');
addLog('', 'Connecting to server...');
setTimeout(connect, 1000);
