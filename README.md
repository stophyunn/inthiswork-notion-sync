# InThisWork Design → Notion 자동 동기화

인디스워크의 **디자인 직무 페이지**에서 공개된 게시물을 확인해 Notion 데이터베이스에 저장하는 개인용 자동화입니다.

다음 유형을 구분해 함께 저장합니다.

- 채용공고
- 공모전
- 대외활동
- 교육·프로그램
- 커리어 콘텐츠
- 기타·확인 필요

공고의 긴 내용은 요약하지 않고, 접근 가능한 HTML 텍스트의 제목·문단·목록 순서를 최대한 유지해 각 Notion 항목의 본문에 넣습니다. 이미지 안에만 있는 글자, 외부 지원 페이지에만 있는 내용, 원문의 시각적 배치는 자동으로 완전히 복제할 수 없습니다.

## 중요한 운영 원칙

- 하루 1회, 한 번에 한 요청씩 실행합니다.
- 요청 사이에 기본 2.5초 간격을 둡니다.
- `robots.txt`가 명시적으로 접근을 막으면 중단합니다.
- 인디스워크가 `403` 또는 `429`를 반환하면 우회하지 않고 즉시 중단합니다.
- 공개 페이지의 개인 구직 관리 용도로만 사용하세요. 수집한 원문을 다시 배포하지 마세요.
- 사이트 구조가 바뀌면 추출 규칙을 수정해야 할 수 있습니다.

## Notion 데이터베이스 구조

최초 `Bootstrap Notion Database` 워크플로가 아래 속성을 자동 생성합니다.

- 공고명
- 콘텐츠 유형
- 사이트 원분류
- 기관/회사명
- 직무/프로그램명
- 디자인 분야
- 경력 분류 / 경력 원문
- 고용형태
- 지원 대상
- 근무·활동 지역
- 주요 업무·활동
- 혜택·상금
- 마감일 / 활동 기간 / 게시일
- 공고 상태
- 원문 링크 / 지원 링크
- 인디스워크 ID
- 최종 확인일
- 수집 상태
- 원문 변경 / 원문 해시

## 1. 이 프로젝트를 GitHub에 올리기

1. 이 ZIP 파일의 압축을 풉니다.
2. GitHub의 `inthiswork-notion-sync` 비공개 저장소를 엽니다.
3. `Add file → Upload files`를 선택합니다.
4. 압축을 푼 **폴더 자체가 아니라 폴더 안의 파일과 폴더 전체**를 업로드합니다.
5. 저장소 최상단에 `README.md`, `requirements.txt`, `src`, `.github`가 보이는지 확인합니다.
6. `Commit changes`를 누릅니다.

`.github` 폴더가 보이지 않는 운영체제에서는 숨김 파일 표시를 켜거나, 압축을 푼 폴더 전체를 GitHub 업로드 화면으로 끌어다 놓으세요.

## 2. 이미 등록했어야 하는 GitHub Secrets

저장소에서 다음으로 이동합니다.

`Settings → Secrets and variables → Actions → Secrets`

아래 두 개가 있어야 합니다.

- `NOTION_TOKEN`: Notion 내부 연결 토큰
- `NOTION_PARENT_PAGE_ID`: 연결 권한을 준 빈 상위 페이지의 ID 또는 URL

토큰은 코드나 README에 직접 쓰지 마세요.

## 3. Notion 데이터베이스 최초 생성

1. GitHub 저장소의 `Actions` 탭으로 이동합니다.
2. 왼쪽에서 **Bootstrap Notion Database**를 선택합니다.
3. `Run workflow`를 누릅니다.
4. 입력 칸에 정확히 `CREATE`를 입력합니다.
5. 실행이 끝난 뒤 실행 결과 페이지의 **Summary**를 엽니다.
6. 아래와 같은 두 값을 확인하고 Data Source ID를 복사합니다.

