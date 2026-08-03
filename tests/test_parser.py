import pytest
from bs4 import BeautifulSoup

from src.parser import parse_post_html


JOB_HTML = """
<html><head>
<meta property="article:published_time" content="2026-08-01T10:00:00+09:00" />
</head><body>
<article>
  <h1 class="entry-title">테스트회사｜Product Designer 인턴</h1>
  <a rel="category tag">신입/인턴</a>
  <div class="entry-content">
    <h2>주요 업무</h2>
    <ul><li>Figma를 활용한 UI/UX 디자인</li><li>디자인 시스템 정리</li></ul>
    <h2>자격 요건</h2>
    <p>대학생 또는 졸업예정자</p>
    <h2>근무 조건</h2>
    <p>고용형태: 체험형 인턴</p>
    <p>근무지: 서울 강남구</p>
    <p>지원기간: 2026.08.01 - 2099.08.31</p>
    <a href="https://jobs.example.com/apply">지원하러 가기</a>
  </div>
</article>
</body></html>
"""


ACTIVITY_HTML = """
<html><body><article>
<h1 class="entry-title">대외활동｜2026 브랜드 디자인 공모전</h1>
<a rel="category tag">교육/대외활동</a>
<div class="entry-content">
<h2>공모 주제</h2><p>새로운 브랜드 아이덴티티 제안</p>
<h2>지원 대상</h2><p>대학생 및 일반인</p>
<h2>상금</h2><p>대상 300만원</p>
<p>모집 기간: 2026년 8월 1일 ~ 2099년 9월 10일</p>
</div></article></body></html>
"""


def test_parse_job_post():
    record = parse_post_html(JOB_HTML, "https://inthiswork.com/archives/123456")
    assert record.post_id == "123456"
    assert record.organization == "테스트회사"
    assert record.content_type == "채용공고"
    assert record.experience_class == "인턴"
    assert record.employment_types == ["인턴"]
    assert "UI/UX" in record.design_fields
    assert record.location.startswith("서울 강남구")
    assert record.apply_url == "https://jobs.example.com/apply"
    assert record.deadline == "2099-08-31"
    assert record.status == "모집 중"
    assert record.content_hash


def test_parse_competition():
    record = parse_post_html(ACTIVITY_HTML, "https://inthiswork.com/archives/999999")
    assert record.content_type == "공모전"
    assert record.experience_class == "해당 없음"
    assert record.role_or_program == "2026 브랜드 디자인 공모전"
    assert "300만원" in record.benefits_prize
    assert record.deadline == "2099-09-10"


def test_empty_body_requires_review_and_job_title_is_classified():
    record = parse_post_html(
        "<html><body><h1>그래픽 디자이너 아르바이트 채용</h1></body></html>",
        "https://inthiswork.com/archives/1",
    )

    assert record.content_type == "채용공고"
    assert record.employment_types == ["아르바이트"]
    assert record.collection_status == "검토 필요"


def test_content_root_scores_candidates_and_deduplicates_fusion_body():
    html = """
    <article><h1 class="entry-title">회사｜UI/UX 디자이너 인턴</h1>
      <div class="post-content"></div>
      <div class="fusion-content-tb">
        <div class="fusion-text"><p><strong>담당업무</strong></p>
          <p>UI/UX 기획 및 디자인 작업 지원</p><p>UI/UX 기획 및 디자인 작업 지원</p>
          <p><strong>근무장소</strong></p><p>경기도 성남시 분당구 정자동</p>
          <p>지원기간: 2026.08.01 ~ 2026.08.12</p>
        </div>
      </div>
    </article>
    """
    record = parse_post_html(html, "https://inthiswork.com/archives/379538")

    assert record.body_blocks
    assert record.key_duties == "UI/UX 기획 및 디자인 작업 지원"
    assert record.location == "경기도 성남시 분당구 정자동"
    assert record.deadline == "2026-08-12"
    assert sum(block.text == "UI/UX 기획 및 디자인 작업 지원" for block in record.body_blocks) == 1


