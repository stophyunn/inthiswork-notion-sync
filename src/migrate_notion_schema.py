from __future__ import annotations

import os

from .config import Settings
from .notion_api import APPLICATION_SECTION_PROPERTIES, NotionClient


def main() -> None:
    if os.getenv("MIGRATION_CONFIRMATION", "") != "MIGRATE":
        raise SystemExit("confirmation 값이 MIGRATE와 일치하지 않아 변경하지 않습니다.")
    settings = Settings.from_env()
    if not settings.notion_data_source_id:
        raise SystemExit("NOTION_DATA_SOURCE_ID가 비어 있습니다.")
    client = NotionClient(settings.notion_token, settings.notion_api_version)
    added, existing = client.migrate_application_schema(settings.notion_data_source_id)
    lines = [
        "## Migrate Notion Schema",
        "",
        "- 새로 추가: " + (", ".join(added) if added else "없음"),
        "- 이미 존재: " + (", ".join(existing) if existing else "없음"),
        "- 최종 확인: " + ", ".join(APPLICATION_SECTION_PROPERTIES),
    ]
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
