"""US identifier adapter (stub) — EIN (Employer Identification Number).

EIN format: ##-####### (9 digits, hyphen after first 2). 본 스텁은 형식만 체크.
"""
from __future__ import annotations

import re

from apps.localizations.base import IdentifierAdapter


class USIdentifierAdapter(IdentifierAdapter):
    """US EIN adapter (stub — format only)."""

    def business_number_format(self) -> str:
        return '##-#######'

    def validate_business_number(self, value: str) -> bool:
        if not value:
            return False
        digits = re.sub(r'\D', '', str(value))
        return len(digits) == 9 and digits.isdigit()
