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
        _fixture("tinkware_live"), "https://inthiswork.com/archives/400001"
    )

    assert record.title == "팅크웨어｜UX/UI 디자이너 채용"
    assert "UX/UI 화면 기획 및 디자인" in record.key_duties
    assert "관련 직무 경험자" in record.target_audience
    assert all("오늘 핫한 공고" not in block.text for block in record.body_blocks)
    assert sum("UX/UI 화면 기획 및 디자인" in block.text for block in record.body_blocks) == 1
    assert any(block.kind == "bulleted_list_item" for block in record.body_blocks)
    assert record.collection_status == "검토 필요"


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
