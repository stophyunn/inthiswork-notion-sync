from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import requests

from .models import ContentBlock, PostRecord

LOGGER = logging.getLogger(__name__)
NOTION_BASE_URL = "https://api.notion.com/v1"


def extract_notion_id(value: str) -> str:
    compact = value.strip()
    if "://" in compact:
        from urllib.parse import urlparse

        candidate = urlparse(compact).path.rstrip("/").split("/")[-1]
    else:
        candidate = compact
    normalized = candidate.replace("-", "")
    match = re.search(r"([0-9a-fA-F]{32})$", normalized)
    if not match:
        # Fallback for values containing labels or surrounding text.
        matches = re.findall(r"[0-9a-fA-F]{32}", normalized)
        if not matches:
            raise ValueError("Notion 페이지/데이터소스 ID를 찾을 수 없습니다.")
        raw = matches[-1].lower()
    else:
        raw = match.group(1).lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def _rich_text(text: str, link: str | None = None) -> list[dict[str, Any]]:
    if not text:
        return []
    chunks = [text[i : i + 1900] for i in range(0, len(text), 1900)]
    output: list[dict[str, Any]] = []
    for chunk in chunks:
        item: dict[str, Any] = {"type": "text", "text": {"content": chunk}}
        if link:
            item["text"]["link"] = {"url": link}
        output.append(item)
    return output


def _property_plain_text(prop: dict[str, Any]) -> str:
    prop_type = prop.get("type")
    if prop_type in {"title", "rich_text"}:
        return "".join(item.get("plain_text", "") for item in prop.get(prop_type, []))
    if prop_type == "url":
        return prop.get("url") or ""
    if prop_type == "select":
        selected = prop.get("select")
        return selected.get("name", "") if selected else ""
    return ""


def database_schema() -> dict[str, Any]:
    return {
        "공고명": {"title": {}},
        "콘텐츠 유형": {
            "select": {
                "options": [
                    {"name": "채용공고"},
                    {"name": "공모전"},
                    {"name": "대외활동"},
                    {"name": "교육·프로그램"},
                    {"name": "커리어 콘텐츠"},
                    {"name": "기타·확인 필요"},
                ]
            }
        },
        "사이트 원분류": {
            "multi_select": {
                "options": [
                    {"name": "신입/인턴"},
                    {"name": "주니어경력"},
                    {"name": "교육/대외활동"},
                    {"name": "대외활동"},
                    {"name": "커리어TV"},
                    {"name": "취업토크"},
                ]
            }
        },
        "기관/회사명": {"rich_text": {}},
        "직무/프로그램명": {"rich_text": {}},
        "디자인 분야": {
            "multi_select": {
                "options": [
                    {"name": "UI/UX"},
                    {"name": "프로덕트"},
                    {"name": "BX/브랜드"},
                    {"name": "그래픽"},
                    {"name": "콘텐츠"},
                    {"name": "영상/모션"},
                    {"name": "VMD"},
                    {"name": "패키지"},
                    {"name": "공간/무대"},
                    {"name": "웹"},
                    {"name": "캐릭터/일러스트"},
                    {"name": "산업/제품"},
                    {"name": "패션"},
                ]
            }
        },
        "경력 분류": {
            "select": {
                "options": [
                    {"name": "신입"},
                    {"name": "인턴"},
                    {"name": "경력"},
                    {"name": "경력무관"},
                    {"name": "해당 없음"},
                    {"name": "확인 필요"},
                ]
            }
        },
        "경력 원문": {"rich_text": {}},
        "고용형태": {
            "multi_select": {
                "options": [
                    {"name": "정규직"},
                    {"name": "계약직"},
                    {"name": "체험형 인턴"},
                    {"name": "전환형 인턴"},
                    {"name": "인턴"},
                    {"name": "프리랜서"},
                    {"name": "아르바이트"},
                    {"name": "파트타임"},
                ]
            }
        },
        "지원 대상": {"rich_text": {}},
        "근무·활동 지역": {"rich_text": {}},
        "주요 업무·활동": {"rich_text": {}},
        "혜택·상금": {"rich_text": {}},
        "마감일": {"date": {}},
        "활동 기간": {"rich_text": {}},
        "게시일": {"date": {}},
        "공고 상태": {
            "select": {
                "options": [
                    {"name": "모집 중"},
                    {"name": "마감"},
                    {"name": "확인 필요"},
                ]
            }
        },
        "원문 링크": {"url": {}},
        "지원 링크": {"url": {}},
        "인디스워크 ID": {"rich_text": {}},
        "최종 확인일": {"date": {}},
        "수집 상태": {
            "select": {
                "options": [
                    {"name": "정상"},
                    {"name": "일부 누락"},
                    {"name": "검토 필요"},
                ]
            }
        },
        "원문 변경": {"checkbox": {}},
        "원문 해시": {"rich_text": {}},
    }


