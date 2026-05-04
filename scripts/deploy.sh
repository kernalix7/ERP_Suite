#!/usr/bin/env bash
# deploy.sh — GitHub에서 임시 clone 받아 코드만 동기 (PROD 완전 격리 방식)
#
# 동작:
#   1. 임시 폴더에 GitHub로부터 fresh clone (--depth 1)
#   2. DB 자동 백업
#   3. 점검모드 ON
#   4. rsync로 코드만 PROD에 복사 (local/, media/, .venv/ 등 제외)
#   5. pip install / migrate / collectstatic
#   6. 점검모드 OFF
#   7. 임시 폴더 삭제
#
# PROD에 .git 없음 → GitHub와 직접 연결 0.
# 데이터 절대 안 건드림 (local/, media/, backups/, .venv/, staticfiles/ 보존).
#
# 사용: bash scripts/deploy.sh
# 환경변수:
#   REPO     (기본: https://github.com/kernalix7/ERP_Suite.git)
#   BRANCH   (기본: main)
#   SETTINGS (기본: config.settings.development)

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "$(dirname "$0")/.."
ROOT=$(pwd)

REPO="${REPO:-https://github.com/kernalix7/ERP_Suite.git}"
BRANCH="${BRANCH:-main}"
SETTINGS="${SETTINGS:-config.settings.development}"
TS=$(date +%Y%m%d_%H%M%S)
LOG="${ROOT}/local/deploy.log"
BACKUP_DIR="${ROOT}/backups/deploy"
TMP=$(mktemp -d -t erp_deploy_XXXX)

mkdir -p "$BACKUP_DIR" "${ROOT}/local"
exec > >(tee -a "$LOG") 2>&1

# 정리 함수
cleanup() {
    [ -d "$TMP" ] && rm -rf "$TMP"
}

on_error() {
    local line=$1
    echo ""
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ 배포 실패 (line $line)${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "🔧 복구:"
    echo "  1) DB 롤백:     gunzip -c '$BACKUP_FILE' > local/db_prod.sqlite3"
    echo "  2) 점검모드 OFF: python manage.py maintenance off --settings=$SETTINGS"
    echo ""
    echo "  코드 롤백은 이전 백업 시점 코드 수동 복구 필요 (git 없음)"
    echo "  로그: $LOG"
    cleanup
    exit 1
}
trap cleanup EXIT
trap 'on_error $LINENO' ERR

echo "════════════════════════════════════════════════════════"
echo "  ERP Suite Deploy (clone 방식, GitHub 격리)"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  ROOT     : $ROOT"
echo "  REPO     : $REPO"
echo "  BRANCH   : $BRANCH"
echo "  Settings : $SETTINGS"
echo "════════════════════════════════════════════════════════"

# 사전 체크
[ -f local/db_prod.sqlite3 ] || { echo -e "${RED}[ERROR] local/db_prod.sqlite3 없음${NC}"; exit 1; }
[ -d .venv ] || { echo -e "${RED}[ERROR] .venv 없음${NC}"; exit 1; }
[ -f manage.py ] || { echo -e "${RED}[ERROR] manage.py 없음 — PROD 폴더 맞나?${NC}"; exit 1; }

source .venv/bin/activate

CURRENT_HEAD=""
[ -f .last_deploy_sha ] && CURRENT_HEAD=$(cat .last_deploy_sha)
BACKUP_FILE="${BACKUP_DIR}/db_prod_${TS}_pre_${CURRENT_HEAD:-init}.sqlite3.gz"

# 1. 임시 clone
echo ""
echo -e "${BLUE}▶ 1/7 GitHub에서 임시 clone (--depth 1)${NC}"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$TMP/repo" 2>&1 | tail -3
cd "$TMP/repo"
NEW_HEAD=$(git rev-parse --short HEAD)
NEW_HEAD_FULL=$(git rev-parse HEAD)
NEW_HEAD_MSG=$(git log -1 --pretty=format:'%s')
cd "$ROOT"
echo "받은 커밋: $NEW_HEAD ($NEW_HEAD_MSG)"

# 변경 없음 체크
if [ "$NEW_HEAD" = "$CURRENT_HEAD" ]; then
    echo ""
    echo -e "${GREEN}✓ 이미 최신 ($CURRENT_HEAD) — 배포 불필요${NC}"
    cleanup
    exit 0
fi

# 2. DB 백업
echo ""
echo -e "${BLUE}▶ 2/7 DB 백업${NC}"
gzip -c local/db_prod.sqlite3 > "$BACKUP_FILE"
echo "백업: $(basename "$BACKUP_FILE") ($(du -h "$BACKUP_FILE" | cut -f1))"

# 오래된 백업 정리 (최근 10개만)
ls -t "$BACKUP_DIR"/db_prod_*.sqlite3.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
echo "보관 백업 수: $(ls "$BACKUP_DIR"/db_prod_*.sqlite3.gz 2>/dev/null | wc -l)개"

# 3. 점검모드 ON
echo ""
echo -e "${BLUE}▶ 3/7 점검모드 ON${NC}"
python manage.py maintenance on --settings="$SETTINGS" 2>&1 | tail -1 || true

# 4. 코드 동기 (data 보존)
echo ""
echo -e "${BLUE}▶ 4/7 코드 동기 (rsync, data 디렉토리 제외)${NC}"
rsync -a --delete \
    --exclude='/local/' \
    --exclude='/media/' \
    --exclude='/backups/' \
    --exclude='/.venv/' \
    --exclude='/staticfiles/' \
    --exclude='/.git/' \
    --exclude='/.last_deploy_sha' \
    "$TMP/repo/" "$ROOT/"
echo "OK"

# 5. 의존성
echo ""
echo -e "${BLUE}▶ 5/7 의존성${NC}"
pip install --quiet -r requirements/base.txt
echo "OK"

# 6. 마이그레이션
echo ""
echo -e "${BLUE}▶ 6/7 마이그레이션${NC}"
MIGRATE_OUT=$(python manage.py migrate --settings="$SETTINGS" 2>&1)
echo "$MIGRATE_OUT" | tail -10
APPLIED=$(echo "$MIGRATE_OUT" | grep -cE "^\s+Applying" || true)
echo "→ 적용된 마이그: ${APPLIED}건"

# 7. 정적 파일
echo ""
echo -e "${BLUE}▶ 7/7 정적 파일${NC}"
python manage.py collectstatic --noinput --settings="$SETTINGS" 2>&1 | tail -2

if [ ! -f static/vendor/js/htmx.min.js ]; then
    echo "vendor 누락 — download_vendor.sh 실행"
    bash scripts/download_vendor.sh 2>&1 | tail -3
    python manage.py collectstatic --noinput --settings="$SETTINGS" 2>&1 | tail -1
fi

# 점검모드 OFF
echo ""
echo -e "${BLUE}▶ 점검모드 OFF${NC}"
python manage.py maintenance off --settings="$SETTINGS" 2>&1 | tail -1

# 배포 SHA 기록
echo "$NEW_HEAD" > .last_deploy_sha

# 완료
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ 배포 완료${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo "  $NEW_HEAD : $NEW_HEAD_MSG"
echo "  마이그: ${APPLIED}건 / 백업: $(basename "$BACKUP_FILE")"
echo "  로그: $LOG"
echo ""
echo "📌 서비스 재시작 (필요 시):"
echo "  pkill -f 'daphne|run.sh' && bash run.sh"
