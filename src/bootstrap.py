from __future__ import annotations

import logging
import os

from .config import Settings
from .notion_api import NotionClient


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    if os.getenv("BOOTSTRAP_CONFIRM", "").strip() != "CREATE":
        raise SystemExit("안전을 위해 BOOTSTRAP_CONFIRM=CREATE가 필요합니다.")
    if not settings.notion_parent_page_id:
        raise SystemExit("NOTION_PARENT_PAGE_ID가 비어 있습니다.")

    client = NotionClient(settings.notion_token, settings.notion_api_version)
    database_id, data_source_id = client.create_database(settings.notion_parent_page_id)

    print("\n=== 생성 완료 ===")
    print(f"NOTION_DATABASE_ID={database_id}")
    print(f"NOTION_DATA_SOURCE_ID={data_source_id}")

    github_output = os.getenv("GITHUB_OUTPUT", "").strip()
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(f"notion_database_id={database_id}\n")
            output.write(f"notion_data_source_id={data_source_id}\n")
    print("\nGitHub 저장소의 Settings → Secrets and variables → Actions → Variables에")
    print("위 NOTION_DATA_SOURCE_ID 값을 등록한 뒤 동기화 워크플로를 실행하세요.")


if __name__ == "__main__":
    main()
