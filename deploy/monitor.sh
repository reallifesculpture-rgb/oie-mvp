#!/bin/bash
# =============================================================================
# OIE Trading Bot - Monitoring Script
# =============================================================================
# Run as cron job: */5 * * * * /opt/oie-trading-bot/deploy/monitor.sh
# =============================================================================

APP_DIR="/opt/oie-trading-bot"
LOG_FILE="$APP_DIR/logs/monitor.log"
HEALTH_URL="http://localhost:8000/health"
STATUS_URL="http://localhost:8000/api/v1/trading/status"

# Telegram notification (optional - set your bot token and chat ID)
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

send_telegram() {
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$1" \
            -d parse_mode="HTML" > /dev/null
    fi
}

# Check if container is running
if ! docker compose -f $APP_DIR/docker-compose.yml ps | grep -q "Up"; then
    log "ALERT: Container is DOWN! Attempting restart..."
    send_telegram "🚨 <b>OIE Trading Bot DOWN!</b>\nAttempting automatic restart..."

    cd $APP_DIR
    docker compose up -d
    sleep 10

    if docker compose ps | grep -q "Up"; then
        log "Container restarted successfully"
        send_telegram "✅ <b>OIE Trading Bot RECOVERED</b>\nContainer restarted successfully."
    else
        log "CRITICAL: Container failed to restart!"
        send_telegram "🔴 <b>CRITICAL: Container failed to restart!</b>\nManual intervention required."
    fi
    exit 1
fi

# Health check
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL 2>/dev/null)

if [ "$HEALTH_RESPONSE" != "200" ]; then
    log "ALERT: Health check failed (HTTP $HEALTH_RESPONSE)"
    send_telegram "⚠️ <b>Health check failed!</b>\nHTTP Status: $HEALTH_RESPONSE"

    # Restart container
    cd $APP_DIR
    docker compose restart
    sleep 10

    RETRY_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL 2>/dev/null)
    if [ "$RETRY_RESPONSE" == "200" ]; then
        log "Health restored after restart"
        send_telegram "✅ <b>Health restored</b>\nBot is running again."
    fi
fi

# Check trading status (optional detailed check)
STATUS=$(curl -s $STATUS_URL 2>/dev/null)
if [ -n "$STATUS" ]; then
    # Check if any runners are active
    ACTIVE_COUNT=$(echo $STATUS | grep -o '"running":true' | wc -l)
    if [ "$ACTIVE_COUNT" -eq 0 ]; then
        log "WARNING: No active trading sessions"
        # Don't alert on this - might be intentional
    fi
fi

# Log memory usage
MEMORY=$(docker stats --no-stream --format "{{.MemUsage}}" oie-trading-bot 2>/dev/null)
if [ -n "$MEMORY" ]; then
    log "Memory usage: $MEMORY"
fi
