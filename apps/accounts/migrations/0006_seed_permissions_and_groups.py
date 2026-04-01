from django.db import migrations


MODULE_CHOICES = [
    ('sales', '판매관리'), ('inventory', '재고관리'), ('production', '생산관리'),
    ('purchase', '구매관리'), ('accounting', '회계관리'), ('hr', '인사관리'),
    ('attendance', '근태관리'), ('approval', '결재관리'), ('board', '게시판'),
    ('calendar_app', '일정관리'), ('messenger', '사내메신저'), ('service', 'AS관리'),
    ('warranty', '정품등록'), ('investment', '투자관리'), ('marketplace', '외부스토어'),
    ('inquiry', '문의관리'), ('asset', '고정자산'), ('ad', 'AD관리'),
    ('advertising', '광고관리'), ('accounts', '사용자관리'), ('core', '시스템관리'),
]

ACTION_CHOICES = [
    ('VIEW', '조회'), ('CREATE', '생성'), ('EDIT', '수정'),
    ('DELETE', '삭제'), ('APPROVE', '승인'), ('EXPORT', '내보내기'),
]

# 매니저 APPROVE 권한: 회계, 결재, 구매만
MANAGER_APPROVE_MODULES = {'accounting', 'approval', 'purchase'}

# 직원 CREATE/EDIT 가능 모듈
STAFF_EDITABLE_MODULES = {'board', 'calendar_app', 'messenger', 'attendance'}


def seed_permissions_and_groups(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    PermissionGroup = apps.get_model('accounts', 'PermissionGroup')
    PermissionGroupPermission = apps.get_model('accounts', 'PermissionGroupPermission')

    # 1. 모듈 권한 시드: 21 x 6 = 126개
    perm_map = {}
    for module_code, module_label in MODULE_CHOICES:
        for action_code, action_label in ACTION_CHOICES:
            codename = f'{module_code}.{action_code}'
            perm = ModulePermission.objects.create(
                module=module_code,
                action=action_code,
                codename=codename,
                description=f'{module_label} {action_label}',
            )
            perm_map[codename] = perm

    # 2. 관리자 그룹 (전체 권한)
    admin_group = PermissionGroup.objects.create(
        name='관리자', description='전체 권한', priority=100,
    )
    for perm in perm_map.values():
        PermissionGroupPermission.objects.create(
            group=admin_group, permission=perm,
        )

    # 3. 매니저 그룹 (전체 VIEW/CREATE/EDIT/EXPORT + 일부 APPROVE)
    manager_group = PermissionGroup.objects.create(
        name='매니저', description='전체 조회/생성/수정/내보내기 + 일부 승인', priority=50,
    )
    for codename, perm in perm_map.items():
        module, action = codename.split('.')
        if action in ('VIEW', 'CREATE', 'EDIT', 'EXPORT'):
            PermissionGroupPermission.objects.create(
                group=manager_group, permission=perm,
            )
        elif action == 'APPROVE' and module in MANAGER_APPROVE_MODULES:
            PermissionGroupPermission.objects.create(
                group=manager_group, permission=perm,
            )

    # 4. 직원 그룹 (전체 VIEW/EXPORT + board/calendar_app/messenger/attendance CREATE/EDIT)
    staff_group = PermissionGroup.objects.create(
        name='직원', description='전체 조회/내보내기 + 그룹웨어 생성/수정', priority=10,
    )
    for codename, perm in perm_map.items():
        module, action = codename.split('.')
        if action in ('VIEW', 'EXPORT'):
            PermissionGroupPermission.objects.create(
                group=staff_group, permission=perm,
            )
        elif action in ('CREATE', 'EDIT') and module in STAFF_EDITABLE_MODULES:
            PermissionGroupPermission.objects.create(
                group=staff_group, permission=perm,
            )


def reverse_seed(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    PermissionGroup = apps.get_model('accounts', 'PermissionGroup')
    PermissionGroupPermission = apps.get_model('accounts', 'PermissionGroupPermission')
    PermissionGroupPermission.objects.all().delete()
    PermissionGroup.objects.all().delete()
    ModulePermission.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_historicalmodulepermission_historicalpermissiongroup_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_permissions_and_groups, reverse_seed),
    ]
