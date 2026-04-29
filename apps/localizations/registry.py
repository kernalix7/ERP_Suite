"""국가 어댑터 레지스트리 — country code → adapter instance 매핑.

사용:
    from apps.localizations import get_adapter, get_active_adapter
    kr = get_adapter('KR')                    # 명시 지정
    active = get_active_adapter()             # 시스템 활성 국가 (default 'KR')

새 국가 추가:
    from apps.localizations import register_adapter
    register_adapter('JP', JPAdapter())
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from .base import LocalizationAdapter

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, LocalizationAdapter] = {}


def register_adapter(country_code: str, adapter: LocalizationAdapter) -> None:
    """국가 어댑터 등록."""
    code = country_code.upper()
    if code in _REGISTRY:
        logger.warning('Adapter for %s already registered, overwriting', code)
    _REGISTRY[code] = adapter
    logger.info('Localization adapter registered: %s', code)


def get_adapter(country_code: str) -> LocalizationAdapter:
    """country code 로 어댑터 조회.

    Raises:
        LookupError: 미등록 국가
    """
    code = (country_code or '').upper()
    if code not in _REGISTRY:
        _autoload()
    if code not in _REGISTRY:
        raise LookupError(
            f'Country adapter for {code!r} not registered. '
            f'Available: {sorted(_REGISTRY.keys())}'
        )
    return _REGISTRY[code]


def get_active_adapter() -> LocalizationAdapter:
    """현재 활성 국가 어댑터.

    우선순위:
      1. SystemConfig('GENERAL', 'active_country')
      2. settings.ACTIVE_COUNTRY
      3. 'KR' (기본)
    """
    code = 'KR'
    try:
        from apps.core.models import SystemConfig
        v = SystemConfig.get_value('GENERAL', 'active_country', '')
        if v:
            code = v
    except Exception:
        pass
    code = getattr(settings, 'ACTIVE_COUNTRY', code) or code
    return get_adapter(code)


def get_registered_codes() -> list[str]:
    """등록된 국가 코드 목록."""
    if not _REGISTRY:
        _autoload()
    return sorted(_REGISTRY.keys())


def _autoload():
    """등록된 어댑터 자동 import — apps/localizations/<code>/__init__.py 가 register_adapter 호출."""
    try:
        # 한국 어댑터 — prod 기본
        from apps.localizations import kr  # noqa: F401
    except ImportError:
        logger.warning('KR adapter import failed', exc_info=True)
    # 미래 추가 — try/except 로 graceful fallback
    for code in ('us', 'jp', 'cn'):
        try:
            __import__(f'apps.localizations.{code}')
        except ImportError:
            pass
