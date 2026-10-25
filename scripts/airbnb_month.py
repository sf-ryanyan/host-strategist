#!/usr/bin/env python3
"""host-strategist（房东军师）· 用 Airbnb 交易记录 CSV 计算月度数字。  (c) 2026 Ryan Yan

用法：
  python3 airbnb_month.py FILE.csv [FILE2.csv ...] --month 2026-10
        [--listing "text in listing name"] [--blocked 2]
        [--mgmt-pct 20] [--basis net_rent|gross|payout]
        [--cleaning-per-turn 120] [--expenses expenses.csv]
        [--owner "屋主姓名"] [--property "房源名"] [--out PREFIX] [--lang zh|en]
        [--workorders workorders.csv] [--prev LAST_report.json] [--fee-on-cancellations]
        [--as-of YYYY-MM-DD] [--occ-target 60] [--drop-pct 15]

计算方法（按入住日期）：
  * 房租按晚数分摊到各月。清洁费算在入住当月。
  * 换房清洁次数 = 本月退房的订单数（用于每次固定清洁收费）。
  * 本月日期的调整 / 纠纷赔付 / 退款行单独列出。
  * 本月日期的 Payout 行 = Airbnb 实际打出的钱。
输出：PREFIX_ledger.csv（导入 Google Sheets）、PREFIX_invoice.json 和 PREFIX_report.json（给 render.py）。
expenses.csv 列：date,description,amount[,receipt]（用户垫付、由屋主报销的费用）
--workorders：屋主承担、可报销、本月完工的工单自动计入账单。--prev：上月 report.json，用于环比。
--lang 同时决定屋主报告 / 账单的语言和屏幕输出（默认 zh；屋主要英文时用 en）。--occ-target、--drop-pct 用 settings.md 里的门槛。使用时不要读这个文件，直接运行。
"""
import sys, csv, json, argparse, calendar, datetime as dt, re

ALIAS = {
  "date": ["date"],
  "type": ["type"],
  "code": ["confirmation code", "confirmation_code", "reservation code"],
  "start": ["start date", "start_date", "check-in", "check in", "checkin"],
  "nights": ["nights", "# of nights"],
  "guest": ["guest", "guest name"],
  "listing": ["listing", "listing name"],
  "details": ["details"],
  "amount": ["amount"],
  "paid_out": ["paid out", "paid_out", "payout"],
  "host_fee": ["service fee", "host fee", "host service fee"],
  "cleaning": ["cleaning fee", "cleaning_fee"],
  "gross": ["gross earnings", "gross_earnings"],
  "tax": ["occupancy taxes", "occupancy tax", "taxes"],
}

TZH = {"cancellation fee": "取消费", "resolution payout": "纠纷赔付", "resolution adjustment": "纠纷调整", "adjustment": "调整",
       "refund": "退款", "host remitted tax": "代缴税", "pass through tot": "代收税", "co-host payout": "协作房东分成"}

def norm(h): return re.sub(r"\s+", " ", (h or "").strip().lower())

def money(s):
    if s is None: return 0.0
    s = str(s).strip().replace("$", "").replace(",", "")
    if s in ("", "-"): return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try: v = float(s)
    except ValueError: return 0.0
    return -v if neg else v

def pdate(s):
    s = (s or "").strip()
    for f in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%b %d, %Y", "%d/%m/%Y"):
        try: return dt.datetime.strptime(s, f).date()
        except ValueError: pass
    return None

def load(paths):
    rows, cols_seen = [], None
    for p in paths:
        with open(p, newline="", encoding="utf-8-sig") as f:
            r = csv.reader(f); header = next(r)
            hmap = {}
            for key, names in ALIAS.items():
                for i, h in enumerate(header):
                    if norm(h) in names: hmap[key] = i; break
            cols_seen = header
            missing = [k for k in ("type", "start", "nights", "amount") if k not in hmap]
            if missing:
                raise SystemExit(f"ERROR: {p} 缺少列 {missing}。找到的列：{header}\n"
                                 "请从 Airbnb > Transaction history（交易记录：completed payouts / gross earnings）下载 CSV。")
            for line in r:
                if not any(x.strip() for x in line): continue
                g = lambda k: line[hmap[k]] if k in hmap and hmap[k] < len(line) else ""
                rows.append({k: g(k) for k in ALIAS})
    return rows, cols_seen

