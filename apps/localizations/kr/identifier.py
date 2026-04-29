"""한국 식별자 어댑터 — 사업자등록번호 형식·체크섬 검증.

국세청 표준 사업자등록번호 검증 알고리즘:
- 10자리 숫자 (하이픈 제거)
- 가중치 [1, 3, 7, 1, 3, 7, 1, 3, 5] 를 앞 9자리에 곱해 합산
- 9번째 자리 × 5 의 결과는 추가로 //10 (몫) 을 더함
- (10 - (합산 % 10)) % 10 == 마지막(10번째) 자리이면 유효
"""
from __future__ import annotations

import re

from apps.localizations.base import IdentifierAdapter


_BUSINESS_NUMBER_WEIGHTS = (1, 3, 7, 1, 3, 7, 1, 3, 5)


class KRIdentifierAdapter(IdentifierAdapter):
    """한국 사업자등록번호 어댑터."""

    def business_number_format(self) -> str:
        return '###-##-#####'

    def validate_business_number(self, value: str) -> bool:
        if not value:
            return False
        digits = re.sub(r'\D', '', str(value))
        if len(digits) != 10 or not digits.isdigit():
            return False

        nums = [int(d) for d in digits]
        total = 0
        for i, weight in enumerate(_BUSINESS_NUMBER_WEIGHTS):
            total += nums[i] * weight
        total += (nums[8] * 5) // 10

        check = (10 - (total % 10)) % 10
        return check == nums[9]
