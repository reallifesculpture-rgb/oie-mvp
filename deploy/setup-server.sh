#!/bin/bash
# =============================================================================
# OIE Trading Bot - Server Setup Script
# =============================================================================
# Run this script on a fresh Ubuntu 22.04 VPS
# Usage: curl -sSL https://your-url/setup-server.sh | bash
# Or: bash setup-server.sh
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "OIE Trading Bot - Server Setup"
echo "=============================================="

# Update system
echo "[1/8] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
echo "[2/8] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installed successfully"
else
    echo "Docker already installed"
fi

# Install Docker Compose plugin
echo "[3/8] Installing Docker Compose..."
sudo apt-get install -y docker-compose-plugin

# Create application directory
echo "[4/8] Creating application directory..."
sudo mkdir -p /opt/oie-trading-bot
sudo chown $USER:$USER /opt/oie-trading-bot

# Setup firewall
echo "[5/8] Configuring firewall..."
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8000/tcp  # Trading bot API
# sudo ufw allow 80/tcp   # HTTP (uncomment if using nginx)
# sudo ufw allow 443/tcp  # HTTPS (uncomment if using nginx)
sudo ufw --force enable

# Install useful tools
echo "[6/8] Installing additional tools..."
sudo apt-get install -y \
    htop \
    curl \
    wget \
    git \
    nano \
    logrotate

# Setup log rotation
echo "[7/8] Configuring log rotation..."
sudo tee /etc/logrotate.d/oie-trading-bot > /dev/null << 'EOF'
/opt/oie-trading-bot/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

# Create directories
echo "[8/8] Creating directories..."
mkdir -p /opt/oie-trading-bot/{logs,results,deploy}

echo ""
echo "=============================================="
echo "Server setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Upload your code to /opt/oie-trading-bot/"
echo "2. Create .env file with API keys"
echo "3. Run: docker compose up -d"
echo "4. Enable systemd service: sudo systemctl enable oie-trading-bot"
echo ""
echo "IMPORTANT: Log out and log back in for Docker permissions to take effect"
echo ""
