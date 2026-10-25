#!/usr/bin/env python3
"""host-strategist（房东军师）· 短租评估测算模型。  (c) 2026 Ryan Yan

用法：
  python3 str_model.py --example > input.json   # 输入示例，复制后修改
  python3 str_model.py input.json               # 打印 Markdown，写出 input_result.json 和 input_owner_spec.json

金额为美元。入住率可写 0.72 或 72。没有提供的数值会标为"假设"。
"user_lang"：给用户看的测算语言（默认 zh）；"lang"：屋主一页摘要的语言（zh 或 en）。
使用时不要读这个文件，直接运行。
"""
import json, sys, calendar, copy, os

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

EXAMPLE = {
  "_note": "EXAMPLE 仅为示例数值 — 每个数字都要换成有来源或屋主提供的数值；不适用的区块删掉",
  "user_lang": "zh",
  "lang": "zh",
  "property": {"name": "123 Example St", "city": "San Jose", "beds": 3, "baths": 2, "sleeps": 6, "year": 2027},
  "monthly": [
    {"m": "Jan", "adr": 210, "occ": 0.55}, {"m": "Feb", "adr": 215, "occ": 0.60},
    {"m": "Mar", "adr": 225, "occ": 0.65}, {"m": "Apr", "adr": 230, "occ": 0.68},
    {"m": "May", "adr": 245, "occ": 0.72}, {"m": "Jun", "adr": 265, "occ": 0.80},
    {"m": "Jul", "adr": 270, "occ": 0.82}, {"m": "Aug", "adr": 265, "occ": 0.80},
    {"m": "Sep", "adr": 240, "occ": 0.70}, {"m": "Oct", "adr": 235, "occ": 0.68},
    {"m": "Nov", "adr": 225, "occ": 0.60}, {"m": "Dec", "adr": 240, "occ": 0.58}],
  "scenarios": {"conservative": {"adr_x": 0.90, "occ_pts": -10},
                "expected": {"adr_x": 1.00, "occ_pts": 0},
                "strong": {"adr_x": 1.08, "occ_pts": 5}},
  "owner_blocked_nights": 0,
  "alos": 3.0,
  "guest_cleaning_fee": 175,
  "cleaning_cost_per_turn": 140,
  "cleaning_charge_to_owner_per_turn": 160,
  "airbnb_host_fee_pct": "CHECK ACCOUNT",
  "airbnb_host_fee_source": "settings.md（核实日期 <date>）",
  "needs_quote": ["屋主保险公司的短租保险报价", "城市登记费"],
  "mgmt_fee_pct": None,
  "mgmt_fee_basis": "net_rent",
  "costs": {"utilities_internet_monthly": 450, "supplies_per_stay": 25, "insurance_annual": 2400,
            "permits_taxes_annual": 500, "software_monthly": 0, "maintenance_pct_of_revenue": 0.05,
            "hoa_monthly": 0, "property_tax_annual": 0, "mortgage_monthly": 0},
  "furnishing": {"needed": True, "cost": 22000, "other_setup": 2500},
  "ltr": {"monthly_rent": 3900, "vacancy_pct": 0.04, "maintenance_pct": 0.05, "insurance_annual": 1600,
          "mgmt_fee_pct": 0.08, "leasing_fee": 1950},
  "hybrid": {"str_months": [5, 6, 7, 8, 9, 10], "mtr_monthly_rent": 5200, "mtr_months_leased": 5.5, "mtr_cleaning_per_turn": 250,
             "mtr_turns": 1, "mtr_mgmt_fee_pct": 0.12, "mtr_maintenance_pct": 0.04},
  "mtr": {"monthly_rent": 5200, "months_leased": 10, "utilities_internet_monthly": 450, "cleaning_per_turn": 250,
          "turns": 3, "maintenance_pct": 0.04, "insurance_annual": 2000, "mgmt_fee_pct": 0.12, "listing_fees_annual": 200}
}

def pct(x):
    if x is None or x == "": return None
    try: x = float(x)
    except (TypeError, ValueError): return None
    return x / 100 if x > 1 else x

def money(v): return f"${v:,.0f}" if v >= 0 else f"-${-v:,.0f}"

