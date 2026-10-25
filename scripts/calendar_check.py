#!/usr/bin/env python3
"""host-strategist（房东军师）· 日历检查：重复订单、空档、换房清洁、未来入住率。  (c) 2026 Ryan Yan

用法：
  python3 calendar_check.py FILE [FILE ...] [--property "Name"] [--as-of YYYY-MM-DD] [--horizon 90]
        [--min-stay 2] [--occ-target 60] [--checkout 11:00] [--checkin 16:00] [--out PREFIX] [--lang zh|en]

FILE 可以是：
  * 从 Airbnb / VRBO / Booking.com 导出的 iCal 日历文件（.ics，每个渠道或房源一个）
  * Airbnb 订单 CSV（Reservations > Export：Confirmation code, Status, Guest name, Start date, End date, # of nights, Listing ...）
打印 Markdown 摘要，包含警告（一定显示）和提示（可选），并写出：
  PREFIX_calendar.json（订单、空档、换房清洁、信号 — 给 rate_plan.py 用）
  PREFIX_board.json 和 PREFIX_dashboard.json（给 render.py：清洁排班表、每周看板）
默认输出中文；--lang en 输出英文。使用时不要读这个文件，直接运行。
"""
import sys, argparse, csv, json, re, datetime as dt, os

def pdate(s):
    s = (s or "").strip()
    for f in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%b %d, %Y"):
        try: return dt.datetime.strptime(s, f).date()
        except ValueError: pass
    try: return dt.datetime.strptime(s[:8], "%Y%m%d").date()
    except ValueError: return None

def read_ics(path):
    txt = open(path, encoding="utf-8", errors="ignore").read().replace("\r\n ", "").replace("\n ", "")
    out, src = [], os.path.basename(path)
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", txt, re.S):
        get = lambda k: (re.search(rf"^{k}[^:\n]*:(.*)$", ev, re.M) or [None, ""])[1].strip()
        s, e = pdate(get("DTSTART")), pdate(get("DTEND"))
        if not s or not e: continue
        summ = get("SUMMARY"); desc = get("DESCRIPTION")
        blocked = bool(re.search(r"not available|blocked|unavailable|closed", summ, re.I))
        code = (re.search(r"/details/([A-Z0-9]+)", desc) or re.search(r"\b(HM[A-Z0-9]{6,})\b", desc + " " + summ) or [None, ""])[1]
        out.append(dict(start=s, end=e, kind="block" if blocked else "booking", code=code or get("UID")[:12], guest="", source=src, listing=""))
    return out

ALIAS = {"code": ["confirmation code", "reservation id", "confirmation_code"], "status": ["status"], "guest": ["guest name", "guest"],
         "start": ["start date", "check-in", "check in", "start_date"], "end": ["end date", "check-out", "checkout", "end_date"],
         "nights": ["# of nights", "nights"], "listing": ["listing", "listing name"], "adults": ["# of adults", "adults"],
         "children": ["# of children", "children"], "earnings": ["earnings", "payout", "amount"]}

def read_csv(path):
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f); head = [h.strip().lower() for h in next(r)]
        idx = {k: next((i for i, h in enumerate(head) if h in v), None) for k, v in ALIAS.items()}
        if idx["start"] is None or (idx["end"] is None and idx["nights"] is None):
            raise SystemExit(f"ERROR: {path}：需要 Start date 和 End date（或 # of nights）列。找到的列：{head}")
        for row in r:
            g = lambda k: row[idx[k]].strip() if idx[k] is not None and idx[k] < len(row) else ""
            s = pdate(g("start")); e = pdate(g("end"))
            if s and not e and g("nights"): e = s + dt.timedelta(int(float(g("nights"))))
            if not s or not e: continue
            st = g("status").lower()
            if "cancel" in st or "declin" in st or "expired" in st: continue
            out.append(dict(start=s, end=e, kind="booking", code=g("code"), guest=g("guest"), source=os.path.basename(path),
                            listing=g("listing"), guests=sum(int(x) for x in (g("adults") or "0", g("children") or "0") if x.isdigit()) or None))
    return out

