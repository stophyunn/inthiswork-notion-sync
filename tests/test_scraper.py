from src.scraper import InThisWorkScraper, normalize_post_url


def test_normalize_post_url():
    assert (
        normalize_post_url("/archives/380755", "https://inthiswork.com/design")
        == "https://inthiswork.com/archives/380755"
    )
    assert normalize_post_url("https://example.com/archives/1", "https://inthiswork.com") is None


def test_extract_listing_urls():
    scraper = object.__new__(InThisWorkScraper)
    scraper._listing_categories = {}
    html = """
    <a href="/archives/100">one</a>
    <a href="https://inthiswork.com/archives/101/">two</a>
    <a href="/archives/category/test">category</a>
    """
    assert scraper._extract_post_urls(html, "https://inthiswork.com/design") == [
        "https://inthiswork.com/archives/100",
        "https://inthiswork.com/archives/101",
    ]


def test_extract_listing_category_for_detail_fallback():
    scraper = object.__new__(InThisWorkScraper)
    scraper._listing_categories = {}
    html = """
    <article><a href="/category/design">디자인</a><a href="/tag/new">신입/인턴</a>
      <h2><a href="/archives/379538">공고</a></h2></article>
    """

    scraper._extract_post_urls(html, "https://inthiswork.com/design")

    assert scraper._listing_categories["https://inthiswork.com/archives/379538"] == ["신입/인턴"]
