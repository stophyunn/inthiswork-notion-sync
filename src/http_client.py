from __future__ import annotations

import logging
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests

LOGGER = logging.getLogger(__name__)


class SiteAccessError(RuntimeError):
    """Base exception for source-site access problems."""


class SiteRateLimitedError(SiteAccessError):
    pass


class SiteBlockedError(SiteAccessError):
    pass


class SiteNotFoundError(SiteAccessError):
    pass


@dataclass
class PoliteHttpClient:
    base_url: str
    delay_seconds: float = 2.5
    timeout_seconds: float = 25.0

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.user_agent = (
            "Mozilla/5.0 (compatible; InThisWorkNotionSync/1.0; "
            "+personal-use; one-request-at-a-time)"
        )
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
                "Cache-Control": "no-cache",
            }
        )
        self._last_request_at = 0.0
        self._robots: urllib.robotparser.RobotFileParser | None = None
        self._robots_checked = False

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _load_robots(self) -> None:
        if self._robots_checked:
            return
        self._robots_checked = True
        parsed = urlparse(self.base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            self._wait()
            response = self.session.get(robots_url, timeout=self.timeout_seconds)
            self._last_request_at = time.monotonic()
            if response.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(robots_url)
                parser.parse(response.text.splitlines())
                self._robots = parser
                LOGGER.info("robots.txt를 확인했습니다.")
            elif response.status_code in {404, 410}:
                LOGGER.info("robots.txt가 없어 일반 공개 페이지 접근으로 처리합니다.")
            else:
                LOGGER.warning(
                    "robots.txt 확인 응답이 %s였습니다. 우회하지 않고 낮은 빈도로만 접근합니다.",
                    response.status_code,
                )
        except requests.RequestException as exc:
            LOGGER.warning("robots.txt를 확인하지 못했습니다: %s", exc)

    def _check_robots(self, url: str) -> None:
        self._load_robots()
        if self._robots is not None and not self._robots.can_fetch(self.user_agent, url):
            raise SiteBlockedError(f"robots.txt에서 접근을 허용하지 않는 URL입니다: {url}")

    def get(self, url: str, *, allow_404: bool = False) -> requests.Response:
        absolute = urljoin(self.base_url, url)
        self._check_robots(absolute)

        last_error: Exception | None = None
        for attempt in range(1, 4):
            self._wait()
            try:
                response = self.session.get(absolute, timeout=self.timeout_seconds)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(attempt * 2)
                    continue
                raise SiteAccessError(f"페이지 요청 실패: {absolute}: {exc}") from exc

            if response.status_code == 429:
                raise SiteRateLimitedError(
                    f"인디스워크가 요청을 제한했습니다(429). 실행을 중단합니다: {absolute}"
                )
            if response.status_code == 403:
                raise SiteBlockedError(
                    f"인디스워크가 접근을 거부했습니다(403). 우회하지 않고 실행을 중단합니다: {absolute}"
                )
            if response.status_code == 404:
                if allow_404:
                    return response
                raise SiteNotFoundError(f"페이지를 찾을 수 없습니다: {absolute}")
            if response.status_code >= 500:
                last_error = SiteAccessError(
                    f"서버 오류 {response.status_code}: {absolute}"
                )
                if attempt < 3:
                    time.sleep(attempt * 3)
                    continue
                raise last_error
            response.raise_for_status()
            return response

        raise SiteAccessError(f"페이지 요청 실패: {absolute}: {last_error}")