def main():
    if len(sys.argv) < 2: print(__doc__); return
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+"); ap.add_argument("--month", required=True)
    ap.add_argument("--listing"); ap.add_argument("--blocked", type=float, default=0)
    ap.add_argument("--mgmt-pct", type=float); ap.add_argument("--basis", default="net_rent", choices=["net_rent", "gross", "payout"])
    ap.add_argument("--cleaning-per-turn", type=float); ap.add_argument("--expenses")
    ap.add_argument("--owner", default=""); ap.add_argument("--property")
    ap.add_argument("--fee-on-cancellations", action="store_true", help="include cancellation-fee income in the management-fee base")
    ap.add_argument("--as-of", help="today's date YYYY-MM-DD (use when the system clock may be wrong)")
    ap.add_argument("--workorders", help="workorders.csv — owner-charged, reimbursable orders closed this month go on the invoice")
    ap.add_argument("--prev", help="last month's PREFIX_report.json — for month-over-month signals")
    ap.add_argument("--occ-target", type=float, default=60); ap.add_argument("--drop-pct", type=float, default=15)
    ap.add_argument("--out", default="month"); ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    a = ap.parse_args()
    zh = a.lang == "zh"; T = (lambda z, e: z if zh else e)
    if not a.owner: a.owner = T("[屋主姓名]", "[Owner name]")
    y, m = map(int, a.month.split("-"))
    m0 = dt.date(y, m, 1); m1 = dt.date(y, m, calendar.monthrange(y, m)[1]) + dt.timedelta(1)
    days = (m1 - m0).days
    rows, _ = load(a.files)
    rows_all = list(rows)
    seen, res, adj, pay, other, warn = set(), [], [], [], [], []
    all_listings = sorted({(r["listing"] or "").strip() for r in rows if (r["listing"] or "").strip()})
    if a.listing:  # payout rows have no listing: keep them (account-level cash, all listings)
        rows = [r for r in rows if a.listing.lower() in (r["listing"] or "").lower() or (r["type"] or "").strip().lower() == "payout"]
        others = [l for l in all_listings if a.listing.lower() not in l.lower()]
        if others: warn.append(T(f"文件里的其他房源未计入：{', '.join(others)}", f"other listings in this file were left out: {', '.join(others)}"))
    today = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    if today < m1:
        warn.append(T(f"本月还没结束（截至 {today}）：报告标注\"截至目前\"，先不要开账单 — 如果日期不对，用 --as-of YYYY-MM-DD 重新运行",
                      f"month not finished (as of {today}): label the report 'to date' and don't invoice yet — if the date is wrong, re-run with --as-of YYYY-MM-DD"))
    for r in rows:
        t = (r["type"] or "").strip().lower()
        d = pdate(r["date"])
        if t == "payout":
            if d and m0 <= d < m1: pay.append(dict(date=d, amount=money(r["paid_out"]) or money(r["amount"]), details=r["details"]))
            continue
        if t == "reservation":
            start = pdate(r["start"]); n = int(money(r["nights"]))
            if not start or n <= 0:
                if d and m0 <= d < m1: adj.append(dict(date=d, type="Cancellation fee", kind="cancel", code=r["code"], amount=money(r["amount"]), details=r["details"] or T("订单已取消 — 保留取消费", "booking cancelled — fee kept")))
                continue
            key = (r["code"], r["start"], r["amount"])
            if key in seen: warn.append(T(f"跳过重复行：{r['code']}", f"duplicate row skipped: {r['code']}")); continue
            seen.add(key)
            end = start + dt.timedelta(n)
            inm = max(0, (min(end, m1) - max(start, m0)).days)
            cin, cout = m0 <= start < m1, m0 <= end < m1
            if inm == 0 and not cin and not cout: continue
            gross = money(r["gross"]); clean = money(r["cleaning"]); net = money(r["amount"]); fee = abs(money(r["host_fee"]))
            if not gross: gross = net + fee
            rent = gross - clean
            sr = rent / gross if gross else 1.0          # share of the booking that is rent
            frac = inm / n
            res.append(dict(code=r["code"], guest=r["guest"], listing=r["listing"], start=start, end=end, nights=n, nights_in_month=inm,
                            rent=rent * frac, cleaning=clean if cin else 0.0,
                            fee_rent=fee * sr * frac, fee_clean=fee * (1 - sr) if cin else 0.0,
                            net=net * sr * frac + (net * (1 - sr) if cin else 0.0),
                            tax=money(r["tax"]) * frac, turnover=cout))
            continue
        if any(w in t for w in ("adjust", "resolution", "refund", "cancel", "co-host", "tax", "withholding")):
            if d and m0 <= d < m1: adj.append(dict(date=d, type=r["type"], kind="cancel" if "cancel" in t else "other", code=r["code"], amount=money(r["amount"]), details=r["details"]))
            continue
        if d and m0 <= d < m1: other.append(dict(date=d, type=r["type"], amount=money(r["amount"]), details=r["details"]))
    for x in res: x["host_fee"] = x["fee_rent"] + x["fee_clean"]
    # overlap check: two stays on the same listing cannot share a night
    by_l = {}
    for x in sorted(res, key=lambda x: x["start"]): by_l.setdefault(x["listing"], []).append(x)
    occupied, checkouts = set(), set()
    for l, xs in by_l.items():
        for i in range(1, len(xs)):
            if xs[i]["start"] < max(z["end"] for z in xs[:i]):
                warn.append(T(f"⚠️ OVERLAP 订单重叠（{l or '房源'}）：{xs[i]['code']} 在 {xs[i]['start']} 入住，早于前一单退房 — 请检查文件；晚数和换房清洁只算一次",
                              f"⚠️ OVERLAP on {l or 'listing'}: {xs[i]['code']} starts {xs[i]['start']} before an earlier stay ends — check the file; nights and turnovers counted once"))
        for x in xs:
            for k in range(x["nights"]):
                dday = x["start"] + dt.timedelta(k)
                if m0 <= dday < m1: occupied.add((l, dday))
            if x["turnover"]: checkouts.add((l, x["end"]))
    if not a.property: a.property = (res[0]["listing"] if len(by_l) == 1 and res[0]["listing"] else (a.listing or T("房源", "Property")))
    nights = len(occupied); rent = sum(x["rent"] for x in res)
    clean = sum(x["cleaning"] for x in res); hf = sum(x["host_fee"] for x in res); net = sum(x["net"] for x in res)
    adj_total = sum(x["amount"] for x in adj); paid = sum(x["amount"] for x in pay)
    avail = days - a.blocked
    turns = len(checkouts)
    base = {"net_rent": rent - sum(x["fee_rent"] for x in res), "gross": rent + clean, "payout": net}[a.basis]
    canc = sum(x["amount"] for x in adj if x.get("kind") == "cancel")
    if a.fee_on_cancellations: base += canc
    mgmt = round(base * a.mgmt_pct / 100, 2) if a.mgmt_pct is not None else None
    cl_charge = round(turns * a.cleaning_per_turn, 2) if a.cleaning_per_turn is not None else None
    exps = []
    if a.expenses:
        with open(a.expenses, newline="", encoding="utf-8-sig") as f:
            for e in csv.DictReader(f):
                ek = {norm(k): v for k, v in e.items()}
                exps.append(dict(date=ek.get("date", ""), description=ek.get("description", ""), amount=money(ek.get("amount")), receipt=ek.get("receipt", "")))
    open_urgent = []
    if a.workorders:
        prop_keys = [k.lower() for k in (a.property, a.listing) if k]
        with open(a.workorders, newline="", encoding="utf-8-sig") as f:
            for w in csv.DictReader(f):
                wk = {norm(k): (v or "").strip() for k, v in w.items()}
                pk = wk.get("property", "").lower()
                if prop_keys and pk and not any(pk in k or k in pk for k in prop_keys): continue
                closed = pdate(wk.get("closed", "")); status = wk.get("status", "").lower()
                if wk.get("severity") in ("1", "2") and status not in ("fixed", "closed", "invoiced", "billed"):
                    open_urgent.append(f"{wk.get('wo_id')} ({wk.get('description','')[:40]})")
                if closed and m0 <= closed < m1 and wk.get("charge_to", "").lower() == "owner" and wk.get("reimbursable", "Y").upper().startswith("Y") and money(wk.get("cost")):
                    if any(e["description"].startswith(wk.get("wo_id", "@@")) for e in exps): continue
                    exps.append(dict(date=str(closed), description=f"{wk.get('wo_id')} — {wk.get('description','')}", amount=money(wk.get("cost")), receipt=wk.get("receipt", "")))
    if open_urgent: warn.append(T("⚠️ 未完成的 1–2 级紧急工单：", "⚠️ open severity 1–2 work orders: ") + ", ".join(open_urgent))
    exp_total = sum(e["amount"] for e in exps)
    # payout check (account level): Airbnb lists each payout's reservation lines under the same date
    by_date_lines, by_date_paid, seen_l = {}, {}, set()
    for r in rows_all:
        d = pdate(r["date"]); t = (r["type"] or "").strip().lower()
        if not d or not (m0 <= d < m1): continue
        if t == "payout": by_date_paid[d] = by_date_paid.get(d, 0) + (money(r["paid_out"]) or money(r["amount"])); continue
        key = (r["code"], r["start"], r["amount"], r["type"])
        if key in seen_l: continue
        seen_l.add(key); by_date_lines[d] = by_date_lines.get(d, 0) + money(r["amount"])
    for d, paid_d in sorted(by_date_paid.items()):
        lines = by_date_lines.get(d, 0)
        if d in by_date_lines and abs(lines - paid_d) > 1: warn.append(T(f"⚠️ 打款 {d}：Airbnb 打款 {paid_d:,.2f}，但当天的明细合计 {lines:,.2f} — 请核对打款",
                                                                         f"⚠️ payout {d}: Airbnb paid {paid_d:,.2f} but the lines dated that day add to {lines:,.2f} — check the payout"))

    def f2(v):
        v = round(v, 2) + 0.0
        return f"${v:,.2f}" if v >= 0 else f"-${-v:,.2f}"
    occ = nights / avail if avail else 0
    mon = f"{y}年{m}月" if zh else f"{calendar.month_name[m]} {y}"
    print(f"## {a.property} — {mon}" + T("（按入住日期计算）", " (stay-date basis)") + "\n")
    print(T("| 指标 | 数值 |", "| Metric | Value |") + "\n|---|---:|")
    for k, v in [(T("已订晚数", "Nights booked"), T(f"{nights} / 可订 {avail:g} 晚", f"{nights} of {avail:g} available")), (T("入住率", "Occupancy"), f"{occ*100:.1f}%"),
                 (T("平均房价 ADR（房租 / 晚）", "ADR (rent / night)"), f2(rent / nights) if nights else "—"), (T("每间可售晚收入 RevPAR", "RevPAR"), f2(rent / avail) if avail else "—"),
                 (T("房租（本月晚数）", "Rent (this month's nights)"), f2(rent)), (T("客人付的清洁费", "Guest cleaning fees"), f2(clean)), (T("Airbnb 房东服务费", "Airbnb host fees"), f2(-hf)),
                 (T("这些订单的屋主收入（已扣服务费）", "Owner earnings from these stays (net of host fee)"), f2(net)), (T("本月日期的调整项", "Adjustments dated this month"), f2(adj_total)),
                 ((T("本月收到的打款（现金，账户级 — 含所有房源）", "Payouts received this month (cash, account-level — all listings)") if a.listing else T("本月收到的打款（现金）", "Payouts received this month (cash)")), f2(paid)),
                 (T("换房清洁次数（退房）", "Turnovers (check-outs)"), str(turns))]:
        print(f"| {k} | {v} |")
    print("\n" + T("### 订单\n\n| 订单号 | 客人 | 入住–退房 | 本月晚数 | 房租 | 清洁费 | 服务费 | 净收入 |", "### Stays\n\n| Code | Guest | Stay | Nights in month | Rent | Cleaning | Host fee | Net |") + "\n|---|---|---|---:|---:|---:|---:|---:|")
    for x in sorted(res, key=lambda x: x["start"]):
        print(f"| {x['code']} | {x['guest']} | {x['start']:%m/%d} – {x['end']:%m/%d} | {x['nights_in_month']} / {x['nights']} | {f2(x['rent'])} | {f2(x['cleaning'])} | {f2(-x['host_fee'])} | {f2(x['net'])} |")
    if adj:
        print("\n" + T("### 调整 / 退款 / 纠纷赔付（逐条核对）\n\n| 日期 | 类型 | 订单号 | 金额 | 说明 |", "### Adjustments / refunds / resolution (check each)\n\n| Date | Type | Code | Amount | Details |") + "\n|---|---|---|---:|---|")
        for x in adj: print(f"| {x['date']} | {(TZH.get((x['type'] or '').lower(), x['type']) if zh else x['type'])} | {x['code']} | {f2(x['amount'])} | {x['details']} |")
    if other:
        print("\n" + T("### 其他行（未分类 — 请检查）", "### Other rows (not classified — review)") + "\n")
        for x in other: print(f"- {x['date']} {x['type']}: {f2(x['amount'])} {x['details']}")
    print("\n" + T("### 给屋主的账单\n\n| 项目 | 金额 |", "### Your invoice to the owner\n\n| Item | Amount |") + "\n|---|---:|")
    bname = {"net_rent": T("净房租", "net rent"), "gross": T("总收入", "gross"), "payout": T("实际到账", "payout")}[a.basis]
    _b = f"{bname} {f2(base - (canc if a.fee_on_cancellations else 0))}" + ((T(" + 取消费 ", " + cancellation fee ") + f2(canc)) if (a.fee_on_cancellations and canc) else "")
    if mgmt is not None: print(T(f"| 管理费（{_b} 的 {a.mgmt_pct:g}%） | {f2(mgmt)} |", f"| Management fee ({a.mgmt_pct:g}% of {_b}) | {f2(mgmt)} |"))
    else: print(T(f"| 管理费 — 比例未设置（基数 {_b}） | 待定 |", f"| Management fee — % not set (base {_b}) | TBD |"))
    if cl_charge is not None: print(T(f"| 清洁 {turns} × {f2(a.cleaning_per_turn)} | {f2(cl_charge)} |", f"| Cleaning {turns} × {f2(a.cleaning_per_turn)} | {f2(cl_charge)} |"))
    else: print(T(f"| 清洁 — {turns} 次 × 收费未设置 | 待定 |", f"| Cleaning — {turns} turnovers × fee not set | TBD |"))
    for e in exps: print(T(f"| 代垫费用：{e['description']}（{e['date']}） | {f2(e['amount'])} |", f"| Reimbursable: {e['description']} ({e['date']}) | {f2(e['amount'])} |"))
    inv_total = (mgmt or 0) + (cl_charge or 0) + exp_total
    complete = mgmt is not None and cl_charge is not None
    print(T(f"| **应付合计** | **{f2(inv_total)}**{'（不完整 — 有费用未设置）' if not complete else ''} |", f"| **Total due** | **{f2(inv_total)}**{' (incomplete — fee not set)' if not complete else ''} |"))
    owner_keep = net + adj_total - inv_total
    print("\n" + T("扣除账单后屋主净得（收入 + 调整 − 账单）：", "Owner net after your invoice (earnings + adjustments − invoice): ") + f"**{f2(owner_keep) if complete else T('待定 — 有费用未设置', 'TBD — fee not set')}**")
    if any("resolution" in (x["type"] or "").lower() for x in adj) and exps:
        warn.append(T("同时存在纠纷赔付和代垫费用 — 请确认不是同一件事（避免 Airbnb 已赔付的又向屋主收费）",
                      "a resolution payout and reimbursable expenses both exist — check they are not for the same item (avoid charging the owner for something Airbnb already paid)"))
    if canc and not a.fee_on_cancellations: print(T(f"注：取消费收入 {f2(canc)} 没有计入管理费基数（如果屋主合同包括，加 --fee-on-cancellations）。", f"Note: cancellation-fee income {f2(canc)} is NOT in the management-fee base (add --fee-on-cancellations if the owner agreement includes it)."))
    listings = sorted({x["listing"] for x in res if x["listing"]})
    if len(listings) > 1: warn.append(T(f"这个文件里有 {len(listings)} 个房源（{', '.join(listings)}）— 每套房用 --listing 分别运行一次", f"{len(listings)} listings in this file ({', '.join(listings)}) — run once per property with --listing"))
    if not res: warn.append(T("本月没有找到订单 — 请检查 --month、--listing 和文件", "no reservations found for this month — check --month, --listing and the file"))
    if warn: print("\n" + T("**警告：**", "**Warnings:**") + "\n" + "\n".join(f"- {w}" for w in warn))
    prompts = []
    if a.prev:
        try:
            pv = json.load(open(a.prev, encoding="utf-8-sig")).get("totals", {}); pn = float(pv.get("net") or 0)
            if pn and (net - pn) / pn < -a.drop_pct / 100: prompts.append(T(f"屋主收入比上月下降 {(pn-net)/pn*100:.0f}% — 要准备给屋主的解释 / 做流失风险检查吗？", f"Owner earnings down {(pn-net)/pn*100:.0f}% vs last month — prepare an explanation / churn check for the owner?"))
            elif pn: print("\n" + T(f"环比上月：屋主收入 {(net-pn)/pn*100:+.0f}% · 晚数 {nights - int(pv.get('nights') or 0):+d}", f"vs last month: owner earnings {(net-pn)/pn*100:+.0f}% · nights {nights - int(pv.get('nights') or 0):+d}"))
        except Exception as ex: print(T(f"（无法读取 --prev：{ex}）", f"(could not read --prev: {ex})"))
    if occ * 100 < a.occ_target and today >= m0: prompts.append(T(f"入住率 {occ*100:.0f}% 低于目标 {a.occ_target:.0f}% — 要做定价检查吗？", f"Occupancy {occ*100:.0f}% below target {a.occ_target:.0f}% — run a pricing check?"))
    if prompts: print("\n" + T("**可选提示（问用户，用户说要才做）：**", "**Optional (ask the user, do nothing unless they say yes):**") + "\n" + "\n".join(f"- {p}" for p in prompts[:3]))

    items = []
    bdesc = f"{bname} {f2(base - (canc if a.fee_on_cancellations else 0))}" + ((f" + {'取消费' if zh else 'cancellation fee'} {f2(canc)}") if (a.fee_on_cancellations and canc) else "")
    if mgmt is not None: items.append([(f"管理费 — （{bdesc}）的 {a.mgmt_pct:g}%" if zh else f"Management fee — {a.mgmt_pct:g}% of ({bdesc})"), 1, mgmt, mgmt])
    if cl_charge is not None: items.append([(f"清洁费 — {turns} 次退房清洁" if zh else f"Cleaning — {turns} turnover(s)"), turns, a.cleaning_per_turn, cl_charge])
    for e in exps: items.append([(f"代垫费用 — {e['description']}（{e['date']}）" if zh else f"Reimbursable — {e['description']} ({e['date']})"), 1, e["amount"], e["amount"]])
    with open(f"{a.out}_ledger.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["month", "property", "row_type", "code", "guest", "check_in", "check_out", "nights", "nights_in_month", "rent", "cleaning_fee", "host_fee", "net_to_owner", "turnover", "invoice_amount", "note"])
        for x in sorted(res, key=lambda x: x["start"]):
            w.writerow([a.month, a.property, "stay", x["code"], x["guest"], x["start"], x["end"], x["nights"], x["nights_in_month"],
                        f"{x['rent']+0.0:.2f}", f"{x['cleaning']+0.0:.2f}", f"{(-x['host_fee'])+0.0:.2f}", f"{x['net']+0.0:.2f}", "Y" if x["turnover"] else "", "", ""])
        for x in adj: w.writerow([a.month, a.property, "adjustment", x["code"], "", "", "", "", "", "", "", "", f"{x['amount']:.2f}", "", "", f"{x['type']}: {x['details']}"])
        for it in items: w.writerow([a.month, a.property, "invoice", "", "", "", "", "", "", "", "", "", "", "", f"{it[3]:.2f}", it[0]])
    json.dump({"type": "invoice", "lang": a.lang, "property": a.property, "to": {"name": a.owner}, "period": (f"{y}年{m}月" if zh else f"{calendar.month_name[m]} {y}"),
               "items": items, "complete": complete}, open(f"{a.out}_invoice.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    K = ([["屋主收入", f2(net), "已扣 Airbnb 服务费"], ["入住率", f"{occ*100:.0f}%", f"{nights} / {avail:g} 晚"],
          ["平均房价", f2(rent / nights) if nights else "—", "每晚，不含清洁费"], ["本月账单", f2(inv_total) if (mgmt is not None and cl_charge is not None) else "待定", "管理费 + 清洁费 + 代垫"]] if zh else
         [["Owner earnings", f2(net), "net of Airbnb fees"], ["Occupancy", f"{occ*100:.0f}%", f"{nights} of {avail:g} nights"],
          ["Average nightly rate", f2(rent / nights) if nights else "—", "rent only"], ["Your invoice", f2(inv_total) if (mgmt is not None and cl_charge is not None) else "TBD", "mgmt + cleaning + reimbursables"]])
    json.dump({"type": "report", "lang": a.lang, "title": (f"{a.property} — {y}年{m}月" if zh else f"{a.property} — {calendar.month_name[m]} {y}"),
               "subtitle": ("屋主月报 · 按入住日期计算" if zh else "Monthly owner report · stay-date basis"),
               "kpis": K,
               "stays": [[x["code"], x["guest"], (f"{x['start']:%m/%d} – {x['end']:%m/%d}" if zh else f"{x['start']:%b %d} – {x['end']:%b %d}"),
                          (f"{x['nights_in_month']}" if x["nights_in_month"] else ("0（本月退房）" if zh else "0 (checkout)")),
                          f2(x["rent"] + x["cleaning"]), f2(x["net"])] for x in sorted(res, key=lambda x: x["start"])],
               "adjustments": [[str(x["date"]), (TZH.get(x["type"].lower(), x["type"]) if zh else x["type"]), x["details"] or "", f2(x["amount"])] for x in adj],
               "totals": dict(nights=nights, avail=avail, rent=round(rent, 2), cleaning=round(clean, 2), host_fee=round(hf, 2), net=round(net, 2),
                              adjustments=round(adj_total, 2), payouts=round(paid, 2), invoice=round(inv_total, 2), invoice_complete=complete, owner_net_after_invoice=round(owner_keep, 2) if complete else None)},
              open(f"{a.out}_report.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print("\n" + T("（文件：", "(files: ") + f"{a.out}_ledger.csv · {a.out}_invoice.json · {a.out}_report.json" + T("）", ")"))

if __name__ == "__main__":
    main()
