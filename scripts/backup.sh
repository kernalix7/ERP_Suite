#!/usr/bin/env bash
set -euo pipefail

# ── ERP Suite 백업 스크립트 ──────────────────────────────────
# PostgreSQL DB 덤프 + media 파일 백업 + 보관일수 관리
#
# 사용법:
#   ./scripts/backup.sh                     (기본값: 7일 보관)
#   BACKUP_RETENTION_DAYS=14 ./scripts/backup.sh

BACKUP_DIR="${BACKUP_DIR:-/app/local/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-erp_suite}"
DB_USER="${DB_USER:-erp}"
MEDIA_DIR="${MEDIA_DIR:-/app/media}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] 백업 시작"

# ── 1. PostgreSQL 덤프 ──────────────────────────────────────
DB_BACKUP_FILE="${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
echo "[$(date)] PostgreSQL 덤프 → ${DB_BACKUP_FILE}"
PGPASSWORD="${PGPASSWORD:-${DB_PASSWORD:-}}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-privileges \
    | gzip > "${DB_BACKUP_FILE}"
echo "[$(date)] DB 덤프 완료 ($(du -h "${DB_BACKUP_FILE}" | cut -f1))"

# ── 2. Media 파일 백업 ──────────────────────────────────────
if [ -d "${MEDIA_DIR}" ] && [ "$(ls -A "${MEDIA_DIR}" 2>/dev/null)" ]; then
    MEDIA_BACKUP_FILE="${BACKUP_DIR}/media_${TIMESTAMP}.tar.gz"
    echo "[$(date)] Media 백업 → ${MEDIA_BACKUP_FILE}"
    tar -czf "${MEDIA_BACKUP_FILE}" -C "$(dirname "${MEDIA_DIR}")" "$(basename "${MEDIA_DIR}")"
    echo "[$(date)] Media 백업 완료 ($(du -h "${MEDIA_BACKUP_FILE}" | cut -f1))"
else
    echo "[$(date)] Media 디렉토리가 비어있음, 건너뜀"
fi

# ── 3. 오래된 백업 삭제 ─────────────────────────────────────
echo "[$(date)] ${RETENTION_DAYS}일 이전 백업 삭제"
find "${BACKUP_DIR}" -name "db_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete -print 2>/dev/null || true
find "${BACKUP_DIR}" -name "media_*.tar.gz" -mtime +"${RETENTION_DAYS}" -delete -print 2>/dev/null || true

echo "[$(date)] 백업 완료"
