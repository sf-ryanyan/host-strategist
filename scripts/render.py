#!/usr/bin/env python3
"""host-strategist（房东军师）· 把屋主报告或账单生成简洁的一页 HTML。  (c) 2026 Ryan Yan

用法：
  python3 render.py spec.json out.html

spec.json — 报告（report）：
  {"type":"report","lang":"zh"|"en","title":"...","subtitle":"...",
   "kpis":[["label","value","note"], ...],               # 最多 4 个
   "summary":["one-line point", ...],                     # 结论，显示在最前面
   "sections":[{"h":"Heading","text":"paragraph"} |
               {"h":"Heading","bullets":["...", "..."]} |
               {"h":"Heading","table":{"head":[...],"rows":[[...]],"total":[...]}}],
   "stays":[[...]], "adjustments":[[...]],                # 可选（来自 airbnb_month.py）
   "from":{"name":"...","lines":["..."]}, "footer":"..."}
spec.json — 账单（invoice）：
  {"type":"invoice","lang":"zh"|"en","invoice_no":"INV-WIL01-2026-10","date":"2026-11-02","due":"2026-11-12",
   "period":"October 2026","property":"...","from":{"name":"...","lines":["..."]},"to":{"name":"...","lines":["..."]},
   "items":[["description",qty,unit_price,amount], ...],"notes":["payment instructions", ...]}
生成独立的 HTML，尽量打印成一页 Letter 纸。lang 不写时默认中文。使用时不要读这个文件，直接运行。
"""
import json, sys, html

L = {
 "en": dict(invoice="Invoice", bill_to="Bill to", from_="From", no="Invoice no.", date="Date", due="Due", period="Period",
            prop="Property", item="Description", qty="Qty", unit="Unit price", amt="Amount", total="Total due",
            stays="Stays", adj="Adjustments", code="Code", guest="Guest", stay="Stay (in – out)", nights="Nights in month",
            guest_paid="Rent + cleaning", net="Net to owner", type="Type", details="Details", summary="Summary"),
 "zh": dict(invoice="账单", bill_to="付款方", from_="收款方", no="账单编号", date="日期", due="付款截止", period="期间",
            prop="房源", item="项目", qty="数量", unit="单价", amt="金额", total="应付合计",
            stays="订单", adj="调整项", code="订单号", guest="客人", stay="入住–退房", nights="本月晚数",
            guest_paid="房费 + 清洁费", net="屋主净收入", type="类型", details="说明", summary="结论"),
}
CSS = """
:root{--ink:#1B2A31;--ink2:#4A5A61;--line:#E4E1DA;--accent:#0F4C5C;--soft:#EEF4F5;--neg:#B5523B}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:14px/1.55 "Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif}
.p{max-width:780px;margin:0 auto;padding:36px 28px}
h1{font-size:24px;margin:0 0 4px;letter-spacing:-.01em}h2{font-size:15px;margin:26px 0 8px;color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.sub{color:var(--ink2);font-size:13px}.bar{height:4px;background:var(--accent);width:56px;margin:14px 0 18px;border-radius:2px}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:8px 0 4px}
.k div{border:1px solid var(--line);border-radius:10px;padding:10px 12px}.k b{display:block;font-size:20px;margin-top:2px}
.k small{display:block;color:var(--ink2);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}.k i{font-style:normal;color:var(--ink2);font-size:12px}
.sum{background:var(--soft);border-left:4px solid var(--accent);border-radius:6px;padding:12px 16px;margin:16px 0}
.sum li{margin:3px 0}ul{margin:6px 0;padding-left:20px}
table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink2);border-bottom:2px solid var(--ink);padding:6px 8px}
td{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}td.n,th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
tr.t td{font-weight:700;border-top:2px solid var(--ink);border-bottom:0}.neg{color:var(--neg)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:6px}.two div{font-size:13px}.two b{display:block;font-size:14px}
.meta td{border:0;padding:2px 8px 2px 0;font-size:13px}.meta td:first-child{color:var(--ink2)}
.f{margin-top:28px;padding-top:10px;border-top:1px solid var(--line);color:var(--ink2);font-size:11.5px}
.big{font-size:22px;color:var(--accent)}
@media (max-width:560px){.p{padding:22px 14px}.two{grid-template-columns:1fr}table{font-size:12px}}
@page{size:Letter;margin:.55in}@media print{.p{padding:0;max-width:none}h2{break-after:avoid}tr,.k div{break-inside:avoid}}
"""
e = lambda x: html.escape(str(x))

def num(x):
    try: return float(str(x).replace("$", "").replace(",", ""))
    except ValueError: return None

def cell(v):
    s = str(v); n = num(s.replace("−", "-"))
    cls = "n" + (" neg" if (n is not None and n < 0) else "") if n is not None or s.startswith(("$", "-$", "−$")) else ""
    return f'<td class="{cls}">{e(s)}</td>' if cls else f"<td>{e(s)}</td>"

