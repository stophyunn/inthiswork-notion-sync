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
]


def clean_text(value: str) -> str:
    value = unescape(value or "")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    value = re.sub(r"[\t\r\f\v]+", " ", value)
    value = re.sub(r"[ ]{2,}", " ", value)
    value = re.sub(r"\n[ ]+", "\n", value)
    value = re.sub(r"[ ]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return clean_text(str(tag["content"]))
    return ""


def extract_title(soup: BeautifulSoup) -> str:
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
            if text:
                return text
    og = _meta_content(soup, "og:title", "twitter:title")
    if og:
        return re.sub(r"\s*[–|-]\s*IN THIS WORK\s*$", "", og, flags=re.I)
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


def _walk_blocks(node: Tag) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []

    def add(kind: str, text: str = "") -> None:
        normalized = clean_text(text)
        if kind != "divider" and not normalized:
            return
        block = ContentBlock(kind=kind, text=normalized)  # type: ignore[arg-type]
        # Some Fusion templates render the same post body twice (desktop/mobile).
        # A global fingerprint avoids saving the duplicate copy to Notion.
        fingerprint = (block.kind, block.text)
        if not block.kind.startswith("heading") and fingerprint in seen:
            return
        if not block.kind.startswith("heading"):
            seen.add(fingerprint)
        blocks.append(block)

    seen: set[tuple[str, str]] = set()

    def walk(current: Tag | NavigableString) -> None:
        if isinstance(current, NavigableString):
            return
        name = current.name.lower() if current.name else ""
        if name in {"h1", "h2"}:
            add("heading_2", current.get_text(" ", strip=True))
            return
        if name in {"h3", "h4", "h5", "h6"}:
            add("heading_3", current.get_text(" ", strip=True))
            return
        if name == "p":
            text = current.get_text("\n", strip=True)
            strong = current.find(["strong", "b"])
            if strong and clean_text(strong.get_text(" ", strip=True)) == clean_text(text):
                add("heading_3", text)
            else:
                add("paragraph", text)
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
                add(item_kind, " ".join(text_parts))
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
    return blocks


def extract_body_blocks(soup: BeautifulSoup) -> tuple[list[ContentBlock], bool]:
    root = find_content_root(soup)
    for selector in NOISE_SELECTORS:
        for node in root.select(selector):
            node.decompose()
    had_images = bool(root.find("img"))
    blocks = _walk_blocks(root)

    # Remove page-title duplication when it appears as the first content heading.
    if blocks and blocks[0].kind.startswith("heading"):
        title = extract_title(soup)
        if clean_text(blocks[0].text) == clean_text(title):
            blocks = blocks[1:]
    return blocks, had_images


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


def classify_content(title: str, categories: list[str], body_text: str) -> str:
    combined = f"{title}\n{body_text[:5000]}".lower()
    if re.search(r"공모전|콘테스트|competition|contest", combined):
        return "공모전"
    if re.search(r"대외활동|서포터즈|기자단|앰배서더|크루\s*모집|봉사단", combined):
        return "대외활동"
    if "교육/대외활동" in categories and re.search(
        r"교육|부트캠프|아카데미|워크숍|세미나|멘토링|과정|프로그램", combined
    ):
        return "교육·프로그램"

    has_job_category = any(cat in categories for cat in ["신입/인턴", "주니어경력"])
    has_job_sections = bool(
        re.search(r"주요\s*업무|자격\s*요건|지원\s*자격|채용\s*절차|근무\s*조건", combined)
    )
    has_job_title = bool(
        re.search(r"채용|인턴|신입|경력|디자이너|designer|아르바이트|알바|정규직|계약직", title, re.I)
    )
    editorial_signal = bool(
        re.search(r"인터뷰|포트폴리오|취업토크|커리어|노하우|필요한가\??|하는 법", title)
    )
    if has_job_category or has_job_title or (has_job_sections and has_job_title):
        return "채용공고"
    if editorial_signal or any(cat in categories for cat in ["커리어TV", "취업토크"]):
        return "커리어 콘텐츠"
    if re.search(r"교육|부트캠프|아카데미|워크숍|세미나|멘토링", combined):
        return "교육·프로그램"
    return "기타·확인 필요"


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
    text = f"{title}\n{body_text[:8000]}"
    range_match = re.search(r"신입\s*[~·/및-]+\s*(\d+)\s*년", text)
    if range_match:
        return "경력무관", clean_text(range_match.group(0))
    if re.search(r"경력\s*무관|신입\s*[·/&및]+\s*경력", text):
        match = re.search(r"경력\s*무관|신입\s*[·/&및]+\s*경력", text)
        return "경력무관", clean_text(match.group(0) if match else "경력무관")
    years = re.search(r"(?:경력\s*)?(\d+)\s*년\s*(?:이상|이하|~\s*\d+\s*년)?", text)
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
    text = f"{title}\n{body_text[:10000]}"
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


def _extract_section(blocks: list[ContentBlock], heading_patterns: list[str], max_chars: int = 1800) -> str:
    heading_re = re.compile("|".join(heading_patterns), re.I)
    output: list[str] = []
    collecting = False
    for block in blocks:
        if block.kind.startswith("heading"):
            if collecting:
                break
            if heading_re.search(block.text):
                collecting = True
            continue
        if collecting and block.text:
            output.append(block.text)
            if sum(len(x) for x in output) >= max_chars:
                break
    return clean_text("\n".join(output))[:max_chars]


def extract_target_audience(blocks: list[ContentBlock]) -> str:
    return _extract_section(
        blocks,
        [r"자격\s*요건", r"지원\s*자격", r"지원\s*대상", r"이런\s*분", r"필수\s*사항", r"지원자격"],
        max_chars=1200,
    )


def extract_key_duties(blocks: list[ContentBlock], content_type: str) -> str:
    patterns = (
        [r"주요\s*업무", r"담당\s*업무", r"업무\s*내용", r"이런\s*일", r"역할", r"하실\s*일", r"담당업무"]
        if content_type == "채용공고"
        else [r"활동\s*내용", r"프로그램\s*내용", r"공모\s*주제", r"모집\s*분야", r"주요\s*활동"]
    )
    return _extract_section(blocks, patterns, max_chars=1800)


def extract_benefits(blocks: list[ContentBlock]) -> str:
    return _extract_section(
        blocks,
        [r"혜택", r"상금", r"시상", r"활동비", r"참여\s*혜택", r"지원\s*내용"],
        max_chars=1200,
    )


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
    candidate_lines = [
        clean_text(line)
        for line in body_text.splitlines()
        if re.search(r"마감|접수\s*기간|지원\s*기간|모집\s*기간|신청\s*기간|접수기간|지원기간", line, re.I)
    ]
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


def parse_post_html(
    html: str, source_url: str, fallback_categories: list[str] | None = None
) -> PostRecord:
    soup = BeautifulSoup(html, "html.parser")
    title = extract_title(soup)
    categories = extract_categories(soup) or list(fallback_categories or [])
    published_date = extract_published_date(soup)
    apply_url = extract_apply_url(soup, source_url)
    body_blocks, had_images = extract_body_blocks(soup)
    body_text = _all_text(body_blocks)
    content_type = classify_content(title, categories, body_text)
    organization, role = split_title(title, content_type, body_text)
    design_fields = detect_design_fields(title, body_text)
    experience_class, experience_raw = extract_experience(
        title, categories, body_text, content_type
    )
    employment_types = extract_employment_types(title, body_text, content_type)
    target_audience = extract_target_audience(body_blocks)
    key_duties = extract_key_duties(body_blocks, content_type)
    benefits = extract_benefits(body_blocks)
    location = extract_location(body_text)
    activity_period = extract_activity_period(body_text)
    deadline = extract_deadline(body_text, published_date)
    status = determine_status(title, body_text, deadline)
    post_match = re.search(r"/archives/(\d+)", source_url)
    if not post_match:
        raise ValueError(f"인디스워크 공고 ID를 URL에서 찾을 수 없습니다: {source_url}")
    post_id = post_match.group(1)

    collection_status = "검토 필요" if not body_blocks or (had_images and len(body_text) < 300) else "정상"
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
        benefits_prize=benefits,
        deadline=deadline,
        activity_period=activity_period,
        published_date=published_date,
        status=status,
        apply_url=apply_url,
        collection_status=collection_status,
        body_blocks=body_blocks,
    )
    record.content_hash = compute_hash(
        {
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
            "benefits_prize": record.benefits_prize,
            "deadline": record.deadline,
            "activity_period": record.activity_period,
            "published_date": record.published_date,
            "status": record.status,
            "apply_url": record.apply_url,
            "body_blocks": [(b.kind, b.text) for b in record.body_blocks],
        }
    )
    return record


