#!/usr/bin/env bash
#
# CrewLedger — Quick Update Script
# Pull latest code and restart the app (run on VPS)
#
# Usage: sudo bash /opt/crewledger/deploy/update.sh
#
set -euo pipefail

APP_DIR="/opt/crewledger"
BRANCH="main"

echo "Pulling latest code..."
cd "${APP_DIR}"
sudo -u crewledger git fetch origin ${BRANCH}
sudo -u crewledger git reset --hard origin/${BRANCH}

echo "Updating Python packages..."
source "${APP_DIR}/venv/bin/activate"
pip install -r requirements.txt -q

echo "Restarting CrewLedger..."
systemctl restart crewledger

echo "Checking health..."
sleep 2
if curl -s http://127.0.0.1:5000/health | grep -q '"ok"'; then
    echo "CrewLedger updated and running!"
else
    echo "WARNING: Health check failed. Check logs:"
    echo "  journalctl -u crewledger -n 20"
fi
