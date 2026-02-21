#!/usr/bin/env bash
#
# CrewLedger — Automated VPS Deployment Script
# Target: Hostinger KVM 2 VPS (Ubuntu 22.04/24.04)
# Hostname: srv1306217.hstgr.cloud
#
# Usage:
#   1. SSH into your VPS:  ssh root@srv1306217.hstgr.cloud
#   2. Upload this script: scp deploy/setup.sh root@srv1306217.hstgr.cloud:~
#   3. Run it:             bash setup.sh
#
# What this script does:
#   - Installs system dependencies (Python 3.11, Nginx, Certbot)
#   - Creates a dedicated crewledger user
#   - Clones the repo to /opt/crewledger
#   - Sets up Python virtual environment + installs packages
#   - Initializes the SQLite database with sample projects
#   - Configures Nginx reverse proxy with HTTPS (Let's Encrypt)
#   - Creates systemd service for auto-start on boot
#   - Sets up log rotation and weekly report cron job
#
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
DOMAIN="srv1306217.hstgr.cloud"
APP_DIR="/opt/crewledger"
REPO_URL="https://github.com/assistantrrofllc-tech/ClaudeCode.git"
BRANCH="main"
PYTHON_VERSION="3.11"
LOG_DIR="/var/log/crewledger"
CERTBOT_EMAIL=""  # Set your email for Let's Encrypt notifications

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

# ─── Pre-flight checks ──────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root. Use: sudo bash setup.sh"
fi

step "Step 1/10 — System Update"
apt-get update -qq
apt-get upgrade -y -qq
log "System packages updated"

step "Step 2/10 — Install Dependencies"
apt-get install -y -qq \
    software-properties-common \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    curl \
    ufw \
    sqlite3 \
    build-essential
log "All system dependencies installed"

# Ensure python3.11 is the default python3 if needed
if ! command -v python${PYTHON_VERSION} &> /dev/null; then
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y -qq python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev
fi
log "Python ${PYTHON_VERSION} ready"

step "Step 3/10 — Firewall Configuration"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
log "Firewall configured (SSH + HTTP/HTTPS)"

step "Step 4/10 — Create Application User"
if ! id "crewledger" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir ${APP_DIR} crewledger
    log "Created system user: crewledger"
else
    log "User crewledger already exists"
fi

step "Step 5/10 — Clone Repository"
if [[ -d "${APP_DIR}/.git" ]]; then
    warn "Repository already exists at ${APP_DIR}. Pulling latest..."
    cd "${APP_DIR}"
    git fetch origin ${BRANCH}
    git reset --hard origin/${BRANCH}
    log "Updated to latest ${BRANCH}"
else
    rm -rf "${APP_DIR}"
    git clone --branch ${BRANCH} "${REPO_URL}" "${APP_DIR}"
    log "Cloned repository to ${APP_DIR}"
fi
cd "${APP_DIR}"

step "Step 6/10 — Python Virtual Environment"
python${PYTHON_VERSION} -m venv "${APP_DIR}/venv"
source "${APP_DIR}/venv/bin/activate"
pip install --upgrade pip wheel setuptools -q
pip install -r requirements.txt -q
pip install gunicorn -q
log "Virtual environment created and packages installed"

step "Step 7/10 — Application Setup"

# Create required directories
mkdir -p "${APP_DIR}/data"
mkdir -p "${APP_DIR}/storage/receipts"
mkdir -p "${LOG_DIR}"
mkdir -p /run/crewledger
mkdir -p /var/www/certbot

