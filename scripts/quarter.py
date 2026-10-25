#!/usr/bin/env python3
"""host-strategist（房东军师）· 用月度结果做季度（或多个月）屋主复盘。  (c) 2026 Ryan Yan

用法：
  python3 quarter.py JUL_report.json AUG_report.json SEP_report.json --title "Willow 2BR — 2026 Q3"
        [--last-year Q3_2025_report.json ...] [--lang zh|en] [--out PREFIX]
输入是 airbnb_month.py 写出的 PREFIX_report.json（每月一个，同一套房）。
打印季度表格，并写出 PREFIX_quarter.json（render.py 的数据 — 补上 "summary" 和 "from" 后再生成页面）。
默认输出中文；--lang en 输出英文。使用时不要读这个文件，直接运行。
"""
import sys, json, argparse

def main():
    if len(sys.argv) < 2: print(__doc__); return
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--title", default="")
    ap.add_argument("--last-year", nargs="*", default=[]); ap.add_argument("--lang", default="zh", choices=["zh", "en"]); ap.add_argument("--out", default="quarter")
    a = ap.parse_args(); zh = a.lang == "zh"; T = (lambda z, e: z if zh else e)
    if not a.title: a.title = T("季度复盘", "Quarterly review")
    m = lambda v: f"${v:,.0f}"
    def load(fs):
        out = []
        for f in fs:
            j = json.load(open(f, encoding="utf-8-sig")); t = j.get("totals", {}); out.append((j.get("title", f).split("—")[-1].strip(), t))
        return out
    cur, ly = load(a.files), load(a.last_year)
    def tot(rows):
        s = {k: sum(float(t.get(k) or 0) for _, t in rows) for k in ("nights", "avail", "rent", "cleaning", "host_fee", "net", "adjustments", "invoice")}
        s["occ"] = s["nights"] / s["avail"] if s["avail"] else 0; s["adr"] = s["rent"] / s["nights"] if s["nights"] else 0
        s["revpar"] = s["rent"] / s["avail"] if s["avail"] else 0; s["owner_after"] = s["net"] + s["adjustments"] - s["invoice"]
        return s
    Q, L = tot(cur), (tot(ly) if ly else None)
    if L and not L["net"]: L = None
    inc = [n for n, t in cur if not t.get("invoice_complete", True)]
    if inc: print(T("警告：以下月份账单不完整（有费用未设置）：", "WARNING: invoice not complete (fee not set) for ") + ", ".join(inc) + T(" — 这些月份和合计的\"扣账单后屋主净得\"显示为 —。", " — 'owner after invoice' shown as — for those months and the total."))
    rows = []
    for name, t in cur:
        n, av, rent = float(t.get("nights") or 0), float(t.get("avail") or 0), float(t.get("rent") or 0)
        ok = t.get("invoice_complete", True)
        rows.append([name, f"{int(n)} / {int(av)}", f"{(n/av*100 if av else 0):.0f}%", m(rent / n) if n else "—", m(float(t.get("net") or 0)),
                     m(float(t.get("invoice") or 0)) if ok else "—", m(float(t.get("net") or 0) + float(t.get("adjustments") or 0) - float(t.get("invoice") or 0)) if ok else "—"])
    chg = lambda k: (f"{(Q[k]-L[k])/L[k]*100:+.0f}%" if L and L[k] else "")
    print(f"## {a.title}\n\n" + T("| 月份 | 晚数 | 入住率 | 平均房价 | 屋主收入 | 管理账单 | 扣账单后屋主净得 |", "| Month | Nights | Occ | ADR | Owner earnings | Invoice | Owner after invoice |") + "\n|---|---|---:|---:|---:|---:|---:|")
    for r in rows: print("| " + " | ".join(r) + " |")
    print(f"| **{T('合计', 'Total')}** | {int(Q['nights'])} / {int(Q['avail'])} | {Q['occ']*100:.0f}% | {m(Q['adr'])} | {m(Q['net'])} | {m(Q['invoice']) if not inc else '—'} | {m(Q['owner_after']) if not inc else '—'} |")
    if L: print("\n" + T(f"同比去年：屋主收入 {chg('net')} · 入住率 {(Q['occ']-L['occ'])*100:+.1f} 个百分点 · 平均房价 {chg('adr')} · RevPAR {chg('revpar')}", f"vs last year: earnings {chg('net')} · occupancy {(Q['occ']-L['occ'])*100:+.1f} pts · ADR {chg('adr')} · RevPAR {chg('revpar')}"))
    spec = {"type": "report", "lang": a.lang, "title": a.title, "subtitle": T("季度复盘 · 按入住日期计算", "Quarterly review · stay-date basis"),
            "kpis": [[T("屋主收入", "Owner earnings"), m(Q["net"]), (T("同比 ", "vs last year ") + chg("net")) if L else ""],
                     [T("入住率", "Occupancy"), f"{Q['occ']*100:.0f}%", f"{int(Q['nights'])} / {int(Q['avail'])}"],
                     [T("平均房价", "Average nightly rate"), m(Q["adr"]), (T("同比 ", "vs LY ") + chg("adr")) if L else ""],
                     [T("每间可售晚收入", "RevPAR"), m(Q["revpar"]), (T("同比 ", "vs LY ") + chg("revpar")) if L else ""]],
            "summary": [],
            "sections": [{"h": T("按月", "By month"), "table": {"head": [T("月份", "Month"), T("晚数", "Nights"), T("入住率", "Occ"), T("房价", "ADR"), T("屋主收入", "Earnings"), T("管理账单", "Invoice"), T("屋主净得", "Owner after invoice")],
                          "rows": rows, "total": [T("合计", "Total"), f"{int(Q['nights'])} / {int(Q['avail'])}", f"{Q['occ']*100:.0f}%", m(Q["adr"]), m(Q["net"]), m(Q["invoice"]) if not inc else "—", m(Q["owner_after"]) if not inc else "—"]}}]}
    json.dump(spec, open(f"{a.out}_quarter.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\n" + T(f"（文件：{a.out}_quarter.json — 补上 summary（3–5 行）、评价 / 维修 / 改进建议、需要屋主决定的事项和 'from'，然后用 render.py 生成）", f"(file: {a.out}_quarter.json — add summary (3–5 lines), reviews/maintenance/ideas sections, decisions needed, and 'from'; then render.py)"))

if __name__ == "__main__":
    main()
