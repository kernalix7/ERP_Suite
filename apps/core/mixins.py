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
