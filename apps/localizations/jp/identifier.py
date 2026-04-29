"""JP 식별자 어댑터 (스텁) — 法人番号 (13자리) 형식 체크.

근거(향후 실 구현 시 참조):
- 国税庁 法人番号公表サイト — 13자리 법인번호, 체크디지트 알고리즘 별도.
- 본 스텁은 형식(13자리 숫자)만 확인.
"""
from __future__ import annotations

import re

from apps.localizations.base import IdentifierAdapter


class JPIdentifierAdapter(IdentifierAdapter):
    """일본 법인번호 어댑터 (스텁 — 형식 체크만)."""

    def business_number_format(self) -> str:
        return '#############'  # 13자리

    def validate_business_number(self, value: str) -> bool:
        if not value:
            return False
        digits = re.sub(r'\D', '', str(value))
        return len(digits) == 13 and digits.isdigit()
