#!/usr/bin/env python3
"""host-strategist（房东军师）· 屋主账单追踪（应收款）。  (c) 2026 Ryan Yan

invoices.csv 列：invoice_no,owner,property,period,date,due,amount,paid_date,paid_amount,notes
用法：
  python3 ar.py invoices.csv [--as-of YYYY-MM-DD]                       # 每张账单的状态 + 警告
  python3 ar.py invoices.csv --add PREFIX_invoice.json [--as-of ...]     # 添加新账单（生成账单之后）
  python3 ar.py invoices.csv --pay INV-WIL01-2026-10 --amount 624.83 --date 2026-11-08
  [--write invoices_updated.csv] [--lang zh|en]  （默认写出 invoices_updated.csv，交给用户保存）
状态：已付 · 部分付款 · 未付 · 逾期 OVERDUE（n 天）。逾期 = 警告。invoices.csv 不存在时会自动新建。
使用时不要读这个文件，直接运行。
"""
import sys, csv, json, argparse, datetime as dt, os

def pdate(s):
    """Parse YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, 'Oct 5, 2026'; return None if not a date."""
    s = (s or "").strip()
    for f in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%Y/%m/%d"):
        try: return dt.datetime.strptime(s, f).date()
        except ValueError: pass
    return None

COLS = ["invoice_no", "owner", "property", "period", "date", "due", "amount", "paid_date", "paid_amount", "notes"]

def num(x):
    try: return float(str(x).replace("$", "").replace(",", "") or 0)
    except ValueError: return 0.0

def main():
    if len(sys.argv) < 2: print(__doc__); return
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--as-of"); ap.add_argument("--add")
    ap.add_argument("--pay"); ap.add_argument("--amount", type=float); ap.add_argument("--date"); ap.add_argument("--write", default="invoices_updated.csv")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"]); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); zh = a.lang == "zh"; T = (lambda z, e: z if zh else e)
    today = (pdate(a.as_of) or dt.date.today()) if a.as_of else dt.date.today()
    rows = []
    if os.path.exists(a.file):
        with open(a.file, newline="", encoding="utf-8-sig") as f: rows = [{c: (r.get(c) or "").strip() for c in COLS} for r in csv.DictReader(f)]
    elif not a.add:
        raise SystemExit(T(f"ERROR: 找不到 {a.file}。第一次使用请用 --add 添加第一张账单（会自动新建列表）。", f"ERROR: {a.file} not found. Use --add to add the first invoice (the list is created automatically)."))
    changed = False
    if a.add:
        j = json.load(open(a.add, encoding="utf-8-sig"))
        total = round(sum(float(i[3]) for i in j.get("items", [])), 2)
        no = j.get("invoice_no") or ""
        if not no: raise SystemExit(T("ERROR: 账单 JSON 没有 invoice_no — 先填写再添加。", "ERROR: the invoice JSON has no invoice_no — fill it before adding."))
        if j.get("complete") is False and not a.force:
            raise SystemExit(T("ERROR: 这张账单不完整（有费用未设置）— 先补齐费用重新生成；确实要添加请加 --force。", "ERROR: this invoice is incomplete (a fee is not set) — fix it first, or add --force."))
        if not j.get("due") and not a.force:
            raise SystemExit(T("ERROR: 账单 JSON 没有 due（付款期限）— 没有期限就无法判断逾期。先填写，或加 --force。", "ERROR: the invoice JSON has no due date — overdue tracking needs it. Fill it in, or add --force."))
        if any(r["invoice_no"] == no for r in rows): print(T(f"（账单 {no} 已在列表里 — 不重复添加）", f"(invoice {no} already in the list — not added again)"))
        else:
            rows.append(dict(invoice_no=no, owner=(j.get("to") or {}).get("name", ""), property=j.get("property", ""), period=j.get("period", ""),
                             date=j.get("date", ""), due=j.get("due", ""), amount=f"{total:.2f}", paid_date="", paid_amount="", notes=""))
            changed = True; print(T(f"已添加 {no}：${total:,.2f}，到期 {j.get('due','')}", f"added {no}: ${total:,.2f} due {j.get('due','')}"))
    if a.pay:
        r = next((r for r in rows if r["invoice_no"] == a.pay), None)
        if not r: raise SystemExit(T(f"ERROR: 找不到账单 {a.pay}", f"ERROR: invoice {a.pay} not found"))
        if a.amount is None: raise SystemExit(T("ERROR: 使用 --pay 时必须填 --amount", "ERROR: --amount is required with --pay"))
        r["paid_amount"] = f"{num(r['paid_amount']) + a.amount:.2f}"; r["paid_date"] = a.date or str(today); changed = True
        print(T(f"已记录 {r['invoice_no']} 收款 {a.amount:,.2f}", f"recorded payment {a.amount:,.2f} on {r['invoice_no']}"))
    warn, open_total = [], 0.0
    print("\n" + T(f"## 屋主账单 — 截至 {today}\n\n| 账单号 | 屋主 | 房源 | 期间 | 金额 | 已付 | 余额 | 到期日 | 状态 |", f"## Owner invoices — as of {today}\n\n| Invoice | Owner | Property | Period | Amount | Paid | Balance | Due | Status |") + "\n|---|---|---|---|---:|---:|---:|---|---|")
    for r in rows:
        amt, paid = num(r["amount"]), num(r["paid_amount"]); bal = round(amt - paid, 2)
        due = pdate(r["due"]) if r["due"] else None
        if r["due"] and not due: warn.append(T(f"⚠️ {r['invoice_no']} 的到期日\"{r['due']}\"无法识别 — 请改成 YYYY-MM-DD", f"⚠️ {r['invoice_no']}: due date '{r['due']}' not recognized — use YYYY-MM-DD"))
        if bal <= 0.005: st = T("已付", "paid")
        elif due and today > due:
            dd = (today - due).days
            st = T(f"逾期 OVERDUE {dd} 天", f"OVERDUE {dd}d"); warn.append(T(f"⚠️ {r['invoice_no']}（{r['owner']}）${bal:,.2f} 已逾期 {dd} 天", f"⚠️ {r['invoice_no']} ({r['owner']}) ${bal:,.2f} overdue {dd} days"))
        else: st = T("部分付款", "partial") if paid else T("未付", "open")
        if bal > 0.005: open_total += bal
        print(f"| {r['invoice_no']} | {r['owner']} | {r['property']} | {r['period']} | ${amt:,.2f} | ${paid:,.2f} | ${bal:,.2f} | {r['due']} | {st} |")
    print("\n" + T("未收合计：", "Outstanding total: ") + f"**${open_total:,.2f}**")
    if warn: print("\n" + T("**警告：**", "**Warnings:**") + "\n" + "\n".join(f"- {w}" for w in warn))
    if changed:
        with open(a.write, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
        print("\n" + T(f"（已写出更新后的列表：{a.write} — 交给用户保存 / 导入 Google Sheets）", f"(updated list written: {a.write} — give this file to the user to keep / import to Google Sheets)"))

if __name__ == "__main__":
    main()
