/**
 * OIE MVP - Multi-Symbol Trading Dashboard
 * JavaScript for LIVE paper trading UI (no demo/mock data)
 */

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

let ws = null;
let reconnectTimeout = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY = 3000;

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
// API CALLS
// ============================================
async function startTradingWithSymbol(symbol, tf) {
    try {
        const resp = await fetch(`http://127.0.0.1:8000/api/v1/trading/start?symbol=${symbol}&interval=${tf}`, { method: 'POST' });
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
        const resp = await fetch(`http://127.0.0.1:8000/api/v1/trading/start-all?interval=${tf}`, { method: 'POST' });
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

        // Reconnect WebSocket to get updates from all symbols
        if (ws) ws.close();
        setTimeout(connect, 500);

    } catch (e) {
        addLog('error', `[ERROR] ${e.message}`);
    }
}

// ============================================
// WEBSOCKET - LIVE ONLY
// ============================================
async function connect() {
    // Clear any pending reconnect
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }

    // If already connected, disconnect
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
        state.connected = false;
        updateConnection(false);
        return;
    }

    // Get selected values
    state.symbol = el.symbolSelect.value;
    state.timeframe = el.timeframeSelect.value;
    el.currentTF.textContent = state.timeframe;

    updateConnection(false, 'Connecting...');
    addLog('', `Connecting to LIVE server...`);

    // Start trading for selected symbol
    const started = await startTradingWithSymbol(state.symbol, state.timeframe);
    if (!started) {
        updateConnection(false, 'Server Offline');
        scheduleReconnect();
        return;
    }

    try {
        ws = new WebSocket('ws://127.0.0.1:8000/ws/live');

        ws.onopen = () => {
            state.connected = true;
            reconnectAttempts = 0;
            updateConnection(true, `LIVE`);
            addLog('', `[LIVE] Connected to trading server`);
        };

        ws.onclose = (event) => {
            state.connected = false;
            if (event.wasClean) {
                updateConnection(false, 'Disconnected');
                addLog('', 'Disconnected from server');
            } else {
                updateConnection(false, 'Connection Lost');
                addLog('error', 'Connection lost - will retry...');
                scheduleReconnect();
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            addLog('error', 'WebSocket error occurred');
        };

        ws.onmessage = (e) => {
            try {
                handleMessage(JSON.parse(e.data));
            } catch (err) {
                console.error('Parse error:', err);
            }
        };
    } catch (err) {
        addLog('error', `Connection failed: ${err.message}`);
        updateConnection(false, 'Connection Failed');
        scheduleReconnect();
    }
}

function scheduleReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        addLog('error', 'Max reconnect attempts reached. Click Connect to retry.');
        updateConnection(false, 'Offline');
        return;
    }

    reconnectAttempts++;
    const delay = RECONNECT_DELAY * Math.min(reconnectAttempts, 5);
    addLog('', `Reconnecting in ${delay / 1000}s (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);

    reconnectTimeout = setTimeout(() => {
        connect();
    }, delay);
}

function handleMessage(data) {
    updateLastUpdate();

    // Handle init message with all runners
    if (data.type === 'init' || data.type === 'heartbeat') {
        if (data.runners) {
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
                }
            }
        }

        if (data.balance) {
            state.equity = data.balance;
            updateEquity(state.equity);
        }
    }

    // Handle live trading updates from broadcast
    if (data.type === 'update') {
        // Store runner data
        const updateSymbol = data.symbol || state.symbol;
        const updateInterval = data.interval || state.timeframe;
        const key = `${updateSymbol}_${updateInterval}`;

        if (!state.runners[key]) {
            state.runners[key] = {};
        }
        if (data.bar) state.runners[key].bar = data.bar;
        if (data.bars_processed !== undefined) state.runners[key].bars_processed = data.bars_processed;
        if (data.stats) state.runners[key].stats = data.stats;
        if (data.topology) state.runners[key].topology = data.topology;
        if (data.predictive) state.runners[key].predictive = data.predictive;

        // Update all market cards
        updateMarketCards();

        // Only update sidebar stats if this is the SELECTED symbol
        const selectedKey = `${state.symbol}_${state.timeframe}`;
        if (key === selectedKey && data.stats) {
            state.today.trades = data.stats.total_trades || 0;
            state.today.wins = data.stats.winning_trades || 0;
            state.today.losses = (data.stats.total_trades || 0) - (data.stats.winning_trades || 0);
            state.today.pnl = data.stats.total_pnl || 0;
            updateTodayStats(state.today);
            updateAllTimeStats(state.today);

            if (data.stats.current_position) {
                const currentPrice = data.bar?.close || 0;
                state.position = {
                    direction: (data.stats.current_position.direction || 'long').toLowerCase(),
                    entryPrice: data.stats.current_position.entry_price || 0,
                    currentPrice: currentPrice,
                    stopLoss: data.stats.current_position.stop_loss || 0,
                    takeProfit: data.stats.current_position.take_profit || 0
                };
                updatePosition(state.position);
            } else {
                state.position = null;
                updatePosition(null);
            }
        }

        // Log bar progress every 5 bars
        const bars = data.bars_processed || 0;
        const shortSymbol = updateSymbol.replace('USDT', '');
        if (bars > 0 && bars <= 20 && bars % 5 === 0) {
            addLog('', `[${shortSymbol}] Collecting bars... ${bars}/20`);
        }
        if (bars === 20) {
            addLog('signal', `[${shortSymbol}] Ready for trading!`);
        }

        // Log signals and vortexes (show for all symbols in activity log)
        if (data.topology?.vortexes?.length > 0) {
            const v = data.topology.vortexes.slice(-1)[0];
            addLog('signal', `[${shortSymbol}] Vortex: ${v.direction} (${v.strength.toFixed(2)})`);
        }

        if (data.signals && data.signals.length > 0) {
            for (const sig of data.signals) {
                const conf = (sig.confidence * 100).toFixed(0);
                if (sig.type.includes('long')) {
                    addLog('long', `[${shortSymbol}] LONG - ${sig.type} (${conf}%)`);
                } else if (sig.type.includes('short')) {
                    addLog('short', `[${shortSymbol}] SHORT - ${sig.type} (${conf}%)`);
                }
            }
        }

        if (data.balance) {
            state.equity = data.balance;
            updateEquity(state.equity);
        }
    }

    // Handle trade events
    if (data.type === 'trade' && data.trade) {
        addTrade(data.trade);
        const pnl = data.trade.pnl || 0;
        addLog(pnl >= 0 ? 'long' : 'short', `[TRADE] Closed: ${pnl >= 0 ? '+' : ''}${fmt.price(pnl)}`);
    }

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
        if (ws) ws.close();
        state.connected = false;
        updateConnection(false);
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }
        reconnectAttempts = 0;
    } else {
        reconnectAttempts = 0;
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