def _fixture(post_id: str) -> str:
    from pathlib import Path

    return Path(f"tests/fixtures/{post_id}.html").read_text(encoding="utf-8")


def test_regression_379538_current_fusion_structure():
    record = parse_post_html(_fixture("379538"), "https://inthiswork.com/archives/379538")

    assert record.content_type == "채용공고"
    assert record.employment_types == ["인턴"]
    assert {"UI/UX", "캐릭터/일러스트"}.issubset(record.design_fields)
    assert record.deadline == "2026-08-12"
    assert record.location == "경기도 성남시 분당구 정자동"
    assert "UI/UX 기획 및 디자인 작업 지원" in record.key_duties
    assert record.body_blocks


def test_regression_379626_part_time_graphic_role():
    record = parse_post_html(_fixture("379626"), "https://inthiswork.com/archives/379626")

    assert record.content_type == "채용공고"
    assert record.employment_types == ["아르바이트"]
    assert "그래픽" in record.design_fields
    assert record.body_blocks


def test_regression_379384_splits_multiple_design_roles():
    from src.parser import parse_post_html_records

    records = parse_post_html_records(
        _fixture("379384"), "https://inthiswork.com/archives/379384"
    )

    assert [record.post_id for record in records] == ["379384-1", "379384-2"]
    assert records[0].design_fields == ["UI/UX"]
    assert records[1].design_fields == ["그래픽"]
    assert "카메라 서비스 UI/UX 디자인" in records[0].key_duties
    assert "서비스 그래픽 에셋 제작" in records[1].key_duties


def test_tinkware_live_shape_prefers_metadata_and_splits_flat_sections():
    record = parse_post_html(
        _fixture("tinkware_live"), "https://inthiswork.com/archives/380820"
    )

    assert record.title == "팅크웨어｜아이나비 브랜드 콘텐츠 디자인 (경력)"
    assert len(record.key_duties.splitlines()) == 6
    assert "브랜드 콘텐츠 디자인" in record.key_duties
    assert "관련 직무 경력 3년 이상" in record.target_audience
    assert record.employment_types == ["정규직"]
    assert record.experience_raw == "경력 3년 이상"
    assert all("오늘 핫한 공고" not in block.text for block in record.body_blocks)
    assert sum("브랜드 콘텐츠 디자인" in block.text for block in record.body_blocks) == 1
    assert any(block.kind == "bulleted_list_item" for block in record.body_blocks)
    assert record.benefits_prize == "유연 근무제"
    assert record.collection_status == "정상"
    assert not any(record.quality_reasons.values())
    assert all(
        block.kind == "bulleted_list_item"
        for block in record.body_blocks
        if block.text in {
            "브랜드 콘텐츠 디자인",
            "SNS 비주얼 제작",
            "프로모션 그래픽 제작",
            "브랜드 가이드 운영",
            "촬영 비주얼 디렉팅",
            "유관 부서 협업",
        }
    )


@pytest.mark.parametrize("marker", ["ㆍ", "•", "·"])
def test_compact_dot_markers_are_bullets_without_spaces(marker):
    html = f"""
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb"><p>수행 업무\n{marker}업무 내용</p></div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600001")

    assert any(
        block.kind == "bulleted_list_item" and block.text == "업무 내용"
        for block in record.body_blocks
    )


@pytest.mark.parametrize("marker", ["-", "–", "—"])
def test_dash_markers_are_bullets_only_with_spaces(marker):
    html = f"""
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb"><p>수행 업무\n{marker} 업무 내용</p></div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600002")

    assert any(
        block.kind == "bulleted_list_item" and block.text == "업무 내용"
        for block in record.body_blocks
    )


