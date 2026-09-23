"""한국 날짜에 맞는 한중일양식 오늘의 메뉴를 골라 하나의 HTML 파일로 만듭니다. 외부 패키지 불필요."""

import argparse
from datetime import date, datetime
from html import escape
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
MENU_FILE = Path(__file__).with_name("menu.json")


def load_menu(filepath=MENU_FILE):
    """빠지거나 형식이 잘못된 목록은 출력 파일을 만들기 전에 중단합니다."""
    with Path(filepath).open(encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise ValueError("menu.json은 객체여야 합니다.")
    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError("categories는 값이 한 개 이상 있는 배열이어야 합니다.")
    for number, category in enumerate(categories, 1):
        if not isinstance(category, dict):
            raise ValueError(f"{number}번째 categories 항목은 객체여야 합니다.")
        if not isinstance(category.get("name"), str) or not category["name"].strip():
            raise ValueError(f"{number}번째 categories 항목의 name은 비어 있지 않은 문자열이어야 합니다.")
        items = category.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"{number}번째 categories 항목의 items는 값이 한 개 이상 있는 배열이어야 합니다.")
    comments = data.get("comments")
    if not isinstance(comments, list) or not comments:
        raise ValueError("comments는 값이 한 개 이상 있는 배열이어야 합니다.")
    return data


