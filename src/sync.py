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
from .models import PostRecord
from .notion_api import NotionClient
from .parser import heading_candidates
from .scraper import InThisWorkScraper

LOGGER = logging.getLogger(__name__)


def _dry_run_preview(record: PostRecord) -> dict[str, object]:
    preview = asdict(record)
    blocks = preview.pop("body_blocks")
    assert isinstance(blocks, list)
    preview["body_blocks_total"] = len(blocks)
    preview["body_blocks_omitted"] = max(0, len(blocks) - 8)
    preview["body_blocks_preview"] = blocks[:8]
    preview["body_blocks_last"] = blocks[-1] if blocks else None
    if record.quality_reasons.get("missing_job_duties"):
        preview["heading_candidates"] = heading_candidates(record.body_blocks)
    return preview


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
    if notion is not None:
        # Dry runs deliberately avoid Notion. Real writes fail before scraping
        # rather than silently dropping structured fields from the payload.
        notion.validate_sync_schema(settings.notion_data_source_id)

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
        existing_for_missing = None
        try:
            if notion is not None:
                existing_for_missing = notion.query_by_post_id(
                    settings.notion_data_source_id, post_id
                )
            records = scraper.fetch_posts(url)
            for record in records:
                existing = None
                if notion is not None:
                    existing = (
                        existing_for_missing
                        if record.post_id == post_id
                        else notion.query_by_post_id(
                            settings.notion_data_source_id, record.post_id
                        )
                    )

                quality_issues: list[str] = []
                if not record.body_blocks:
                    quality_issues.append("본문 블록 없음")
                if record.content_type == "기타·확인 필요":
                    quality_issues.append("콘텐츠 유형 미분류")
                if record.content_type == "채용공고" and not record.employment_types:
                    quality_issues.append("고용형태 누락")
                if quality_issues:
                    LOGGER.warning(
                        "파싱 품질 검토 필요 (%s, ID=%s): %s",
                        url,
                        record.post_id,
                        ", ".join(quality_issues),
                    )

                if settings.dry_run:
                    if record.collection_status == "검토 필요":
                        active_reasons = [
                            name for name, active in record.quality_reasons.items() if active
                        ]
                        LOGGER.warning(
                            "dry-run 수집 상태 검토 필요 (URL=%s, ID=%s): %s",
                            url,
                            record.post_id,
                            ", ".join(active_reasons),
                        )
                    preview = _dry_run_preview(record)
                    print(json.dumps(preview, ensure_ascii=False, indent=2))
                    counters["skipped"] += 1
                    continue

                assert notion is not None
                if existing is None:
                    notion.create_record(settings.notion_data_source_id, record)
                    counters["created"] += 1
                else:
                    changed = notion.existing_hash(existing) != record.content_hash
                    if changed:
                        notion.update_record(existing, record, changed=True)
                    counters["updated" if changed else "unchanged"] += 1
        except SiteNotFoundError:
            LOGGER.warning("원문이 사라졌거나 404입니다: %s", url)
            if notion is not None and existing_for_missing is not None:
                notion.mark_inaccessible(existing_for_missing)
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
