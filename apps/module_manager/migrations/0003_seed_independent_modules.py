"""Data migration: seed 23 independent/groupware module records.

All modules default to is_enabled=True to preserve existing behavior.
"""
from django.db import migrations


MODULES = [
    # === 영업관리 ===
    {
        'module_id': 'helpdesk',
        'name': '헬프데스크',
        'description': '고객 지원 티켓 관리, SLA 추적, 지식베이스',
        'category': 'SALES',
        'icon': 'life-buoy',
        'sort_order': 100,
    },
    {
        'module_id': 'portal',
        'name': '고객/공급처 포털',
        'description': '고객·공급처 셀프서비스 포털',
        'category': 'SALES',
        'icon': 'globe',
        'sort_order': 110,
    },
    {
        'module_id': 'logistics',
        'name': '물류/배송관리',
        'description': '배송사 관리, 운임, 추적',
        'category': 'SALES',
        'icon': 'truck',
        'sort_order': 120,
    },
    {
        'module_id': 'subscription',
        'name': '구독/정기과금',
        'description': '구독 플랜, 사용량 계측, 정기 결제',
        'category': 'SALES',
        'icon': 'refresh-cw',
        'sort_order': 130,
    },
    {
        'module_id': 'advertising',
        'name': '광고 관리',
        'description': '광고 플랫폼 관리, 캠페인, 예산',
        'category': 'SALES',
        'icon': 'megaphone',
        'sort_order': 140,
    },
    # === 생산 ===
    {
        'module_id': 'cmms',
        'name': '설비보전(CMMS)',
        'description': '예방/사후 보전, 작업지시, 설비 관리',
        'category': 'PRODUCTION',
        'icon': 'settings',
        'sort_order': 200,
    },
    {
        'module_id': 'plm',
        'name': '제품수명관리(PLM)',
        'description': '제품 버전 관리, ECN, 도면',
        'category': 'PRODUCTION',
        'icon': 'layers',
        'sort_order': 210,
    },
    {
        'module_id': 'qms',
        'name': '품질관리(QMS)',
        'description': '검사, NCR, CAPA, SPC',
        'category': 'PRODUCTION',
        'icon': 'shield',
        'sort_order': 220,
    },
    {
        'module_id': 'forecast',
        'name': '수요예측/S&OP',
        'description': '수요 예측, 시나리오 분석, S&OP 계획',
        'category': 'PRODUCTION',
        'icon': 'trending-up',
        'sort_order': 230,
    },
    # === 회계/재무 ===
    {
        'module_id': 'document',
        'name': '전자문서/계약',
        'description': '문서 버전 관리, 전자 계약, 승인',
        'category': 'ACCOUNTING',
        'icon': 'file-text',
        'sort_order': 300,
    },
    {
        'module_id': 'expense',
        'name': '경비관리',
        'description': '경비 보고서, 영수증 스캔, 정산',
        'category': 'ACCOUNTING',
        'icon': 'credit-card',
        'sort_order': 310,
    },
    # === 법규/컴플라이언스 ===
    {
        'module_id': 'esg',
        'name': 'ESG/컴플라이언스',
        'description': '탄소 관리, 지속가능성, 규정 준수',
        'category': 'COMPLIANCE',
        'icon': 'globe',
        'sort_order': 400,
    },
    # === 인사/그룹웨어 ===
    {
        'module_id': 'lms',
        'name': '학습관리(LMS)',
        'description': '교육과정, 수강, 수료증',
        'category': 'HR',
        'icon': 'book-open',
        'sort_order': 500,
    },
    {
        'module_id': 'visitor',
        'name': '방문자관리',
        'description': '방문 신청, 체크인/아웃, NDA',
        'category': 'HR',
        'icon': 'user-check',
        'sort_order': 510,
    },
    # === 그룹웨어 ===
    {
        'module_id': 'board',
        'name': '게시판',
        'description': '공지사항, 자유게시판, 댓글',
        'category': 'GROUPWARE',
        'icon': 'clipboard',
        'sort_order': 600,
    },
    {
        'module_id': 'calendar_app',
        'name': '일정관리',
        'description': 'FullCalendar 일정, 공유 캘린더',
        'category': 'GROUPWARE',
        'icon': 'calendar',
        'sort_order': 610,
    },
    {
        'module_id': 'messenger',
        'name': '사내 메신저',
        'description': '1:1/그룹 채팅, WebSocket 실시간',
        'category': 'GROUPWARE',
        'icon': 'message-circle',
        'sort_order': 620,
    },
    # === 시스템 ===
    {
        'module_id': 'wiki',
        'name': '지식베이스/위키',
        'description': '문서, 카테고리, 버전 관리',
        'category': 'SYSTEM',
        'icon': 'book',
        'sort_order': 700,
    },
    {
        'module_id': 'project',
        'name': '프로젝트관리',
        'description': '마일스톤, 태스크, 시간 추적',
        'category': 'SYSTEM',
        'icon': 'briefcase',
        'sort_order': 710,
    },
    {
        'module_id': 'bi',
        'name': 'BI 대시보드',
        'description': '리포트 빌더, 차트 패널, 데이터 분석',
        'category': 'SYSTEM',
        'icon': 'bar-chart-2',
        'sort_order': 720,
    },
    {
        'module_id': 'rpa',
        'name': '자동화(RPA)',
        'description': '규칙 기반 자동화, 스케줄링',
        'category': 'SYSTEM',
        'icon': 'cpu',
        'sort_order': 730,
    },
    {
        'module_id': 'edi',
        'name': 'EDI 전자문서교환',
        'description': 'PO/인보이스/ASN 전자 메시지',
        'category': 'SYSTEM',
        'icon': 'share-2',
        'sort_order': 740,
    },
    {
        'module_id': 'ad',
        'name': 'Active Directory 연동',
        'description': 'LDAP 기반 AD 사용자 동기화',
        'category': 'SYSTEM',
        'icon': 'users',
        'sort_order': 750,
    },
]


def seed_modules(apps, schema_editor):
    InstalledModule = apps.get_model('module_manager', 'InstalledModule')
    for mod in MODULES:
        InstalledModule.objects.get_or_create(
            module_id=mod['module_id'],
            defaults={
                'name': mod['name'],
                'description': mod['description'],
                'category': mod['category'],
                'icon': mod.get('icon', ''),
                'sort_order': mod.get('sort_order', 0),
                'is_enabled': True,   # preserve existing behavior
                'is_active': True,
                'dependencies': mod.get('dependencies', []),
                'version': '1.0.0',
            },
        )


def reverse_seed(apps, schema_editor):
    InstalledModule = apps.get_model('module_manager', 'InstalledModule')
    module_ids = [m['module_id'] for m in MODULES]
    InstalledModule.objects.filter(module_id__in=module_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('module_manager', '0002_alter_historicalinstalledmodule_category_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_modules, reverse_seed),
    ]
