from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsManagerOrReadOnly(BasePermission):
    """
    관리자(admin) 또는 매니저(manager) 역할만 쓰기 허용.
    나머지는 읽기 전용.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return user.is_authenticated and user.role in ('admin', 'manager')
