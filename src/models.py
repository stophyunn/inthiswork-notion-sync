from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal[
    "heading_1",
    "heading_2",
    "heading_3",
    "paragraph",
    "bulleted_list_item",
    "numbered_list_item",
    "quote",
    "divider",
]


@dataclass(frozen=True)
class ContentBlock:
    kind: BlockKind
    text: str = ""


@dataclass
class PostRecord:
    post_id: str
    source_url: str
    title: str
    content_type: str
    site_categories: list[str] = field(default_factory=list)
    organization: str = ""
    role_or_program: str = ""
    design_fields: list[str] = field(default_factory=list)
    experience_class: str = "해당 없음"
    experience_raw: str = ""
    employment_types: list[str] = field(default_factory=list)
    target_audience: str = ""
    location: str = ""
    key_duties: str = ""
    qualifications: str = ""
    preferred_qualifications: str = ""
    essay_questions: str = ""
    pre_assignment: str = ""
    benefits_prize: str = ""
    deadline: str | None = None
    activity_period: str = ""
    published_date: str | None = None
    status: str = "확인 필요"
    apply_url: str | None = None
    collection_status: str = "정상"
    quality_reasons: dict[str, bool] = field(default_factory=dict)
    body_blocks: list[ContentBlock] = field(default_factory=list)
    content_hash: str = ""
