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
    assert "체험형 인턴" in record.employment_types
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
