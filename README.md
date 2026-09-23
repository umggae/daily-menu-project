# 오늘의 외대 맛집

**한식·중식·일식·양식 중 골라서 오늘 갈 맛집을 원형 룰렛으로 뽑는 예제**입니다. 장소 데이터는 [외대 맛집 지도](https://hufs-gourmet-map.notion.site/)(한국외대 이탈리아어과 정서연 제작)에서 가게 이름·대표 메뉴만 가져와 정리했습니다. `daily-quote-project`와 같은 구조(Actions가 Python 실행 → 정적 HTML 생성 → Pages 배포)를 쓰고, 외부 API나 API 키가 필요 없습니다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `places.json` | 카테고리별 맛집 목록(이름·대표 메뉴)과 출처 정보. 여기만 고치면 내용이 바뀝니다 |
| `main.py` | 한국 날짜 계산, 카테고리별 맛집 선택, HTML·SVG 룰렛 휠 생성 |
| `index.html` | 로컬에서 생성해 둔 저장본 |
| `.github/workflows/daily_menu.yml` | 실행 조건, Python 실행, Pages 배포 |

같은 날짜에도 카테고리마다 서로 다른 맛집이 나오도록 카테고리 순서를 오프셋으로 사용합니다. (`(날짜 순번 + 카테고리 순번 × 배수) % 목록 길이`)

탭을 누르면 오늘의 확정 맛집으로 휠이 돌아가며, **다시 돌리기** 버튼을 누르면 매번 진짜 랜덤으로 다른 맛집이 뽑힙니다.

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
