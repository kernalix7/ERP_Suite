#!/usr/bin/env bash
# ERP Suite — Prod(8000) + Sandbox(8001) 동시 실행
set -e
source .venv/bin/activate

echo "┌─────────────────────────────────────────────────────────┐"
echo "│  ERP Suite Multi-Environment                            │"
echo "├─────────┬──────────────────────┬────────────────────────┤"
echo "│  Prod   │ http://localhost:8000 │ admin / admin1234!    │"
echo "│  Sandbox│ http://localhost:8001 │ admin / admin1234!    │"
echo "└─────────┴──────────────────────┴────────────────────────┘"
echo ""
echo "  Prod    = 실제 운영 DB (수동 입력)"
echo "  Sandbox = 이전 Prod 데이터 백업 + 테스트용"
echo ""

python manage.py runserver 0.0.0.0:8000 &
DJANGO_SETTINGS_MODULE=config.settings.sandbox python manage.py runserver 0.0.0.0:8001 &

trap 'kill $(jobs -p) 2>/dev/null' INT TERM
wait
