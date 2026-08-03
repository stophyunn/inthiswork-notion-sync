from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import date, datetime
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from .models import ContentBlock, PostRecord

GENERIC_PREFIXES = {
    "대외활동",
    "공모전",
    "교육",
    "교육/대외활동",
    "신입/인턴",
    "주니어경력",
    "채용",
}

CATEGORY_WHITELIST = {
    "신입/인턴",
    "주니어경력",
    "교육/대외활동",
    "대외활동",
    "커리어TV",
    "취업토크",
}

NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "nav",
    "footer",
    "aside",
    ".sharedaddy",
    ".jp-relatedposts",
    ".related-posts",
    ".fusion-sharing-box",
    ".fusion-meta-info",
    ".post-meta",
    ".comments-area",
    ".single-navigation",
    ".fusion-post-title-meta-wrap",
    ".yarpp-related",
    ".adsbygoogle",
    ".fusion-comments-tb",
    ".fusion-related-posts",
    ".fusion-post-cards",
    ".related-posts-wrapper",
    ".recent-comments",
]

SECTION_HEADINGS = {
    "duties": (
        "우리 팀과 함께할 미션을 소개합니다", "함께할 미션을 소개합니다",
        "합류하면 아래와 같은 업무를 하게 됩니다",
        "저희와 함께 하시게 될 일들이에요", "저희와 함께 하게 될 일들이에요",
        "함께 하시게 될 일들이에요", "함께 하게 될 일들이에요",
        "이런 일을 합니다", "이런 일을 해요", "이런 일을 하게 됩니다", "담당하게 될 일",
        "이런 일을 함께해요", "이런 경험을 할 수 있어요", "이런 업무를 함께 할 예정이에요",
        "이런 업무를 담당해요", "합류하면 함께 할 업무예요", "합류하면 함께할 업무예요",
        "주요 업무", "주요 업무 및 역할", "주요업무 및 역할", "담당 업무", "담당업무 및 역할",
        "담당하실 업무", "수행 업무", "업무 내용",
        "하실 일", "역할",
        "Responsibilities", "What you'll do", "What you will do", "Your role",
    ),
    "audience": (
        "우리는 이런 분을 찾고 있어요", "우리는 이런 분을 찾습니다",
        "이런 분을 모시고 싶어요", "이런 분을 모시고 싶습니다",
        "이런 분을 모시고 있어요", "이런 분을 찾고 있어요", "이런 분을 찾습니다",
        "이런 분을 찾아요", "우리가 찾는 분", "이런 분을 기다립니다",
        "이런 분과 함께하고 싶어요", "이런 분과 함께하고 싶습니다", "이런 역량을 가진 분을 찾아요",
        "지원 자격", "지원자격", "자격 요건", "자격요건",
        "필수 사항", "필수 요건", "필수 자격", "지원자격 및 요건", "지원 자격 및 요건",
        "자격요건 및 역량", "지원 대상", "Requirements", "Qualifications",
        "Required", "Required Qualifications", "What we're looking for", "Who you are",
    ),
    "preferred": (
        "이런 분이면 더더욱 환영해요", "이런 분이면 더 좋아요", "이런 분이면 좋습니다",
        "이런 경험을 우대합니다", "있으면 좋은 경험", "이런 경험이 있다면 더욱 좋아요",
        "이런 경험이 있다면 더 좋아요", "이번 채용은 이런 분을 우대해요",
        "우대 사항", "우대사항", "우대사항 및 역량", "우대 사항 및 역량", "우대 요건", "우대 자격",
        "Preferred Qualifications",
        "Preferred", "Nice to have", "Nice-to-have", "Plus if you have",
    ),
    "benefits": (
        "혜택", "혜택 및 복지", "복지", "복리후생", "디밀은 이렇게 일해요", "이런 혜택을 드려요",
        "지원 내용", "참여 혜택", "활동 혜택", "상금", "시상 내역",
    ),
    "conditions": (
        "고용 조건", "근무 환경", "근무 조건", "근무 형태", "근무 장소", "근무지",
        "꼭 확인해주세요",
    ),
    "process": (
        "채용은 이렇게 진행돼요", "전형 절차 및 일정", "지원 전 꼭 확인해 주세요", "참고 사항",
        "지원서류", "인재영입 프로세스", "채용 절차", "이력서는 이렇게 작성하시는 걸 추천해요",
        "토스로의 합류여정", "채용 전형", "합류 여정", "전형 절차", "지원 절차", "지원 방법",
        "지원 서류", "제출 서류",
    ),
    "essay": (
        "자기소개서 문항", "자기 소개서 문항", "자소서 문항", "지원서 문항", "에세이 문항",
        "지원서 질문", "자기소개서 질문", "작성 문항", "지원 시 작성해 주세요", "지원 시 작성해주세요",
        "Essay Questions", "Application Questions", "Written Questions",
    ),
    "assignment": (
        "사전과제", "사전 과제", "사전과제로 지원하기", "과제 전형", "직무 과제", "디자인 과제", "디자인 테스트",
        "실무 과제", "과제 안내", "제출 과제", "과제 제출", "사전 테스트", "Assignment",
        "Take-home Assignment", "Take Home Assignment", "Design Test", "Task", "Practical Test",
    ),
}
SECTION_BOUNDARY_HEADINGS = (
    "문화 및 복지", "문화 및", "복지", "복리후생", "혜택", "마감기한", "마감 기한",
    "접수 기간", "접수기간", "접수 마감", "지원서 접수 마감", "마감일", "게시일", "등록일",
    "채용 시 마감", "기타 사항", "유의사항", "회사 소개",
    "팀 소개", "포지션 소개", "채용 배경", "지원 시 직군/직무 설정", "직군/직무 설정",
    "포트폴리오로 지원하기", "토스플레이스로의 합류 여정",
    "이런 분이면 잘 맞습니다", "이런 분이면 잘 맞아요",
    "이런 분과 잘 맞습니다", "이런 분과 잘 맞아요",
    "합류 과정", "합류 프로세스", "채용 여정",
    "최고의 동료와 함께, 성장에만 집중하세요",
    "최고의 동료와 함께 성장에만 집중하세요", "복지 및 문화",
    "성장 지원", "성장을 위한 전폭적인 지원",
    "이렇게 성장할 수 있어요", "이렇게 성장할 수 있습니다",
    "합류 여정 안내드려요", "바이트랩 합류 여정 안내드려요",
    "크래프톤의 도전에 함께 하기 위해 아래의 전형 과정이 필요합니다",
    "아래의 전형 과정이 필요합니다", "전형 과정",
    "필요 서류를 확인해주세요", "아래 안내 사항을 확인해주세요",
)
SECTION_HEADING_VALUES = tuple(
    heading for headings in SECTION_HEADINGS.values() for heading in headings
)
SECTION_TITLE_PATTERN = "|".join(
    sorted((re.escape(value).replace(r"\ ", r"\s*") for value in SECTION_HEADING_VALUES), key=len, reverse=True)
)
SECTION_TITLE_RE = re.compile(
    rf"^\s*[\[(]?\s*(?:{SECTION_TITLE_PATTERN})\s*(?:\([^)]*\))?\s*[:：]?\s*[\])]?\s*$",
    re.I,
)
INLINE_SECTION_RE = re.compile(rf"\[\s*(?:{SECTION_TITLE_PATTERN})\s*\]|(?:{SECTION_TITLE_PATTERN})", re.I)
DECORATION_ONLY_RE = re.compile(r"^[\sㆍ•·\-–—😉❤❤️♡]+$")
STRUCTURED_DECORATION_RE = re.compile(r"^[\s\[\](){}:：!！❖🌟📌🎯✨😀🎆📩🤝🎁ㆍ•·\-–—]+$")
URL_ONLY_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
STRUCTURED_LEAK_RE = re.compile(
    r"^(?:사전과제\s*확인하기|※?\s*지원\s*시\s*직군\s*/\s*직무\s*설정|"
    r"직군\s*/\s*직무\s*설정|(?:Design|Service\s*&\s*Business)\s*>.*)$",
    re.I,
)
ROLE_MARKER_RE = re.compile(
    r"^\s*(?:\d{1,2}[.)]\s*)?(?=\S)(?:.*?)(?:디자이너|디자인|UI\s*/?\s*UX|그래픽|BX|브랜드|일러스트)"
    r"(?:.*?)(?:인턴|디자이너|직무|부문)\s*$",
    re.I,
)
NUMBERED_JOB_MARKER_RE = re.compile(
    r"^\s*(\d{1,2})[.)]\s*\S.{0,100}(?:인턴|디자이너|매니저|개발|기획|마케팅|직무|채용)\s*$",
    re.I,
)
COMPACT_BULLET_RE = re.compile(r"^[ㆍ•·]\s*(\S.*)$")
SPACED_BULLET_RE = re.compile(r"^[\-–—]\s+(\S.*)$")
RESUME_GUIDANCE_RE = re.compile(
    r"(?:이력서|지원서).*?(?:작성|기재)|"
    r"개인\s*인적\s*사항.*?(?:시기|기재)|"
    r"학력.*?대외활동.*?인턴.*?(?:시기|작성|기재)",
    re.I,
)
ESSAY_SUBMISSION_ONLY_RE = re.compile(
    r"^(?:(?:국문\s*)?이력서\s*(?:및|와|,)?\s*)?(?:자유\s*양식\s*)?"
    r"자기\s*소개서\s*(?:제출|첨부|파일)?(?:해\s*주세요|필수)?[.!]?$",
    re.I,
)
MIN_RENDER_REPEAT_BLOCKS = 6
MIN_RENDER_REPEAT_CHARS = 180
MIN_UNRESOLVED_REPEAT_BLOCKS = 4
MIN_UNRESOLVED_REPEAT_CHARS = 120


