#!/usr/bin/env bash
# run.sh — ERP Suite 서버 시작 (환경 자동 감지)
#
# 동작:
#   - 폴더명에 "PROD" 포함 또는 ERP_ENV=prod → 운영 모드 (daphne, 8000 단일)
#   - 그 외 → 개발 모드 (runserver, 8000=dev / 8001=sandbox 병렬)
#
# 명시 지정:
#   ./run.sh prod    # 운영 모드 강제
#   ./run.sh dev     # 개발 모드 강제

set -e

cd "$(dirname "$0")"
source .venv/bin/activate

# ── 모드 결정 ──────────────────────────────────────────────
MODE="${1:-${ERP_ENV:-auto}}"
if [ "$MODE" = "auto" ]; then
    if [[ "$(pwd)" == *PROD* ]]; then
        MODE="prod"
    else
        MODE="dev"
    fi
fi

# ── 운영 모드 ──────────────────────────────────────────────
if [ "$MODE" = "prod" ]; then
    PORT="${PORT:-8000}"
    SETTINGS="${DJANGO_SETTINGS_MODULE:-config.settings.development}"
    export DJANGO_SETTINGS_MODULE="$SETTINGS"

    echo "┌────────────────────────────────────────────┐"
    echo "│  ERP Suite — PRODUCTION                    │"
    echo "├────────────────────────────────────────────┤"
    printf "│  URL      : http://localhost:%-13s│\n" "$PORT"
    printf "│  Settings : %-32s│\n" "$SETTINGS"
    echo "│  Server   : daphne (ASGI + WebSocket)      │"
    echo "└────────────────────────────────────────────┘"
    echo ""

    # 점검모드 자동 OFF (서버 시작 시점)
    python manage.py maintenance off --settings="$SETTINGS" 2>/dev/null | tail -1 || true
    echo ""

    exec daphne -b 0.0.0.0 -p "$PORT" config.asgi:application
fi

# ── 개발 모드 ──────────────────────────────────────────────
if [ "$MODE" = "dev" ]; then
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│  ERP Suite — DEV / SANDBOX (병렬)                       │"
    echo "├─────────┬──────────────────────┬────────────────────────┤"
    echo "│  Dev    │ http://localhost:8000 │ admin / admin1234!    │"
    echo "│  Sandbox│ http://localhost:8001 │ admin / admin1234!    │"
    echo "└─────────┴──────────────────────┴────────────────────────┘"
    echo ""

    python manage.py runserver 0.0.0.0:8000 &
    DJANGO_SETTINGS_MODULE=config.settings.sandbox python manage.py runserver 0.0.0.0:8001 &

    trap 'kill $(jobs -p) 2>/dev/null' INT TERM
    wait
    exit 0
fi

echo "Usage: $0 [prod|dev]" >&2
exit 1
