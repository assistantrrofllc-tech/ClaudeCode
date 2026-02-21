#!/usr/bin/env bash
#
# CrewLedger — Database & Receipt Backup Script
# Backs up SQLite DB and receipt images to timestamped archive
#
# Usage:  sudo bash /opt/crewledger/deploy/backup.sh
# Cron:   0 2 * * * /opt/crewledger/deploy/backup.sh
#
set -euo pipefail

APP_DIR="/opt/crewledger"
BACKUP_DIR="/opt/crewledger/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/crewledger_${TIMESTAMP}.tar.gz"
KEEP_DAYS=30

mkdir -p "${BACKUP_DIR}"

echo "Backing up CrewLedger data..."

# Use SQLite backup command for safe copy while app is running
sqlite3 "${APP_DIR}/data/crewledger.db" ".backup '${BACKUP_DIR}/crewledger_${TIMESTAMP}.db'"

# Archive DB backup + receipt images
tar -czf "${BACKUP_FILE}" \
    -C "${BACKUP_DIR}" "crewledger_${TIMESTAMP}.db" \
    -C "${APP_DIR}" "storage/receipts"

# Clean up temp DB copy
rm -f "${BACKUP_DIR}/crewledger_${TIMESTAMP}.db"

# Remove backups older than KEEP_DAYS
find "${BACKUP_DIR}" -name "crewledger_*.tar.gz" -mtime +${KEEP_DAYS} -delete

SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup complete: ${BACKUP_FILE} (${SIZE})"