def _heading_patterns(kind: str) -> list[str]:
    return [re.escape(value).replace(r"\ ", r"\s*") for value in SECTION_HEADINGS[kind]]


def _strip_heading_wrapper(text: str) -> str:
    value = clean_text(text)
    value = re.sub(r"^[\s\[\](){}【】（）：:🌟📌🎯✨😀🎆📩🤝🎁❖※!！]+", "", value)
    value = re.sub(r"[\s\[\](){}【】（）：:!！.。]+$", "", value)
    return clean_text(value)


def _exact_section_kind(text: str) -> str | None:
    original = clean_text(text)
    inner_candidates = re.findall(r"[\(（【\[]\s*([^\)）】\]]{2,50})\s*[\)）】\]]", original)
    candidates = [_strip_heading_wrapper(value) for value in inner_candidates]
    candidates.append(_strip_heading_wrapper(original))
    for candidate in candidates:
        if not candidate:
            continue
        for kind in SECTION_HEADINGS:
            if any(re.fullmatch(pattern, candidate, re.I) for pattern in _heading_patterns(kind)):
                return kind
        if any(
            re.fullmatch(re.escape(value).replace(r"\ ", r"\s*"), candidate, re.I)
            for value in SECTION_BOUNDARY_HEADINGS
        ):
            return "boundary"
    candidate = candidates[-1]
    if not candidate:
        return None
    if len(candidate) <= 60 and re.fullmatch(
        r".+?(?:디자이너|Designer|디자인\s*직무|디자인\s*팀)(?:는|은)\s*이렇게\s*일해요",
        candidate,
        re.I,
    ):
        return "duties"
    if len(candidate) <= 60 and re.fullmatch(r".+?에서는\s*이런\s*일을\s*해요", candidate, re.I):
        return "duties"
    if len(candidate) <= 80 and re.fullmatch(
        r".+?는\s*두\s*가지\s*방식으로\s*지원할\s*수\s*있어요", candidate, re.I
    ):
        return "boundary"
    if len(candidate) <= 100 and re.fullmatch(
        r".+?로서\s*하게\s*될\s*일은\s*다음과\s*같습니다", candidate, re.I
    ):
        return "duties"
    if re.fullmatch(r"(?:Design|Service\s*&\s*Business)\s*>.*", candidate, re.I):
        return "boundary"
    return None


def _logical_section_kind(blocks: list[ContentBlock], index: int) -> str | None:
    direct = _exact_section_kind(blocks[index].text)
    if direct:
        return direct
    # Fusion can split one heading across adjacent paragraph/heading nodes,
    # such as "지원" + "자격" + "요건" or "문화 및" + "복지".
    for start, end in (
        (index - 1, index + 1), (index, index + 2), (index - 1, index + 2),
        (index, index + 3),
    ):
        if start < 0 or end > len(blocks):
            continue
        pieces = [_strip_heading_wrapper(block.text) for block in blocks[start:end]]
        if any(not piece or len(piece) > 30 for piece in pieces):
            continue
        combined = clean_text(" ".join(pieces))
        if re.fullmatch(r"지원\s*자격\s*요건", combined):
            return "audience"
        combined_kind = _exact_section_kind(combined)
        if combined_kind:
            return combined_kind
    return None


def _is_role_marker(block: ContentBlock) -> bool:
    text = _strip_heading_wrapper(block.text)
    numbered = bool(re.match(r"^\d{1,2}[.)]\s*", text))
    return bool(ROLE_MARKER_RE.fullmatch(text)) and (
        block.kind.startswith("heading") or numbered
    ) and bool(detect_design_fields(text, ""))


def _numbered_job_marker(block: ContentBlock) -> re.Match[str] | None:
    return NUMBERED_JOB_MARKER_RE.fullmatch(_strip_heading_wrapper(block.text))


def _is_design_numbered_role(role_title: str, blocks: list[ContentBlock]) -> bool:
    """Classify a numbered role from its title and explicit application path."""
    title = _strip_heading_wrapper(role_title)
    lines = [_strip_heading_wrapper(block.text) for block in blocks]
    if any(re.match(r"^Service\s*&\s*Business\s*>", line, re.I) for line in lines):
        return False
    if any(re.match(r"^Design\s*>", line, re.I) for line in lines):
        return True
    explicit_design = re.search(
        r"(?:디자이너|디자인|Designer|Product\s+Design|Visual\s+Design|Graphic\s+Design|"
        r"UI\s*/?\s*UX\s+Design|BX\s*/?\s*Brand\s+Design|Content\s+Design)",
        title,
        re.I,
    )
    non_design = re.search(
        r"(?:기획\s*/?\s*운영|Content\s+Development|Product\s+Development|Marketing|Operation|Planning)",
        title,
        re.I,
    )
    return bool(explicit_design) and not (
        non_design and not re.search(r"디자인|디자이너|Design|Designer", title, re.I)
    )


