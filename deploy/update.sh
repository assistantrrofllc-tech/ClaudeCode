#!/usr/bin/env bash
#
# CrewLedger — Quick Update Script
# Pull latest code and restart the app (run on VPS as root)
#
# Usage: bash /opt/crewledger/deploy/update.sh
#
set -euo pipefail

APP_DIR="/opt/crewledger"
BRANCH="main"

echo "Fixing permissions..."
chown -R crewledger:crewledger "${APP_DIR}/"

echo "Pulling latest code..."
cd "${APP_DIR}"
su -s /bin/bash crewledger -c "git fetch origin ${BRANCH} && git reset --hard origin/${BRANCH}"

echo "Updating Python packages..."
source "${APP_DIR}/venv/bin/activate"
pip install -r requirements.txt -q

echo "Restarting CrewLedger..."
systemctl restart crewledger

echo "Checking health..."
sleep 3
if curl -sf http://127.0.0.1:5000/health | grep -q '"ok"'; then
    echo "CrewLedger updated and running!"
else
    echo "WARNING: Health check failed. Check logs:"
    journalctl -u crewledger -n 20 --no-pager
    exit 1
fi
