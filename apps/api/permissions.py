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


class HasModulePermission(BasePermission):
    """DRF 모듈 권한 퍼미션 클래스.

    ViewSet에 module_permission 속성을 지정하면 HTTP 메서드에 따라
    자동으로 액션을 매핑하여 권한을 검사한다.

    사용법:
        class OrderViewSet(ModelViewSet):
            module_permission = 'sales'
            permission_classes = [IsAuthenticated, HasModulePermission]
    """
    METHOD_ACTION_MAP = {
        'GET': 'VIEW',
        'HEAD': 'VIEW',
        'OPTIONS': 'VIEW',
        'POST': 'CREATE',
        'PUT': 'EDIT',
        'PATCH': 'EDIT',
        'DELETE': 'DELETE',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == 'admin':
            return True

        module = getattr(view, 'module_permission', None)
        if not module:
            return True

        action = self.METHOD_ACTION_MAP.get(request.method, 'VIEW')
        return request.user.has_module_permission(module, action)
