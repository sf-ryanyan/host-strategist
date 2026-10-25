#!/usr/bin/env python3
"""host-strategist（房东军师）· 小工具。  (c) 2026 Ryan Yan

  python3 tools.py inspection --property "Willow 2BR" [--items items.txt] [--standard 95] [--out inspection.html]
      手机验收页（英文，给清洁工 / 验收人）：每项点一下 Pass → Fail → N/A，实时打分、备注、"Copy result" 按钮。把 HTML 发给清洁工。
      items.txt（可选）：一行一项；以 "# " 开头的行是新的房间分区。默认 = 45 项标准清单。
  python3 tools.py expiry compliance.csv [--as-of YYYY-MM-DD] [--days 60] [--lang zh|en]
      compliance.csv 列：property,item,number_ref,issued,expires,renew_lead_days,task_owner,source,verified_on,notes
      对已过期或在窗口期内到期的项目（许可证、登记、保险、灭火器等）打印警告。
使用时不要读这个文件，直接运行。
"""
import sys, csv, json, argparse, datetime as dt, html

DEFAULT = """# Entry & exterior
Path, porch and entry clean
Exterior lights work
Lock works, battery OK
Doors and windows lock
# Living
Floors vacuumed / mopped, no hair
Surfaces dusted
Cushions and throws staged to photo
Remotes clean, in basket, batteries OK
TV / streaming signed out of guest accounts
# Kitchen
Dishes clean and put away
Dishwasher empty
Fridge emptied and wiped
Microwave / oven / stovetop clean
Sink and faucet clean, no drips
Counters and cabinet fronts wiped
Coffee station reset
Basics stocked (oil, salt, pepper, dish soap, tabs, paper towels)
Trash and recycling out, new bags
# Bathrooms
Toilet disinfected
Shower / tub clean, drain hair-free
Mirror streak-free
Floor hair-free, bath mat fresh
Towels folded to standard
Toiletries full (shampoo, conditioner, body wash, hand soap)
Toilet paper + 2 spares
Exhaust fan works
# Bedrooms
Fresh linens, beds made to photo
Under beds and nightstands checked
Closet: hangers, spare blanket and pillows
Lamps work
Curtains / blinds neat
# Laundry & supplies
Washer / dryer empty, lint filter clean
Linen closet at par
Supplies closet at par
# Safety
Smoke alarms present
CO alarm present
Fire extinguisher present, gauge green
First-aid kit stocked
No trip hazards
# Reset
Thermostat at welcome setting
Lights off, blinds as standard
Welcome note / Wi-Fi card in place
Photos of every room taken
Damage or missing items reported to host
Lost & found bagged and labeled"""

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inspection — __PROP__</title><style>
:root{--ink:#1B2A31;--mut:#5B6A70;--line:#E4E1DA;--acc:#0F4C5C;--ok:#2E7A57;--okbg:#E3F1E9;--bad:#B5523B;--badbg:#F8E3DE}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;color:var(--ink);background:#fff}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:12px 16px;z-index:2;display:flex;align-items:center;gap:14px}
.ring{width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;background:conic-gradient(var(--c,var(--ok)) calc(var(--p)*1%),#EEE 0)}
.ring span{width:42px;height:42px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:13px}
h1{font-size:17px;margin:0}small{color:var(--mut)}main{padding:4px 16px 90px;max-width:680px;margin:0 auto}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--acc);margin:22px 0 6px}
.it{display:flex;gap:10px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}.it span{flex:1}
button.s{min-width:68px;min-height:40px;border-radius:10px;border:1px solid var(--line);background:#fff;font-weight:700;font-size:13px}
.pass button.s{background:var(--okbg);color:var(--ok);border-color:#BFDCCB}.fail button.s{background:var(--bad);color:#fff;border-color:var(--bad)}
.na button.s{background:#F2F2F2;color:var(--mut)}.fail span{color:var(--bad);font-weight:600}
textarea{width:100%;min-height:80px;border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit}
.bar{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px}
.bar button{flex:1;min-height:46px;border-radius:12px;border:0;background:var(--acc);color:#fff;font-weight:700;font-size:15px}
</style></head><body><header><div class="ring" id="ring" style="--p:0"><span id="pct">0%</span></div>
<div><h1>__PROP__ — Turnover inspection</h1><small id="cnt">Tap each item: Pass → Fail → N/A · standard __STD__%</small></div></header>
<main>__ITEMS__<h2>Notes / damage / missing</h2><textarea id="notes" placeholder="What failed, what was fixed, photos sent?"></textarea>
<p><small>Name: <input id="who" style="border:1px solid var(--line);border-radius:8px;padding:6px"></small></p></main>
<div class="bar"><button onclick="copyRes()">Copy result</button></div>
<script>
var STD=__STD__,o=['','pass','fail','na'],L={'':'Check','pass':'Pass','fail':'Fail','na':'N/A'};
function sc(){var a=document.querySelectorAll('.it'),c=0,p=0,f=[];a.forEach(function(x){var s=x.dataset.s;if(s&&s!=='na'){c++;if(s==='pass')p++;else f.push(x.querySelector('span').textContent)}});
var v=c?Math.round(p/c*1000)/10:0,r=document.getElementById('ring');r.style.setProperty('--p',v);r.style.setProperty('--c',v>=STD?'var(--ok)':'var(--bad)');
document.getElementById('pct').textContent=Math.round(v)+'%';document.getElementById('cnt').textContent=p+' / '+c+' passed · '+(a.length-c-[].filter.call(a,function(x){return x.dataset.s==='na'}).length)+' not checked · standard '+STD+'%';return {v:v,c:c,p:p,f:f,t:a.length}}
document.querySelectorAll('.it button').forEach(function(b){b.onclick=function(){var x=b.parentNode,i=(o.indexOf(x.dataset.s||'')+1)%4;x.className='it '+o[i];x.dataset.s=o[i];b.textContent=L[o[i]];sc()}});
function copyRes(){var r=sc(),t='Inspection __PROP__ '+new Date().toLocaleString()+'\\nScore '+r.v+'% ('+r.p+'/'+r.c+')'+(r.v>=STD?' READY':' FIX BEFORE CHECK-IN')+'\\nFails: '+(r.f.join('; ')||'none')+'\\nNotes: '+document.getElementById('notes').value+'\\nBy: '+document.getElementById('who').value;
if(navigator.clipboard)navigator.clipboard.writeText(t).then(function(){alert('Copied — paste it to your host')});else prompt('Copy this:',t)}
</script></body></html>"""

def pdate(s):
    """Parse YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, 'Oct 5, 2026'; return None if not a date."""
    s = (s or "").strip()
    for f in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%Y/%m/%d"):
        try: return dt.datetime.strptime(s, f).date()
        except ValueError: pass
    return None

def inspection(a):
    txt = open(a.items, encoding="utf-8").read() if a.items else DEFAULT
    out, n = [], 0
    for line in txt.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith("#"): out.append(f"<h2>{html.escape(line.lstrip('# '))}</h2>"); continue
        n += 1; out.append(f'<div class="it" data-s=""><span>{html.escape(line)}</span><button class="s" type="button">Check</button></div>')
    page = PAGE.replace("__PROP__", html.escape(a.property)).replace("__STD__", str(int(a.standard))).replace("__ITEMS__", "".join(out))
    open(a.out, "w", encoding="utf-8").write(page)
    print(f"已生成 {a.out}（{n} 项，合格标准 {int(a.standard)}%）— 把这个文件发给清洁工 / 验收人；手机离线也能用")

def expiry(a):
    zh = a.lang == "zh"; T = (lambda z, e: z if zh else e)
    today = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    warn, rows = [], []
    with open(a.file, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items()}
            ex = pdate(r.get("expires", ""))
            if not ex:
                if r.get("expires"):
                    rows.append((r, None, T("日期无法识别", "date not recognized")))
                    warn.append(f"⚠️ {r.get('property')} — {r.get('item')} " + T(f"的到期日\"{r.get('expires')}\"无法识别 — 请改成 YYYY-MM-DD", f"expiry date '{r.get('expires')}' not recognized — use YYYY-MM-DD"))
                else: rows.append((r, None, T("没有日期", "no date")))
                continue
            left = (ex - today).days; lead = int(r.get("renew_lead_days") or a.days)
            st = T("已过期 EXPIRED", "EXPIRED") if left < 0 else (T(f"剩 {left} 天", f"{left} days left") if left <= max(lead, a.days) else T("正常", "ok"))
            rows.append((r, left, st))
            if left < 0 or left <= max(lead, a.days):
                warn.append(f"⚠️ {r.get('property')} — {r.get('item')} " + (T(f"已过期 {-left} 天", f"EXPIRED {-left} days ago") if left < 0 else T(f"{ex} 到期（剩 {left} 天）", f"expires {ex} ({left} days)")) + ((T(" · 负责人：", " · task: ") + r["task_owner"]) if r.get("task_owner") else ""))
    print(T(f"## 合规与续期 — 截至 {today}\n\n| 房源 | 项目 | 到期日 | 状态 | 核实日期 |", f"## Compliance & renewals — as of {today}\n\n| Property | Item | Expires | Status | Verified on |") + "\n|---|---|---|---|---|")
    for r, left, st in sorted(rows, key=lambda x: (x[1] if x[1] is not None else 99999)):
        print(f"| {r.get('property')} | {r.get('item')} | {r.get('expires') or '—'} | {st} | {r.get('verified_on') or '—'} |")
    if warn: print("\n" + T("**警告：**", "**Warnings:**") + "\n" + "\n".join(f"- {w}" for w in warn))
    def _old(v):
        d0 = pdate(v)
        return bool(d0) and (today - d0).days > 365
    stale = [r for r, _, _ in rows if r.get("verified_on") and _old(r["verified_on"])]
    if stale: print("\n" + T(f"可选提示：有 {len(stale)} 项上次核实已超过一年 — 要重新核实规定吗？", f"Optional: {len(stale)} item(s) last verified over a year ago — re-check the rules?"))

def main():
    if len(sys.argv) < 2: print(__doc__); return
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("inspection"); i.add_argument("--property", required=True); i.add_argument("--items"); i.add_argument("--standard", type=float, default=95); i.add_argument("--out", default="inspection.html"); i.add_argument("--lang", default="zh", choices=["zh", "en"])
    e = sub.add_parser("expiry"); e.add_argument("file"); e.add_argument("--as-of"); e.add_argument("--days", type=int, default=60); e.add_argument("--lang", default="zh", choices=["zh", "en"])
    a = ap.parse_args()
    if not a.cmd: print(__doc__); return
    {"inspection": inspection, "expiry": expiry}[a.cmd](a)

if __name__ == "__main__":
    main()
