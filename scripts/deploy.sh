#!/usr/bin/env bash
# deploy.sh — origin/main 최신 소스 적용 (PROD 전용)
#
# 동작:
#   1. 미커밋 변경 검사 (있으면 경고)
#   2. 원격 fetch → 변경사항 표시
#   3. DB 백업 (backups/deploy/)
#   4. 점검모드 ON
#   5. git reset --hard origin/main
#   6. pip install (의존성 변경 시 반영)
#   7. migrate
#   8. collectstatic
#   9. 점검모드 OFF
#
# 데이터 보존: local/, media/ 절대 안 건드림
# 사용: bash scripts/deploy.sh

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 스크립트 위치의 상위가 프로젝트 루트
cd "$(dirname "$0")/.."
ROOT=$(pwd)

SETTINGS="${DEPLOY_SETTINGS:-config.settings.development}"
TS=$(date +%Y%m%d_%H%M%S)
LOG_DIR="${ROOT}/local"
LOG_FILE="${LOG_DIR}/deploy.log"
BACKUP_DIR="${ROOT}/backups/deploy"

mkdir -p "$LOG_DIR" "$BACKUP_DIR"

# 모든 출력 → stdout + log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "════════════════════════════════════════════════════════"
echo "  ERP Suite Deploy — $(date '+%Y-%m-%d %H:%M:%S')"
echo "  ROOT: $ROOT"
echo "  Settings: $SETTINGS"
echo "════════════════════════════════════════════════════════"

# ── 사전 체크 ───────────────────────────────────────────────
[ -f local/db_prod.sqlite3 ] || { echo -e "${RED}[ERROR] local/db_prod.sqlite3 없음 — PROD 폴더 맞나?${NC}"; exit 1; }
[ -d .venv ] || { echo -e "${RED}[ERROR] .venv 없음 — 먼저 setup 필요${NC}"; exit 1; }
[ -f manage.py ] || { echo -e "${RED}[ERROR] manage.py 없음 — 잘못된 디렉토리${NC}"; exit 1; }

source .venv/bin/activate

# CURRENT 커밋 저장 (롤백/에러 안내용)
CURRENT=$(git rev-parse HEAD)
CURRENT_SHORT=${CURRENT:0:7}
BACKUP_FILE="${BACKUP_DIR}/db_prod_${TS}_pre_${CURRENT_SHORT}.sqlite3.gz"

# ── 에러 트랩 ──────────────────────────────────────────────
on_error() {
    local line=$1
    echo ""
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ 배포 실패 (line $line)${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "🔧 복구 절차:"
    echo "  1) 코드 롤백:   git reset --hard ${CURRENT}"
    echo "  2) DB 롤백:     gunzip -c '$BACKUP_FILE' > local/db_prod.sqlite3"
    echo "  3) 점검모드 OFF: python manage.py maintenance off --settings=$SETTINGS"
    echo ""
    echo "  로그: $LOG_FILE"
    exit 1
}
trap 'on_error $LINENO' ERR

# ── 1. 미커밋 변경 검사 ────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 1/8 미커밋 변경 검사${NC}"
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}[WARN] 미커밋 로컬 변경 발견 — 진행 시 덮어쓰기됨:${NC}"
    git status --short | head -10
    echo ""
    if [ -t 0 ]; then  # 인터랙티브 터미널
        read -p "계속 진행? [y/N] " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || { echo "취소됨"; exit 0; }
    else
        echo -e "${YELLOW}비대화형 — 자동 진행${NC}"
    fi
else
    echo "OK — 미커밋 변경 없음"
fi

# ── 2. 원격 fetch ──────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 2/8 원격 fetch${NC}"
git fetch origin main 2>&1 | tail -3

LATEST=$(git rev-parse origin/main)
LATEST_SHORT=${LATEST:0:7}

if [ "$CURRENT" = "$LATEST" ]; then
    echo ""
    echo -e "${GREEN}✓ 이미 최신 (${CURRENT_SHORT}) — 배포 불필요${NC}"
    exit 0
fi

echo ""
echo "변경: ${CURRENT_SHORT} → ${LATEST_SHORT}"
echo "신규 커밋:"
git log --oneline "${CURRENT}..${LATEST}" | sed 's/^/  /' | head -20
echo ""
echo "신규 마이그레이션:"
NEW_MIGRATIONS=$(git diff --name-only "${CURRENT}" "${LATEST}" -- '**/migrations/*.py' 2>/dev/null | grep -v __pycache__ || true)
if [ -n "$NEW_MIGRATIONS" ]; then
    echo "$NEW_MIGRATIONS" | sed 's/^/  /'
else
    echo "  (없음)"
fi

# ── 3. DB 백업 ────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 3/8 DB 백업${NC}"
gzip -c local/db_prod.sqlite3 > "$BACKUP_FILE"
echo "백업: $(basename "$BACKUP_FILE") ($(du -h "$BACKUP_FILE" | cut -f1))"

# 오래된 백업 정리 (최근 10개만 유지)
ls -t "$BACKUP_DIR"/db_prod_*.sqlite3.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
echo "보관 백업 수: $(ls "$BACKUP_DIR"/db_prod_*.sqlite3.gz 2>/dev/null | wc -l)개"

# ── 4. 점검모드 ON ────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 4/8 점검모드 ON${NC}"
python manage.py maintenance on --settings="$SETTINGS" 2>&1 | tail -1

# ── 5. 소스 업데이트 ──────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 5/8 소스 업데이트${NC}"
git reset --hard origin/main 2>&1 | tail -2

# ── 6. 의존성 ─────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 6/8 의존성 (requirements/base.txt)${NC}"
pip install --quiet -r requirements/base.txt
echo "OK"

# ── 7. 마이그레이션 ───────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 7/8 마이그레이션${NC}"
MIGRATE_OUT=$(python manage.py migrate --settings="$SETTINGS" 2>&1)
echo "$MIGRATE_OUT" | tail -10
APPLIED=$(echo "$MIGRATE_OUT" | grep -cE "^\s+Applying" || true)
echo "→ 적용된 마이그: ${APPLIED}건"

# ── 8. 정적 파일 ──────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 8/8 정적 파일 재수집${NC}"
python manage.py collectstatic --noinput --settings="$SETTINGS" 2>&1 | tail -2

# vendor 폴더 누락 시 다운로드
if [ ! -f static/vendor/js/htmx.min.js ]; then
    echo "vendor 누락 — download_vendor.sh 실행"
    bash scripts/download_vendor.sh 2>&1 | tail -3
    python manage.py collectstatic --noinput --settings="$SETTINGS" 2>&1 | tail -1
fi

# ── 점검모드 OFF ──────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 점검모드 OFF${NC}"
python manage.py maintenance off --settings="$SETTINGS" 2>&1 | tail -1

# ── 완료 ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ 배포 완료${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo "  $(git log -1 --pretty=format:'%h %s')"
echo "  ${CURRENT_SHORT} → $(git rev-parse --short HEAD)"
echo "  마이그: ${APPLIED}건 / 백업: $(basename "$BACKUP_FILE")"
echo "  로그: $LOG_FILE"
echo ""
echo "📌 서비스 재시작 (필요 시):"
echo "  - runserver autoreload  → 자동 반영됨"
echo "  - daphne / --noreload   → 직접 재시작 필요"
echo "    (예: pkill -f 'daphne|runserver' && bash scripts/start.sh)"
