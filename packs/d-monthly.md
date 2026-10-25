# D · 屋主月报 + 账单（invoice）（精简）

模式 A：Airbnb 打款给屋主；用户汇报当月情况并就自己的管理费开账单（invoice）。每个数字都用脚本算——不要把 CSV 读进对话，也不要手算。

## 步骤
1. **文件**：用户上传 Airbnb **Transaction history（交易记录）** CSV（Earnings / Transaction history → completed payouts 或 gross earnings → 下载 CSV；菜单名称可能不同）。如果当月有仍在进行中的入住，且用户希望包含它们，也请用户提供“upcoming/future”。
2. **所需信息**：月份、房源代码 + 房源名称、屋主姓名和语言、管理费 %、每次换房清洁（turnover）收费、屋主自用屏蔽晚数、可报销费用（日期、描述、金额）。从粘贴的房源卡 / `settings.md` 获取；只问缺失的。如果管理费 % 未知，照样运行——脚本会标记为"待定（TBD）"。
   - 月份尚未结束 → 照样运行，但所有内容标注“截至 <date> / to date”；月份结束前不开账单（账单日期规则见设置）。
   - 取消费收入：只有当设置 / 屋主协议规定管理费也适用于取消费时，才加 `--fee-on-cancellations`。
   - 屋主自用屏蔽晚数：用 0，除非房源卡、用户或日历显示有屋主自住。
   - 脚本会根据系统时钟警告“本月还没结束”；如果用户说月份已结束（或对话中的日期更晚），用 `--as-of YYYY-MM-DD` 重新运行。
3. **运行**：
   `python3 scripts/airbnb_month.py FILE.csv --month YYYY-MM --listing "<name>" --mgmt-pct <n> --cleaning-per-turn <n> --blocked <n> [--workorders workorders.csv] [--expenses exp.csv] [--prev <last month>_report.json] --owner "<name>" --property "<name>" --lang <屋主语言 zh|en> --occ-target <settings 入住率门槛> --drop-pct <settings 收入下降门槛> --out <CODE>_<YYYY-MM>`
   - `--lang` 决定屋主月报和账单的语言（也决定屏幕输出语言）。屋主要英文时用 `en`，再用用户的语言向用户总结。
   - `--workorders`：如果用户上传了自己的 workorders.csv，当月关闭的、由屋主承担的可报销工单会自动加入（不要再在 expenses 里重复列出）。
   - `--expenses`：用户垫付的其他费用（`date,description,amount,receipt`）——根据他列出的内容创建该文件。
   - `--prev`：上月的报告 JSON（如果用户保存了）→ 生成环比一行，收入下降 > 15% 时给出提示。
4. **检查输出**：“警告”（OVERLAP 订单重叠、重复行、其他房源、本月还没结束、打款不符、未完成的紧急工单）、“其他行”、调整项 → 每项用一行向用户解释；OVERLAP 或打款不符通常意味着数据有问题——开账单前先问用户。费用信息不完整 → 直接说明。“可选提示” → 询问用户，用户说要才做。
   - 屋主报告会把只在本月退房的入住列为“0（本月退房）”，使清洁次数与账单一致。

## 回复用户（用用户的语言（settings.md 里设置，默认中文），简短）
- **本月结论**：2–3 行（收入、入住率、ADR；如用户提供了上月数据则与上月对比；主要原因）。
- 脚本输出的关键表格（直接复制，不要重新输入数字）。
- **需要注意**：调整项、退款、索赔、空档、评价——仅在有时列出。
- **跟屋主怎么说**（屋主的语言）：3–5 句——结果、原因、一个亮点、一个正在改进的点、账单金额和到期日。
- 询问：“要生成屋主月报 PDF 和 invoice 吗？”——只有对方说要才生成。

## 屋主月报 + 账单（被要求时）
- 月报：打开 `<out>_report.json`，添加 `"summary"`（用屋主语言写 3–4 行短句）和 `"from"`（来自设置的姓名 + 电话 + 邮箱）；可选添加一个 `"sections"` 项写下月展望或备注。运行 `python3 scripts/render.py <out>_report.json <out>_report.html`。
- 账单：打开 `<out>_invoice.json`，添加 `invoice_no`（设置中的格式）、`date`、`due`（设置）、`from`、`to`、`notes`（设置中的付款方式——如为空，问用户；“Details: monthly report attached”）。运行 `python3 scripts/render.py <out>_invoice.json <out>_invoice.html`。如果 `"complete": false`，停下来询问缺失的费用。
- 把两个文件发给用户。可在浏览器中打印为 PDF。
- Google Sheet：`<out>_ledger.csv`（row_type = stay / adjustment / invoice）——告诉用户把它导入/追加到自己的总表（所有房源一个标签页；按房源筛选）。
- 应收账款：账单定稿后，运行 `python3 scripts/ar.py invoices.csv --add <out>_invoice.json`（如果用户还没有清单就新建一个），并把 `invoices_updated.csv` 交给用户。
- 屋主邮件：`msgs/owner-routine.md` A（只在用户需要邮件时才读）。
- 告诉用户保留 `<out>_report.json`——下月对比和季度回顾都要用。

## 规则
- 按入住日期计算：房租按当月所占晚数拆分；清洁费计入入住所在月份；换房清洁次数 = 当月退房次数。
- 屋主收入取自 Airbnb 的数字（已扣除 Airbnb 费用）。Airbnb 代收的税不是屋主收入。
- 可报销费用必须有收据或用户确认。
- 绝不为了好看而改数字；改为解释原因。