def heading_candidates(blocks: list[ContentBlock]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for index, block in enumerate(blocks):
        if len(block.text) > 100:
            continue
        normalized = _strip_heading_wrapper(block.text)
        section = _logical_section_kind(blocks, index)
        candidates.append(
            {
                "index": index,
                "kind": block.kind,
                "text": block.text,
                "normalized": normalized,
                "section": "qualifications" if section == "audience" else section,
            }
        )
    return candidates
TRAILING_NOISE_RE = re.compile(
    r"(?:최신\s*댓글|추천\s*(?:아티클|콘텐츠|공고)|오늘\s*핫한\s*공고|"
    r"함께\s*보면\s*좋은\s*커리어\s*정보|관련\s*공고|카톡\s*(?:채팅방|오픈채팅)|"
    r"공유\s*(?:안내|하기)|댓글\s*(?:남기기|목록))",
    re.I,
)


def clean_text(value: str) -> str:
    value = unescape(value or "")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    value = re.sub(r"[\t\r\f\v]+", " ", value)
    value = re.sub(r"[ ]{2,}", " ", value)
    value = re.sub(r"\n[ ]+", "\n", value)
    value = re.sub(r"[ ]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _bullet_text(value: str) -> str | None:
    """Return text after a supported line-leading bullet marker."""
    normalized = clean_text(value)
    marker = COMPACT_BULLET_RE.match(normalized) or SPACED_BULLET_RE.match(normalized)
    return clean_text(marker.group(1)) if marker else None


def _sequence_text_length(blocks: list[ContentBlock]) -> int:
    return sum(len(block.text) for block in blocks if block.text)


def _find_repeated_sequence(
    blocks: list[ContentBlock],
    min_blocks: int,
    min_chars: int,
    complete_render_only: bool = False,
) -> tuple[int, int, int] | None:
    """Return the longest non-overlapping repeated contiguous block sequence."""
    for size in range(len(blocks) // 2, min_blocks - 1, -1):
        positions: dict[tuple[ContentBlock, ...], int] = {}
        for start in range(0, len(blocks) - size + 1):
            sequence = tuple(blocks[start : start + size])
            first_start = positions.get(sequence)
            if first_start is not None and first_start + size <= start:
                if _sequence_text_length(list(sequence)) >= min_chars:
                    candidate = (first_start, start, size)
                    if not complete_render_only or _is_complete_render_repeat(
                        blocks, *candidate
                    ):
                        return candidate
            positions.setdefault(sequence, start)
    return None


def _is_complete_render_repeat(
    blocks: list[ContentBlock], first_start: int, second_start: int, size: int
) -> bool:
    sequence = blocks[first_start : first_start + size]
    heading_count = sum(block.kind.startswith("heading") for block in sequence)
    covers_body = first_start == 0 and second_start + size == len(blocks)
    return first_start == 0 or covers_body or heading_count >= 2


def _heading_has_content(blocks: list[ContentBlock], heading_index: int) -> bool:
    for block in blocks[heading_index + 1 :]:
        if block.kind.startswith("heading"):
            return False
        if block.kind != "divider" and block.text:
            return True
    return False


def _render_completeness_score(blocks: list[ContentBlock]) -> tuple[int, ...]:
    duty_heading_indexes = [
        index
        for index, block in enumerate(blocks)
        if block.kind.startswith("heading")
        and re.search("|".join(_heading_patterns("duties")), block.text, re.I)
    ]
    duties_have_content = any(
        _heading_has_content(blocks, index) for index in duty_heading_indexes
    )
    late_section_patterns = (
        _heading_patterns("audience")
        + _heading_patterns("preferred")
        + _heading_patterns("conditions")
        + _heading_patterns("process")
    )
    late_section_count = sum(
        block.kind.startswith("heading")
        and bool(re.search("|".join(late_section_patterns), block.text, re.I))
        for block in blocks
    )
    heading_indexes = [
        index for index, block in enumerate(blocks) if block.kind.startswith("heading")
    ]
    last_heading_has_content = bool(
        not heading_indexes or _heading_has_content(blocks, heading_indexes[-1])
    )
    list_item_count = sum(
        block.kind in {"bulleted_list_item", "numbered_list_item"} for block in blocks
    )
    return (
        int(duties_have_content),
        late_section_count,
        int(last_heading_has_content),
        list_item_count,
        len(heading_indexes),
        _sequence_text_length(blocks),
        len(blocks),
    )


def _remove_duplicate_renderings(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """Keep one complete copy of confidently repeated desktop/mobile bodies."""
    result: list[ContentBlock] = []
    for block in blocks:
        if result and not block.kind.startswith("heading") and block == result[-1]:
            continue
        result.append(block)

    while True:
        repeated = _find_repeated_sequence(
            result,
            MIN_RENDER_REPEAT_BLOCKS,
            MIN_RENDER_REPEAT_CHARS,
            complete_render_only=True,
        )
        if repeated is None:
            break
        first_start, second_start, _ = repeated
        first_render = result[first_start:second_start]
        second_render = result[second_start:]
        selected = (
            second_render
            if _render_completeness_score(second_render)
            > _render_completeness_score(first_render)
            else first_render
        )
        result = [*result[:first_start], *selected]

    seen_headings: set[str] = set()
    cleaned: list[ContentBlock] = []
    for index, block in enumerate(result):
        if not block.kind.startswith("heading"):
            cleaned.append(block)
            continue
        heading = clean_text(block.text).casefold()
        end = index + 1
        while end < len(result) and not result[end].kind.startswith("heading"):
            end += 1
        has_content = any(item.text for item in result[index + 1 : end])
        if heading in seen_headings and not has_content:
            continue
        seen_headings.add(heading)
        cleaned.append(block)
    return cleaned


def _has_unresolved_repetition(blocks: list[ContentBlock]) -> bool:
    """Detect a sufficiently long unresolved body sequence within a section."""
    sections: list[list[tuple[str, str]]] = [[]]
    for block in blocks:
        if block.kind.startswith("heading"):
            sections.append([])
        elif block.kind != "divider" and block.text:
            sections[-1].append((block.kind, clean_text(block.text).casefold()))

    for section in sections:
        content_blocks = [ContentBlock(kind=kind, text=text) for kind, text in section]
        if _find_repeated_sequence(
            content_blocks,
            MIN_UNRESOLVED_REPEAT_BLOCKS,
            MIN_UNRESOLVED_REPEAT_CHARS,
        ):
            return True
    return False


def _meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return clean_text(str(tag["content"]))
    return ""


def extract_title(soup: BeautifulSoup) -> str:
    for key in ("og:title", "twitter:title"):
        meta_title = _meta_content(soup, key)
        meta_title = re.sub(r"\s*[–|-]\s*IN THIS WORK\s*$", "", meta_title, flags=re.I)
        if meta_title and not SECTION_TITLE_RE.fullmatch(meta_title):
            return meta_title
    selectors = [
        "h1.entry-title",
        "h1.fusion-post-title",
        "h1.post-title",
        "article h1",
        "main h1",
        "h1",
    ]
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            text = clean_text(tag.get_text(" ", strip=True))
            if text and not SECTION_TITLE_RE.fullmatch(text):
                return text
    document_title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    document_title = re.sub(r"\s*[–|-]\s*IN THIS WORK\s*$", "", document_title, flags=re.I)
    if document_title and not SECTION_TITLE_RE.fullmatch(document_title):
        return document_title
    return "제목 미기재"


def extract_published_date(soup: BeautifulSoup) -> str | None:
    raw = _meta_content(soup, "article:published_time", "date", "datePublished")
    if not raw:
        time_tag = soup.find("time", attrs={"datetime": True})
        raw = str(time_tag.get("datetime")) if time_tag else ""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        match = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", raw)
        if match:
            return date(int(match[1]), int(match[2]), int(match[3])).isoformat()
    return None


def extract_categories(soup: BeautifulSoup) -> list[str]:
    categories: list[str] = []
    for anchor in soup.select("a[rel~='category'], a[rel~='tag']"):
        text = clean_text(anchor.get_text(" ", strip=True))
        if text in CATEGORY_WHITELIST and text not in categories:
            categories.append(text)
    section = _meta_content(soup, "article:section")
    if section in CATEGORY_WHITELIST and section not in categories:
        categories.append(section)
    for anchor in soup.select(
        ".fusion-meta-tb-categories a, .fusion-post-cards-meta-tb a, "
        ".fusion-post-meta a, a[href*='/category/'], a[href*='/tag/']"
    ):
        text = clean_text(anchor.get_text(" ", strip=True))
        if text in CATEGORY_WHITELIST and text not in categories:
            categories.append(text)
    return categories


def find_content_root(soup: BeautifulSoup) -> Tag:
    selectors = [
        ".fusion-content-tb",
        ".fusion-post-content-wrapper .post-content",
        "article .post-content",
        "article .entry-content",
        "article .fusion-post-content",
        ".single-post .post-content",
        ".entry-content",
        ".post-content",
        "article",
        "main",
    ]
    candidates: list[Tag] = []
    for selector in selectors:
        for node in soup.select(selector):
            if isinstance(node, Tag) and node not in candidates:
                candidates.append(node)
    # Fusion layouts can contain an early, empty post-content placeholder followed
    # by the rendered template body. Prefer the candidate with the most useful
    # structural blocks and text rather than trusting selector order.
    def score(node: Tag) -> tuple[int, int, int]:
        structural = node.select("h1,h2,h3,h4,h5,h6,p,li,tr")
        useful = [clean_text(item.get_text(" ", strip=True)) for item in structural]
        useful = [text for text in useful if text]
        return len(set(useful)), sum(len(text) for text in set(useful)), len(useful)

    if candidates:
        specific = [
            node
            for node in candidates
            if node.name not in {"article", "main", "body"} and score(node)[0] > 0
        ]
        return max(specific or candidates, key=score)
    return soup.body or soup


def _table_text(table: Tag) -> list[str]:
    rows: list[str] = []
    for tr in table.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" | ".join(cells))
    return rows


def _walk_blocks(node: Tag) -> tuple[list[ContentBlock], bool]:
    blocks: list[ContentBlock] = []

    def add(kind: str, text: str = "") -> None:
        normalized = clean_text(text)
        if kind != "divider" and not normalized:
            return
        if kind != "divider" and (
            DECORATION_ONLY_RE.fullmatch(normalized)
            or re.fullmatch(r"지원(?:하러\s*가기|하기)", normalized, re.I)
        ):
            return
        block = ContentBlock(kind=kind, text=normalized)  # type: ignore[arg-type]
        blocks.append(block)

    stopped = False

    def deduplicate_repeated_text(text: str) -> tuple[str, bool]:
        normalized = clean_text(text)
        lines = [line for line in normalized.splitlines() if line.strip()]
        if len(lines) >= 2 and len(lines) % 2 == 0:
            half = len(lines) // 2
            if lines[:half] == lines[half:]:
                return "\n".join(lines[:half]), True
        for midpoint in range(len(normalized) // 2 - 3, len(normalized) // 2 + 4):
            if midpoint > 0 and clean_text(normalized[:midpoint]) == clean_text(normalized[midpoint:]):
                return clean_text(normalized[:midpoint]), True
        return normalized, False

    def split_sections(text: str) -> list[tuple[str, str]]:
        """Split flattened Fusion text without losing the original ordering."""
        matches = []
        for match in INLINE_SECTION_RE.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start : line_end if line_end >= 0 else len(text)]
            # A section word inside a normal sentence is not a heading. Fusion
            # wrappers and bracketed headings still resolve after decoration
            # normalization, while ordinary prose remains intact.
            bracketed = clean_text(match.group(0)).startswith("[")
            normalized_match = clean_text(match.group(0))
            if (
                not bracketed
                and _exact_section_kind(line)
                and clean_text(line) != normalized_match
            ):
                continue
            if _bullet_text(line) is None and (bracketed or _exact_section_kind(line)):
                matches.append(match)
        if not matches:
            return [("content", text)]
        parts: list[tuple[str, str]] = []
        cursor = 0
        for match in matches:
            before = clean_text(text[cursor : match.start()])
            if before:
                parts.append(("content", before))
            parts.append(("heading", clean_text(match.group(0)).strip("[] ")))
            cursor = match.end()
        after = clean_text(text[cursor:])
        if after:
            parts.append(("content", after))
        return parts

    def add_content(text: str, default_kind: str = "paragraph") -> None:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        if len(lines) > 1:
            for line in lines:
                bullet = _bullet_text(line)
                add("bulleted_list_item" if bullet is not None else default_kind, bullet or line)
            return
        bullet = _bullet_text(text)
        add("bulleted_list_item" if bullet is not None else default_kind, bullet or text)

    def add_paragraph_content(text: str, default_kind: str = "paragraph") -> None:
        nonlocal repeated_body
        text, repeated = deduplicate_repeated_text(text)
        repeated_body = repeated_body or repeated
        noise = TRAILING_NOISE_RE.search(text)
        if noise:
            text = text[: noise.start()]
        for kind, piece in split_sections(text):
            if kind == "heading":
                add("heading_3", piece)
            else:
                add_content(piece, default_kind)

    repeated_body = False

    def walk(current: Tag | NavigableString) -> None:
        nonlocal stopped
        if stopped:
            return
        if isinstance(current, NavigableString):
            return
        name = current.name.lower() if current.name else ""
        if name in {"h1", "h2"}:
            text = clean_text(current.get_text(" ", strip=True))
            if TRAILING_NOISE_RE.search(text):
                stopped = True
                return
            add("heading_2", text)
            return
        if name in {"h3", "h4", "h5", "h6"}:
            text = clean_text(current.get_text(" ", strip=True))
            if TRAILING_NOISE_RE.search(text):
                stopped = True
                return
            add("heading_3", text)
            return
        if name == "p":
            text = current.get_text("\n", strip=True)
            strong = current.find(["strong", "b"])
            if strong and clean_text(strong.get_text(" ", strip=True)) == clean_text(text) and SECTION_TITLE_RE.fullmatch(text):
                add("heading_3", text)
            else:
                add_paragraph_content(text)
            return
        if name == "blockquote":
            add("quote", current.get_text("\n", strip=True))
            return
        if name == "hr":
            add("divider")
            return
        if name in {"ul", "ol"}:
            item_kind = "bulleted_list_item" if name == "ul" else "numbered_list_item"
            for li in current.find_all("li", recursive=False):
                text_parts: list[str] = []
                for child in li.contents:
                    if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                        continue
                    if isinstance(child, NavigableString):
                        text_parts.append(str(child))
                    elif isinstance(child, Tag):
                        text_parts.append(child.get_text(" ", strip=True))
                add_paragraph_content(" ".join(text_parts), item_kind)
                for nested in li.find_all(["ul", "ol"], recursive=False):
                    walk(nested)
            return
        if name == "table":
            for row in _table_text(current):
                add("paragraph", row)
            return
        if name == "img":
            return
        for child in current.children:
            if isinstance(child, (Tag, NavigableString)):
                walk(child)

    walk(node)
    return _remove_duplicate_renderings(blocks), repeated_body


def extract_body_blocks(soup: BeautifulSoup) -> tuple[list[ContentBlock], bool, bool]:
    root = find_content_root(soup)
    for selector in NOISE_SELECTORS:
        for node in root.select(selector):
            node.decompose()
    had_images = bool(root.find("img"))
    blocks, repeated_body = _walk_blocks(root)

    # Remove page-title duplication when it appears as the first content heading.
    if blocks and blocks[0].kind.startswith("heading"):
        title = extract_title(soup)
        if clean_text(blocks[0].text) == clean_text(title):
            blocks = blocks[1:]
    return blocks, had_images, repeated_body


def extract_apply_url(soup: BeautifulSoup, source_url: str) -> str | None:
    source_host = urlparse(source_url).netloc.replace("www.", "")
    preferred = re.compile(r"지원하러\s*가기|지원하기|신청하기|접수하기|apply", re.I)
    candidates: list[str] = []
    for anchor in soup.find_all("a", href=True):
        text = clean_text(anchor.get_text(" ", strip=True))
        href = urljoin(source_url, str(anchor["href"]))
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.replace("www.", "") == source_host:
            continue
        if preferred.search(text):
            return href
        if any(domain in parsed.netloc.lower() for domain in ["recruit", "career", "jobs", "forms", "google"]):
            candidates.append(href)
    return candidates[0] if candidates else None


def _all_text(blocks: Iterable[ContentBlock]) -> str:
    return "\n".join(block.text for block in blocks if block.text)


def classify_content(
    title: str, categories: list[str], body_text: str, apply_url: str | None = None
) -> str:
    combined = f"{title}\n{body_text[:5000]}".lower()
    if re.search(r"공모전|콘테스트|competition|contest", combined):
        return "공모전"

    has_job_category = any(cat in categories for cat in ["신입/인턴", "주니어경력"])
    has_job_sections = bool(
        re.search(r"주요\s*업무|자격\s*요건|지원\s*자격|채용\s*절차|근무\s*조건", combined)
    )
    has_job_title = bool(
        re.search(
            r"채용|인턴|신입|경력|디자이너|designer|아르바이트|알바|정규직|계약직|"
            r"developer|engineer|manager|scientist|assistant|\bRA\b",
            title,
            re.I,
        )
    )
    has_job_url = bool(apply_url and re.search(
        r"(?:/careers?(?:/|$)|/career/job-detail|/jobs?(?:/|$)|/job_posting/|"
        r"greetinghr\.com|greenhouse\.io|recruit|careers)",
        apply_url,
        re.I,
    ))
    editorial_signal = bool(
        re.search(r"인터뷰|포트폴리오|취업토크|커리어|노하우|필요한가\??|하는 법", title)
    )
    if has_job_category or has_job_title or has_job_url or (has_job_sections and has_job_title):
        return "채용공고"
    if re.search(r"대외활동|서포터즈|기자단|앰배서더|크루\s*모집|봉사단", combined):
        return "대외활동"
    if "교육/대외활동" in categories and re.search(
        r"교육|부트캠프|아카데미|워크숍|세미나|멘토링|과정|프로그램", combined
    ):
        return "교육·프로그램"
    if editorial_signal or any(cat in categories for cat in ["커리어TV", "취업토크"]):
        return "커리어 콘텐츠"
    if re.search(r"교육|부트캠프|아카데미|워크숍|세미나|멘토링", combined):
        return "교육·프로그램"
    return "기타·확인 필요"


DESIGN_ROLE_RE = re.compile(
    r"(?:디자이너|일러스트레이터|디자인\s*(?:직무|인턴|어시스턴트)|"
    r"(?:프로덕트|제품|UI\s*/?\s*UX|UX\s*/?\s*UI|UI|UX|"
    r"비주얼|그래픽|콘텐츠|브랜드|BX|모션|캐릭터|공간|패션)\s*디자인(?:\s*(?:직무|인턴))?|"
    r"Product\s+Designer|Visual\s+Designer|Graphic\s+Designer|UI\s+Designer|UX\s+Designer|"
    r"Brand\s+Designer|Content\s+Designer|Motion\s+Designer|Design\s+Assistant|Design\s+Intern)",
    re.I,
)
NON_DESIGN_ROLE_RE = re.compile(
    r"(?:Developer|Engineer|Software\s+Engineer|Research\s+Scientist|Research\s+Assistant|\bRA\b|"
    r"Data\s+Scientist|ML\s+Engineer|AI\s+Engineer|Product\s+Manager|Product\s+Owner|Marketer|"
    r"Marketing|Sales|Operation|Planning|기획|운영|개발|연구|영업|인사|재무)",
    re.I,
)
DESIGN_PROGRAM_RE = re.compile(
    r"(?:디자인|디자이너|UI\s*/?\s*UX|UX\s*/?\s*UI|시각디자인|프로덕트\s*디자인|"
    r"Product\s+Design|Visual\s+Design|Graphic\s+Design|Design\s+(?:Contest|Competition|Program))",
    re.I,
)
MIXED_ROLE_RE = re.compile(
    r"(?:관리|마케팅|영업|디자인|개발|연구)(?:\s*[/·,]\s*(?:관리|마케팅|영업|디자인|개발|연구)){2,}",
    re.I,
)


def classify_opportunity_scope(record: PostRecord) -> str:
    """Return ``in_scope`` or a stable exclusion reason for final output."""
    role_text = clean_text(record.role_or_program or record.title)
    path_lines = [_strip_heading_wrapper(block.text) for block in record.body_blocks]
    has_design_path = any(re.match(r"^Design\s*>", line, re.I) for line in path_lines)
    has_service_path = any(
        re.match(r"^Service\s*&\s*Business\s*>", line, re.I) for line in path_lines
    )
    if record.content_type == "채용공고":
        if has_service_path:
            return "non_design_role"
        if has_design_path or DESIGN_ROLE_RE.search(role_text):
            return "in_scope"
        if MIXED_ROLE_RE.search(role_text) or (
            "디자인" in role_text and NON_DESIGN_ROLE_RE.search(role_text)
        ):
            return "ambiguous_mixed_roles" if record.body_blocks else "no_isolated_design_role"
        return "non_design_role"
    if record.content_type in {"공모전", "대외활동", "교육·프로그램"}:
        return "in_scope" if DESIGN_PROGRAM_RE.search(role_text) else "non_design_opportunity"
    return "non_design_opportunity"


def split_title(title: str, content_type: str, body_text: str) -> tuple[str, str]:
    for separator in ["｜", "|", " – ", " - "]:
        if separator in title:
            left, right = [clean_text(part) for part in title.split(separator, 1)]
            if left in GENERIC_PREFIXES:
                return _extract_organizer(body_text), right or title
            return left, right or title
    return _extract_organizer(body_text), title


def _extract_organizer(body_text: str) -> str:
    for pattern in [r"(?:주최|주관|운영기관|기관명)\s*[:：]\s*([^\n]{2,80})"]:
        match = re.search(pattern, body_text)
        if match:
            return clean_text(match.group(1))
    return ""


def detect_design_fields(title: str, body_text: str) -> list[str]:
    text = f"{title}\n{body_text[:4000]}".lower()
    rules = [
        ("UI/UX", r"ui\s*/?\s*ux|ux\s*/?\s*ui|사용자 경험|인터페이스"),
        ("프로덕트", r"프로덕트\s*디자|product\s*design"),
        ("BX/브랜드", r"\bbx\b|브랜드\s*디자|브랜딩|brand\s*design"),
        ("그래픽", r"그래픽\s*디자|graphic\s*design"),
        ("콘텐츠", r"콘텐츠\s*디자|content\s*design|sns\s*콘텐츠"),
        ("영상/모션", r"영상|모션|motion|video|릴스"),
        ("VMD", r"\bvmd\b|비주얼\s*머천"),
        ("패키지", r"패키지\s*디자|package\s*design"),
        ("공간/무대", r"공간\s*디자|무대\s*디자|전시\s*디자|spatial"),
        ("웹", r"웹\s*디자|web\s*design"),
        ("캐릭터/일러스트", r"캐릭터|일러스트|illustrat"),
        ("산업/제품", r"산업\s*디자|제품\s*디자|industrial\s*design"),
        ("패션", r"패션\s*디자|fashion\s*design"),
    ]
    return [name for name, pattern in rules if re.search(pattern, text, re.I)]


def extract_experience(title: str, categories: list[str], body_text: str, content_type: str) -> tuple[str, str]:
    if content_type != "채용공고":
        return "해당 없음", ""
    experience_lines = [
        line for line in body_text[:8000].splitlines() if not RESUME_GUIDANCE_RE.search(line)
    ]
    text = "\n".join([title, *experience_lines])
    range_match = re.search(r"신입\s*[~·/및-]+\s*(\d+)\s*년", text)
    if range_match:
        return "경력무관", clean_text(range_match.group(0))
    if re.search(r"경력\s*무관|신입\s*[·/&및]+\s*경력", text):
        match = re.search(r"경력\s*무관|신입\s*[·/&및]+\s*경력", text)
        return "경력무관", clean_text(match.group(0) if match else "경력무관")
    years = re.search(
        r"(?:경력|실무\s*경험|관련\s*경험)\s*[:：]?\s*(\d+)\s*년"
        r"(?:\s*(?:이상|이하|~\s*\d+\s*년))?"
        r"|(?<!\d)(\d{1,2})\s*년\s*(?:이상|이하)\s*(?:경력|경험)?",
        text,
    )
    if years:
        return "경력", clean_text(years.group(0))
    if re.search(r"인턴", title) or "신입/인턴" in categories and re.search(r"인턴", text):
        return "인턴", "인턴"
    if re.search(r"신입", text) or "신입/인턴" in categories:
        return "신입", "신입"
    if "주니어경력" in categories or re.search(r"경력", title):
        return "경력", "경력"
    return "확인 필요", ""


def extract_employment_types(title: str, body_text: str, content_type: str) -> list[str]:
    if content_type != "채용공고":
        return []
    # Prefer the title and explicit employment/working-condition lines. This
    # excludes notices such as "향후 정규직 공고에 지원하더라도".
    relevant_lines = [
        line for line in body_text[:10000].splitlines()
        if re.search(r"고용\s*형태|근무\s*형태|근무\s*조건|채용\s*형태|인턴|아르바이트|알바|계약직|파트\s*타임", line, re.I)
        and not re.search(r"향후|추후|공고에\s*지원|지원하더라도", line, re.I)
        and not RESUME_GUIDANCE_RE.search(line)
    ]
    text = "\n".join([title, *relevant_lines])
    rules = [
        ("정규직", r"정규직"),
        ("계약직", r"계약직"),
        ("인턴", r"체험형\s*인턴|(?<!전환형\s)인턴"),
        ("전환형 인턴", r"전환형\s*인턴|채용\s*연계형\s*인턴"),
        ("프리랜서", r"프리랜서"),
        ("아르바이트", r"아르바이트|알바"),
        ("파트타임", r"파트\s*타임|part[- ]?time"),
    ]
    values: list[str] = []
    for name, pattern in rules:
        if re.search(pattern, text, re.I) and name not in values:
            values.append(name)
    if "전환형 인턴" in values:
        values = [v for v in values if v != "인턴"]
    return values


def _truncate_at_text_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    prefix = text[: max_chars + 1]
    boundaries = [match.end() for match in re.finditer(r"(?:\s+|[.!?。！？](?=\s|$))", prefix)]
    return clean_text(prefix[: boundaries[-1]]) if boundaries else clean_text(text[:max_chars])


def _join_complete_lines(lines: list[str], max_chars: int) -> str:
    output: list[str] = []
    length = 0
    for line in lines:
        separator_length = 1 if output else 0
        if length + separator_length + len(line) > max_chars:
            if not output:
                output.append(_truncate_at_text_boundary(line, max_chars))
            break
        output.append(line)
        length += separator_length + len(line)
    return clean_text("\n".join(output))


def _extract_section(
    blocks: list[ContentBlock],
    heading_patterns: list[str],
    max_chars: int = 1800,
    section_kind: str | None = None,
) -> str:
    heading_re = re.compile("|".join(heading_patterns), re.I)
    candidates: list[tuple[int, int, list[str]]] = []
    collecting = False
    output: list[str] = []
    priority = 0
    start_index = -1
    for index, block in enumerate(blocks):
        logical_kind = _logical_section_kind(blocks, index)
        candidate_text = _strip_heading_wrapper(block.text)
        is_target = (
            logical_kind == section_kind
            if section_kind
            else block.kind.startswith("heading") and bool(heading_re.search(candidate_text))
        )
        if is_target and not collecting:
            collecting = True
            output = []
            start_index = index
            priority = 2 if re.fullmatch(
                r"(?:주요|담당|수행)\s*업무|업무\s*내용|자격\s*요건|지원\s*자격|"
                r"지원자격|우대\s*사항|우대\s*요건|우대\s*자격",
                candidate_text,
                re.I,
            ) else 1
            continue
        if not collecting:
            continue
        if logical_kind or block.kind.startswith("heading") or _is_role_marker(block):
            if logical_kind == section_kind and not output:
                continue
            candidates.append((priority, start_index, output))
            collecting = False
            output = []
            if is_target:
                collecting = True
                start_index = index
            continue
        text = clean_text(block.text)
        if not text or STRUCTURED_DECORATION_RE.fullmatch(text):
            continue
        if re.match(
            r"^(?:게시일|등록일|접수\s*(?:기간|마감)|지원(?:서)?\s*(?:기간|접수\s*마감)|"
            r"마감일|마감\s*기한|근무\s*(?:지|장소|조건))\s*[:：]?",
            text,
            re.I,
        ):
            candidates.append((priority, start_index, output))
            collecting = False
            output = []
            continue
        if section_kind in {"duties", "audience", "preferred"} and (
            URL_ONLY_RE.fullmatch(text)
            or re.fullmatch(r".*홈페이지.*(?:블로그|SNS).*", text, re.I)
        ):
            candidates.append((priority, start_index, output))
            collecting = False
            output = []
            continue
        output.append(text)
    if collecting:
        candidates.append((priority, start_index, output))
    if not candidates:
        return ""
    # Explicit headings win over broad natural-language headings. For equal
    # headings prefer the later complete section, avoiding introductory copies.
    _, _, selected = max(candidates, key=lambda item: (item[0], item[1]))
    while selected and STRUCTURED_DECORATION_RE.fullmatch(selected[0]):
        selected.pop(0)
    while selected and STRUCTURED_DECORATION_RE.fullmatch(selected[-1]):
        selected.pop()
    return _join_complete_lines(selected, max_chars)


def _has_section(blocks: list[ContentBlock], section: str) -> bool:
    return any(_logical_section_kind(blocks, index) == section for index in range(len(blocks)))


def extract_target_audience(blocks: list[ContentBlock], content_type: str) -> str:
    if content_type == "채용공고":
        return ""
    return _extract_section(blocks, _heading_patterns("audience"), 1200, "audience")


def extract_qualifications(blocks: list[ContentBlock], content_type: str) -> str:
    if content_type != "채용공고":
        return ""
    return _extract_section(blocks, _heading_patterns("audience"), 1800, "audience")


def extract_preferred_qualifications(blocks: list[ContentBlock]) -> str:
    return _extract_section(blocks, _heading_patterns("preferred"), 1800, "preferred")


def extract_essay_questions(blocks: list[ContentBlock]) -> str:
    value = _extract_section(blocks, _heading_patterns("essay"), 1800, "essay")
    lines = [line for line in value.splitlines() if line]
    if lines and all(ESSAY_SUBMISSION_ONLY_RE.fullmatch(line) for line in lines):
        return ""
    return value


def extract_pre_assignment(blocks: list[ContentBlock]) -> str:
    # Only an explicit section starts extraction. Incidental mentions in work
    # history, portfolios, or a generic hiring-process sentence are ignored.
    output: list[str] = []
    collecting = False
    first_heading = ""
    for index, block in enumerate(blocks):
        logical_kind = _logical_section_kind(blocks, index)
        if logical_kind == "assignment" and not collecting:
            collecting = True
            first_heading = _strip_heading_wrapper(block.text)
            continue
        if collecting and (logical_kind or block.kind.startswith("heading")):
            if logical_kind == "assignment" and not output:
                candidate = _strip_heading_wrapper(block.text)
                if candidate and candidate != first_heading:
                    output.append(candidate)
                continue
            break
        if collecting and block.text:
            text = clean_text(block.text)
            if not STRUCTURED_DECORATION_RE.fullmatch(text):
                output.append(text)
    return _join_complete_lines(output, 1800)


def extract_key_duties(blocks: list[ContentBlock], content_type: str) -> str:
    patterns = (
        _heading_patterns("duties")
        if content_type == "채용공고"
        else [r"활동\s*내용", r"프로그램\s*내용", r"공모\s*주제", r"모집\s*분야", r"주요\s*활동"]
    )
    return _extract_section(
        blocks, patterns, 1800, "duties" if content_type == "채용공고" else None
    )


def extract_benefits(blocks: list[ContentBlock]) -> str:
    return _extract_section(
        blocks,
        _heading_patterns("benefits") + [r"활동비"],
        max_chars=1200,
        section_kind="benefits",
    )


def _structured_sections(blocks: list[ContentBlock], content_type: str) -> dict[str, str]:
    return {
        "key_duties": extract_key_duties(blocks, content_type),
        "target_audience": extract_target_audience(blocks, content_type),
        "qualifications": extract_qualifications(blocks, content_type),
        "preferred_qualifications": extract_preferred_qualifications(blocks),
        "essay_questions": extract_essay_questions(blocks),
        "pre_assignment": extract_pre_assignment(blocks),
    }


def _structured_sections_are_consistent(
    blocks: list[ContentBlock], sections: dict[str, str]
) -> bool:
    body_lines = {clean_text(block.text) for block in blocks if block.text}
    present_in_body = all(
        any(body_line == clean_text(line) or body_line.startswith(clean_text(line)) for body_line in body_lines)
        for value in sections.values()
        for line in value.splitlines()
        if clean_text(line)
    )
    if not present_in_body:
        return False
    for field in ("key_duties", "qualifications", "preferred_qualifications"):
        lines = [clean_text(line) for line in sections[field].splitlines() if clean_text(line)]
        if not lines:
            continue
        if STRUCTURED_DECORATION_RE.fullmatch(lines[0]) or STRUCTURED_DECORATION_RE.fullmatch(lines[-1]):
            return False
        for line in lines:
            if (
                URL_ONLY_RE.fullmatch(line)
                or STRUCTURED_LEAK_RE.fullmatch(line)
                or _exact_section_kind(line) is not None
            ):
                return False
            if _is_role_marker(ContentBlock(kind="paragraph", text=line)):
                return False
    return True


def _line_value(body_text: str, labels: str, max_chars: int = 500) -> str:
    match = re.search(rf"(?:{labels})\s*[:：]?\s*([^\n]{{2,{max_chars}}})", body_text, re.I)
    return clean_text(match.group(1))[:max_chars] if match else ""


def extract_location(body_text: str) -> str:
    return _line_value(body_text, r"근무지|근무\s*장소|활동\s*지역|근무\s*지역|근무장소|근무주소", 250)


def extract_activity_period(body_text: str) -> str:
    return _line_value(body_text, r"활동\s*기간|교육\s*기간|프로그램\s*기간|인턴\s*기간", 500)


def _parse_date_token(token: str, reference_year: int) -> str | None:
    token = token.strip()
    full = re.search(r"(20\d{2})\s*[년./-]\s*(\d{1,2})\s*[월./-]\s*(\d{1,2})\s*일?", token)
    if full:
        year, month, day = map(int, full.groups())
    else:
        short = re.search(r"(?<!\d)(\d{1,2})\s*[월./-]\s*(\d{1,2})\s*일?", token)
        if not short:
            return None
        year = reference_year
        month, day = map(int, short.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def extract_deadline(body_text: str, published_date: str | None) -> str | None:
    reference_year = int(published_date[:4]) if published_date else date.today().year
    lines = [clean_text(line) for line in body_text.splitlines()]
    candidate_lines = []
    for index, line in enumerate(lines):
        if re.search(r"마감|접수\s*기간|지원\s*기간|모집\s*기간|신청\s*기간|접수기간|지원기간", line, re.I):
            candidate_lines.append(" ".join(lines[index : index + 4]))
    for line in candidate_lines:
        tokens = re.findall(
            r"(?:20\d{2}\s*[년./-]\s*)?\d{1,2}\s*[월./-]\s*\d{1,2}\s*일?",
            line,
        )
        parsed = [_parse_date_token(token, reference_year) for token in tokens]
        parsed = [value for value in parsed if value]
        if parsed:
            result = parsed[-1]
            if published_date and result and result < published_date:
                dt = datetime.fromisoformat(result).date()
                if (datetime.fromisoformat(published_date).date() - dt).days > 180:
                    try:
                        result = date(dt.year + 1, dt.month, dt.day).isoformat()
                    except ValueError:
                        pass
            return result
    return None


def determine_status(title: str, body_text: str, deadline: str | None) -> str:
    leading = f"{title}\n{body_text[:2500]}"
    if re.search(r"마감된\s*공고|공고는\s*마감|모집\s*마감|접수\s*마감|비공개", leading, re.I):
        return "마감"
    if deadline:
        try:
            if datetime.fromisoformat(deadline).date() < date.today():
                return "마감"
        except ValueError:
            pass
    if re.search(r"채용시\s*마감|상시\s*채용|상시\s*모집", body_text, re.I):
        return "모집 중"
    return "모집 중"


def compute_hash(record_data: dict[str, object]) -> str:
    payload = json.dumps(record_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _refresh_content_hash(record: PostRecord) -> None:
    record.content_hash = compute_hash(
        {
            "post_id": record.post_id,
            "title": record.title,
            "content_type": record.content_type,
            "site_categories": record.site_categories,
            "organization": record.organization,
            "role_or_program": record.role_or_program,
            "design_fields": record.design_fields,
            "experience_class": record.experience_class,
            "experience_raw": record.experience_raw,
            "employment_types": record.employment_types,
            "target_audience": record.target_audience,
            "location": record.location,
            "key_duties": record.key_duties,
            "qualifications": record.qualifications,
            "preferred_qualifications": record.preferred_qualifications,
            "essay_questions": record.essay_questions,
            "pre_assignment": record.pre_assignment,
            "benefits_prize": record.benefits_prize,
            "deadline": record.deadline,
            "activity_period": record.activity_period,
            "published_date": record.published_date,
            "status": record.status,
            "apply_url": record.apply_url,
            "collection_status": record.collection_status,
            "quality_reasons": record.quality_reasons,
            "body_blocks": [(b.kind, b.text) for b in record.body_blocks],
        }
    )


def _quality_reasons(
    *, title: str, content_type: str, blocks: list[ContentBlock], had_images: bool
) -> dict[str, bool]:
    sections = _structured_sections(blocks, content_type)
    body_text = _all_text(blocks)
    multiple_role_markers = sum(_is_role_marker(block) for block in blocks) >= 2
    return {
        "suspicious_title": title == "제목 미기재" or bool(SECTION_TITLE_RE.fullmatch(title)),
        "missing_body": not blocks,
        "missing_job_duties": content_type == "채용공고" and not sections["key_duties"],
        "image_only_content": had_images and len(body_text) < 300,
        "unresolved_repetition": _has_unresolved_repetition(blocks),
        "empty_qualifications_section": _has_section(blocks, "audience") and not (
            sections["qualifications"] or sections["target_audience"]
        ),
        "empty_preferred_section": _has_section(blocks, "preferred") and not sections["preferred_qualifications"],
        "empty_essay_questions_section": _has_section(blocks, "essay") and not sections["essay_questions"],
        "empty_pre_assignment_section": _has_section(blocks, "assignment") and not sections["pre_assignment"],
        "inconsistent_structured_sections": (
            multiple_role_markers or not _structured_sections_are_consistent(blocks, sections)
        ),
    }


def parse_post_html(
    html: str, source_url: str, fallback_categories: list[str] | None = None
) -> PostRecord:
    soup = BeautifulSoup(html, "html.parser")
    title = extract_title(soup)
    categories = extract_categories(soup) or list(fallback_categories or [])
    published_date = extract_published_date(soup)
    apply_url = extract_apply_url(soup, source_url)
    body_blocks, had_images, repeated_body = extract_body_blocks(soup)
    body_text = _all_text(body_blocks)
    content_type = classify_content(title, categories, body_text, apply_url)
    organization, role = split_title(title, content_type, body_text)
    experience_class, experience_raw = extract_experience(
        title, categories, body_text, content_type
    )
    employment_types = extract_employment_types(title, body_text, content_type)
    sections = _structured_sections(body_blocks, content_type)
    target_audience = sections["target_audience"]
    key_duties = sections["key_duties"]
    # Avoid false positives from company introductions, benefits, and related
    # content: role/title and the actual duties are the authoritative signals.
    design_fields = detect_design_fields(title, key_duties)
    benefits = extract_benefits(body_blocks)
    location = extract_location(body_text)
    activity_period = extract_activity_period(body_text)
    deadline = extract_deadline(body_text, published_date)
    status = determine_status(title, body_text, deadline)
    post_match = re.search(r"/archives/(\d+)", source_url)
    if not post_match:
        raise ValueError(f"인디스워크 공고 ID를 URL에서 찾을 수 없습니다: {source_url}")
    post_id = post_match.group(1)

    quality_reasons = _quality_reasons(
        title=title, content_type=content_type, blocks=body_blocks, had_images=had_images
    )
    collection_status = (
        "검토 필요"
        if any(quality_reasons.values())
        else "정상"
    )
    record = PostRecord(
        post_id=post_id,
        source_url=source_url,
        title=title,
        content_type=content_type,
        site_categories=categories,
        organization=organization,
        role_or_program=role,
        design_fields=design_fields,
        experience_class=experience_class,
        experience_raw=experience_raw,
        employment_types=employment_types,
        target_audience=target_audience,
        location=location,
        key_duties=key_duties,
        qualifications=sections["qualifications"],
        preferred_qualifications=sections["preferred_qualifications"],
        essay_questions=sections["essay_questions"],
        pre_assignment=sections["pre_assignment"],
        benefits_prize=benefits,
        deadline=deadline,
        activity_period=activity_period,
        published_date=published_date,
        status=status,
        apply_url=apply_url,
        collection_status=collection_status,
        quality_reasons=quality_reasons,
        body_blocks=body_blocks,
    )
    _refresh_content_hash(record)
    return record


def parse_post_html_records(
    html: str, source_url: str, fallback_categories: list[str] | None = None
) -> list[PostRecord]:
    """Parse a page, splitting clearly separated design roles into stable records."""
    record = parse_post_html(html, source_url, fallback_categories)
    numbered_markers = [
        (index, int(match.group(1)))
        for index, block in enumerate(record.body_blocks)
        if (match := _numbered_job_marker(block))
    ]
    if len(numbered_markers) >= 2:
        role_markers = numbered_markers
    else:
        design_markers = [
            index for index, block in enumerate(record.body_blocks) if _is_role_marker(block)
        ]
        role_markers = [
            (index, sequence) for sequence, index in enumerate(design_markers, start=1)
        ]
    if len(role_markers) < 2:
        return [record]

    records: list[PostRecord] = []
    for marker_index, (start, source_number) in enumerate(role_markers):
        end = (
            role_markers[marker_index + 1][0]
            if marker_index + 1 < len(role_markers)
            else len(record.body_blocks)
        )
        blocks = record.body_blocks[start:end]
        segment_text = _all_text(blocks)
        role_title = blocks[0].text
        if numbered_markers and not _is_design_numbered_role(role_title, blocks):
            continue
        split_record = deepcopy(record)
        split_record.post_id = f"{record.post_id}-{source_number}"
        split_record.title = f"{record.title}｜{role_title}"
        split_record.role_or_program = role_title
        split_record.body_blocks = blocks
        split_record.design_fields = detect_design_fields(role_title, segment_text)
        sections = _structured_sections(blocks, "채용공고")
        for field, value in sections.items():
            setattr(split_record, field, value)
        segment_employment = extract_employment_types(role_title, segment_text, "채용공고")
        if segment_employment:
            split_record.employment_types = segment_employment
        split_record.quality_reasons = _quality_reasons(
            title=split_record.title,
            content_type="채용공고",
            blocks=blocks,
            had_images=False,
        )
        split_record.collection_status = (
            "검토 필요" if any(split_record.quality_reasons.values()) else "정상"
        )
        _refresh_content_hash(split_record)
        records.append(split_record)
    return records
