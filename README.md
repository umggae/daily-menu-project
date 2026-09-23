# 오늘의 메뉴 추천

**한식·중식·일식·양식 중 골라서 오늘의 메뉴를 뽑는 예제**입니다. `daily-quote-project`와 같은 구조(Actions가 Python 실행 → 정적 HTML 생성 → Pages 배포)를 쓰고, 외부 API나 API 키가 필요 없습니다. 카테고리를 누르면 후보 메뉴들이 빠르게 지나가다 점점 느려지며 오늘의 메뉴에 멈추는 룰렛 연출이 들어있습니다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `menu.json` | 카테고리별 메뉴 목록과 코멘트 문구. 여기만 고치면 내용이 바뀝니다 |
| `main.py` | 한국 날짜 계산, 카테고리별 메뉴 선택, HTML·룰렛 애니메이션 생성 |
| `index.html` | 로컬에서 생성해 둔 저장본 |
| `.github/workflows/daily_menu.yml` | 실행 조건, Python 실행, Pages 배포 |

같은 날짜에도 카테고리마다 서로 다른 메뉴가 나오도록 카테고리 순서를 오프셋으로 사용합니다. (`(날짜 순번 + 카테고리 순번 × 배수) % 목록 길이`)

룰렛 애니메이션은 화면(클라이언트)에서만 도는 연출이라, 다시 뽑기를 눌러도 항상 오늘의 실제 메뉴로 착지합니다. 진짜 메뉴가 바뀌는 건 날짜가 바뀔 때뿐입니다.

## 로컬에서 확인하기

```bash
python3 main.py
```

다른 날짜 미리보기:

```bash
python3 main.py --date 2026-09-24 --output preview.html
```

## 배포하기 (daily-quote-project와 동일한 절차)

1. Public 저장소를 새로 만들고 이 폴더 내용을 `main` 최상위에 올립니다.
2. **Settings → Pages → Build and deployment → Source → GitHub Actions** 선택.
3. **Actions → Daily Menu Generator → Run workflow**, `preview_date` 비운 채 실행.
4. build·deploy 모두 성공하면 공개 URL에서 확인.
5. 수동 배포 성공 후 `daily_menu.yml`의 예약 두 줄 주석(`#`)을 지우면 매일 자동 갱신됩니다.