def test_dates_negative_numbers_and_inline_hyphens_are_not_bullets():
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb"><p>수행 업무
    2026-08-12
    -3
    문장 중간-하이픈</p></div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600003")
    blocks = {block.text: block.kind for block in record.body_blocks}

    assert blocks["2026-08-12"] == "paragraph"
    assert blocks["-3"] == "paragraph"
    assert blocks["문장 중간-하이픈"] == "paragraph"


def test_native_unordered_and_ordered_lists_keep_their_block_kinds():
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb"><h2>수행 업무</h2>
    <ul><li>브랜드 콘텐츠 제작</li></ul>
    <ol><li>포트폴리오 제출</li></ol>
    </div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600008")
    blocks = {block.text: block.kind for block in record.body_blocks}

    assert blocks["브랜드 콘텐츠 제작"] == "bulleted_list_item"
    assert blocks["포트폴리오 제출"] == "numbered_list_item"


def test_repeated_heading_with_distinct_content_is_preserved_without_review():
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb">
    <h2>수행 업무</h2><p>브랜드 영상 제작</p>
    <h2>수행 업무</h2><p>마케팅 콘텐츠 편집</p>
    </div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600004")

    assert [block.text for block in record.body_blocks] == [
        "수행 업무", "브랜드 영상 제작", "수행 업무", "마케팅 콘텐츠 편집"
    ]
    assert record.collection_status == "정상"
    assert record.quality_reasons["unresolved_repetition"] is False


def test_orphan_duplicate_heading_is_removed_after_render_deduplication():
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb">
    <h2>수행 업무</h2><p>브랜드 영상 제작</p><h2>수행 업무</h2>
    </div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600005")

    assert sum(block.text == "수행 업무" for block in record.body_blocks) == 1
    assert record.collection_status == "정상"


