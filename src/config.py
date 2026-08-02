from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_parent_page_id: str
    notion_data_source_id: str
    notion_api_version: str
    design_url: str
    sync_mode: str
    recent_list_pages: int
    full_list_pages: int
    max_list_pages_override: int | None
    max_posts_per_run: int
    recheck_open_limit: int
    request_delay_seconds: float
    request_timeout_seconds: float
    dry_run: bool

    @classmethod
    def from_env(cls) -> "Settings":
        override_raw = os.getenv("MAX_LIST_PAGES", "").strip()
        override = int(override_raw) if override_raw else None
        return cls(
            notion_token=os.getenv("NOTION_TOKEN", "").strip(),
            notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID", "").strip(),
            notion_data_source_id=os.getenv("NOTION_DATA_SOURCE_ID", "").strip(),
            notion_api_version=os.getenv("NOTION_API_VERSION", "2026-03-11").strip(),
            design_url=os.getenv("INTHISWORK_DESIGN_URL", "https://inthiswork.com/design").strip(),
            sync_mode=os.getenv("SYNC_MODE", "recent").strip().lower(),
            recent_list_pages=_int("RECENT_LIST_PAGES", 3),
            full_list_pages=_int("FULL_LIST_PAGES", 0),
            max_list_pages_override=override,
            max_posts_per_run=_int("MAX_POSTS_PER_RUN", 0),
            recheck_open_limit=_int("RECHECK_OPEN_LIMIT", 20),
            request_delay_seconds=_float("INTHISWORK_REQUEST_DELAY_SECONDS", 2.5),
            request_timeout_seconds=_float("REQUEST_TIMEOUT_SECONDS", 25.0),
            dry_run=_bool("DRY_RUN", False),
        )

    def list_page_limit(self) -> int:
        if self.max_list_pages_override is not None:
            return self.max_list_pages_override
        return self.full_list_pages if self.sync_mode == "full" else self.recent_list_pages
