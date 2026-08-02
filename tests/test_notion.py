from unittest.mock import Mock

import pytest

from src.notion_api import NotionClient, database_schema, extract_notion_id


def test_extract_notion_id_from_url():
    value = "https://www.notion.so/workspace/Page-1234567890abcdef1234567890abcdef"
    assert extract_notion_id(value) == "12345678-90ab-cdef-1234-567890abcdef"


def test_schema_has_required_properties():
    schema = database_schema()
    for name in ["공고명", "콘텐츠 유형", "원문 링크", "인디스워크 ID", "원문 해시"]:
        assert name in schema


def test_request_error_includes_structured_notion_details():
    client = NotionClient("secret", min_interval_seconds=0)
    response = Mock(status_code=400, ok=False, content=b"error", headers={})
    response.json.return_value = {
        "code": "validation_error",
        "message": "invalid parent",
        "request_id": "request-123",
    }
    client.session.request = Mock(return_value=response)

    with pytest.raises(RuntimeError, match=r"HTTP 400.*validation_error.*invalid parent.*request-123"):
        client._request("GET", "/pages/bad")


def test_create_database_validates_parent_before_writing():
    client = NotionClient("secret", min_interval_seconds=0)
    client._request = Mock(return_value={"object": "page", "archived": True})

    with pytest.raises(RuntimeError, match="사용 가능한 Notion 페이지"):
        client.create_database("1234567890abcdef1234567890abcdef")

    client._request.assert_called_once_with(
        "GET", "/pages/12345678-90ab-cdef-1234-567890abcdef"
    )