def test_repeated_meaningful_body_sequence_requires_review():
    repeated = [
        "브랜드 캠페인의 핵심 비주얼을 다양한 채널 규격에 맞춰 제작하고 관리해요.",
        "마케팅 목표와 사용자 맥락을 반영해 디지털 콘텐츠의 완성도를 지속적으로 개선해요.",
        "유관 부서와 긴밀하게 협업하며 일관된 브랜드 경험을 위한 디자인 기준을 운영해요.",
        "프로젝트 결과를 정리하고 다음 제작 과정에 활용할 수 있도록 작업 자산을 체계화해요.",
    ]
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb"><h2>수행 업무</h2>
    {body}
    </div></article></body></html>
    """.format(body="".join(f"<p>{line}</p>" for line in repeated * 2))

    record = parse_post_html(html, "https://inthiswork.com/archives/600006")

    assert record.collection_status == "검토 필요"
    assert record.quality_reasons["unresolved_repetition"] is True


def test_short_accidental_sequence_repetition_is_preserved_without_review():
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb"><h2>수행 업무</h2>
    <p>검토</p><p>협업</p><p>검토</p><p>협업</p>
    </div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600009")

    assert [block.text for block in record.body_blocks].count("검토") == 2
    assert [block.text for block in record.body_blocks].count("협업") == 2
    assert record.quality_reasons["unresolved_repetition"] is False
    assert record.collection_status == "정상"


def test_tossbank_complete_repeated_body_keeps_one_full_render():
    html = _fixture("tossbank_visual_design_assistant_live")
    source_url = "https://inthiswork.com/archives/378352"

    record = parse_post_html(html, source_url, fallback_categories=["신입/인턴"])

    duties = [
        "브랜딩/마케팅에 필요한 다양한 콘텐츠(인스타그램 이미지·영상, 배너, 썸네일 등)를 디자인해요.",
        "대내외 커뮤니케이션을 위한 이미지와 PPT 제작을 서포트해요.",
        "인터널 이벤트 전반에 필요한 디자인 관련 업무를 서포트해요. (포스터, 굿즈 제작 등)",
    ]
    qualification = (
        "Figma, Photoshop, Illustrator 등 그래픽 툴을 능숙하게 활용하며, "
        "디자인 제작 요청에 맞춰 다양한 그래픽을 기획하고 제작할 수 있는 분을 찾고 있어요."
    )
    preferred = "모션/3D, 레터링 등 다양한 아트웍 제작 경험이 있다면 이 포지션과 잘 맞아요."
    contract = "고용 형태는 단기계약직으로 진행되고, 계약기간은 입사일로부터 3개월이에요."
    texts = [block.text for block in record.body_blocks]
    assert all(text in texts for text in duties)
    assert all(texts.count(text) == 1 for text in duties)
    assert qualification in texts
    assert preferred in texts
    assert contract in texts
    assert all(text not in {"지원하기", "지원하러 가기"} for text in texts)
    assert texts.count("토스뱅크 소속") == 1
    assert len(texts) == len(set((block.kind, block.text) for block in record.body_blocks))
    assert [texts.index(text) for text in duties] == sorted(texts.index(text) for text in duties)
    assert record.quality_reasons["unresolved_repetition"] is False
    assert record.quality_reasons["missing_job_duties"] is False
    assert record.collection_status == "정상"
    assert record.employment_types == ["계약직"]
    assert record.experience_class == "신입"
    assert record.key_duties == "\n".join(duties)
    assert qualification in record.target_audience
    assert all(duty in texts for duty in record.key_duties.splitlines())
    assert all(line in texts for line in record.target_audience.splitlines())
    assert record.body_blocks[-1].text != "합류하면 함께 할 업무예요"

    single_soup = BeautifulSoup(html, "html.parser")
    single_soup.select_one(".fusion-content-tb-1").decompose()
    single_record = parse_post_html(
        str(single_soup), source_url, fallback_categories=["신입/인턴"]
    )
    assert record.content_hash == single_record.content_hash


def test_tossbank_incomplete_first_render_selects_complete_second_render():
    soup = BeautifulSoup(_fixture("tossbank_visual_design_assistant_live"), "html.parser")
    first_render = soup.select_one(".fusion-content-tb-1")
    duty_heading = next(
        child
        for child in first_render.find_all(recursive=False)
        if child.get_text(" ", strip=True) == "합류하면 함께 할 업무예요"
    )
    for sibling in list(duty_heading.find_next_siblings()):
        sibling.decompose()

    record = parse_post_html(
        str(soup),
        "https://inthiswork.com/archives/378352",
        fallback_categories=["신입/인턴"],
    )
    texts = [block.text for block in record.body_blocks]

    assert texts.count("토스뱅크 소속") == 1
    assert "브랜딩/마케팅에 필요한 다양한 콘텐츠(인스타그램 이미지·영상, 배너, 썸네일 등)를 디자인해요." in texts
    assert "Figma, Photoshop, Illustrator 등 그래픽 툴을 능숙하게 활용하며, 디자인 제작 요청에 맞춰 다양한 그래픽을 기획하고 제작할 수 있는 분을 찾고 있어요." in texts
    assert "모션/3D, 레터링 등 다양한 아트웍 제작 경험이 있다면 이 포지션과 잘 맞아요." in texts
    assert "고용 형태는 단기계약직으로 진행되고, 계약기간은 입사일로부터 3개월이에요." in texts
    assert record.quality_reasons["unresolved_repetition"] is False
    assert record.quality_reasons["missing_job_duties"] is False
    assert record.collection_status == "정상"


def test_job_ending_at_duty_heading_requires_review():
    soup = BeautifulSoup(_fixture("tossbank_visual_design_assistant_live"), "html.parser")
    soup.select_one(".fusion-content-tb-2").decompose()
    first_render = soup.select_one(".fusion-content-tb-1")
    duty_heading = next(
        child
        for child in first_render.find_all(recursive=False)
        if child.get_text(" ", strip=True) == "합류하면 함께 할 업무예요"
    )
    for sibling in list(duty_heading.find_next_siblings()):
        sibling.decompose()

    record = parse_post_html(
        str(soup),
        "https://inthiswork.com/archives/378352",
        fallback_categories=["신입/인턴"],
    )

    assert record.body_blocks[-1].text == "합류하면 함께 할 업무예요"
    assert record.key_duties == ""
    assert record.quality_reasons["missing_job_duties"] is True
    assert record.collection_status == "검토 필요"


def test_short_common_prefix_keeps_both_unique_tails():
    html = """
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb">
    <p>공통 소개</p><h2>수행 업무</h2><p>첫 번째 고유 업무</p>
    <p>공통 소개</p><h2>수행 업무</h2><p>두 번째 고유 업무</p>
    </div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600011")
    texts = [block.text for block in record.body_blocks]

    assert "첫 번째 고유 업무" in texts
    assert "두 번째 고유 업무" in texts
    assert sum(text == "수행 업무" for text in texts) == 2


