#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  FLOW Production Deployment Script
#  Installs Nginx, Certbot, Redis, Gunicorn — configures everything.
#  Run as root on a fresh Ubuntu 22.04+ server.
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

DOMAIN="${1:?Usage: $0 <your-domain.com>}"
APP_DIR="/opt/flow"
FRONTEND_DIR="/var/www/flow/frontend/dist"
BACKEND_DIR="$APP_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"

echo "═══════════════════════════════════════════════════"
echo "  FLOW Production Setup — $DOMAIN"
echo "═══════════════════════════════════════════════════"

# ── 1. System packages ────────────────────────────────────────────────────
echo "[1/8] Installing system packages..."
apt update && apt install -y \
    nginx certbot python3-certbot-nginx \
    redis-server \
    python3.11 python3.11-venv python3-pip \
    build-essential libffi-dev \
    ufw fail2ban

# ── 2. Firewall ──────────────────────────────────────────────────────────
echo "[2/8] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

# ── 3. Redis ─────────────────────────────────────────────────────────────
echo "[3/8] Configuring Redis..."
# Bind to localhost only, no external access
sed -i 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
# Set memory limit
echo "maxmemory 256mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
systemctl restart redis-server
systemctl enable redis-server

# ── 4. Python virtual environment + dependencies ─────────────────────────
echo "[4/8] Setting up Python environment..."
mkdir -p "$APP_DIR"
# Copy project files here (or git clone)
# cp -r /path/to/FLOW/* "$APP_DIR/"

cd "$BACKEND_DIR"
python3.11 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# ── 5. Systemd service for Gunicorn ─────────────────────────────────────
echo "[5/8] Creating systemd service..."
cat > /etc/systemd/system/flow.service << EOF
[Unit]
Description=FLOW RPG Backend (Gunicorn + Uvicorn)
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$BACKEND_DIR/.env

ExecStart=$VENV_DIR/bin/gunicorn main:app \\
    --workers 4 \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --bind 127.0.0.1:8000 \\
    --timeout 30 \\
    --graceful-timeout 10 \\
    --max-requests 1000 \\
    --max-requests-jitter 50 \\
    --access-logfile /var/log/flow/access.log \\
    --error-logfile /var/log/flow/error.log \\
    --log-level warning

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$BACKEND_DIR /var/log/flow
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /var/log/flow
chown www-data:www-data /var/log/flow

systemctl daemon-reload
systemctl enable flow.service

# ── 6. Build frontend ───────────────────────────────────────────────────
echo "[6/8] Building frontend..."
mkdir -p "$FRONTEND_DIR"
cd "$APP_DIR/frontend"
npm ci --production=false
npm run build
cp -r dist/* "$FRONTEND_DIR/"
chown -R www-data:www-data "$FRONTEND_DIR"

# ── 7. Nginx configuration ──────────────────────────────────────────────
echo "[7/8] Configuring Nginx..."
# Replace domain placeholder in config
cp "$APP_DIR/deploy/nginx/flow.conf" /etc/nginx/sites-available/flow.conf
sed -i "s/YOUR_DOMAIN.com/$DOMAIN/g" /etc/nginx/sites-available/flow.conf

ln -sf /etc/nginx/sites-available/flow.conf /etc/nginx/sites-enabled/flow.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx

# ── 8. SSL Certificate (Let's Encrypt) ──────────────────────────────────
echo "[8/8] Obtaining SSL certificate..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN"

# Set up automatic renewal
systemctl enable certbot.timer

# ── Post-setup ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  FLOW deployment complete!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Domain:  https://$DOMAIN"
echo "  Backend: Gunicorn on 127.0.0.1:8000"
echo "  Redis:   127.0.0.1:6379 (localhost only)"
echo "  Logs:    /var/log/flow/ + /var/log/nginx/"
echo ""
echo "  Commands:"
echo "    systemctl status flow        # Check backend"
echo "    systemctl restart flow       # Restart backend"
echo "    journalctl -u flow -f        # Tail logs"
echo "    certbot renew --dry-run      # Test SSL renewal"
echo ""
echo "  IMPORTANT: Update $BACKEND_DIR/.env with:"
echo "    REDIS_URL=redis://127.0.0.1:6379/0"
echo "    ALLOWED_ORIGINS=[\"https://$DOMAIN\"]"
echo "    DEBUG=False"
echo ""
