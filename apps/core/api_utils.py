"""
외부 API 호출 유틸리티 -- 재시도(Retry) + 서킷브레이커(CircuitBreaker)
"""
import logging
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def create_retry_session(
    retries=3,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    timeout=30,
):
    """재시도 로직이 포함된 requests.Session을 생성한다."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST", "PUT", "DELETE"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.timeout = timeout
    return session


class CircuitBreaker:
    """간단한 서킷 브레이커 패턴 구현."""

    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, name, failure_threshold=3, recovery_timeout=60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._lock = threading.Lock()

    @property
    def state(self):
        with self._lock:
            if self._state == self.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info('CircuitBreaker[%s]: OPEN -> HALF_OPEN', self.name)
            return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            if self._state == self.HALF_OPEN:
                self._state = self.CLOSED
                logger.info('CircuitBreaker[%s]: HALF_OPEN -> CLOSED', self.name)

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    'CircuitBreaker[%s]: CLOSED -> OPEN (failures=%d)',
                    self.name, self._failure_count,
                )

    @property
    def is_available(self):
        return self.state != self.OPEN


# 전역 서킷 브레이커 인스턴스 (API별 1개)
circuit_breakers = {
    'nts': CircuitBreaker('nts', failure_threshold=3, recovery_timeout=60),
    'naver': CircuitBreaker('naver', failure_threshold=3, recovery_timeout=60),
    'coupang': CircuitBreaker('coupang', failure_threshold=3, recovery_timeout=60),
    'juso': CircuitBreaker('juso', failure_threshold=3, recovery_timeout=30),
    'nominatim': CircuitBreaker('nominatim', failure_threshold=5, recovery_timeout=30),
}
