from django.core.cache import cache


def get_user_permissions(user):
    """사용자의 모듈 권한 코드 집합을 반환한다.

    admin 역할이면 None을 반환 (sentinel: 전체 통과).
    그 외 역할은 그룹 권한 + 사용자 직접 권한을 합산한 frozenset을 반환한다.
    결과는 캐시(TTL 300초)에 저장된다.
    """
    if user.role == 'admin':
        return None

    cache_key = f'user_perms:{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.accounts.models import (
        PermissionGroupMembership,
        PermissionGroupPermission,
        UserPermission,
    )

    # 1. 그룹 권한 수집
    group_ids = (
        PermissionGroupMembership.objects
        .filter(user=user, is_active=True, group__is_active=True)
        .values_list('group_id', flat=True)
    )
    group_perms = set(
        PermissionGroupPermission.objects
        .filter(
            group_id__in=group_ids,
            is_active=True,
            permission__is_active=True,
        )
        .values_list('permission__codename', flat=True)
    )

    # 2. 사용자 직접 권한 적용 (grant=True 추가, grant=False 제거)
    user_overrides = (
        UserPermission.objects
        .filter(user=user, is_active=True, permission__is_active=True)
        .values_list('permission__codename', 'grant')
    )
    for codename, grant in user_overrides:
        if grant:
            group_perms.add(codename)
        else:
            group_perms.discard(codename)

    result = frozenset(group_perms)
    cache.set(cache_key, result, timeout=300)
    return result


def invalidate_user_perm_cache(user_id):
    """특정 사용자의 권한 캐시를 무효화한다."""
    cache.delete(f'user_perms:{user_id}')


def invalidate_group_perm_cache(group_id):
    """해당 그룹 소속 모든 사용자의 권한 캐시를 무효화한다."""
    from apps.accounts.models import PermissionGroupMembership

    user_ids = (
        PermissionGroupMembership.objects
        .filter(group_id=group_id, is_active=True)
        .values_list('user_id', flat=True)
    )
    for uid in user_ids:
        cache.delete(f'user_perms:{uid}')
