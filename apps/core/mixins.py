from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class StaffRequiredMixin(LoginRequiredMixin):
    """모든 로그인 사용자 허용 (기본)"""
    pass


class ManagerRequiredMixin(LoginRequiredMixin):
    """매니저 이상만 접근 가능 (manager, admin)"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in ('admin', 'manager'):
            raise PermissionDenied('매니저 이상 권한이 필요합니다.')
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(LoginRequiredMixin):
    """관리자만 접근 가능 (admin)"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != 'admin':
            raise PermissionDenied('관리자 권한이 필요합니다.')
        return super().dispatch(request, *args, **kwargs)


class ModulePermissionMixin(LoginRequiredMixin):
    """모듈 권한 기반 접근 제어 Mixin.

    사용법:
        required_permission = 'sales.VIEW'           # 단일 권한
        required_permissions = ['sales.VIEW', 'inventory.VIEW']  # 복수 권한
        require_all_permissions = True   # True=AND(모두 필요), False=OR(하나만)
    """
    required_permission = None
    required_permissions = None
    require_all_permissions = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role == 'admin':
            return super().dispatch(request, *args, **kwargs)

        perms_to_check = self._get_permissions_to_check()
        if perms_to_check and not self._check_permissions(request.user, perms_to_check):
            raise PermissionDenied('해당 기능에 접근할 권한이 없습니다.')
        return super().dispatch(request, *args, **kwargs)

    def _get_permissions_to_check(self):
        if self.required_permissions:
            return self.required_permissions
        if self.required_permission:
            return [self.required_permission]
        return []

    def _check_permissions(self, user, perms_to_check):
        user_perms = user.get_module_permissions()
        if user_perms is None:
            return True
        if self.require_all_permissions:
            return all(p in user_perms for p in perms_to_check)
        return any(p in user_perms for p in perms_to_check)
