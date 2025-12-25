#!/bin/bash
# =============================================================================
# OIE Trading Bot - Deployment Script
# =============================================================================
# Run this script to deploy or update the trading bot
# Usage: ./deploy.sh [--build] [--restart]
# =============================================================================

set -e

APP_DIR="/opt/oie-trading-bot"
SERVICE_NAME="oie-trading-bot"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
BUILD=false
RESTART=false
for arg in "$@"; do
    case $arg in
        --build) BUILD=true ;;
        --restart) RESTART=true ;;
    esac
done

echo "=============================================="
echo "OIE Trading Bot - Deployment"
echo "=============================================="

cd $APP_DIR

# Check if .env exists
if [ ! -f ".env" ]; then
    log_error ".env file not found! Create it with your API keys."
    echo ""
    echo "Example .env file:"
    echo "BINANCE_TESTNET_API_KEY=your_api_key"
    echo "BINANCE_TESTNET_SECRET=your_secret_key"
    exit 1
fi

# Pull latest code (if using git)
if [ -d ".git" ]; then
    log_info "Pulling latest code..."
    git pull origin main
fi

# Build if requested
if [ "$BUILD" = true ]; then
    log_info "Building Docker image..."
    docker compose build --no-cache
fi

# Stop current container if running
if docker compose ps | grep -q "Up"; then
    log_info "Stopping current container..."
    docker compose down
fi

# Start container
log_info "Starting trading bot..."
docker compose up -d

# Wait for health check
log_info "Waiting for health check..."
sleep 10

# Check if container is running
if docker compose ps | grep -q "Up"; then
    log_info "Trading bot is running!"

    # Show status
    echo ""
    echo "Container Status:"
    docker compose ps

    echo ""
    echo "Recent Logs:"
    docker compose logs --tail=20

    echo ""
    log_info "Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
else
    log_error "Container failed to start!"
    echo ""
    echo "Logs:"
    docker compose logs --tail=50
    exit 1
fi

# Restart if requested
if [ "$RESTART" = true ]; then
    log_info "Restarting systemd service..."
    sudo systemctl restart $SERVICE_NAME
fi

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
