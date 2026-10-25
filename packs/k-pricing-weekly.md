# K1 · 每周定价检查（精简）

使用已保存的文件 —— 不联网。如果 `pricing_<CODE>.json` 还不存在，说明这一点，并提出做一次性设置（`packs/k-pricing-setup.md`）。

## 运行
需要：`pricing_<CODE>.json`（用户保存的规则）、最新的 `<CODE>_calendar.json`（如果没有，先运行 `scripts/calendar_check.py`）、可选的 `events.csv`、可选的当前价格（`current.csv`：date,price,min_stay —— 用户可以粘贴接下来几周的价格，由你生成文件）。
`python3 scripts/rate_plan.py pricing_<CODE>.json --calendar <CODE>_calendar.json [--events events.csv] [--current current.csv] [--as-of YYYY-MM-DD] --out <CODE>`
已内置美国联邦节假日。本地活动只来自 `events.csv`（已核实的日期）。

## 回复用户：用用户的语言（settings.md 里设置，默认中文）
1. **要改的晚数** —— 脚本输出的"需要在 Airbnb 修改的晚数"表（日期、现价 → 建议、最少入住晚数）。这是用户要在 Airbnb 里修改的内容。如果没有提供当前价格，改为展示"需要注意的日期"表。
2. 用 1–3 行说明原因（空档、临近入住、节假日、活动、底价）。
3. 只有用户需要时才附上 `<CODE>_rates.csv`（完整 90 天）。
4. 提示（每条一行，仅在属实时）：events.csv 超过约 30 天未更新或缺失 →“要更新本地活动表吗？”（定期，`k-pricing-setup.md` §Events）；未来 30 天入住率远高于目标且空档很少 →“价格可能偏低，要不要提高基础价？”。

## 快速规则（用户没给文件就提问时）
- 未来 30 天入住率 > 目标 + 20 个百分点 → 提价 5–10%；< 目标 − 20 个百分点 → 先检查价格、照片 / 标题、最少入住晚数，再考虑继续降价。
- 节假日 / 活动当晚不打折；改为降低最少入住晚数。
- 周 / 月折扣不能低于带家具月租的价格（中租价值）。
- 每个改动都要有理由；没有用户同意，绝不低于底价。
