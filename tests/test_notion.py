from src.notion_api import database_schema, extract_notion_id


def test_extract_notion_id_from_url():
    value = "https://www.notion.so/workspace/Page-1234567890abcdef1234567890abcdef"
    assert extract_notion_id(value) == "12345678-90ab-cdef-1234-567890abcdef"


def test_schema_has_required_properties():
    schema = database_schema()
    for name in ["공고명", "콘텐츠 유형", "원문 링크", "인디스워크 ID", "원문 해시"]:
        assert name in schema
