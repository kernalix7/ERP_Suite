def effective_role(request):
    """현재 유효 역할을 템플릿 컨텍스트에 주입.

    관리자가 RoleSwitchView로 뷰 모드를 변경하면 session['view_mode']에 저장됨.
    이 값이 있으면 effective_role로, 없으면 실제 user.role을 반환.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    user = request.user
    view_mode = request.session.get('view_mode', '')

    # 관리자만 뷰 모드 전환 가능
    if user.role == 'admin' and view_mode in ('staff', 'manager', 'admin'):
        role = view_mode
    else:
        role = user.role

    return {
        'effective_role': role,
        'is_view_mode_active': role != user.role,
    }