def parse_preview_date(value):
    """입력은 정확히 YYYY-MM-DD 형식으로 받고 존재하는 날짜인지 확인합니다."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식으로 입력하세요.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"사용할 수 없는 날짜입니다: {value}") from error


def choose_date(preview_date, generated_at):
    """생성 시각이 UTC여도 날짜 선택은 한국시간으로 합니다."""
    return preview_date if preview_date is not None else generated_at.astimezone(KST).date()


def pick_for_category(data, category_index, target_date):
    """카테고리마다 다른 오프셋으로 같은 날짜에도 서로 다른 메뉴가 나오게 합니다."""
    day = target_date.toordinal()
    category = data["categories"][category_index]
    items, comments = category["items"], data["comments"]
    index = (day + category_index * 5) % len(items)
    dish = items[index]
    comment = comments[(day + category_index * 7) % len(comments)]
    return {"name": category["name"], "dish": dish, "comment": comment, "index": index}


def generate_html(data, target_date, generated_at, is_preview=False, environment=None):
    """사용자가 편집한 메뉴 데이터를 HTML 이스케이프하여 화면을 만듭니다."""
    environment = os.environ if environment is None else environment
    generated_kst = generated_at.astimezone(KST)
    picks = [pick_for_category(data, i, target_date) for i in range(len(data["categories"]))]
    accent_colors = ["#a78bfa", "#7dd3fc", "#a5b4fc", "#6ee7b7", "#f9a8d4", "#fcd34d", "#fdba74"]
    accent = accent_colors[target_date.toordinal() % len(accent_colors)]
    mode_label = "날짜 미리보기" if is_preview else "한국 날짜 기준"
    run_number = environment.get("GITHUB_RUN_NUMBER", "")
    run_attempt = environment.get("GITHUB_RUN_ATTEMPT", "1")
    commit = environment.get("GITHUB_SHA", "")
    provenance = []
    if run_number:
        provenance.append(f"Actions 실행 #{escape(run_number)} · 시도 {escape(run_attempt)}")
    if commit:
        provenance.append(f"커밋 {escape(commit[:7])}")
    provenance_text = " · ".join(provenance) if provenance else "로컬 생성본"
    preview_note = '<p class="preview-note">선택한 날짜의 메뉴를 확인하는 화면입니다.</p>' if is_preview else ""

    tabs = "\n".join(
        f'<button class="tab" data-target="cat-{i}" aria-selected="{"true" if i == 0 else "false"}">{escape(p["name"])}</button>'
        for i, p in enumerate(picks)
    )
    panels = "\n".join(
        f'''<section class="panel" id="cat-{i}" data-category="{escape(p['name'])}" data-final-index="{p['index']}" role="tabpanel" {"" if i == 0 else "hidden"}>
      <div class="wheel-stage">
        <div class="pointer" aria-hidden="true"></div>
        <svg class="wheel" viewBox="0 0 300 300" aria-hidden="true"><g class="wheel-slices"></g></svg>
      </div>
      <p class="dish" data-final="{escape(p['dish'])}">{escape(p['dish'])}</p>
      <p class="comment">{escape(p['comment'])}</p>
      <button type="button" class="respin" data-target="cat-{i}">🎡 다시 돌리기</button>
    </section>'''
        for i, p in enumerate(picks)
    )
    pools_json = json.dumps(
        {
            "categories": {p["name"]: data["categories"][i]["items"] for i, p in enumerate(picks)},
            "comments": data["comments"],
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="한중일양식 중 골라 보는 오늘의 메뉴 추천">
  <title>오늘의 메뉴 추천</title>
  <style>
    * {{ box-sizing: border-box; }}
    :root {{ color-scheme: dark; --accent: {accent}; }}
    body {{ margin: 0; min-height: 100vh; padding: 42px 18px 30px;
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
      background: linear-gradient(135deg, #0f0c29, #302b63, #182235); color: #f1f5f9;
      display: flex; justify-content: center; }}
    .container {{ width: 100%; max-width: 640px; text-align: center; }}
    .eyebrow {{ font-size: 11px; letter-spacing: 3px; color: var(--accent); margin: 0 0 12px; }}
    h1 {{ font-size: 27px; font-weight: 650; margin: 0 0 20px; letter-spacing: -1px; }}
    .date-badge {{ display: inline-flex; gap: 13px; align-items: center; flex-wrap: wrap; justify-content: center;
      padding: 9px 20px; border: 1px solid #ffffff26; border-radius: 30px; color: #cbd5e1;
      background: #ffffff08; font-size: 13px; margin-bottom: 22px; }}
    .mode {{ color: var(--accent); font-size: 12px; }}
    .preview-note {{ margin: -8px 0 20px; color: #d8b4fe; font-size: 13px; }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 22px; }}
    .tab {{ font: inherit; font-size: 14px; padding: 10px 22px; border-radius: 20px;
      border: 1px solid #ffffff26; background: #ffffff08; color: #f1f5f9; cursor: pointer; }}
    .tab[aria-selected="true"] {{ background: var(--accent); color: #14121f; border-color: var(--accent); font-weight: 600; }}
    .panel {{ background: #ffffff07; border: 1px solid #ffffff1c; border-radius: 24px;
      padding: 34px 30px 30px; margin-bottom: 20px; box-shadow: 0 18px 45px #00000018; }}
    .wheel-stage {{ position: relative; width: 220px; height: 220px; margin: 0 auto 22px; }}
    .wheel {{ width: 100%; height: 100%; display: block; }}
    .wheel-slices {{ transform-origin: 150px 150px; }}
    .wheel-slices text {{ fill: #14121f; font-size: 15px; font-weight: 600; text-anchor: middle;
      dominant-baseline: middle; }}
    .pointer {{ position: absolute; top: -4px; left: 50%; transform: translateX(-50%);
      width: 0; height: 0; border-left: 10px solid transparent; border-right: 10px solid transparent;
      border-top: 16px solid var(--accent); z-index: 2; filter: drop-shadow(0 2px 3px #00000040); }}
    .dish {{ font-size: 27px; font-weight: 700; margin: 0 0 14px; word-break: keep-all; transition: opacity .2s ease; }}
    @keyframes pop {{ 0% {{ transform: scale(1.18); }} 100% {{ transform: scale(1); }} }}
    .panel.landed .dish {{ animation: pop .35s ease; }}
    .comment {{ font-size: 15px; color: #cbd5e1; margin: 0 0 18px; line-height: 1.6; word-break: keep-all;
      transition: opacity .2s ease; }}
    .panel.spinning .dish, .panel.spinning .comment {{ opacity: .15; }}
    .respin {{ font: inherit; font-size: 13px; padding: 9px 18px; border-radius: 20px;
      border: 1px solid #ffffff26; background: #ffffff08; color: #f1f5f9; cursor: pointer; }}
    .respin:hover {{ border-color: var(--accent); }}
    .respin:disabled {{ opacity: .5; cursor: default; }}
    footer {{ font-size: 11px; line-height: 1.9; color: #a8b4c8; }}
    footer p {{ margin: 3px 0; }}
    .generated {{ color: #d3dbea; }}
    @media (max-width: 600px) {{
      body {{ padding: 30px 14px 24px; }} h1 {{ font-size: 23px; }}
      .panel {{ padding: 28px 18px 26px; }} .dish {{ font-size: 22px; }}
      .wheel-stage {{ width: 190px; height: 190px; }}
      .wheel-slices text {{ font-size: 12px; }}
    }}
  </style>
</head>
<body>
  <main class="container">
    <p class="eyebrow">TODAY'S MENU PICK</p>
    <h1>오늘의 메뉴 추천</h1>
    <div class="date-badge"><time id="selected-date" datetime="{target_date.isoformat()}">{target_date.isoformat()}</time><span class="mode">{mode_label}</span></div>
    {preview_note}
    <div class="tabs" role="tablist" aria-label="카테고리 선택">
{tabs}
    </div>
{panels}
    <script type="application/json" id="menu-pools">{pools_json}</script>
    <footer>
      <p class="generated">마지막 생성 <time id="generated-at" datetime="{generated_kst.isoformat(timespec='seconds')}">{generated_kst.strftime('%Y.%m.%d %H:%M:%S')} KST</time></p>
      <p id="build-info">{provenance_text}</p>
      <p>한중일양식, 매일 자동으로 갱신되는 수업 예제</p>
    </footer>
  </main>
  <script>
    var pools = JSON.parse(document.getElementById("menu-pools").textContent);
    var palette = ["#a78bfa", "#7dd3fc", "#a5b4fc", "#6ee7b7", "#f9a8d4", "#fcd34d",
      "#fdba74", "#f87171", "#38bdf8", "#34d399", "#facc15", "#fb7185"];
    var SVG_NS = "http://www.w3.org/2000/svg";

    function slicePoint(cx, cy, r, deg) {{
      var rad = (deg - 90) * Math.PI / 180;
      return {{ x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }};
    }}

    function buildWheel(panel, items) {{
      var group = panel.querySelector(".wheel-slices");
      group.innerHTML = "";
      var n = items.length;
      var sliceAngle = 360 / n;
      var cx = 150, cy = 150, r = 148, labelR = 100;
      for (var i = 0; i < n; i++) {{
        var start = i * sliceAngle;
        var end = start + sliceAngle;
        var p1 = slicePoint(cx, cy, r, start);
        var p2 = slicePoint(cx, cy, r, end);
        var largeArc = sliceAngle > 180 ? 1 : 0;
        var path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("d", "M" + cx + "," + cy + " L" + p1.x + "," + p1.y +
          " A" + r + "," + r + " 0 " + largeArc + ",1 " + p2.x + "," + p2.y + " Z");
        path.setAttribute("fill", palette[i % palette.length]);
        path.setAttribute("stroke", "#0f0c29");
        path.setAttribute("stroke-width", "1.5");
        group.appendChild(path);
        var mid = start + sliceAngle / 2;
        var lp = slicePoint(cx, cy, labelR, mid);
        var text = document.createElementNS(SVG_NS, "text");
        text.setAttribute("x", lp.x);
        text.setAttribute("y", lp.y);
        var label = items[i].length > 5 ? items[i].slice(0, 5) + "…" : items[i];
        text.textContent = label;
        group.appendChild(text);
      }}
    }}

    function spin(panel, targetIndex) {{
      if (panel.classList.contains("spinning")) return;
      var category = panel.dataset.category;
      var items = pools.categories[category];
      var idx = (typeof targetIndex === "number") ? targetIndex : parseInt(panel.dataset.finalIndex, 10);
      var dishEl = panel.querySelector(".dish");
      var commentEl = panel.querySelector(".comment");
      var button = panel.querySelector(".respin");
      var group = panel.querySelector(".wheel-slices");

      if (!panel.dataset.built) {{
        buildWheel(panel, items);
        panel.dataset.built = "1";
      }}

      var sliceAngle = 360 / items.length;
      var mid = idx * sliceAngle + sliceAngle / 2;
      var current = parseFloat(group.dataset.rotation || "0");
      var spins = 4 + Math.floor(Math.random() * 2);
      var base = current + spins * 360;
      var targetMod = (360 - mid) % 360;
      var diff = ((targetMod - base) % 360 + 360) % 360;
      var next = base + diff;

      panel.classList.remove("landed");
      panel.classList.add("spinning");
      if (button) button.disabled = true;

      group.style.transition = "transform 3.1s cubic-bezier(.15,.65,.25,1)";
      group.style.transform = "rotate(" + next + "deg)";
      group.dataset.rotation = String(next);

      var isManualReroll = typeof targetIndex === "number";
      setTimeout(function () {{
        dishEl.textContent = items[idx];
        if (isManualReroll) {{
          commentEl.textContent = pools.comments[Math.floor(Math.random() * pools.comments.length)];
        }}
        panel.classList.remove("spinning");
        panel.classList.add("landed");
        if (button) button.disabled = false;
      }}, 3150);
    }}

    document.querySelectorAll(".tab").forEach(function (tab) {{
      tab.addEventListener("click", function () {{
        document.querySelectorAll(".tab").forEach(function (t) {{ t.setAttribute("aria-selected", "false"); }});
        document.querySelectorAll(".panel").forEach(function (p) {{ p.hidden = true; }});
        tab.setAttribute("aria-selected", "true");
        var panel = document.getElementById(tab.dataset.target);
        panel.hidden = false;
        spin(panel);
      }});
    }});

    document.querySelectorAll(".respin").forEach(function (button) {{
      button.addEventListener("click", function () {{
        var panel = document.getElementById(button.dataset.target);
        var items = pools.categories[panel.dataset.category];
        var randomIndex = Math.floor(Math.random() * items.length);
        spin(panel, randomIndex);
      }});
    }});

    var firstPanel = document.querySelector(".panel:not([hidden])");
    if (firstPanel) spin(firstPanel);
  </script>
</body>
</html>
'''


def atomic_write(output, content):
    """같은 폴더에 임시 파일을 완성한 뒤 교체하여 기존 HTML의 손상을 막습니다."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="한국 날짜에 맞는 오늘의 메뉴 추천을 생성합니다.")
    parser.add_argument("--date", type=parse_preview_date, help="날짜 미리보기: YYYY-MM-DD")
    parser.add_argument("--output", default="index.html", type=Path, help="출력 HTML 경로")
    args = parser.parse_args(argv)
    try:
        generated_at = datetime.now(KST)
        target_date = choose_date(args.date, generated_at)
        data = load_menu()
        html = generate_html(data, target_date, generated_at, is_preview=args.date is not None)
        atomic_write(args.output, html)
    except (OSError, ValueError) as error:
        print(f"생성 실패: {error}", file=sys.stderr)
        return 1
    print(f"카테고리 {len(data['categories'])}개 · 선택 날짜 {target_date} · {'날짜 미리보기' if args.date else '한국 날짜 기준'}")
    print(f"마지막 생성: {generated_at.strftime('%Y.%m.%d %H:%M:%S')} KST")
    print(f"HTML 생성 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
