#!/usr/bin/env python3
"""host-strategist（房东军师）· 90 天价格计划：节假日、活动、空档、临近入住、最少入住晚数。  (c) 2026 Ryan Yan

用法：
  python3 rate_plan.py --example > pricing.json      # 每套房的定价规则示例，复制后修改（保存下来反复使用）
  python3 rate_plan.py pricing.json [--calendar PREFIX_calendar.json] [--events events.csv]
        [--current current.csv] [--as-of YYYY-MM-DD] [--days 90] [--out PREFIX] [--lang zh|en]

--calendar : calendar_check.py 的输出（已订 / 封锁的晚数跳过，空档用空档价）
--events   : events.csv  start,end,name,uplift_pct,min_stay,source,verified_on（本地活动 — 每个日期都要核实）
--current  : Airbnb 现在的价格：date,price[,min_stay] → 只打印需要修改的晚数
美国联邦节假日由脚本自动计算（不需要上网）。节假日加价是默认规则 — 在 pricing.json 里修改。
写出 PREFIX_rates.csv（日期、星期、状态、基础价、建议价、最少入住晚数、原因）。默认输出中文。使用时不要读这个文件，直接运行。
"""
import json, sys, csv, argparse, datetime as dt, calendar

EXAMPLE = {
  "_note": "EXAMPLE 示例 — 按竞品 / 自己的数据设置；每套房保存一份，每周重复使用",
  "property": "WIL01", "base_weekday": 220, "base_weekend": 260, "weekend_days": ["Fri", "Sat"],
  "floor": 160, "ceiling": 600,
  "season": {"1": 0.85, "2": 0.88, "3": 0.95, "4": 1.0, "5": 1.02, "6": 1.10, "7": 1.12, "8": 1.10, "9": 1.0, "10": 1.0, "11": 0.95, "12": 0.92},
  "last_minute": {"days": 7, "pct": -12},
  "far_out": {"days": 90, "pct": 5},
  "gap": {"pct": -10, "min_stay": 1},
  "min_stay": {"weekday": 2, "weekend": 2, "within_7_days": 1},
  "holidays": {"long_weekend_pct": 15, "thanksgiving_pct": 25, "christmas_pct": 20, "new_years_eve_pct": 40, "july4_pct": 20, "holiday_min_stay": 3},
  "round_to": 1
}

def pdate(s):
    """Parse YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, 'Oct 5, 2026'; return None if not a date."""
    s = (s or "").strip()
    for f in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%Y/%m/%d"):
        try: return dt.datetime.strptime(s, f).date()
        except ValueError: pass
    return None

def nth_weekday(y, m, wd, n):  # wd: Mon=0
    d = dt.date(y, m, 1); d += dt.timedelta((wd - d.weekday()) % 7); return d + dt.timedelta(7 * (n - 1))
def last_weekday(y, m, wd):
    d = dt.date(y, m, calendar.monthrange(y, m)[1]); return d - dt.timedelta((d.weekday() - wd) % 7)

def us_holidays(y, H):
    """Return {date: (name, pct, min_stay)} for nights around US federal holidays (default rules)."""
    out, lw, ms = {}, H.get("long_weekend_pct", 15), H.get("holiday_min_stay", 3)
    def span(start, n, name, pct, mstay=ms):
        for k in range(n): out[start + dt.timedelta(k)] = (name, pct, mstay)
    for name, mon in [("MLK Day weekend", nth_weekday(y, 1, 0, 3)), ("Presidents' Day weekend", nth_weekday(y, 2, 0, 3)),
                      ("Memorial Day weekend", last_weekday(y, 5, 0)), ("Labor Day weekend", nth_weekday(y, 9, 0, 1))]:
        span(mon - dt.timedelta(3), 3, name, lw, 2)              # Fri, Sat, Sun nights
    tg = nth_weekday(y, 11, 3, 4); span(tg - dt.timedelta(1), 4, "Thanksgiving", H.get("thanksgiving_pct", 25))
    span(dt.date(y, 12, 23), 4, "Christmas", H.get("christmas_pct", 20))
    span(dt.date(y, 12, 30), 2, "New Year's Eve", H.get("new_years_eve_pct", 40))
    j4 = dt.date(y, 7, 4); span(j4 - dt.timedelta(1), 2, "Independence Day", H.get("july4_pct", 20), 2)
    return out

