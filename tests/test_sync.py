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