def test_job_category_wins_over_incidental_activity_word_in_resume_guidance():
    html = """
    <html><head><meta property="og:title" content="회사｜Visual Design Assistant" /></head>
    <body><article><div class="fusion-content-tb">
    <h2>수행 업무</h2><p>브랜드 콘텐츠 디자인을 지원해요.</p>
    <p>학력, 대외활동, 인턴 시기를 명확하게 작성해 주세요.</p>
    <p>고용 형태는 단기계약직이에요.</p>
    </div></article></body></html>
    """

    record = parse_post_html(
        html,
        "https://inthiswork.com/archives/600012",
        fallback_categories=["신입/인턴"],
    )

    assert record.content_type == "채용공고"
    assert record.employment_types == ["계약직"]
    assert record.quality_reasons["missing_job_duties"] is False

    explicit_intern_html = """
    <html><head><meta property="og:title" content="회사｜Design Assistant" /></head>
    <body><article><div class="fusion-content-tb">
    <h2>수행 업무</h2><p>대외활동 콘텐츠를 디자인해요.</p>
    <p>고용 형태는 인턴이며 관련 디자인 업무를 수행해요.</p>
    </div></article></body></html>
    """
    explicit_intern_record = parse_post_html(
        explicit_intern_html,
        "https://inthiswork.com/archives/600013",
        fallback_categories=["신입/인턴"],
    )

    assert explicit_intern_record.content_type == "채용공고"
    assert explicit_intern_record.employment_types == ["인턴"]
    assert explicit_intern_record.experience_class == "인턴"


def test_hyundai_livart_image_only_post_still_requires_review():
    record = parse_post_html(
        _fixture("hyundai_livart_378233"),
        "https://inthiswork.com/archives/378233",
        fallback_categories=["주니어경력"],
    )

    assert record.quality_reasons["missing_body"] is True
    assert record.quality_reasons["image_only_content"] is True
    assert record.collection_status == "검토 필요"


def test_benefits_stop_at_last_complete_line():
    first_line = " ".join(f"리프레시휴가{index:02d}" for index in range(80))
    second_line = " ".join(f"포상지원제도{index:02d}" for index in range(80))
    html = f"""
    <html><head><meta property="og:title" content="회사｜콘텐츠 디자이너 채용" /></head>
    <body><article><div class="fusion-content-tb">
    <h2>수행 업무</h2><p>브랜드 콘텐츠 제작</p>
    <h2>혜택 및 복지</h2><p>{first_line}</p><p>{second_line}</p>
    </div></article></body></html>
    """

    record = parse_post_html(html, "https://inthiswork.com/archives/600007")

    assert record.benefits_prize == first_line
    assert record.benefits_prize.endswith("리프레시휴가79")
    assert len(record.benefits_prize) <= 1200


def test_dmil_live_shape_ignores_publish_year_and_non_duty_design_terms():
    record = parse_post_html(
        _fixture("dmil_live"), "https://inthiswork.com/archives/400002"
    )

    assert record.title == "DMIL｜콘텐츠 디자이너 채용"
    assert record.experience_raw == ""
    assert record.experience_class == "확인 필요"
    assert "SNS 콘텐츠 및 광고 소재 디자인" in record.key_duties
    assert "포트폴리오 제출 가능자" in record.target_audience
    assert record.benefits_prize == "장비 지원"
    assert record.design_fields == ["콘텐츠"]
    assert all("함께 보면 좋은" not in block.text for block in record.body_blocks)


