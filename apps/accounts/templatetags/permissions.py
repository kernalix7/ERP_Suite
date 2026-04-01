from django import template

register = template.Library()


@register.simple_tag
def perm_codename(module, action):
    """모듈코드 + 액션코드 → codename 생성."""
    return f'{module}.{action}'


@register.simple_tag
def perm_checked(module, action, assigned_perms):
    """권한 그룹 폼에서 해당 권한이 할당되어 있으면 'checked' 반환."""
    codename = f'{module}.{action}'
    if codename in assigned_perms:
        return 'checked'
    return ''


@register.simple_tag
def direct_perm_value(module, action, direct_perms):
    """사용자 직접 권한의 상태 반환: 'grant', 'deny', 'none'."""
    codename = f'{module}.{action}'
    if codename in direct_perms:
        return 'grant' if direct_perms[codename] else 'deny'
    return 'none'


@register.simple_tag
def has_group_perm(module, action, group_perms):
    """그룹으로부터 해당 권한을 보유하고 있는지 확인."""
    codename = f'{module}.{action}'
    return codename in group_perms


@register.filter
def has_module_access(user, module):
    """템플릿에서 사용자의 모듈 접근 권한 확인.

    Usage: {% if user|has_module_access:"sales" %}
    """
    if not user or not user.is_authenticated:
        return False
    if user.role == 'admin':
        return True
    return user.has_module_permission(module, 'VIEW')
