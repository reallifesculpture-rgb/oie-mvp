# OIE Trading Bot - Deployment Guide

## Quick Start (5 minute deploy)

### 1. Get a VPS

**Recommended: Hetzner Cloud CAX11** (~$4/month)
- 2 vCPU, 4GB RAM, 40GB SSD
- Go to: https://www.hetzner.com/cloud
- Create account and new server with Ubuntu 22.04

**Alternatives:**
- DigitalOcean $6/month: https://www.digitalocean.com
- Vultr $6/month: https://www.vultr.com
- AWS Free Tier (12 months): https://aws.amazon.com/free

### 2. Connect to Server

```bash
ssh root@YOUR_SERVER_IP
```

### 3. Run Setup Script

```bash
# Download and run setup
curl -sSL https://raw.githubusercontent.com/YOUR_REPO/main/deploy/setup-server.sh | bash

# Or manually:
apt update && apt install -y docker.io docker-compose-plugin git
```

### 4. Deploy the Bot

```bash
# Clone your repository
cd /opt
git clone https://github.com/YOUR_REPO/oie-mvp.git oie-trading-bot
cd oie-trading-bot

# Create .env file with API keys
cat > .env << 'EOF'
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_SECRET=your_secret_key_here
EOF

# Start the bot
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

### 5. Enable Auto-Start on Boot

```bash
# Copy systemd service
sudo cp deploy/oie-trading-bot.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable oie-trading-bot
sudo systemctl start oie-trading-bot

# Check status
sudo systemctl status oie-trading-bot
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              VPS (Hetzner/DO)               │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │     Docker Container: trading-bot     │  │
│  │                                       │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │    FastAPI + Uvicorn            │  │  │
│  │  │    - REST API (:8000)           │  │  │
│  │  │    - WebSocket connections      │  │  │
│  │  │    - Binance API client         │  │  │
│  │  └─────────────────────────────────┘  │  │
│  │                                       │  │
│  │  Auto-restart: always                 │  │
│  │  Health check: every 60s              │  │
│  └───────────────────────────────────────┘  │
│              ▲                              │
│              │ managed by                   │
│  ┌───────────┴────────────┐                 │
│  │   systemd service      │                 │
│  │   (auto-start on boot) │                 │
│  └────────────────────────┘                 │
│                                             │
│  Volumes:                                   │
│  - /opt/oie-trading-bot/logs                │
│  - /opt/oie-trading-bot/results             │
└─────────────────────────────────────────────┘
```

---

## Commands Reference

### Docker Commands

```bash
# Start bot
docker compose up -d

# Stop bot
docker compose down

# View logs (follow)
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# Restart bot
docker compose restart

# Rebuild after code changes
docker compose build --no-cache && docker compose up -d

# Check resource usage
docker stats oie-trading-bot
```

### Systemd Commands

```bash
# Check status
sudo systemctl status oie-trading-bot

# Start service
sudo systemctl start oie-trading-bot

# Stop service
sudo systemctl stop oie-trading-bot

# Restart service
sudo systemctl restart oie-trading-bot

# View logs
sudo journalctl -u oie-trading-bot -f
```

### Monitoring

```bash
# System resources
htop

# Disk usage
df -h

# Docker disk usage
docker system df

# Clean unused Docker resources
docker system prune -a
```

---

## Updating the Bot

### Option 1: Git Pull (Recommended)

```bash
cd /opt/oie-trading-bot
git pull origin main
docker compose build
docker compose up -d
```

### Option 2: Manual Upload

```bash
# On your local machine
scp -r ./oie_mvp/* root@YOUR_SERVER:/opt/oie-trading-bot/

# On server
cd /opt/oie-trading-bot
docker compose build
docker compose up -d
```

### Option 3: Using deploy.sh

```bash
./deploy/deploy.sh --build
```

---

## Monitoring & Alerts

### 1. UptimeRobot (Free)

1. Go to https://uptimerobot.com
2. Create free account
3. Add new monitor:
   - Type: HTTP(s)
   - URL: `http://YOUR_SERVER_IP:8000/health`
   - Interval: 5 minutes
4. Setup email/Telegram alerts

### 2. Health Check Endpoint

The bot exposes a health endpoint at `GET /health`:

```json
{
  "status": "ok"
}
```

### 3. Check Trading Status

```bash
# API endpoint
curl http://YOUR_SERVER_IP:8000/api/v1/trading/status

# Or access dashboard in browser
http://YOUR_SERVER_IP:8000
```

---

## Security Checklist

- [ ] Change SSH port (optional but recommended)
- [ ] Setup SSH key authentication
- [ ] Disable password login
- [ ] Enable UFW firewall
- [ ] Keep system updated
- [ ] Never commit .env to git

### SSH Key Setup

```bash
# On your local machine
ssh-keygen -t ed25519 -C "your_email@example.com"
ssh-copy-id root@YOUR_SERVER_IP

# On server - disable password login
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### Firewall Rules

```bash
sudo ufw status
sudo ufw allow ssh
sudo ufw allow 8000/tcp
sudo ufw enable
```

---

## Troubleshooting

### Bot not starting

```bash
# Check container logs
docker compose logs --tail=100

# Check if port is in use
sudo netstat -tulpn | grep 8000

# Restart Docker service
sudo systemctl restart docker
```

### WebSocket disconnections

The bot has built-in reconnection logic. Check logs for:
```bash
docker compose logs | grep -i "websocket\|reconnect"
```

### High memory usage

```bash
# Check memory
free -h
docker stats

# Restart container
docker compose restart
```

### Disk full

```bash
# Check disk
df -h

# Clean Docker
docker system prune -a

# Clean old logs
sudo find /opt/oie-trading-bot/logs -mtime +7 -delete
```

---

## Backup & Recovery

### Backup

```bash
# Backup trading results and config
tar -czvf oie-backup-$(date +%Y%m%d).tar.gz \
    /opt/oie-trading-bot/results \
    /opt/oie-trading-bot/.env

# Download to local
scp root@YOUR_SERVER:/root/oie-backup-*.tar.gz ./
```

### Restore

```bash
# Upload backup
scp ./oie-backup-20241222.tar.gz root@YOUR_SERVER:/tmp/

# Restore
cd /opt/oie-trading-bot
tar -xzvf /tmp/oie-backup-20241222.tar.gz
docker compose restart
```

---

## Cost Summary

| Provider | Plan | Monthly Cost | Specs |
|----------|------|--------------|-------|
| **Hetzner** | CAX11 | ~$4 | 2 vCPU, 4GB RAM, 40GB SSD |
| DigitalOcean | Basic | $6 | 1 vCPU, 1GB RAM, 25GB SSD |
| Vultr | Cloud | $6 | 1 vCPU, 1GB RAM, 25GB SSD |
| AWS | t3.micro | Free (12mo) | 2 vCPU, 1GB RAM |

**Recommended: Hetzner CAX11** - Best value for 24/7 trading bots.

---

## Support

- Check logs: `docker compose logs -f`
- Health endpoint: `GET /health`
- Trading status: `GET /api/v1/trading/status`
- Dashboard: `http://YOUR_SERVER:8000`
