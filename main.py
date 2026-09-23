"""외대 맛집 지도 데이터로 오늘의 맛집을 룰렛으로 골라주는 미리보기용 스크립트."""

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
PLACES_FILE = Path(__file__).with_name("places.json")
MEAL_OFFSETS = {"lunch": 0, "dinner": 1}
MEAL_LABELS = {"lunch": "점심", "dinner": "저녁"}


def load_places(filepath=PLACES_FILE):
    with Path(filepath).open(encoding="utf-8") as source:
        data = json.load(source)
    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError("categories는 값이 한 개 이상 있는 배열이어야 합니다.")
    for category in categories:
        items = category.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("각 categories 항목의 items는 값이 한 개 이상 있어야 합니다.")
    return data


def parse_preview_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식으로 입력하세요.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"사용할 수 없는 날짜입니다: {value}") from error


def choose_date(preview_date, generated_at):
    return preview_date if preview_date is not None else generated_at.astimezone(KST).date()


def choose_meal(explicit_meal, generated_at):
    """명시하지 않으면 한국시간 16시를 기준으로 점심/저녁을 자동 판단합니다."""
    if explicit_meal is not None:
        return explicit_meal
    return "lunch" if generated_at.astimezone(KST).hour < 16 else "dinner"


def pick_for_category(data, category_index, target_date, meal):
    day = target_date.toordinal()
    category = data["categories"][category_index]
    items = category["items"]
    offset = category_index * 5 + MEAL_OFFSETS[meal] * 4
    index = (day + offset) % len(items)
    place = items[index]
    return {
        "name": category["name"],
        "place": place["name"],
        "note": place["note"],
        "hours": place.get("hours", ""),
        "address": place.get("address", ""),
        "index": index,
    }


