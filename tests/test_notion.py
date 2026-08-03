from unittest.mock import Mock

import pytest

from src.models import PostRecord
from src.notion_api import (
    APPLICATION_SECTION_PROPERTIES,
    NotionClient,
    database_schema,
    extract_notion_id,
)


def test_extract_notion_id_from_url():
    value = "https://www.notion.so/workspace/Page-1234567890abcdef1234567890abcdef"
    assert extract_notion_id(value) == "12345678-90ab-cdef-1234-567890abcdef"


def test_schema_has_required_properties():
    schema = database_schema()
    for name in ["공고명", "콘텐츠 유형", "원문 링크", "인디스워크 ID", "원문 해시"]:
        assert name in schema
    assert all(schema[name] == {"rich_text": {}} for name in APPLICATION_SECTION_PROPERTIES)


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


def test_record_properties_map_jobs_and_explicitly_clear_target_audience():
    client = NotionClient("secret", min_interval_seconds=0)
    record = PostRecord(
        post_id="1", source_url="https://example.test/1", title="Designer",
        content_type="채용공고", target_audience="legacy", key_duties="Design",
        qualifications="Required", preferred_qualifications="Preferred",
        essay_questions="Question", pre_assignment="Assignment",
    )
    properties = client._record_properties(record, changed=True)
    assert properties["지원 대상"] == {"rich_text": []}
    assert properties["자격요건"]["rich_text"][0]["text"]["content"] == "Required"
    assert properties["우대사항"]["rich_text"][0]["text"]["content"] == "Preferred"
    assert properties["자소서 문항"]["rich_text"][0]["text"]["content"] == "Question"
    assert properties["사전과제"]["rich_text"][0]["text"]["content"] == "Assignment"
    assert properties["주요 업무·활동"]["rich_text"][0]["text"]["content"] == "Design"


def test_record_properties_keep_non_job_audience_and_clear_qualifications():
    client = NotionClient("secret", min_interval_seconds=0)
    record = PostRecord(
        post_id="2", source_url="https://example.test/2", title="Contest",
        content_type="공모전", target_audience="Students", qualifications="stale",
    )
    properties = client._record_properties(record, changed=False)
    assert properties["지원 대상"]["rich_text"][0]["text"]["content"] == "Students"
    assert properties["자격요건"] == {"rich_text": []}


def test_create_and_update_payloads_share_application_section_mapping():
    client = NotionClient("secret", min_interval_seconds=0)
    record = PostRecord(
        post_id="3", source_url="https://example.test/3", title="Designer",
        content_type="채용공고", qualifications="Required",
        preferred_qualifications="Preferred", essay_questions="Question",
        pre_assignment="Assignment",
    )
    client._request = Mock(return_value={"id": "page-3"})
    client.create_record("1234567890abcdef1234567890abcdef", record)
    create_payload = client._request.call_args.kwargs["json"]["properties"]
    client._request.reset_mock()
    client.update_record({"id": "page-3"}, record, changed=False)
    update_payload = client._request.call_args.kwargs["json"]["properties"]
    for name in APPLICATION_SECTION_PROPERTIES:
        assert create_payload[name] == update_payload[name]


def test_schema_validation_names_missing_properties_and_migration_workflow():
    client = NotionClient("secret", min_interval_seconds=0)
    client.retrieve_data_source = Mock(return_value={"properties": {}})
    with pytest.raises(RuntimeError, match="자격요건.*Migrate Notion Schema"):
        client.validate_sync_schema("1234567890abcdef1234567890abcdef")


def test_schema_migration_adds_only_missing_properties_and_is_idempotent():
    client = NotionClient("secret", min_interval_seconds=0)
    properties = {"자격요건": {"type": "rich_text"}, "기존": {"type": "title"}}

    def request(method, path, json=None):
        if method == "PATCH":
            properties.update({name: {"type": "rich_text"} for name in json["properties"]})
        return {"properties": properties}

    client._request = Mock(side_effect=request)
    added, existing = client.migrate_application_schema("1234567890abcdef1234567890abcdef")
    assert added == ["우대사항", "자소서 문항", "사전과제"]
    assert existing == ["자격요건"]
    patch_calls = [call for call in client._request.call_args_list if call.args[0] == "PATCH"]
    assert len(patch_calls) == 1
    added_again, existing_again = client.migrate_application_schema(
        "1234567890abcdef1234567890abcdef"
    )
    assert added_again == []
    assert existing_again == list(APPLICATION_SECTION_PROPERTIES)
    patch_calls = [call for call in client._request.call_args_list if call.args[0] == "PATCH"]
    assert len(patch_calls) == 1
    assert properties["기존"] == {"type": "title"}