def parse_post_html_records(
    html: str, source_url: str, fallback_categories: list[str] | None = None
) -> list[PostRecord]:
    """Parse a page, splitting clearly separated design roles into stable records."""
    record = parse_post_html(html, source_url, fallback_categories)
    role_markers = [
        index
        for index, block in enumerate(record.body_blocks)
        if block.kind.startswith("heading")
        and re.search(
            r"디자이너|디자인\s*(?:직무|부문|인턴)|UI\s*/?\s*UX|그래픽|BX|브랜드|일러스트",
            block.text,
            re.I,
        )
        and detect_design_fields(block.text, "")
    ]
    if len(role_markers) < 2:
        return [record]

    records: list[PostRecord] = []
    for sequence, start in enumerate(role_markers, start=1):
        end = role_markers[sequence] if sequence < len(role_markers) else len(record.body_blocks)
        blocks = record.body_blocks[start:end]
        segment_text = _all_text(blocks)
        role_title = blocks[0].text
        split_record = deepcopy(record)
        split_record.post_id = f"{record.post_id}-{sequence}"
        split_record.title = f"{record.title}｜{role_title}"
        split_record.role_or_program = role_title
        split_record.body_blocks = blocks
        split_record.design_fields = detect_design_fields(role_title, segment_text)
        split_record.key_duties = extract_key_duties(blocks, "채용공고")
        split_record.target_audience = extract_target_audience(blocks)
        segment_employment = extract_employment_types(role_title, segment_text, "채용공고")
        if segment_employment:
            split_record.employment_types = segment_employment
        split_record.content_hash = compute_hash(
            {
                "post_id": split_record.post_id,
                "title": split_record.title,
                "body_blocks": [(block.kind, block.text) for block in blocks],
                "design_fields": split_record.design_fields,
            }
        )
        records.append(split_record)
    return records
