# 用户自己保存的数据文件（放在一个文件夹，或 Google Drive）

Claude 无法在不同对话之间记住文件。请把这些文件保存在你自己的文件夹里，做某项任务时上传需要的那个。

| 文件 | 内容 | 何时更新 |
|---|---|---|
| `pricing_<CODE>.json` | 每个房源的定价规则（来自 `scripts/rate_plan.py --example`） | 定价设置时生成，之后每周重复使用 |
| `events.csv` | 已核实的本地活动（start,end,name,uplift_pct,min_stay,source,verified_on） | 每月活动更新 |
| `workorders.csv` | 工单记录；向屋主收费、可报销的工单会计入账单（invoice） | 每次维修 |
| `invoices.csv` | 屋主账单和付款（paid / open / overdue） | 每次开账单 / 收款（`scripts/ar.py`） |
| `compliance.csv` | 许可证、登记、保险、安全设备的到期日期 | 有事项续期时（`scripts/tools.py expiry`） |
| `vendors.csv` | 清洁工和各类工种，每个关键类别两家 | 供应商变动时 |
| `<CODE>_<YYYY-MM>_report.json` | 月度结果（用于和上月对比及季度复盘） | 每月（`scripts/airbnb_month.py`） |
| `ledger.csv`（Google Sheet） | 追加每个月的 `_ledger.csv` | 每月 |

标有 EXAMPLE 的行是占位示例 —— 请删除。

**注意：** 列名（第一行）保持英文，脚本按列名读取，请不要修改。`workorders.csv` 里 `status`（open / scheduled / fixed / invoiced / billed）、`charge_to`（owner / guest damage / warranty）、`reimbursable`（Y / N）也必须用英文值，月报脚本会按这些值把工单计入账单。
