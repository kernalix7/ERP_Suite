#!/bin/bash
# ============================================================
# ERP Suite 실무 투입 검증 스크립트
# 보안, 데이터 무결성, 성능, 워크플로우, 장애 복구 검증
# ============================================================

set -e

# 프로젝트 루트 디렉토리로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 환경변수 설정
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.development}"

echo "============================================================"
echo " ERP Suite 실무 투입 검증"
echo " 실행일시: $(date '+%Y-%m-%d %H:%M:%S')"
echo " 환경설정: $DJANGO_SETTINGS_MODULE"
echo "============================================================"
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_ERROR=0

run_test_suite() {
    local suite_name="$1"
    local test_module="$2"
    local suite_number="$3"

    echo "------------------------------------------------------------"
    echo " ${suite_number}. ${suite_name}"
    echo "------------------------------------------------------------"

    if python manage.py test "$test_module" -v 2 2>&1; then
        echo ""
        echo " [PASS] ${suite_name} 검증 완료"
    else
        echo ""
        echo " [FAIL] ${suite_name} 검증에서 실패 항목 발견"
    fi
    echo ""
}

# 1. 보안 검증
run_test_suite "보안 검증 (SEC-001 ~ SEC-015)" \
    "tests.verification.test_security" "1"

# 2. 데이터 무결성 검증
run_test_suite "데이터 무결성 검증 (INT-001 ~ INT-010)" \
    "tests.verification.test_data_integrity" "2"

# 3. 성능 검증
run_test_suite "성능 검증 (PERF-001 ~ PERF-004)" \
    "tests.verification.test_performance" "3"

# 4. 기능 워크플로우 검증
run_test_suite "기능 워크플로우 검증 (FUNC-001 ~ FUNC-006)" \
    "tests.verification.test_workflow" "4"

# 5. 장애 복구 검증
run_test_suite "장애 복구 검증 (DR-001 ~ DR-004)" \
    "tests.verification.test_disaster_recovery" "5"

echo "============================================================"
echo " 전체 검증 완료"
echo " 완료일시: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""
echo " 전체 테스트 실행:"
echo "   python manage.py test tests.verification -v 2"
echo ""
echo " 개별 모듈 실행:"
echo "   python manage.py test tests.verification.test_security -v 2"
echo "   python manage.py test tests.verification.test_data_integrity -v 2"
echo "   python manage.py test tests.verification.test_performance -v 2"
echo "   python manage.py test tests.verification.test_workflow -v 2"
echo "   python manage.py test tests.verification.test_disaster_recovery -v 2"
echo ""