@dataclass
class NotionClient:
    token: str
    api_version: str = "2026-03-11"
    min_interval_seconds: float = 0.38

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("NOTION_TOKEN이 비어 있습니다.")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": self.api_version,
                "Content-Type": "application/json",
            }
        )
        self._last_request_at = 0.0

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{NOTION_BASE_URL}{path}"
        for attempt in range(1, 6):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.min_interval_seconds:
                time.sleep(self.min_interval_seconds - elapsed)
            response = self.session.request(method, url, json=json, timeout=30)
            self._last_request_at = time.monotonic()
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", attempt * 2))
                LOGGER.warning("Notion API 요청 제한. %.1f초 후 재시도합니다.", wait)
                time.sleep(wait)
                continue
            if response.status_code >= 500 and attempt < 5:
                time.sleep(attempt * 2)
                continue
            if not response.ok:
                raise RuntimeError(
                    f"Notion API 오류 {response.status_code} {method} {path}: {response.text[:1000]}"
                )
            if not response.content:
                return {}
            return response.json()
        raise RuntimeError(f"Notion API 요청이 반복 실패했습니다: {method} {path}")

    def create_database(self, parent_page_id: str, title: str = "Design Opportunities") -> tuple[str, str]:
        payload = {
            "parent": {"type": "page_id", "page_id": extract_notion_id(parent_page_id)},
            "title": [{"type": "text", "text": {"content": title}}],
            "description": [
                {
                    "type": "text",
                    "text": {
                        "content": "인디스워크 디자인 직무·공모전·대외활동·교육 게시물 자동 수집"
                    },
                }
            ],
            "is_inline": True,
            "initial_data_source": {"properties": database_schema()},
            "icon": {"type": "emoji", "emoji": "🎨"},
        }
        response = self._request("POST", "/databases", json=payload)
        database_id = response["id"]
        data_sources = response.get("data_sources", [])
        if data_sources:
            return database_id, data_sources[0]["id"]
        database = self._request("GET", f"/databases/{database_id}")
        sources = database.get("data_sources", [])
        if not sources:
            raise RuntimeError("생성된 데이터베이스에서 data_source_id를 찾지 못했습니다.")
        return database_id, sources[0]["id"]

    def retrieve_data_source(self, data_source_id: str) -> dict[str, Any]:
        return self._request("GET", f"/data_sources/{extract_notion_id(data_source_id)}")

    def query_by_post_id(self, data_source_id: str, post_id: str) -> dict[str, Any] | None:
        payload = {
            "filter": {
                "property": "인디스워크 ID",
                "rich_text": {"equals": post_id},
            },
            "page_size": 5,
        }
        result = self._request(
            "POST", f"/data_sources/{extract_notion_id(data_source_id)}/query", json=payload
        )
        pages = result.get("results", [])
        return pages[0] if pages else None

    def query_open_for_recheck(self, data_source_id: str, limit: int = 20) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        payload = {
            "filter": {"property": "공고 상태", "select": {"equals": "모집 중"}},
            "sorts": [{"property": "최종 확인일", "direction": "ascending"}],
            "page_size": min(limit, 100),
        }
        result = self._request(
            "POST", f"/data_sources/{extract_notion_id(data_source_id)}/query", json=payload
        )
        output: list[dict[str, str]] = []
        for page in result.get("results", [])[:limit]:
            props = page.get("properties", {})
            output.append(
                {
                    "page_id": page.get("id", ""),
                    "post_id": _property_plain_text(props.get("인디스워크 ID", {})),
                    "url": _property_plain_text(props.get("원문 링크", {})),
                }
            )
        return [item for item in output if item["url"] and item["post_id"]]

    def _record_properties(self, record: PostRecord, *, changed: bool) -> dict[str, Any]:
        today = date.today().isoformat()
        return {
            "공고명": {"title": _rich_text(record.title[:1900])},
            "콘텐츠 유형": {"select": {"name": record.content_type}},
            "사이트 원분류": {
                "multi_select": [{"name": value} for value in record.site_categories]
            },
            "기관/회사명": {"rich_text": _rich_text(record.organization[:1800])},
            "직무/프로그램명": {"rich_text": _rich_text(record.role_or_program[:1800])},
            "디자인 분야": {
                "multi_select": [{"name": value} for value in record.design_fields]
            },
            "경력 분류": {"select": {"name": record.experience_class}},
            "경력 원문": {"rich_text": _rich_text(record.experience_raw[:1800])},
            "고용형태": {
                "multi_select": [{"name": value} for value in record.employment_types]
            },
            "지원 대상": {"rich_text": _rich_text(record.target_audience[:1800])},
            "근무·활동 지역": {"rich_text": _rich_text(record.location[:1800])},
            "주요 업무·활동": {"rich_text": _rich_text(record.key_duties[:1800])},
            "혜택·상금": {"rich_text": _rich_text(record.benefits_prize[:1800])},
            "마감일": {"date": {"start": record.deadline} if record.deadline else None},
            "활동 기간": {"rich_text": _rich_text(record.activity_period[:1800])},
            "게시일": {
                "date": {"start": record.published_date} if record.published_date else None
            },
            "공고 상태": {"select": {"name": record.status}},
            "원문 링크": {"url": record.source_url},
            "지원 링크": {"url": record.apply_url},
            "인디스워크 ID": {"rich_text": _rich_text(record.post_id)},
            "최종 확인일": {"date": {"start": today}},
            "수집 상태": {"select": {"name": record.collection_status}},
            "원문 변경": {"checkbox": changed},
            "원문 해시": {"rich_text": _rich_text(record.content_hash)},
        }

    def _content_blocks(self, record: PostRecord) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": _rich_text("원문")},
            }
        ]
        for block in record.body_blocks:
            if block.kind == "divider":
                blocks.append({"object": "block", "type": "divider", "divider": {}})
                continue
            text_chunks = [block.text[i : i + 1900] for i in range(0, len(block.text), 1900)] or [""]
            for text in text_chunks:
                kind = block.kind
                payload_kind = kind if kind in {
                    "heading_1",
                    "heading_2",
                    "heading_3",
                    "paragraph",
                    "bulleted_list_item",
                    "numbered_list_item",
                    "quote",
                } else "paragraph"
                blocks.append(
                    {
                        "object": "block",
                        "type": payload_kind,
                        payload_kind: {"rich_text": _rich_text(text)},
                    }
                )
        blocks.extend(
            [
                {"object": "block", "type": "divider", "divider": {}},
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": "출처: "}},
                            {
                                "type": "text",
                                "text": {
                                    "content": record.source_url,
                                    "link": {"url": record.source_url},
                                },
                            },
                        ]
                    },
                },
            ]
        )
        return blocks

    def _append_blocks(self, page_id: str, blocks: Iterable[dict[str, Any]]) -> None:
        block_list = list(blocks)
        for index in range(0, len(block_list), 100):
            self._request(
                "PATCH",
                f"/blocks/{page_id}/children",
                json={"children": block_list[index : index + 100]},
            )

    def create_record(self, data_source_id: str, record: PostRecord) -> str:
        blocks = self._content_blocks(record)
        payload = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": extract_notion_id(data_source_id),
            },
            "properties": self._record_properties(record, changed=False),
            "children": blocks[:100],
        }
        page = self._request("POST", "/pages", json=payload)
        if len(blocks) > 100:
            self._append_blocks(page["id"], blocks[100:])
        return page["id"]

    def _get_all_children(self, page_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            suffix = f"?page_size=100&start_cursor={cursor}" if cursor else "?page_size=100"
            response = self._request("GET", f"/blocks/{page_id}/children{suffix}")
            results.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return results

    def _replace_page_body(self, page_id: str, record: PostRecord) -> None:
        for block in self._get_all_children(page_id):
            self._request("DELETE", f"/blocks/{block['id']}")
        self._append_blocks(page_id, self._content_blocks(record))

    def existing_hash(self, page: dict[str, Any]) -> str:
        return _property_plain_text(page.get("properties", {}).get("원문 해시", {}))

    def update_record(self, page: dict[str, Any], record: PostRecord, *, changed: bool) -> None:
        page_id = page["id"]
        self._request(
            "PATCH",
            f"/pages/{page_id}",
            json={"properties": self._record_properties(record, changed=changed)},
        )
        if changed:
            self._replace_page_body(page_id, record)

    def mark_inaccessible(self, page: dict[str, Any]) -> None:
        today = date.today().isoformat()
        self._request(
            "PATCH",
            f"/pages/{page['id']}",
            json={
                "properties": {
                    "공고 상태": {"select": {"name": "확인 필요"}},
                    "수집 상태": {"select": {"name": "검토 필요"}},
                    "최종 확인일": {"date": {"start": today}},
                }
            },
        )