def model(cfg, sc, mgmt, occ_scale=1.0):
    """Pure annual model for one scenario and one management-fee level."""
    year = int(cfg.get("property", {}).get("year", 2027))
    days = [calendar.monthrange(year, i + 1)[1] for i in range(12)]
    total_days = sum(days)
    s = cfg["scenarios"][sc]
    ax, op = float(s.get("adr_x", 1)), float(s.get("occ_pts", 0)) / 100
    alos, gcf = cfg["_alos"], float(cfg.get("guest_cleaning_fee", 0))
    ccost, hostfee = float(cfg.get("cleaning_cost_per_turn", 0)), cfg["_hostfee"]
    charge = cfg.get("cleaning_charge_to_owner_per_turn")
    owner_clean = float(charge) if charge not in (None, "") else ccost
    blocked = float(cfg.get("owner_blocked_nights", 0))
    c = cfg.get("costs", {})
    rows, T = [], dict(nights=0.0, rent=0.0, cf=0.0, stays=0.0, avail=0.0)
    for i, mrow in enumerate(cfg["monthly"]):
        avail = days[i] - blocked * days[i] / total_days
        occ = min(0.95, max(0.0, pct(mrow["occ"]) * occ_scale + op))
        adr = float(mrow["adr"]) * ax
        nights = avail * occ; rent = nights * adr; stays = nights / alos; cf = stays * gcf
        rows.append(dict(m=MONTHS[i], occ=occ, adr=adr, nights=nights, rent=rent, gross=rent + cf,
                         revpar=rent / avail if avail else 0))
        for k, v in dict(nights=nights, rent=rent, cf=cf, stays=stays, avail=avail).items(): T[k] += v
    gross = T["rent"] + T["cf"]
    host_fee = gross * hostfee
    base = {"net_rent": T["rent"] * (1 - hostfee), "gross": gross, "payout": gross - host_fee}[cfg.get("mgmt_fee_basis", "net_rent")]
    mgmt_fee = base * (mgmt or 0)
    costs = {
        "Airbnb host fee": host_fee,
        "Cleaning (per turnover)": T["stays"] * owner_clean,
        "Supplies": T["stays"] * float(c.get("supplies_per_stay", 0)),
        "Utilities & internet": 12 * float(c.get("utilities_internet_monthly", 0)),
        "Insurance": float(c.get("insurance_annual", 0)),
        "Permits & local fees": float(c.get("permits_taxes_annual", 0)),
        "Software": 12 * float(c.get("software_monthly", 0)),
        "Maintenance reserve": gross * float(c.get("maintenance_pct_of_revenue", 0)),
        "Management fee": mgmt_fee,
    }
    noi = gross - sum(costs.values())
    fixed = 12 * float(c.get("hoa_monthly", 0)) + float(c.get("property_tax_annual", 0)) + 12 * float(c.get("mortgage_monthly", 0))
    return dict(rows=rows, nights=T["nights"], stays=T["stays"], avail=T["avail"], rent=T["rent"], cleaning_fees=T["cf"],
                gross=gross, occ=T["nights"] / T["avail"], adr=T["rent"] / T["nights"] if T["nights"] else 0,
                revpar=T["rent"] / T["avail"], costs=costs, owner_noi=noi, owner_after_fixed=noi - fixed,
                fixed_owner_costs=fixed, mgmt_income=mgmt_fee, cleaning_margin=T["stays"] * (owner_clean - ccost),
                manager_income=mgmt_fee + T["stays"] * (owner_clean - ccost))