def isnum(v):
    s = str(v); return num(s.replace("−", "-")) is not None or s.startswith(("$", "-$", "−$"))

def table(head, rows, total=None):
    right = [bool(rows) and all(isnum(r[i]) for r in rows if i < len(r) and str(r[i]) != "") for i in range(len(head))]
    out = ["<table><thead><tr>"] + [f'<th class="{"n" if right[i] else ""}">{e(h)}</th>' for i, h in enumerate(head)] + ["</tr></thead><tbody>"]
    for r in rows: out.append("<tr>" + "".join(cell(v) for v in r) + "</tr>")
    if total: out.append('<tr class="t">' + "".join(cell(v) for v in total) + "</tr>")
    return "".join(out) + "</tbody></table>"

def report(s, t):
    o = [f"<h1>{e(s.get('title',''))}</h1>"]
    if s.get("subtitle"): o.append(f'<div class="sub">{e(s["subtitle"])}</div>')
    o.append('<div class="bar"></div>')
    if s.get("kpis"):
        o.append('<div class="k">' + "".join(f"<div><small>{e(k[0])}</small><b>{e(k[1])}</b><i>{e(k[2]) if len(k)>2 else ''}</i></div>" for k in s["kpis"][:4]) + "</div>")
    if s.get("summary"):
        o.append('<div class="sum"><b>' + e(t["summary"]) + "</b><ul>" + "".join(f"<li>{e(x)}</li>" for x in s["summary"]) + "</ul></div>")
    for sec in s.get("sections", []):
        o.append(f"<h2>{e(sec.get('h',''))}</h2>")
        if "text" in sec: o.append(f"<p>{e(sec['text'])}</p>")
        if "bullets" in sec: o.append("<ul>" + "".join(f"<li>{e(b)}</li>" for b in sec["bullets"]) + "</ul>")
        if "table" in sec: tb = sec["table"]; o.append(table(tb["head"], tb["rows"], tb.get("total")))
    if s.get("stays"):
        o.append(f"<h2>{t['stays']}</h2>" + table([t["code"], t["guest"], t["stay"], t["nights"], t["guest_paid"], t["net"]], s["stays"]))
    if s.get("adjustments"):
        o.append(f"<h2>{t['adj']}</h2>" + table([t["date"], t["type"], t["details"], t["amt"]], s["adjustments"]))
    fr = s.get("from") or {}
    foot = " · ".join([fr.get("name", "")] + fr.get("lines", []) + ([s["footer"]] if s.get("footer") else []))
    if foot.strip(" ·"): o.append(f'<div class="f">{e(foot)}</div>')
    return "".join(o)

def invoice(s, t):
    fr, to = s.get("from") or {"name": ("[Your name]" if s.get("lang") == "en" else "[你的名字]")}, s.get("to") or {"name": ("[Owner name]" if s.get("lang") == "en" else "[屋主姓名]")}
    items = s.get("items", [])
    total = sum(float(i[3]) for i in items)
    m = lambda v: f"${float(v):,.2f}"
    o = [f"<h1>{t['invoice']}</h1><div class='bar'></div>",
         '<div class="two"><div><span class="sub">' + t["from_"] + f"</span><b>{e(fr.get('name',''))}</b>" + "<br>".join(e(x) for x in fr.get("lines", [])) + "</div>",
         '<div><span class="sub">' + t["bill_to"] + f"</span><b>{e(to.get('name',''))}</b>" + "<br>".join(e(x) for x in to.get("lines", [])) + "</div></div>",
         '<table class="meta" style="width:auto;margin:16px 0">' + "".join(f"<tr><td>{t[k]}</td><td><b>{e(s[v])}</b></td></tr>" for k, v in [("no", "invoice_no"), ("date", "date"), ("due", "due"), ("period", "period"), ("prop", "property")] if s.get(v)) + "</table>",
         table([t["item"], t["qty"], t["unit"], t["amt"]], [[i[0], f"{float(i[1]):g}", m(i[2]), m(i[3])] for i in items], ["", "", t["total"], m(total)])]
    if s.get("notes"): o.append("<ul style='margin-top:16px'>" + "".join(f"<li>{e(n)}</li>" for n in s["notes"]) + "</ul>")
    o.append(f'<p style="margin-top:18px"><span class="sub">{t["total"]}</span><br><b class="big">{m(total)}</b></p>')
    return "".join(o)

def main():
    if len(sys.argv) < 3: print(__doc__); return
    s = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    t = L.get(s.get("lang", "zh"), L["zh"])
    body = invoice(s, t) if s.get("type") == "invoice" else report(s, t)
    title = s.get("title") or f"{t['invoice']} {s.get('invoice_no','')}"
    lang = "en" if s.get("lang") == "en" else "zh-CN"
    open(sys.argv[2], "w", encoding="utf-8").write(f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>{CSS}</style></head><body><main class="p">{body}</main></body></html>')
    print(f"已生成 {sys.argv[2]}")

if __name__ == "__main__":
    main()
