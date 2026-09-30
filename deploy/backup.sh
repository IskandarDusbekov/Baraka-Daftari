#!/usr/bin/env bash
# PostgreSQL zaxira nusxasi: har kecha crontab orqali, 14 kunlik nusxalar saqlanadi.
#   install -m 755 deploy/backup.sh /usr/local/bin/baraka-backup
#   sudo -u postgres crontab -e  ->  30 3 * * * /usr/local/bin/baraka-backup
set -euo pipefail
DIR=/var/backups/baraka
mkdir -p "$DIR"
pg_dump -Fc baraka > "$DIR/baraka-$(date +%F).dump"
find "$DIR" -name 'baraka-*.dump' -mtime +14 -delete