def run(cfg):
    cfg = copy.deepcopy(cfg); notes = []
    zh = cfg.get("user_lang", "zh") == "zh"; T = (lambda z, e: z if zh else e)
    if not cfg.get("monthly") or len(cfg["monthly"]) != 12:
        raise SystemExit(T("ERROR: 'monthly' 必须列出 12 个月，每个月都有 adr 和 occ。", "ERROR: 'monthly' must list 12 months, each with adr and occ."))
    cfg.setdefault("scenarios", EXAMPLE["scenarios"])
    if "expected" not in cfg["scenarios"]:
        raise SystemExit(T("ERROR: scenarios 必须包含 'expected'（预期）。", "ERROR: scenarios must include 'expected'."))
    cfg["_alos"] = float(cfg.get("alos") or 0) or 3.0
    if not cfg.get("alos"): notes.append(T("假设：平均每单住 3.0 晚", "ASSUMPTION: average stay 3.0 nights"))
    hf = pct(cfg.get("airbnb_host_fee_pct"))
    if hf is None:
        raise SystemExit(T("ERROR: 必须填写 airbnb_host_fee_pct。请在 Airbnb 账户（或 settings.md）查看收费模式，填写房东承担的 %。", "ERROR: airbnb_host_fee_pct is required. Check the fee model in the Airbnb account (or settings.md) and enter the host-side %."))
    cfg["_hostfee"] = hf
    notes.append(T(f"Airbnb 房东服务费 {hf*100:g}% — 来源：{cfg.get('airbnb_host_fee_source') or '输入值（请在 Airbnb 账户确认）'}", f"Airbnb host fee {hf*100:g}% — source: {cfg.get('airbnb_host_fee_source') or 'input (confirm in the Airbnb account)'}"))
    for q in cfg.get("needs_quote", []): notes.append(T(f"需报价 / 需核实：{q}", f"Needs quote / to confirm: {q}"))
    if cfg.get("mgmt_fee_basis", "net_rent") not in ("net_rent", "gross", "payout"):
        raise SystemExit(T("ERROR: mgmt_fee_basis 只能是 net_rent、gross 或 payout。", "ERROR: mgmt_fee_basis must be net_rent, gross or payout."))
    for k in ("guest_cleaning_fee", "cleaning_cost_per_turn"):
        if k not in cfg: notes.append(T(f"假设：{k} = 0（未提供）", f"ASSUMPTION: {k} = 0 (not supplied)"))
    for k in ("utilities_internet_monthly", "supplies_per_stay", "insurance_annual", "permits_taxes_annual", "maintenance_pct_of_revenue"):
        if k not in (cfg.get("costs") or {}): notes.append(T(f"假设：costs.{k} = 0（未提供）", f"ASSUMPTION: costs.{k} = 0 (not supplied)"))
    if "furnishing" not in cfg: notes.append(T("假设：没有家具 / 一次性投入（缺少 furnishing 区块）", "ASSUMPTION: no furnishing / set-up cost (block missing)"))
    mg = pct(cfg.get("mgmt_fee_pct"))
    levels = [mg] if mg is not None else [0.15, 0.20, 0.25]
    if mg is None: notes.append(T("管理费未设置：屋主结果按 15% / 20% / 25% 三档显示", "Management fee not set: owner results shown at 15% / 20% / 25%"))
    out = {"property": cfg.get("property", {}), "notes": notes, "needs_quote": cfg.get("needs_quote", []), "levels": [f"{round(l*100)}%" for l in levels], "scenarios": {}}
    for sc in cfg["scenarios"]:
        out["scenarios"][sc] = {f"{round(l*100)}%": model(cfg, sc, l) for l in levels}
    ltr = cfg.get("ltr") or {}
    if ltr.get("monthly_rent"):
        rent = float(ltr["monthly_rent"]); rev = 12 * rent * (1 - (pct(ltr.get("vacancy_pct")) or 0))
        lc = rev * (pct(ltr.get("maintenance_pct")) or 0) + float(ltr.get("insurance_annual", 0)) \
             + rev * (pct(ltr.get("mgmt_fee_pct")) or 0) + float(ltr.get("leasing_fee", 0))
        out["ltr"] = dict(revenue=rev, costs=lc, noi=rev - lc)
    f = cfg.get("furnishing") or {}
    setup = (float(f.get("cost", 0)) if f.get("needed") else 0) + float(f.get("other_setup", 0))
    out["setup_cost"] = setup
    ref = out.get("ltr", {}).get("noi", 0.0)
    out["compare_to"] = "ltr" if "ltr" in out else "zero"
    l0 = levels[0]
    e = model(cfg, "expected", l0)
    diff = e["owner_noi"] - ref
    out["payback_months"] = setup / (diff / 12) if (setup and diff > 0) else None
    out["payback_note"] = "none" if not setup else ("not_better" if diff <= 0 else "")
    hy = cfg.get("hybrid") or {}
    if hy.get("str_months") and hy.get("mtr_monthly_rent"):
        e = model(cfg, "expected", l0); keep = set(int(x) for x in hy["str_months"])
        rows = [r for i, r in enumerate(e["rows"]) if (i + 1) in keep]
        rent = sum(r["rent"] for r in rows); nights = sum(r["nights"] for r in rows); stays = nights / cfg["_alos"]
        gross = rent + stays * float(cfg.get("guest_cleaning_fee", 0)); c = cfg.get("costs", {})
        charge = cfg.get("cleaning_charge_to_owner_per_turn"); oc = float(charge) if charge not in (None, "") else float(cfg.get("cleaning_cost_per_turn", 0))
        mrev = float(hy["mtr_monthly_rent"]) * float(hy.get("mtr_months_leased", 0))
        costs = gross * cfg["_hostfee"] + stays * oc + stays * float(c.get("supplies_per_stay", 0)) + 12 * float(c.get("utilities_internet_monthly", 0)) \
                + float(c.get("insurance_annual", 0)) + float(c.get("permits_taxes_annual", 0)) + 12 * float(c.get("software_monthly", 0)) \
                + gross * float(c.get("maintenance_pct_of_revenue", 0)) + rent * (1 - cfg["_hostfee"]) * (l0 or 0) \
                + float(hy.get("mtr_cleaning_per_turn", 0)) * float(hy.get("mtr_turns", 0)) + mrev * (pct(hy.get("mtr_maintenance_pct")) or 0) \
                + mrev * (pct(hy.get("mtr_mgmt_fee_pct")) or 0)
        out["hybrid"] = dict(revenue=gross + mrev, str_revenue=gross, mtr_revenue=mrev, costs=costs, noi=gross + mrev - costs,
                             str_months=sorted(keep), mgmt_income=rent * (1 - cfg["_hostfee"]) * (l0 or 0) + mrev * (pct(hy.get("mtr_mgmt_fee_pct")) or 0))
    mtr = cfg.get("mtr") or {}
    if mtr.get("monthly_rent"):
        rev = float(mtr["monthly_rent"]) * float(mtr.get("months_leased", 12))
        mc = 12 * float(mtr.get("utilities_internet_monthly", 0)) + float(mtr.get("cleaning_per_turn", 0)) * float(mtr.get("turns", 0)) \
             + rev * (pct(mtr.get("maintenance_pct")) or 0) + float(mtr.get("insurance_annual", 0)) + rev * (pct(mtr.get("mgmt_fee_pct")) or 0) \
             + float(mtr.get("listing_fees_annual", 0))
        out["mtr"] = dict(revenue=rev, costs=mc, noi=rev - mc, mgmt_income=rev * (pct(mtr.get("mgmt_fee_pct")) or 0))
    # break-even: uniform occupancy scale where owner NOI == reference
    if model(cfg, "expected", l0, 3.0)["owner_noi"] > ref and model(cfg, "expected", l0, 0.0)["owner_noi"] < ref:
        lo, hi = 0.0, 3.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if model(cfg, "expected", l0, mid)["owner_noi"] > ref: hi = mid
            else: lo = mid
        out["breakeven_occupancy"] = model(cfg, "expected", l0, hi)["occ"]
    else:
        out["breakeven_occupancy"] = None
    out["breakeven_at_mgmt"] = f"{round(l0*100)}%"
    return out

