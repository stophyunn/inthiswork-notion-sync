from src.models import ContentBlock, PostRecord
from src.sync import _dry_run_preview


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
