# Repository Working Rules

1. 모든 작업을 시작하기 전에 `git fetch origin main --prune`을 실행한다.
2. fetch가 실패하면 코드 수정이나 브랜치 생성을 시작하지 않는다.
3. `main` 브랜치에서는 직접 수정하거나 커밋하지 않는다.
4. 항상 최신 `origin/main`에서 작업별 새 브랜치를 생성한다.
5. 과거 PR 브랜치를 새 작업에 재사용하지 않는다.
6. 수정 후 반드시 다음 명령을 실행한다.
   - `pytest -q`
   - `python -m compileall -q src tests`
   - `git diff --check`
7. PR 직전에는 최신 `origin/main`을 다시 fetch하고 rebase한다.
8. rebase 후 테스트를 다시 실행한다.
9. `git diff --name-status origin/main...HEAD`로 변경 파일을 확인한다.
10. 사용자 승인 없이 push, force-push, PR 생성 또는 `main` 병합을 하지 않는다.
11. `main`에는 절대 force-push하지 않는다.
12. `.env`, 토큰, Secret 및 환경변수 실제 값을 출력하거나 커밋하지 않는다.
13. 403이나 429가 발생하면 우회하지 않고 중단한다.
14. 인디스워크 요청은 순차 실행하고 약 2.5초 간격을 유지한다.
15. 기존 파서 기능과 회귀 테스트를 삭제하지 않는다.
