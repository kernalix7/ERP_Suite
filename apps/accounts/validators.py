"""Custom password validators — complexity + reuse prevention."""
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ComplexityValidator:
    """대문자+소문자+숫자+특수문자 포함, 최소 10자"""

    def validate(self, password, user=None):
        errors = []
        if len(password) < 10:
            errors.append('최소 10자 이상이어야 합니다.')
        if not re.search(r'[A-Z]', password):
            errors.append('영문 대문자를 1개 이상 포함해야 합니다.')
        if not re.search(r'[a-z]', password):
            errors.append('영문 소문자를 1개 이상 포함해야 합니다.')
        if not re.search(r'\d', password):
            errors.append('숫자를 1개 이상 포함해야 합니다.')
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:\'",.<>?/\\`~]', password):
            errors.append('특수문자를 1개 이상 포함해야 합니다.')
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            '비밀번호는 10자 이상이며, '
            '영문 대문자/소문자/숫자/특수문자를 각 1개 이상 포함해야 합니다.'
        )


class NoReuseValidator:
    """최근 5개 비밀번호 재사용 금지"""
    HISTORY_COUNT = 5

    def validate(self, password, user=None):
        if user is None or not user.pk:
            return
        from django.contrib.auth.hashers import check_password
        from apps.accounts.models import PasswordHistory
        recent = PasswordHistory.objects.filter(
            user=user, is_active=True,
        ).order_by('-created_at')[:self.HISTORY_COUNT]
        for entry in recent:
            if check_password(password, entry.password_hash):
                raise ValidationError(
                    _('최근 %(count)d개 비밀번호는 재사용할 수 없습니다.'),
                    params={'count': self.HISTORY_COUNT},
                )

    def get_help_text(self):
        return _('최근 5개 비밀번호는 재사용할 수 없습니다.')