WZH = {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四", "Fri": "周五", "Sat": "周六", "Sun": "周日"}
RZH = {"BASE": "基础价", "DOW": "周末", "SEASON": "季节", "HOLIDAY": "节假日", "EVENT": "活动", "LASTMIN": "临近入住",
       "FAROUT": "远期", "GAP": "空档", "FLOOR": "最低价", "CEILING": "最高价"}
HZH = {"MLK Day weekend": "马丁·路德·金纪念日长周末", "Presidents' Day weekend": "总统日长周末", "Memorial Day weekend": "阵亡将士纪念日长周末",
       "Labor Day weekend": "劳动节长周末", "Thanksgiving": "感恩节", "Christmas": "圣诞节", "New Year's Eve": "跨年夜", "Independence Day": "独立日"}

def main():
    if len(sys.argv) < 2: print(__doc__); return
    if len(sys.argv) > 1 and sys.argv[1] == "--example": print(json.dumps(EXAMPLE, indent=2, ensure_ascii=False)); return
    ap = argparse.ArgumentParser(); ap.add_argument("config"); ap.add_argument("--calendar"); ap.add_argument("--events")
    ap.add_argument("--current"); ap.add_argument("--as-of"); ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--out", default="rates"); ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    a = ap.parse_args(); C = json.load(open(a.config, encoding="utf-8-sig")); zh = a.lang == "zh"; T = (lambda z, e: z if zh else e)
    for k in ("base_weekday", "base_weekend", "floor"):
        if k not in C: raise SystemExit(f"ERROR: pricing.json 缺少 {k}")
    today = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    nights, gaps = {}, set()
    if a.calendar:
        cj = json.load(open(a.calendar, encoding="utf-8-sig"))
        nights = {dt.date.fromisoformat(k): v for k, v in cj.get("nights", {}).items()}
        for g in cj.get("gaps", []):
            d = dt.date.fromisoformat(g["start"])
            while d < dt.date.fromisoformat(g["end"]): gaps.add(d); d += dt.timedelta(1)
    hol = {}
    for y in {today.year, (today + dt.timedelta(a.days)).year}: hol.update(us_holidays(y, C.get("holidays", {})))
    ev = {}
    if a.events:
        with open(a.events, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                s, e = pdate(r.get("start")), pdate(r.get("end"))
                if not s or not e: print(T(f"（跳过 events.csv 中日期无法识别的一行：{r.get('name','')}）", f"(skipped an events.csv row with unreadable dates: {r.get('name','')})")); continue
                d = s
                while d <= e:
                    ev[d] = (r["name"], float(r.get("uplift_pct") or 0), int(r["min_stay"]) if r.get("min_stay") else None, r.get("verified_on", ""))
                    d += dt.timedelta(1)
    cur = {}
    if a.current:
        with open(a.current, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                d0 = pdate(r.get("date"))
                if not d0: continue
                cur[d0] = (float(str(r["price"]).replace("$", "").replace(",", "")), int(r["min_stay"]) if r.get("min_stay") else None)
    wk = set(C.get("weekend_days", ["Fri", "Sat"])); MS = C.get("min_stay", {}); rnd = C.get("round_to", 1)
    rows = []
    for k in range(a.days):
        d = today + dt.timedelta(k); dow = d.strftime("%a"); st = nights.get(d, "open")
        we = dow in wk; base = C["base_weekend"] if we else C["base_weekday"]
        p = base * float(C.get("season", {}).get(str(d.month), 1.0)); why = ["BASE"] + (["DOW"] if we else []) + (["SEASON"] if C.get("season", {}).get(str(d.month), 1.0) != 1.0 else [])
        ms = MS.get("weekend" if we else "weekday", 2); label = ""
        if d in hol: n, pc, m2 = hol[d]; p *= 1 + pc / 100; ms = max(ms, m2); why.append("HOLIDAY"); label = n
        if d in ev:
            n, pc, m2, vo = ev[d]; p *= 1 + pc / 100; why.append("EVENT"); label = (label + " + " if label else "") + n
            if m2: ms = max(ms, m2)
        lead = (d - today).days
        if lead < C.get("last_minute", {}).get("days", 7) and "HOLIDAY" not in why and "EVENT" not in why:
            p *= 1 + C["last_minute"].get("pct", -12) / 100; ms = min(ms, MS.get("within_7_days", 1)); why.append("LASTMIN")
        if lead >= C.get("far_out", {}).get("days", 9999): p *= 1 + C["far_out"].get("pct", 0) / 100; why.append("FAROUT")
        if d in gaps and "HOLIDAY" not in why and "EVENT" not in why:
            p *= 1 + C.get("gap", {}).get("pct", -10) / 100; ms = min(ms, C.get("gap", {}).get("min_stay", 1)); why.append("GAP")
        if p < C["floor"]: p = C["floor"]; why.append("FLOOR")
        if C.get("ceiling") and p > C["ceiling"]: p = C["ceiling"]; why.append("CEILING")
        p = round(p / rnd) * rnd
        rows.append(dict(date=d, day=dow, status=st, base=base, price=p, min_stay=ms, reasons=" ".join(why), label=label))
    with open(f"{a.out}_rates.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["date", "day", "status", "base", "recommended_price", "min_stay", "reasons", "holiday_or_event"])
        for r in rows: w.writerow([r["date"], r["day"], r["status"], r["base"], "" if r["status"] != "open" else r["price"], "" if r["status"] != "open" else r["min_stay"], r["reasons"], r["label"]])
    op = [r for r in rows if r["status"] == "open"]
    dd = (lambda d: f"{WZH[d.strftime('%a')]} {d:%m/%d}") if zh else (lambda d: f"{d:%a %m/%d}")
    rs = (lambda x: " ".join(RZH.get(w, w) for w in x.split())) if zh else (lambda x: x)
    lb = (lambda x: " + ".join(HZH.get(w, w) for w in x.split(" + ")) if x else "") if zh else (lambda x: x)
    print(f"## {T('90 天价格计划', 'Price plan')} — {C.get('property','')} · {T('截至', 'as of')} {today}\n")
    print(f"{T('可订晚数', 'Open nights')}: {len(op)} / {len(rows)} · {T('平均建议价', 'Avg recommended')}: ${sum(r['price'] for r in op)/len(op):,.0f}" if op else T("没有可订晚数", "No open nights"))
    att = [r for r in op if any(x in r["reasons"] for x in ("HOLIDAY", "EVENT", "GAP", "FLOOR", "CEILING"))]
    if att:
        print("\n" + T("### 需要注意的日期", "### Nights that need attention") + "\n\n| " + T("日期 | 价格 | 最少晚数 | 原因 | 节日/活动", "Date | Price | Min stay | Reasons | Holiday/event") + " |\n|---|---:|---:|---|---|")
        for r in att[:40]: print(f"| {dd(r['date'])} | ${r['price']:,.0f} | {r['min_stay']} | {rs(r['reasons'])} | {lb(r['label'])} |")
    if cur:
        ch = []
        for r in op:
            c = cur.get(r["date"])
            if c and (abs(c[0] - r["price"]) / c[0] > 0.05 or (c[1] and c[1] != r["min_stay"])): ch.append((r, c))
        print("\n" + T(f"### 需要在 Airbnb 修改的晚数（{len(ch)}）", f"### Nights to change in Airbnb ({len(ch)})") + "\n\n| " + T("日期 | 现价 → 建议 | 最少晚数 | 原因", "Date | Now → New | Min stay | Reasons") + " |\n|---|---|---|---|")
        for r, c in ch[:60]: print(f"| {dd(r['date'])} | ${c[0]:,.0f} → ${r['price']:,.0f} | {(str(c[1]) + ' → ') if c[1] and c[1] != r['min_stay'] else ''}{r['min_stay']} | {rs(r['reasons'])} |")
    if not a.calendar: print("\n" + T("注：没有提供 --calendar — 已订晚数没有排除，所有晚数都按可订计算。", "Note: no --calendar — booked nights were not excluded; every night is treated as open."))
    if not a.events: print("\n" + T("注：没有提供本地活动表（events.csv）— 只计算了美国法定节假日。", "Note: no events.csv — only US federal holidays applied."))
    print(T(f"\n（文件：{a.out}_rates.csv）", f"\n(file: {a.out}_rates.csv)"))

if __name__ == "__main__":
    main()