def test_natural_headings_and_heading_attached_to_bullet_are_split():
    html = """
    <html><head><meta property="og:title" content="DMIL｜콘텐츠 디자이너 채용" /></head><body>
    <article><div class="fusion-content-tb"><p>
    이런 일을 함께해요
    ㆍ 자사 브랜드 인스타그램 콘텐츠 및 SNS 비주얼을 디자인해요.\n[이런 분을 모시고 있어요]
    ㆍ 포트폴리오 제출 가능자
    디밀은 이렇게 일해요
    ㆍ 장비 지원
    </p></div></article></body></html>
    """
    record = parse_post_html(html, "https://inthiswork.com/archives/500001")

    assert [block.text for block in record.body_blocks if block.kind == "heading_3"] == [
        "이런 일을 함께해요", "이런 분을 모시고 있어요", "디밀은 이렇게 일해요"
    ]
    assert record.key_duties == "자사 브랜드 인스타그램 콘텐츠 및 SNS 비주얼을 디자인해요."
    assert record.target_audience == "포트폴리오 제출 가능자"
    assert record.benefits_prize == "장비 지원"


def test_successful_duplicate_removal_is_normal_and_removes_decorations():
    body = """이런 일을 함께해요
- 모바일 게임 2D 아트 제작 보조
이런 분을 찾고 있어요
• 2D 아트 포트폴리오 보유자
😉
지원하러 가기"""
    html = f"""
    <html><head><meta property="og:title" content="퍼즐원스튜디오｜2D 아트 아르바이트" /></head>
    <body><article><div class="fusion-content-tb"><p>{body}\n{body}</p></div></article></body></html>
    """
    record = parse_post_html(html, "https://inthiswork.com/archives/500002")

    assert record.key_duties == "모바일 게임 2D 아트 제작 보조"
    assert record.target_audience == "2D 아트 포트폴리오 보유자"
    assert record.employment_types == ["아르바이트"]
    assert sum(block.text == "모바일 게임 2D 아트 제작 보조" for block in record.body_blocks) == 1
    assert all(block.text not in {"😉", "지원하러 가기"} for block in record.body_blocks)
    assert record.collection_status == "정상"


def test_snow_natural_sections_ignore_future_regular_job_and_parse_split_deadline():
    html = """
    <html><head><meta property="og:title" content="SNOW｜UI/UX 체험형 인턴 채용" />
    <meta property="article:published_time" content="2026-08-01T00:00:00+09:00" /></head><body>
    <article><div class="fusion-content-tb"><p>이런 경험을 할 수 있어요
    - AI 기반 캐릭터 채팅 서비스 UI/UX 기획 및 디자인 작업 지원
    - AI 서비스 콘텐츠 및 데이터 구성 지원
    이런 분을 기다립니다
    - UI/UX 포트폴리오 제출 가능자
    향후 정규직 공고에 지원하더라도 별도 가산점은 없습니다.
    지원서 접수 마감
    :
    2026.08.12(수) 23:59
    😉</p></div></article></body></html>
    """
    record = parse_post_html(html, "https://inthiswork.com/archives/379538")

    assert "AI 기반 캐릭터 채팅 서비스 UI/UX 기획 및 디자인 작업 지원" in record.key_duties
    assert "AI 서비스 콘텐츠 및 데이터 구성 지원" in record.key_duties
    assert record.target_audience == "UI/UX 포트폴리오 제출 가능자\n향후 정규직 공고에 지원하더라도 별도 가산점은 없습니다."
    assert record.employment_types == ["인턴"]
    assert record.deadline == "2026-08-12"
    assert record.collection_status == "정상"