def main():
    if len(sys.argv) < 2: print(__doc__); return
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+"); ap.add_argument("--property", default="")
    ap.add_argument("--as-of"); ap.add_argument("--horizon", type=int, default=90)
    ap.add_argument("--min-stay", type=int, default=2); ap.add_argument("--occ-target", type=float, default=60)
    ap.add_argument("--checkout", default="11:00"); ap.add_argument("--checkin", default="16:00")
    ap.add_argument("--out", default="cal"); ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    end_h = today + dt.timedelta(a.horizon)
    ev = []
    for p in a.files:
        ev += read_ics(p) if p.lower().endswith((".ics", ".ical")) else read_csv(p)
    if a.property:
        ev = [e for e in ev if not e["listing"] or a.property.lower() in e["listing"].lower()]
    listings = sorted({e["listing"] for e in ev if e["listing"]})
    warns, prompts = [], []
    zh = a.lang == "zh"
    T = (lambda z, e: z if zh else e)
    if not a.property: a.property = listings[0] if len(listings) == 1 else T("房源", "Property")
    if len(listings) > 1: warns.append(T(f"文件里有多个房源（{', '.join(listings)}）— 请用 --property 每套房单独检查", f"several listings in the files ({', '.join(listings)}) — run once per property with --property"))
    ev = [e for e in ev if e["end"] > today - dt.timedelta(1) and e["start"] < end_h]
    ev.sort(key=lambda e: (e["start"], e["end"]))
    # de-duplicate the same booking seen in two exports (same dates + same code, or same dates from CSV + ics)
    uniq = []
    for e in ev:
        dup = next((u for u in uniq if u["start"] == e["start"] and u["end"] == e["end"] and u["kind"] == e["kind"] and
                    (u["code"] == e["code"] or u["source"] != e["source"] and (not u["code"] or not e["code"] or u["source"].endswith(".csv") != e["source"].endswith(".csv")))), None)
        if dup:
            if not dup["guest"] and e["guest"]: dup["guest"] = e["guest"]
            continue
        uniq.append(e)
    bookings = [e for e in uniq if e["kind"] == "booking"]; blocks = [e for e in uniq if e["kind"] == "block"]
    # overlaps / double bookings
    for i, x in enumerate(bookings):
        for y in bookings[i + 1:]:
            if y["start"] < x["end"] and x["start"] < y["end"]:
                warns.append(T(f"⚠️ 重叠/可能重复预订：{x['code'] or x['source']} ({x['start']}–{x['end']}) 与 {y['code'] or y['source']} ({y['start']}–{y['end']})",
                               f"⚠️ OVERLAP / possible double booking: {x['code'] or x['source']} ({x['start']}–{x['end']}) and {y['code'] or y['source']} ({y['start']}–{y['end']})")
                             + (T(" — 来自不同平台，立即处理", " — different channels, act now") if x["source"] != y["source"] else ""))
    # night map
    night = {}
    for b in blocks:
        d = b["start"]
        while d < b["end"]: night.setdefault(d, "block"); d += dt.timedelta(1)
    for b in bookings:
        d = b["start"]
        while d < b["end"]: night[d] = "booked"; d += dt.timedelta(1)
    def occ(days):
        rng = [today + dt.timedelta(k) for k in range(days)]
        avail = [d for d in rng if night.get(d) != "block"]
        return (sum(1 for d in avail if night.get(d) == "booked") / len(avail)) if avail else 0, len(avail)
    o30, o60, o90 = occ(30)[0], occ(60)[0], occ(90)[0]
    # gaps (open runs between two bookings)
    gaps, d = [], today
    while d < end_h:
        if night.get(d) is None:
            s = d
            while d < end_h and night.get(d) is None: d += dt.timedelta(1)
            before, after = night.get(s - dt.timedelta(1)) == "booked", night.get(d) == "booked"
            n = (d - s).days
            if before and after and n <= max(2, a.min_stay):
                gaps.append(dict(start=s, end=d, nights=n, within14=(s - today).days < 14, shorter_than_min=n < a.min_stay))
        else: d += dt.timedelta(1)
    # turnovers
    turns = []
    for b in bookings:
        if not (today <= b["end"] < end_h): continue
        nxt = next((x for x in bookings if x["start"] == b["end"]), None)
        turns.append(dict(date=b["end"], out=b["code"] or b["guest"], next=(nxt["code"] or nxt["guest"]) if nxt else "", same_day=bool(nxt)))
    for b in bookings:  # arrivals after a vacant night still need readiness
        if today <= b["start"] < end_h and not any(t["date"] == b["start"] for t in turns):
            turns.append(dict(date=b["start"], out="", next=b["code"] or b["guest"], same_day=False, arrival_only=True))
    turns.sort(key=lambda t: t["date"])
    h = lambda t: int(t.split(":")[0]) + int(t.split(":")[1]) / 60
    window = h(a.checkin) - h(a.checkout)
    # signals
    soon_gaps = [g for g in gaps if g["within14"]]
    if soon_gaps:
        gl = ", ".join(g["start"].strftime("%m/%d") + " " + str(g["nights"]) + T("晚", "n") for g in soon_gaps)
        prompts.append(T(f"未来 14 天有 {len(soon_gaps)} 个空档（{gl}）— 要不要做填空档定价 / 改最少入住晚数？", f"{len(soon_gaps)} gap(s) in the next 14 days ({gl}) — run gap pricing / adjust min stay?"))
    if o30 * 100 < a.occ_target: prompts.append(T(f"未来 30 天入住率 {o30*100:.0f}%，低于目标 {a.occ_target:.0f}% — 要不要做一次定价检查？", f"Next-30-day occupancy {o30*100:.0f}% is below the {a.occ_target:.0f}% target — run a pricing check?"))
    sd = [t for t in turns if t.get("same_day") and (t["date"] - today).days < 7]
    if sd and window < 4: warns.append(T(f"⚠️ 7 天内有 {len(sd)} 次同日换房，清洁时间只有 {window:g} 小时", f"⚠️ {len(sd)} same-day turnover(s) in 7 days with only a {window:g}-hour cleaning window"))
    # print
    WZH = {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四", "Fri": "周五", "Sat": "周六", "Sun": "周日"}
    dd = (lambda d: f"{WZH[d.strftime('%a')]} {d:%m/%d}") if zh else (lambda d: f"{d:%a %m/%d}")
    print(f"## {T('日历检查', 'Calendar check')} — {a.property} · {T('截至', 'as of')} {today}\n")
    if warns: print(T("**警告**", "**Warnings**") + "\n" + "\n".join(f"- {w}" for w in warns) + "\n")
    print(f"| {T('未来','Next')} | 30 {T('天','days')} | 60 {T('天','days')} | 90 {T('天','days')} |\n|---|---:|---:|---:|\n| {T('入住率','Occupancy')} | {o30*100:.0f}% | {o60*100:.0f}% | {o90*100:.0f}% |\n")
    print(f"{T('预订','Bookings')}: {len(bookings)} · {T('封锁','Blocks')}: {len(blocks)} · {T('来源','Sources')}: {', '.join(sorted({e['source'] for e in uniq})) or '-'}\n")
    if gaps:
        print(T("### 空档（夹在两个订单之间）", "### Gaps between bookings") + "\n\n| " + T("日期 | 晚数 | 14天内 | 短于最少入住", "Dates | Nights | Within 14d | Below min stay") + " |\n|---|---:|---|---|")
        for g in gaps: print(f"| {dd(g['start'])} – {dd(g['end'])} | {g['nights']} | {'Y' if g['within14'] else ''} | {'Y' if g['shorter_than_min'] else ''} |")
        print()
    print(T("### 清洁排班（未来 14 天）", "### Turnovers (next 14 days)") + "\n\n| " + T("日期 | 退房 | 入住 | 类型", "Date | Out | In | Type") + " |\n|---|---|---|---|")
    for t in [t for t in turns if (t["date"] - today).days < 14]:
        kind = T("同日换房", "same-day") if t.get("same_day") else (T("仅入住（检查就绪）", "arrival only (readiness)") if t.get("arrival_only") else T("退房清洁", "checkout clean"))
        print(f"| {dd(t['date'])} | {t['out']} | {t['next']} | {kind} |")
    if prompts: print("\n" + T("**可选（要做吗？）**", "**Optional — want me to?**") + "\n" + "\n".join(f"- {p}" for p in prompts[:3]))
    # outputs
    j = dict(as_of=str(today), property=a.property, horizon=a.horizon, occ={"30": o30, "60": o60, "90": o90},
             nights={str(k): v for k, v in night.items()}, bookings=[{**b, "start": str(b["start"]), "end": str(b["end"])} for b in bookings],
             gaps=[{**g, "start": str(g["start"]), "end": str(g["end"])} for g in gaps], warnings=warns, prompts=prompts)
    json.dump(j, open(f"{a.out}_calendar.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    rows = [[dd(t['date']), t["out"], t["next"], (T("同日换房", "Same-day") if t.get("same_day") else (T("仅入住", "Arrival only") if t.get("arrival_only") else T("退房清洁", "Checkout clean"))),
             f"{a.checkout} → {a.checkin}" if t.get("same_day") else "", ""] for t in turns if (t["date"] - today).days < 14]
    json.dump({"type": "report", "lang": a.lang, "title": T(f"清洁排班 — {a.property}", f"Turnover board — {a.property}"),
               "subtitle": T(f"未来 14 天 · 截至 {today}", f"Next 14 days · as of {today}"),
               "kpis": [[T("退房清洁", "Cleans"), str(sum(1 for t in turns if not t.get('arrival_only') and (t['date']-today).days < 14)), ""],
                        [T("同日换房", "Same-day"), str(sum(1 for t in turns if t.get('same_day') and (t['date']-today).days < 14)), T(f"窗口 {window:g} 小时", f"{window:g} h window")]],
               "sections": [{"h": T("排班", "Schedule"), "table": {"head": [T("日期", "Date"), T("退房", "Out"), T("入住", "In"), T("类型", "Type"), T("时间", "Window"), T("清洁员", "Cleaner")], "rows": rows}}]},
              open(f"{a.out}_board.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"type": "report", "lang": a.lang, "title": T(f"每周运营看板 — {a.property}", f"Weekly ops — {a.property}"), "subtitle": T(f"截至 {today}", f"as of {today}"),
               "kpis": [[T("未来30天入住率", "Occupancy next 30d"), f"{o30*100:.0f}%", T(f"目标 {a.occ_target:.0f}%", f"target {a.occ_target:.0f}%")],
                        [T("未来60天", "Next 60d"), f"{o60*100:.0f}%", ""], [T("空档", "Gaps"), str(len(gaps)), T(f"14天内 {len(soon_gaps)}", f"{len(soon_gaps)} within 14d")],
                        [T("本周换房", "Turnovers this week"), str(sum(1 for t in turns if (t['date']-today).days < 7 and not t.get('arrival_only'))), ""]],
               "summary": warns + prompts[:3],
               "sections": [{"h": T("清洁排班（7天）", "Turnovers (7 days)"), "table": {"head": [T("日期", "Date"), T("退房", "Out"), T("入住", "In"), T("类型", "Type")],
                             "rows": [r[:4] for r, t in zip(rows, [t for t in turns if (t["date"] - today).days < 14]) if (t["date"] - today).days < 7]}}]},
              open(f"{a.out}_dashboard.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(T("\n（文件：", "\n(files: ") + f"{a.out}_calendar.json · {a.out}_board.json · {a.out}_dashboard.json" + T("）", ")"))

if __name__ == "__main__":
    main()