CZ = {"Airbnb host fee": "Airbnb 房东服务费", "Cleaning (per turnover)": "清洁费（每次换房）", "Supplies": "耗材",
      "Utilities & internet": "水电网", "Insurance": "保险", "Permits & local fees": "许可证与当地费用", "Software": "软件",
      "Maintenance reserve": "维修预留", "Management fee": "管理费"}
SCZ = {"conservative": "保守", "expected": "预期", "strong": "乐观"}

def markdown(o, lang="zh"):
    zh = lang == "zh"; T = (lambda z, e: z if zh else e)
    L = []
    p = o["property"]
    cmp_name = T("长租净收入", "long-term lease NOI") if o["compare_to"] == "ltr" else T("不出租（$0）", "not renting ($0)")
    L.append(T(f"## 短租测算 — {p.get('name','')}（{p.get('city','')}，{p.get('beds','?')}房{p.get('baths','?')}卫）\n",
               f"## STR model — {p.get('name','')} ({p.get('city','')}, {p.get('beds','?')}BR/{p.get('baths','?')}BA)\n"))
    lv = o["levels"]
    L.append(T("### 年度汇总（屋主角度）\n", "### Annual summary (owner view)\n"))
    L.append(T("| 情景 | 管理费 | 入住率 | 平均房价 | RevPAR | 总收入 | 屋主净收入 NOI | 管理人收入 |",
               "| Scenario | Mgmt fee | Occupancy | ADR | RevPAR | Gross revenue | Owner NOI | Your mgmt income |"))
    L.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for sc, byl in o["scenarios"].items():
        for k, r in byl.items():
            L.append(f"| {SCZ.get(sc, sc) if zh else sc} | {k} | {r['occ']*100:.1f}% | {money(r['adr'])} | {money(r['revpar'])} | {money(r['gross'])} | {money(r['owner_noi'])} | {money(r['mgmt_income'])} |")
    e = o["scenarios"]["expected"][lv[0]]
    L.append(T("\n### 预期情景 · 逐月\n", "\n### Expected case by month\n"))
    L.append(T("| 月份 | 入住率 | 平均房价 | 晚数 | 房租 | 总收入（含清洁费） |", "| Month | Occ | ADR | Nights | Rent | Gross (incl. cleaning fees) |"))
    L.append("|---|---:|---:|---:|---:|---:|")
    for i, r in enumerate(e["rows"]):
        L.append(f"| {T(f'{i+1}月', r['m'])} | {r['occ']*100:.0f}% | {money(r['adr'])} | {r['nights']:.1f} | {money(r['rent'])} | {money(r['gross'])} |")
    L.append(f"| **{T('全年', 'Year')}** | **{e['occ']*100:.1f}%** | **{money(e['adr'])}** | **{e['nights']:.0f}** | **{money(e['rent'])}** | **{money(e['gross'])}** |")
    L.append(T(f"\n### 预期情景 · 年度开支（管理费 {lv[0]}）\n", f"\n### Expected case costs (mgmt {lv[0]})\n"))
    L.append(T("| 项目 | 每年 |", "| Line | Annual |"))
    L.append("|---|---:|")
    L.append(T(f"| 总收入 | {money(e['gross'])} |", f"| Gross revenue | {money(e['gross'])} |"))
    for k, v in e["costs"].items():
        if round(v): L.append(f"| {CZ.get(k, k) if zh else k} | -{money(v)} |")
    L.append(f"| **{T('屋主净收入 NOI', 'Owner NOI')}** | **{money(e['owner_noi'])}** |")
    if e["fixed_owner_costs"]:
        L.append(T(f"| 屋主固定成本（HOA、房产税、房贷） | -{money(e['fixed_owner_costs'])} |", f"| Owner fixed costs (HOA, property tax, mortgage) | -{money(e['fixed_owner_costs'])} |"))
        L.append(f"| **{T('屋主现金流', 'Owner cash flow')}** | **{money(e['owner_after_fixed'])}** |")
    if "ltr" in o:
        L.append(T("\n### 长租对比\n", "\n### Long-term lease comparison\n"))
        L.append(T(f"| | 每年 |\n|---|---:|\n| 长租收入 | {money(o['ltr']['revenue'])} |\n| 长租成本 | -{money(o['ltr']['costs'])} |\n| **长租净收入** | **{money(o['ltr']['noi'])}** |",
                   f"| | Annual |\n|---|---:|\n| LTR revenue | {money(o['ltr']['revenue'])} |\n| LTR costs | -{money(o['ltr']['costs'])} |\n| **LTR NOI** | **{money(o['ltr']['noi'])}** |"))
        d = e["owner_noi"] - o["ltr"]["noi"]
        if o["ltr"]["noi"]: L.append(T(f"\n短租（预期）比长租：**每年 {money(d)}**（{d/o['ltr']['noi']*100:+.0f}%）。", f"\nSTR expected vs LTR: **{money(d)} / year** ({d/o['ltr']['noi']*100:+.0f}%)."))
    L.append(T("\n### 投入、回本、盈亏平衡\n", "\n### Setup, payback, break-even\n"))
    L.append(T(f"- 一次性投入（家具 + 其他）：**{money(o['setup_cost'])}**", f"- One-time setup (furnishing + other): **{money(o['setup_cost'])}**"))
    pb = o.get("payback_months")
    pnote = {"none": T("没有一次性投入", "no set-up cost"), "not_better": T(f"短租预期没有超过{cmp_name}", f"STR expected does not beat {cmp_name}")}.get(o.get("payback_note"), "—")
    L.append(T(f"- 相比{cmp_name}的回本时间：**{pb:.0f} 个月**", f"- Payback vs {cmp_name}: **{pb:.0f} months**") if pb else T(f"- 相比{cmp_name}的回本时间：—（{pnote}）", f"- Payback vs {cmp_name}: — ({pnote})"))
    be = o.get("breakeven_occupancy")
    if be is not None:
        L.append(T(f"- 相比{cmp_name}的盈亏平衡入住率（管理费 {o['breakeven_at_mgmt']}）：平均 **{be*100:.0f}%**", f"- Break-even occupancy vs {cmp_name} (mgmt {o['breakeven_at_mgmt']}): **{be*100:.0f}%** average"))
    else:
        above = o['scenarios']['expected'][o['levels'][0]]['owner_noi'] > (o.get('ltr', {}).get('noi', 0))
        L.append(T(f"- 相比{cmp_name}的盈亏平衡入住率：—（任何入住率下屋主净收入都{'高于' if above else '低于'}它）", f"- Break-even occupancy vs {cmp_name}: — (owner NOI stays {'above' if above else 'below'} it at any occupancy)"))
    e0 = o["scenarios"]["expected"][o["levels"][0]]
    if round(e0["cleaning_margin"]): L.append(T(f"- 管理人收入（预期，管理费 {o['levels'][0]}）：管理费 {money(e0['mgmt_income'])} + 清洁差价 {money(e0['cleaning_margin'])} = **每年 {money(e0['manager_income'])}**",
                                                f"- Manager income (expected, mgmt {o['levels'][0]}): management {money(e0['mgmt_income'])} + cleaning margin {money(e0['cleaning_margin'])} = **{money(e0['manager_income'])}** / year"))
    if "hybrid" in o:
        hy = o["hybrid"]
        L.append(T(f"\n### 混合模式：{'、'.join(str(x) for x in hy['str_months'])} 月做短租 + 其余月份做中租\n\n| | 每年 |\n|---|---:|\n| 短租收入 | {money(hy['str_revenue'])} |\n| 中租收入 | {money(hy['mtr_revenue'])} |\n| 成本 | -{money(hy['costs'])} |\n| **混合模式净收入** | **{money(hy['noi'])}** |",
                   f"\n### Hybrid: short-term in months {hy['str_months']} + mid-term the rest\n\n| | Annual |\n|---|---:|\n| STR revenue | {money(hy['str_revenue'])} |\n| MTR revenue | {money(hy['mtr_revenue'])} |\n| Costs | -{money(hy['costs'])} |\n| **Hybrid NOI** | **{money(hy['noi'])}** |"))
    if "mtr" in o:
        L.append(T(f"\n### 中租（30 晚以上）对比\n\n| | 每年 |\n|---|---:|\n| 中租收入 | {money(o['mtr']['revenue'])} |\n| 中租成本 | -{money(o['mtr']['costs'])} |\n| **中租净收入** | **{money(o['mtr']['noi'])}** |",
                   f"\n### Mid-term (30+ nights) comparison\n\n| | Annual |\n|---|---:|\n| MTR revenue | {money(o['mtr']['revenue'])} |\n| MTR costs | -{money(o['mtr']['costs'])} |\n| **MTR NOI** | **{money(o['mtr']['noi'])}** |"))
    if o["notes"]:
        L.append(T("\n### 已标注的假设\n", "\n### Assumptions flagged\n") + "\n".join(f"- {n}" for n in o["notes"]))
    return "\n".join(L)