def generate_html(data, target_date, generated_at, meal, is_preview=False, environment=None):
    environment = os.environ if environment is None else environment
    generated_kst = generated_at.astimezone(KST)
    picks = [pick_for_category(data, i, target_date, meal) for i in range(len(data["categories"]))]
    meal_label = MEAL_LABELS[meal]
    mode_label = "날짜 미리보기" if is_preview else f"한국 날짜 기준 · {meal_label}"
    preview_note = '<p class="preview-note">선택한 날짜의 맛집을 확인하는 화면입니다.</p>' if is_preview else ""
    source = data.get("source", {})
    total_places = sum(len(c["items"]) for c in data["categories"])
    run_number = environment.get("GITHUB_RUN_NUMBER", "")
    run_attempt = environment.get("GITHUB_RUN_ATTEMPT", "1")
    commit = environment.get("GITHUB_SHA", "")
    provenance = []
    if run_number:
        provenance.append(f"Actions 실행 #{escape(run_number)} · 시도 {escape(run_attempt)}")
    if commit:
        provenance.append(f"커밋 {escape(commit[:7])}")
    provenance_text = " · ".join(provenance) if provenance else "로컬 생성본"

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
      <p class="place" data-final="{escape(p['place'])}">{escape(p['place'])}</p>
      <p class="note" data-final="{escape(p['note'])}">{escape(p['note'])}</p>
      <div class="meta">
        <span class="meta-row hours">{escape(p['hours'])}</span>
        <span class="meta-row address">{escape(p['address'])}</span>
      </div>
      <button type="button" class="respin" data-target="cat-{i}">다시 돌리기</button>
    </section>'''
        for i, p in enumerate(picks)
    )
    pools_json = json.dumps(
        {p["name"]: data["categories"][i]["items"] for i, p in enumerate(picks)},
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="외대 맛집 지도 데이터로 오늘의 맛집을 고르는 룰렛">
  <title>오늘의 외대 맛집</title>
  <style>
    * {{ box-sizing: border-box; }}
    :root {{
      color-scheme: dark;
      --bg: #14151a;
      --panel: #1b1c22;
      --border: #2a2b33;
      --text: #eceef2;
      --muted: #8b8f9c;
      --accent: #7c9eff;
      --accent-soft: #35406b;
    }}
    body {{ margin: 0; min-height: 100vh; padding: 56px 18px;
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Pretendard", "Malgun Gothic", sans-serif;
      background: var(--bg); color: var(--text); display: flex; justify-content: center; }}
    .container {{ width: 100%; max-width: 460px; text-align: center; }}
    .eyebrow {{ font-size: 11px; font-weight: 700; letter-spacing: .12em; color: var(--accent);
      margin: 0 0 10px; text-transform: uppercase; }}
    h1 {{ font-size: 34px; font-weight: 800; margin: 0 0 12px; letter-spacing: -0.03em; line-height: 1.15; }}
    .subtitle {{ font-size: 13.5px; color: var(--muted); margin: 0 0 20px; line-height: 1.6; }}
    .stat-row {{ display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: 22px; }}
    .stat {{ font-size: 11.5px; color: var(--muted); border: 1px solid var(--border); border-radius: 100px;
      padding: 6px 13px; }}
    .stat strong {{ color: var(--text); }}
    .date-badge {{ display: inline-flex; gap: 10px; align-items: center;
      padding: 7px 16px; border: 1px solid var(--border); border-radius: 100px; color: var(--muted);
      font-size: 12.5px; margin-bottom: 22px; }}
    .date-badge time {{ color: var(--text); }}
    .preview-note {{ margin: -18px 0 20px; color: var(--accent); font-size: 12.5px; }}
    .tabs {{ display: flex; gap: 6px; justify-content: center; margin-bottom: 20px;
      border: 1px solid var(--border); border-radius: 12px; padding: 4px; }}
    .tab {{ flex: 1; font: inherit; font-size: 13.5px; padding: 9px 0; border-radius: 9px;
      border: none; background: transparent; color: var(--muted); cursor: pointer; }}
    .tab[aria-selected="true"] {{ background: var(--accent); color: #0c0d10; font-weight: 600; }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 20px;
      padding: 30px 24px 26px; }}
    .wheel-stage {{ position: relative; width: 208px; height: 208px; margin: 0 auto 24px; }}
    .wheel {{ width: 100%; height: 100%; display: block; }}
    .wheel-slices {{ transform-origin: 150px 150px; }}
    .wheel-slices text {{ fill: #0c0d10; font-size: 13px; font-weight: 600; text-anchor: middle;
      dominant-baseline: middle; }}
    .pointer {{ position: absolute; top: -3px; left: 50%; transform: translateX(-50%);
      width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent;
      border-top: 13px solid var(--text); z-index: 2; }}
    .place {{ font-size: 22px; font-weight: 700; margin: 0 0 6px; word-break: keep-all;
      transition: opacity .2s ease; }}
    .note {{ font-size: 13.5px; color: var(--accent); font-weight: 600; margin: 0 0 14px; transition: opacity .2s ease; }}
    .meta {{ display: flex; flex-direction: column; gap: 4px; margin: 0 0 20px;
      transition: opacity .2s ease; }}
    .meta-row {{ font-size: 12px; color: var(--muted); }}
    .meta-row.hours::before {{ content: "🕐 "; }}
    .meta-row.address::before {{ content: "📍 "; }}
    @keyframes settle {{ 0% {{ transform: scale(1.08); }} 100% {{ transform: scale(1); }} }}
    .panel.landed .place {{ animation: settle .3s ease; }}
    .panel.spinning .place, .panel.spinning .note, .panel.spinning .meta {{ opacity: .2; }}
    .respin {{ font: inherit; font-size: 13px; padding: 9px 20px; border-radius: 100px;
      border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer; }}
    .respin:hover {{ border-color: var(--accent); color: var(--accent); }}
    .respin:disabled {{ opacity: .4; cursor: default; }}
    footer {{ margin-top: 22px; font-size: 11.5px; line-height: 1.8; color: var(--muted); }}
    footer p {{ margin: 2px 0; }}
    footer a {{ color: var(--muted); }}
    footer .provenance {{ color: var(--text); font-weight: 600; }}
    @media (max-width: 480px) {{
      body {{ padding: 40px 14px; }}
      .panel {{ padding: 24px 16px 22px; }}
      .wheel-stage {{ width: 184px; height: 184px; }}
      .wheel-slices text {{ font-size: 11px; }}
      h1 {{ font-size: 27px; }}
      .place {{ font-size: 19px; }}
    }}
  </style>
</head>
<body>
  <main class="container">
    <p class="eyebrow">HUFS Gourmet Roulette</p>
    <h1>{meal_label} 뭐 먹지?</h1>
    <p class="subtitle">외대 정문·후문 상권 실제 맛집 데이터를 점심·저녁 시간대에 맞춰 골라줍니다.</p>
    <div class="stat-row">
      <span class="stat">총 <strong>{total_places}</strong>곳</span>
      <span class="stat"><strong>{len(picks)}</strong>개 카테고리</span>
      <span class="stat">하루 <strong>2번</strong> 자동 갱신</span>
    </div>
    <div class="date-badge"><time id="selected-date" datetime="{target_date.isoformat()}">{target_date.isoformat()}</time><span>{mode_label}</span></div>
    {preview_note}
    <div class="tabs" role="tablist" aria-label="카테고리 선택">
{tabs}
    </div>
{panels}
    <script type="application/json" id="menu-pools">{pools_json}</script>
    <footer>
      <p class="provenance">{provenance_text}</p>
      <p>마지막 생성 {generated_kst.strftime('%Y.%m.%d %H:%M:%S')} KST</p>
      <p>장소 정보 출처: <a href="{escape(source.get('url', ''))}" target="_blank" rel="noopener">{escape(source.get('title', ''))}</a> ({escape(source.get('credit', ''))})</p>
    </footer>
  </main>
  <script>
    var pools = JSON.parse(document.getElementById("menu-pools").textContent);
    var palette = ["#7c9eff", "#5f7fd6", "#93b1ff", "#4a63ad"];
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
        path.setAttribute("stroke", "#14151a");
        path.setAttribute("stroke-width", "1.5");
        group.appendChild(path);
        var mid = start + sliceAngle / 2;
        var lp = slicePoint(cx, cy, labelR, mid);
        var text = document.createElementNS(SVG_NS, "text");
        text.setAttribute("x", lp.x);
        text.setAttribute("y", lp.y);
        var label = items[i].name.length > 5 ? items[i].name.slice(0, 5) + "…" : items[i].name;
        text.textContent = label;
        group.appendChild(text);
      }}
    }}

    function spin(panel, targetIndex) {{
      if (panel.classList.contains("spinning")) return;
      var category = panel.dataset.category;
      var items = pools[category];
      var idx = (typeof targetIndex === "number") ? targetIndex : parseInt(panel.dataset.finalIndex, 10);
      var placeEl = panel.querySelector(".place");
      var noteEl = panel.querySelector(".note");
      var hoursEl = panel.querySelector(".meta .hours");
      var addressEl = panel.querySelector(".meta .address");
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

      setTimeout(function () {{
        placeEl.textContent = items[idx].name;
        noteEl.textContent = items[idx].note;
        hoursEl.textContent = items[idx].hours || "";
        addressEl.textContent = items[idx].address || "";
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
        var items = pools[panel.dataset.category];
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
    parser = argparse.ArgumentParser(description="외대 맛집 지도 데이터로 오늘의 맛집 룰렛을 생성합니다.")
    parser.add_argument("--date", type=parse_preview_date, help="날짜 미리보기: YYYY-MM-DD")
    parser.add_argument("--meal", choices=["lunch", "dinner"], help="비우면 한국시간 기준 자동 판단 (16시 이전=점심)")
    parser.add_argument("--output", default="index.html", type=Path, help="출력 HTML 경로")
    args = parser.parse_args(argv)
    try:
        generated_at = datetime.now(KST)
        target_date = choose_date(args.date, generated_at)
        meal = choose_meal(args.meal, generated_at)
        data = load_places()
        html = generate_html(data, target_date, generated_at, meal, is_preview=args.date is not None)
        atomic_write(args.output, html)
    except (OSError, ValueError) as error:
        print(f"생성 실패: {error}", file=sys.stderr)
        return 1
    print(f"카테고리 {len(data['categories'])}개 · 선택 날짜 {target_date} · {MEAL_LABELS[meal]}")
    print(f"HTML 생성 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
