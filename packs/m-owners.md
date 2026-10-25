# M · 屋主生命周期：季度复盘、续约、流失检查、新屋主、应收款（定期 / 深度）

只读取被要求的那一节。消息模板：`msgs/owner-lifecycle.md`（季度、续约、新屋主跟进序列、邻居）和 `msgs/owner-routine.md`（月度、维修、淡月、差评、事故）—— 只读需要的那一个。

## §Quarterly review 季度复盘（定期）
1. 收集三个 `<CODE>_<YYYY-MM>_report.json` 文件（来自每月运行），如果用户有，再加上去年同期的几个月。
2. `python3 scripts/quarter.py M1.json M2.json M3.json --title "<property> — Q<n> <year>" [--last-year ...] --lang <owner language> --out <CODE>_Q<n>`（`--lang` = 屋主语言）
3. 在 spec 里加上：`summary`（3–5 行）、评价部分（主题 + 一句引用，如果用户粘贴了评价）、维护部分（来自 workorders.csv）、2–4 个改进想法并附成本和预估效果（标明是估算）、下季度定价计划、关于屋主自用日期的问题、**需要决定的事项**；`from` 取自设置。用 `scripts/render.py` 渲染。
4. 通话议程（30 分钟）：结果 → 客人和维护 → 下季度 → 决定事项 → 问题。跟进邮件：`msgs/owner-lifecycle.md` C2。

## §Churn-risk check 流失风险检查（定期，或月度提示触发时）
按以下情况打分 低 / 中 / 高：屋主收入同比下降 > 15% 或连续 2 个月下降（高）· 屋主 30 天以上没有回应或语气变化（中）· 询问合同 / 解约，或提到自己管理 / 换其他管理方（高）· 90 天内有 2 个以上未解决的投诉（中）· 60 天内有一笔较大的意外支出（中）· 账单（invoice）/ 报告出错（高）。输出：分数、原因、一个挽留行动（业绩沟通电话、定价 / 房源改进计划、运营修正、费用 / 服务调整，或一个体面的退出方案）以及消息草稿。

## §Renewal 续约（合同周年前 60 天）
12 个月的结果（把月报或季度文件加总）、三件真正起作用的具体事情、未来 12 个月的预估范围（需要时用指令包 A 的模型）、任何条款变化都用价值来解释、清楚的下一步。草稿：`msgs/owner-lifecycle.md` I。

## §New owners 新屋主（线索管道 + 跟进）
用户自己维护的管道表：屋主 · 房源 · 城市 · 现状（自己管理 / 其他管理方 / 长租）· 阶段（线索 → 通话 → 已发评估 → 已发协议 → 已签约 → 上线准备 → 已上线）· 下一步 · 日期。发出评估后的跟进序列：`msgs/owner-lifecycle.md` J1–J4（第 0 / 3 / 10 / 21 天）。

## §Receivables 应收款（账单已付 / 未付 / 逾期）
`python3 scripts/ar.py invoices.csv [--add <CODE>_<YYYY-MM>_invoice.json] [--pay <INVOICE_NO> --amount <n> --date <d>] [--as-of <d>]`
逾期 → 警告行。如果用户需要，用屋主的语言起草一封礼貌的催款提醒（事实、金额、到期日、付款方式；逾期 30 天以上语气更坚定）。把更新后的 `invoices_updated.csv` 交给用户保存。
