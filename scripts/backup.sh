#\!/bin/bash
# CrewOS Nightly Backup — DB + storage, 7-day rotation
# Runs via cron: 0 3 * * * /opt/crewledger/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="/opt/crewledger/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7
LOG="/var/log/crewledger/backup.log"

mkdir -p "$BACKUP_DIR"

echo "[$TIMESTAMP] Starting backup..." >> "$LOG"

# Backup SQLite database (safe copy while running)
DB_PATH="/opt/crewledger/data/crewledger.db"
if [ -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" ".backup $BACKUP_DIR/crewledger_${TIMESTAMP}.db"
    echo "[$TIMESTAMP] DB backup: crewledger_${TIMESTAMP}.db ($(du -h $BACKUP_DIR/crewledger_${TIMESTAMP}.db | cut -f1))" >> "$LOG"
else
    echo "[$TIMESTAMP] WARNING: DB not found at $DB_PATH" >> "$LOG"
fi

# Backup storage directory (receipts, certs, documents)
STORAGE_PATH="/opt/crewledger/storage"
if [ -d "$STORAGE_PATH" ]; then
    tar -czf "$BACKUP_DIR/storage_${TIMESTAMP}.tar.gz" -C /opt/crewledger storage/
    echo "[$TIMESTAMP] Storage backup: storage_${TIMESTAMP}.tar.gz ($(du -h $BACKUP_DIR/storage_${TIMESTAMP}.tar.gz | cut -f1))" >> "$LOG"
fi

# Cleanup backups older than retention period
find "$BACKUP_DIR" -name "crewledger_*.db" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -name "storage_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

REMAINING=$(ls -1 "$BACKUP_DIR" | wc -l)
echo "[$TIMESTAMP] Backup complete. $REMAINING files in backup dir." >> "$LOG"
