from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from .http_client import PoliteHttpClient, SiteNotFoundError
from .parser import parse_post_html
from .models import PostRecord

LOGGER = logging.getLogger(__name__)
POST_URL_RE = re.compile(r"^/archives/(\d+)/?$")


def normalize_post_url(href: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.netloc.replace("www.", "") != "inthiswork.com":
        return None
    match = POST_URL_RE.match(parsed.path.rstrip("/") + "/")
    if not match:
        # Accommodate the same path without the normalization above.
        match = re.match(r"^/archives/(\d+)$", parsed.path.rstrip("/"))
    if not match:
        return None
    clean_path = f"/archives/{match.group(1)}"
    return urlunparse((parsed.scheme or "https", parsed.netloc, clean_path, "", "", ""))


class InThisWorkScraper:
    def __init__(self, client: PoliteHttpClient, design_url: str) -> None:
        self.client = client
        self.design_url = design_url.rstrip("/")

    def _extract_post_urls(self, html: str, page_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            normalized = normalize_post_url(str(anchor["href"]), page_url)
            if normalized and normalized not in urls:
                urls.append(normalized)
        return urls

    def _next_page_url(self, html: str, current_url: str, page_number: int) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for selector in ["a[rel='next']", "a.next", ".pagination-next a", ".next.page-numbers"]:
            anchor = soup.select_one(selector)
            if anchor and anchor.get("href"):
                return urljoin(current_url, str(anchor["href"]))
        return f"{self.design_url}/page/{page_number + 1}/"

    def discover_post_urls(self, max_pages: int = 3) -> list[str]:
        """Discover post URLs. max_pages=0 means continue until pagination ends."""
        collected: list[str] = []
        seen_pages: set[str] = set()
        current_url = self.design_url
        page_number = 1
        consecutive_empty = 0

        while current_url and current_url not in seen_pages:
            if max_pages > 0 and page_number > max_pages:
                break
            seen_pages.add(current_url)
            response = self.client.get(current_url, allow_404=True)
            if response.status_code == 404:
                break
            page_urls = self._extract_post_urls(response.text, current_url)
            new_urls = [url for url in page_urls if url not in collected]
            LOGGER.info("목록 %s페이지: 새 게시물 %s개", page_number, len(new_urls))
            collected.extend(new_urls)
            consecutive_empty = consecutive_empty + 1 if not new_urls else 0
            if consecutive_empty >= 2:
                break
            next_url = self._next_page_url(response.text, current_url, page_number)
            if not next_url or next_url in seen_pages:
                break
            current_url = next_url
            page_number += 1
        return collected

    def fetch_post(self, url: str) -> PostRecord:
        response = self.client.get(url)
        return parse_post_html(response.text, url)
