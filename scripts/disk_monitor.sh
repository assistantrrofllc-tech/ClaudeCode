#\!/bin/bash
# CrewOS Disk Monitor — warn 70%, alert 85%
# Runs via cron: 0 */6 * * * /opt/crewledger/scripts/disk_monitor.sh

set -euo pipefail

LOG="/var/log/crewledger/disk_monitor.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WARN_THRESHOLD=70
ALERT_THRESHOLD=85

DISK_USAGE=$(df / | tail -1 | awk "{print \$5}" | sed "s/%//")
DISK_AVAIL=$(df -h / | tail -1 | awk "{print \$4}")
DISK_TOTAL=$(df -h / | tail -1 | awk "{print \$2}")

if [ "$DISK_USAGE" -ge "$ALERT_THRESHOLD" ]; then
    echo "[$TIMESTAMP] ALERT: Disk at ${DISK_USAGE}% (${DISK_AVAIL} free of ${DISK_TOTAL})" >> "$LOG"
    # Future: send SMS/email alert
elif [ "$DISK_USAGE" -ge "$WARN_THRESHOLD" ]; then
    echo "[$TIMESTAMP] WARNING: Disk at ${DISK_USAGE}% (${DISK_AVAIL} free of ${DISK_TOTAL})" >> "$LOG"
else
    echo "[$TIMESTAMP] OK: Disk at ${DISK_USAGE}% (${DISK_AVAIL} free of ${DISK_TOTAL})" >> "$LOG"
fi
