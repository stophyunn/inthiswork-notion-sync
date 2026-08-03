from src.models import ContentBlock, PostRecord
from src.sync import _dry_run_preview, _filter_in_scope_records


def test_dry_run_preview_explicitly_marks_truncated_body_blocks():
    record = PostRecord(
        post_id="378352",
        source_url="https://inthiswork.com/archives/378352",
        title="토스뱅크｜Visual Design Assistant",
        content_type="채용공고",
        body_blocks=[ContentBlock(kind="paragraph", text=f"블록 {index}") for index in range(10)],
    )

    preview = _dry_run_preview(record)

    assert "body_blocks" not in preview
    assert preview["body_blocks_total"] == 10
    assert preview["body_blocks_omitted"] == 2
    assert len(preview["body_blocks_preview"]) == 8
    assert preview["body_blocks_last"] == {"kind": "paragraph", "text": "블록 9"}
    for field in (
        "key_duties", "qualifications", "preferred_qualifications",
        "essay_questions", "pre_assignment", "target_audience",
    ):
        assert field in preview


def test_missing_duties_preview_includes_heading_candidates_only_in_diagnostics():
    record = PostRecord(
        post_id="380773", source_url="https://inthiswork.com/archives/380773",
        title="LinqAlpha｜Product Designer", content_type="채용공고",
        quality_reasons={"missing_job_duties": True},
        body_blocks=[
            ContentBlock(kind="paragraph", text="이런 일을 하게 됩니다!"),
            ContentBlock(kind="paragraph", text="x" * 101),
        ],
        content_hash="stable-hash",
    )
    preview = _dry_run_preview(record)
    assert preview["heading_candidates"] == [
        {
            "index": 0, "kind": "paragraph", "text": "이런 일을 하게 됩니다!",
            "normalized": "이런 일을 하게 됩니다", "section": "duties",
        }
    ]
    assert record.content_hash == "stable-hash"
    assert not hasattr(record, "heading_candidates")


def test_normal_preview_does_not_include_heading_candidates():
    record = PostRecord(
        post_id="1", source_url="https://inthiswork.com/archives/1", title="Normal",
        content_type="채용공고",
        quality_reasons={"missing_job_duties": False},
    )
    assert "heading_candidates" not in _dry_run_preview(record)


def test_scope_filter_excludes_non_design_records_before_output_or_notion_work(caplog):
    import logging

    caplog.set_level(logging.INFO)
    design = PostRecord(
        post_id="1", source_url="https://inthiswork.com/archives/1",
        title="회사｜Product Designer", role_or_program="Product Designer",
        content_type="채용공고",
    )
    ios = PostRecord(
        post_id="372901", source_url="https://inthiswork.com/archives/372901",
        title="토스｜iOS Developer", role_or_program="iOS Developer",
        content_type="채용공고",
        body_blocks=[ContentBlock(kind="paragraph", text="TDS 디자인 시스템과 UI 인터랙션")],
    )
    mixed = PostRecord(
        post_id="378641", source_url="https://inthiswork.com/archives/378641",
        title="동국제약｜관리/마케팅/영업/디자인/개발/연구 등 모집",
        role_or_program="관리/마케팅/영업/디자인/개발/연구 등 모집",
        content_type="채용공고",
    )
    eland = PostRecord(
        post_id="380915", source_url="https://inthiswork.com/archives/380915",
        title="이랜드월드｜이랜드뮤지엄 신입 및 경력채용 (전시기획 디자이너, 컨서베이터)",
        role_or_program="이랜드뮤지엄 신입 및 경력채용 (전시기획 디자이너, 컨서베이터)",
        content_type="채용공고",
        quality_reasons={"missing_body": True, "image_only_content": True},
    )

    included, counts = _filter_in_scope_records(
        [design, ios, mixed, eland], "https://inthiswork.com/list"
    )

    assert included == [design]
    assert counts == {"in_scope": 1, "filtered_non_design": 1, "filtered_ambiguous": 2}
    assert "ID=372901" in caplog.text
    assert "reason=non_design_role" in caplog.text
    assert "ID=380915" in caplog.text
    assert "reason=no_isolated_design_role" in caplog.text
    assert all(record.post_id != "372901" for record in included)
    assert all(record.post_id != "380915" for record in included)
