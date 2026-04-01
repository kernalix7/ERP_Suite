from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import (
    PermissionGroupMembership,
    PermissionGroupPermission,
    UserPermission,
)
from apps.accounts.permission_utils import (
    invalidate_group_perm_cache,
    invalidate_user_perm_cache,
)


@receiver(post_save, sender=PermissionGroupMembership)
@receiver(post_delete, sender=PermissionGroupMembership)
def on_membership_change(sender, instance, **kwargs):
    invalidate_user_perm_cache(instance.user_id)


@receiver(post_save, sender=PermissionGroupPermission)
@receiver(post_delete, sender=PermissionGroupPermission)
def on_group_permission_change(sender, instance, **kwargs):
    invalidate_group_perm_cache(instance.group_id)


@receiver(post_save, sender=UserPermission)
@receiver(post_delete, sender=UserPermission)
def on_user_permission_change(sender, instance, **kwargs):
    invalidate_user_perm_cache(instance.user_id)
