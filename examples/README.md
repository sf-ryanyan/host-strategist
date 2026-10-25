# 示例数据 · 试跑指南

> 本文件夹里的所有房源、客人、屋主、订单号和金额都是**虚构的**，只用于演示。请不要把真实的客人或屋主资料放进公开仓库。

## 文件说明
| 文件 | 内容 |
|---|---|
| `airbnb_transactions_2026-10.csv` | Airbnb 交易记录（Transaction history）示例：订单、打款、纠纷赔付、取消费 |
| `airbnb_calendar.ics`、`vrbo_calendar.ics` | 两个平台的日历导出示例（故意放了一个跨平台重叠，用来演示警告） |
| `reservations.csv` | Airbnb 订单导出（Reservations）示例 |
| `pricing_WIL01.json` | 定价规则示例 |
| `events.csv`、`current_prices.csv` | 本地活动示例、Airbnb 当前价格示例 |
| `workorders.csv`、`invoices.csv`、`compliance.csv` | 工单、账单、合规到期示例 |
| `evaluation_input.json` | 评估测算输入示例 |

## 方法一：在 Claude 里试（推荐）
安装技能后，开一个新对话，上传对应文件，然后说：
- 上传 `airbnb_transactions_2026-10.csv` 和 `workorders.csv` → "用示例数据做 Willow 2BR 的 10 月月报，管理费 20%，每次清洁收 120 美元"
- 上传两个 `.ics` → "检查一下日历，今天按 2026-11-01 算"
- 上传 `pricing_WIL01.json` → "做这周定价，今天按 2026-11-01 算"
- 上传 `evaluation_input.json` → "用这个输入做一次评估测算"

## 方法二：在自己电脑上运行脚本（需要 Python 3）
在项目根目录运行：
```
python3 scripts/airbnb_month.py examples/airbnb_transactions_2026-10.csv --month 2026-10 --listing "Willow" --mgmt-pct 20 --cleaning-per-turn 120 --workorders examples/workorders.csv --owner "示例屋主" --property "Willow 2BR (Example)" --as-of 2026-11-02 --out WIL01_2026-10
python3 scripts/render.py WIL01_2026-10_report.json report.html
python3 scripts/calendar_check.py examples/airbnb_calendar.ics examples/vrbo_calendar.ics --property "Willow 2BR (Example)" --as-of 2026-11-01 --out WIL01
python3 scripts/rate_plan.py examples/pricing_WIL01.json --calendar WIL01_calendar.json --events examples/events.csv --current examples/current_prices.csv --as-of 2026-11-01 --out WIL01
python3 scripts/ar.py examples/invoices.csv --as-of 2026-11-20
python3 scripts/tools.py expiry examples/compliance.csv --as-of 2026-11-01
python3 scripts/tools.py inspection --property "Willow 2BR (Example)" --out inspection.html
python3 scripts/str_model.py examples/evaluation_input.json
```

## 预期结果（核对用）
- 10 月月报：已订 15 晚 / 31 晚，入住率 48.4%，平均房价 $250.67，屋主收入 $3,684.20，换房清洁 4 次，账单合计 $1,153.94；会出现两条警告（未完成的紧急工单、纠纷赔付和代垫费用同时存在）。
- 日历检查：发现 1 个跨平台订单重叠（11/12–11/14），1 个空档（11/09，2 晚）。
- 定价：感恩节（11/25–11/28）自动加价，最少入住 3 晚；需要修改的晚数 3 个。
- 账单追踪：9 月账单逾期。
- 合规：灭火器年检和短租登记在 60 天内到期。