# Set up .env file
if [[ ! -f "${APP_DIR}/.env" ]]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    # Generate a random SECRET_KEY
    SECRET_KEY=$(python${PYTHON_VERSION} -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change_this_to_a_random_secret_key/${SECRET_KEY}/" "${APP_DIR}/.env"
    sed -i "s/APP_DEBUG=false/APP_DEBUG=false/" "${APP_DIR}/.env"
    warn ".env file created from template — YOU MUST EDIT IT with your API keys:"
    warn "   nano ${APP_DIR}/.env"
else
    log ".env file already exists"
fi

# Initialize database
python scripts/setup_db.py --seed
log "Database initialized with sample projects"

# Set ownership
chown -R crewledger:crewledger "${APP_DIR}"
chown -R crewledger:crewledger "${LOG_DIR}"
chown -R crewledger:crewledger /run/crewledger
log "File permissions set"

step "Step 8/10 — Systemd Service"
cp "${APP_DIR}/deploy/crewledger.service" /etc/systemd/system/crewledger.service
systemctl daemon-reload
systemctl enable crewledger
log "Systemd service installed and enabled"

step "Step 9/10 — Nginx + SSL"

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Install initial HTTP-only config (for certbot challenge)
cat > /etc/nginx/sites-available/crewledger <<'NGINX_TEMP'
server {
    listen 80;
    listen [::]:80;
    server_name srv1306217.hstgr.cloud;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_TEMP

ln -sf /etc/nginx/sites-available/crewledger /etc/nginx/sites-enabled/crewledger
nginx -t && systemctl restart nginx
log "Nginx configured (HTTP)"

# Obtain SSL certificate
if [[ -n "${CERTBOT_EMAIL}" ]]; then
    certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect
    log "SSL certificate obtained and installed"
else
    warn "CERTBOT_EMAIL not set — skipping SSL. To add HTTPS later run:"
    warn "   certbot --nginx -d ${DOMAIN} --agree-tos -m your@email.com --redirect"
fi

# Install full Nginx config (with SSL if cert exists)
if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    cp "${APP_DIR}/deploy/nginx/crewledger.conf" /etc/nginx/sites-available/crewledger
    nginx -t && systemctl reload nginx
    log "Full Nginx config with SSL installed"
fi

step "Step 10/10 — Start Application"
systemctl start crewledger

# Set up log rotation
cat > /etc/logrotate.d/crewledger <<'LOGROTATE'
/var/log/crewledger/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 crewledger crewledger
    postrotate
        systemctl reload crewledger > /dev/null 2>&1 || true
    endscript
}
LOGROTATE
log "Log rotation configured"

# Set up weekly report cron job (Monday 8am)
(crontab -u crewledger -l 2>/dev/null; echo "0 8 * * 1 curl -s -X POST http://127.0.0.1:5000/reports/weekly/send > /dev/null 2>&1") | sort -u | crontab -u crewledger -
log "Weekly report cron job set (Monday 8:00 AM)"

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  CrewLedger deployed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  App URL:       http://${DOMAIN}"
echo -e "  Health check:  http://${DOMAIN}/health"
echo -e "  Webhook URL:   http://${DOMAIN}/webhook/sms"
echo -e "  Report preview: http://${DOMAIN}/reports/weekly/preview"
echo ""
echo -e "  App directory: ${APP_DIR}"
echo -e "  Config file:   ${APP_DIR}/.env"
echo -e "  Database:      ${APP_DIR}/data/crewledger.db"
echo -e "  Receipts:      ${APP_DIR}/storage/receipts/"
echo -e "  Logs:          ${LOG_DIR}/"
echo ""
echo -e "${YELLOW}  NEXT STEPS:${NC}"
echo -e "  1. Edit your .env file with real API keys:"
echo -e "     ${BLUE}nano ${APP_DIR}/.env${NC}"
echo -e ""
echo -e "  2. Add your Twilio, OpenAI, and SMTP credentials"
echo -e ""
echo -e "  3. Restart after editing .env:"
echo -e "     ${BLUE}systemctl restart crewledger${NC}"
echo -e ""
echo -e "  4. Set up SSL (if not done above):"
echo -e "     ${BLUE}certbot --nginx -d ${DOMAIN} --agree-tos -m your@email.com --redirect${NC}"
echo -e ""
echo -e "  5. Configure Twilio webhook URL to:"
echo -e "     ${BLUE}https://${DOMAIN}/webhook/sms${NC}"
echo ""
echo -e "${GREEN}  Management commands:${NC}"
echo -e "  systemctl status crewledger     # Check app status"
echo -e "  systemctl restart crewledger    # Restart app"
echo -e "  journalctl -u crewledger -f     # Live logs"
echo -e "  tail -f ${LOG_DIR}/error.log    # Error log"
echo -e "  sqlite3 ${APP_DIR}/data/crewledger.db  # Query database"
echo ""
