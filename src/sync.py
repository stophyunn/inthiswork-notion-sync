from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict

from .config import Settings
from .http_client import (
    PoliteHttpClient,
    SiteBlockedError,
    SiteNotFoundError,
    SiteRateLimitedError,
)
from .notion_api import NotionClient
from .scraper import InThisWorkScraper

LOGGER = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if settings.sync_mode not in {"recent", "full"}:
        raise SystemExit("SYNC_MODE는 recent 또는 full이어야 합니다.")
    if not settings.dry_run and not settings.notion_data_source_id:
        raise SystemExit("NOTION_DATA_SOURCE_ID가 비어 있습니다.")

    source_client = PoliteHttpClient(
        settings.design_url,
        delay_seconds=settings.request_delay_seconds,
        timeout_seconds=settings.request_timeout_seconds,
    )
    scraper = InThisWorkScraper(source_client, settings.design_url)
    notion = (
        None
        if settings.dry_run
        else NotionClient(settings.notion_token, settings.notion_api_version)
    )

    urls = scraper.discover_post_urls(max_pages=settings.list_page_limit())
    if notion is not None and settings.sync_mode == "recent":
        for item in notion.query_open_for_recheck(
            settings.notion_data_source_id, settings.recheck_open_limit
        ):
            if item["url"] not in urls:
                urls.append(item["url"])

    if settings.max_posts_per_run > 0:
        urls = urls[: settings.max_posts_per_run]

    counters = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}
    LOGGER.info("처리 대상 URL: %s개", len(urls))

    for index, url in enumerate(urls, start=1):
        post_id = url.rstrip("/").split("/")[-1]
        LOGGER.info("[%s/%s] %s", index, len(urls), url)
        existing = None
        try:
            if notion is not None:
                existing = notion.query_by_post_id(settings.notion_data_source_id, post_id)
            record = scraper.fetch_post(url)

            if settings.dry_run:
                preview = asdict(record)
                preview["body_blocks"] = [asdict(block) for block in record.body_blocks[:8]]
                print(json.dumps(preview, ensure_ascii=False, indent=2))
                counters["skipped"] += 1
                continue

            assert notion is not None
            if existing is None:
                notion.create_record(settings.notion_data_source_id, record)
                counters["created"] += 1
            else:
                changed = notion.existing_hash(existing) != record.content_hash
                notion.update_record(existing, record, changed=changed)
                counters["updated" if changed else "unchanged"] += 1
        except SiteNotFoundError:
            LOGGER.warning("원문이 사라졌거나 404입니다: %s", url)
            if notion is not None and existing is not None:
                notion.mark_inaccessible(existing)
                counters["updated"] += 1
            else:
                counters["skipped"] += 1
        except (SiteRateLimitedError, SiteBlockedError) as exc:
            LOGGER.error("%s", exc)
            LOGGER.error("접근 제한을 우회하지 않고 즉시 중단합니다.")
            raise SystemExit(2) from exc
        except Exception:
            counters["errors"] += 1
            LOGGER.exception("게시물 처리 중 오류가 발생했습니다: %s", url)

    LOGGER.info("동기화 결과: %s", counters)
    print("SYNC_SUMMARY=" + json.dumps(counters, ensure_ascii=False))
    if counters["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