def owner_spec(o, lang="zh"):
    zh = lang == "zh"; lv = o["levels"][len(o["levels"]) // 2]; p = o["property"]
    sc = o["scenarios"]; e = sc["expected"][lv]
    rng = f"{money(sc['conservative'][lv]['owner_noi'])} – {money(sc['strong'][lv]['owner_noi'])}" if "conservative" in sc and "strong" in sc else money(e["owner_noi"])
    T = (lambda zh_s, en_s: zh_s if zh else en_s)
    mname = (lambda i, m: f"{i+1}月") if zh else (lambda i, m: m)
    rows = [[mname(i, r["m"]), f"{r['occ']*100:.0f}%", money(r["adr"]), money(r["gross"])] for i, r in enumerate(e["rows"])]
    comp = [[T("短租（预期）", "Short-term (expected)"), money(e["gross"]), money(e["owner_noi"])]]
    if "hybrid" in o: comp.append([T("混合（旺季短租 + 淡季中租）", "Hybrid (peak short-term + off-season mid-term)"), money(o["hybrid"]["revenue"]), money(o["hybrid"]["noi"])])
    if "mtr" in o: comp.append([T("中租 30 晚以上", "Mid-term 30+ nights"), money(o["mtr"]["revenue"]), money(o["mtr"]["noi"])])
    if "ltr" in o: comp.append([T("长租", "Long-term lease"), money(o["ltr"]["revenue"]), money(o["ltr"]["noi"])])
    return {"type": "report", "lang": lang,
            "title": T(f"短租收益评估 — {p.get('name','')}", f"Airbnb income estimate — {p.get('name','')}"),
            "subtitle": T(f"{p.get('city','')} · {p.get('beds','?')}房{p.get('baths','?')}卫 · 估算，非保证", f"{p.get('city','')} · {p.get('beds','?')}BR/{p.get('baths','?')}BA · estimate, not a guarantee"),
            "kpis": [[T("屋主年净收入（区间）", "Owner net income / year"), rng, T(f"管理费 {lv}", f"after {lv} management fee")],
                     [T("预期入住率", "Expected occupancy"), f"{e['occ']*100:.0f}%", T("全年平均", "year average")],
                     [T("平均房价", "Average nightly rate"), money(e["adr"]), T("每晚，不含清洁费", "per night, excl. cleaning")],
                     [T("一次性投入", "One-time set-up"), money(o["setup_cost"]), (T(f"约 {o['payback_months']:.0f} 个月回本", f"payback ≈ {o['payback_months']:.0f} months") if o.get("payback_months") else "")]],
            "summary": [],
            "sections": [
                {"h": T("逐月预期", "Month by month (expected)"), "table": {"head": [T("月份", "Month"), T("入住率", "Occupancy"), T("房价", "Nightly rate"), T("总收入", "Gross revenue")], "rows": rows,
                                                                       "total": [T("全年", "Year"), f"{e['occ']*100:.0f}%", money(e["adr"]), money(e["gross"])]}},
                {"h": T("年度开支（预期）", "Annual costs (expected)"), "table": {"head": [T("项目", "Item"), T("金额", "Amount")],
                    "rows": [[(CZ.get(k, k) if zh else k), "-" + money(v)] for k, v in e["costs"].items() if round(v)], "total": [T("屋主净收入", "Owner net income"), money(e["owner_noi"])]}},
                {"h": T("出租方式比较", "Short vs mid vs long term"), "table": {"head": [T("方式", "Option"), T("年收入", "Revenue"), T("屋主净收入", "Owner net")], "rows": comp}},
            ] + ([{"h": T("待核实 / 需报价", "To confirm / quotes needed"), "bullets": cfg_needs}] if (cfg_needs := o.get("needs_quote")) else [])}

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--example":
        print(json.dumps(EXAMPLE, indent=2, ensure_ascii=False)); return
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"): print(__doc__); return
    cfg = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    o = run(cfg)
    ul = cfg.get("user_lang", "zh"); print(markdown(o, ul))
    base = os.path.splitext(sys.argv[1])[0]
    json.dump(o, open(base + "_result.json", "w", encoding="utf-8"), indent=1, default=float)
    json.dump(owner_spec(o, cfg.get("lang", "zh")), open(base + "_owner_spec.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print((f"\n（已保存：{base}_result.json · {base}_owner_spec.json → 补上 'summary' 结论后运行：python3 scripts/render.py {base}_owner_spec.json out.html）" if ul == "zh"
           else f"\n(saved: {base}_result.json · {base}_owner_spec.json → add 'summary' lines, then: python3 scripts/render.py {base}_owner_spec.json out.html)"))

if __name__ == "__main__":
    main()