```text
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_DATA_SOURCE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

> Bootstrap은 먼저 상위 페이지 접근 권한을 확인하고, 같은 상위 페이지에 같은 이름의 데이터베이스가
> 발견되면 새로 만들지 않고 실패합니다. 그래도 최초 생성이 확인된 뒤에는 다시 실행하지 마세요.

## 4. Data Source ID를 GitHub Variable로 등록

저장소에서 다음으로 이동합니다.

`Settings → Secrets and variables → Actions → Variables → New repository variable`

다음과 같이 등록합니다.

```text
Name: NOTION_DATA_SOURCE_ID
Value: Bootstrap 결과의 ID
```

이 값은 토큰이 아니므로 `Variables`에 넣어도 됩니다.

## 5. 첫 안전 테스트

바로 전체 동기화를 실행하지 말고 먼저 소량 테스트를 권장합니다.

1. `Actions → InThisWork Design Sync → Run workflow`
2. 다음과 같이 선택합니다.

```text
mode: recent
dry_run: true
max_list_pages: 1
max_posts: 3
```

3. 실행 결과에서 게시물 제목, 유형, 회사명, 직무명 등이 적절히 추출되는지 확인합니다.
4. `dry_run: true`에서는 Notion에 아무것도 쓰지 않습니다.

## 6. Notion 쓰기 테스트

추출 결과가 괜찮다면 다시 실행합니다.

```text
mode: recent
dry_run: false
max_list_pages: 1
max_posts: 3
```

Notion에 3개 항목이 생성됐는지 확인하세요. 같은 설정으로 다시 실행해도 `인디스워크 ID`를 기준으로 중복 생성하지 않고 기존 항목을 확인합니다.

## 7. 최초 전체 동기화

테스트가 끝나면 수동 실행에서 다음을 선택합니다.

```text
mode: full
dry_run: false
max_list_pages: 0
max_posts: 0
```

- `0`은 제한 없음입니다.
- 전체 게시물 수에 따라 오래 걸릴 수 있습니다.
- 사이트가 `403` 또는 `429`를 반환하면 자동화는 실패 상태로 중단됩니다. 요청 간격을 줄이거나 우회하지 마세요.
- 전체 실행이 너무 크면 `max_list_pages`를 5 또는 10으로 나눠 시도할 수 있습니다. 다만 매번 최신 페이지부터 시작하므로 완전한 분할 수집 기능은 아닙니다.

## 8. 매일 자동 실행

업로드 후 예약 실행은 **매일 오전 9시 10분(Asia/Seoul)**에 동작합니다.

예약 실행은 다음 설정으로 작동합니다.

- 최신 디자인 목록 3페이지 확인
- 새 게시물 생성
- 기존 게시물의 원문 해시가 달라지면 속성과 본문 갱신
- 모집 중인 기존 항목 중 가장 오래 확인하지 않은 20개를 다시 확인
- 마감 또는 접근 불가 상태 반영

GitHub Actions의 예약 실행은 서버 상황에 따라 몇 분 이상 늦어질 수 있습니다.

## 분류 방식

자동 분류는 사이트 원분류, 제목, 본문 내 표현을 함께 봅니다.

- `공모전`, `콘테스트` → 공모전
- `서포터즈`, `기자단`, `앰배서더` → 대외활동
- `부트캠프`, `교육`, `아카데미`, `워크숍` → 교육·프로그램
- 신입/인턴·주니어경력 분류 또는 주요 업무·자격요건이 있는 모집글 → 채용공고
- 포트폴리오·인터뷰·취업 노하우 글 → 커리어 콘텐츠

명확하지 않은 항목은 `기타·확인 필요` 또는 `수집 상태=검토 필요`로 남기며, 임의로 사실을 만들어 넣지 않습니다.

## 자주 생기는 오류

### Bootstrap에서 403 또는 404

- Notion 내부 연결에 읽기·삽입·수정 권한이 있는지 확인하세요.
- 상위 `Job posting` 페이지의 `••• → 연결 추가`에서 해당 연결을 공유했는지 확인하세요.
- `NOTION_PARENT_PAGE_ID`에 다른 페이지 주소가 들어가지 않았는지 확인하세요.

### Sync에서 NOTION_DATA_SOURCE_ID가 비어 있다고 나옴

GitHub `Variables`에 `NOTION_DATA_SOURCE_ID`를 등록했는지 확인하세요. `Secrets`가 아니라 `Variables` 탭입니다.

### 인디스워크 403/429

자동화가 접근을 우회하지 않고 중단한 정상적인 안전 동작입니다. 잠시 후 수동 재시도하되 반복 실행하지 마세요. GitHub 실행 환경 자체가 차단되는 경우에는 이 방식으로 안정적인 자동 수집을 보장할 수 없습니다.

### 본문이 일부 비어 있음

공고가 이미지 중심이거나 외부 사이트에 내용이 있는 경우입니다. 해당 항목은 `검토 필요`로 분류될 수 있으므로 `원문 링크`와 `지원 링크`를 직접 확인하세요.

## 로컬 테스트(선택)

Python 3.12 기준입니다.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

실제 실행 환경 변수는 `.env.example`을 참고하되 `.env` 파일은 GitHub에 올리지 마세요.
