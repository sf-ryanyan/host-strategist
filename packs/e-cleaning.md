# E · 清洁与维修（精简——固定格式）

选出用户需要的格式，根据房源卡和用户粘贴的内容填写，然后返回。发给清洁工/供应商的消息用英文；给用户的说明用用户的语言（settings.md 里设置，默认中文）。任何文字中都不出现密码——写“code sent via lock app”。

## 1. 换房清洁（turnover）清单（发给清洁工，保持英文；结束时逐项打勾 + 每个房间拍照）
**Kitchen:** dishes clean & put away · dishwasher empty · fridge emptied & wiped · microwave/oven/stovetop clean · sink & faucet shiny, no drips · counters wiped · coffee station reset · trash/recycling out, new bags
**Bathrooms:** toilet disinfected · shower/tub clean, drain hair-free · mirror streak-free · floor hair-free · towels folded to standard · toilet paper + 2 spares · soap/shampoo/conditioner/body wash full
**Bedrooms:** fresh linens, beds made to photo standard · under beds & nightstands checked · closet: hangers, spare blanket & pillows · lamps work
**Living:** vacuum/mop · dust surfaces · cushions/throws staged · remotes in basket, batteries ok
**Safety & reset:** smoke/CO alarms present · extinguisher present · doors/windows lock · lock battery ok · thermostat to welcome setting · lights off · welcome note / Wi-Fi card in place
**Report:** damage or missing items (photo) · low supplies · lost & found (bag + note) · anything broken → tell the host before leaving

## 2. 排班、手机检查表、消息
- **排班 / 看板**：来自 `scripts/calendar_check.py`（指令包 J）——`<CODE>_board.json` → `scripts/render.py`。
- **手机巡检页面**（点按 Pass/Fail/N/A、实时得分、“copy result”）：`python3 scripts/tools.py inspection --property "<name>" [--items items.txt] --standard <settings 验收合格标准> --out <CODE>_inspection.html`——把文件发给清洁工/巡检员。房源专属项目：写 items.txt（每行一项，用“# Room”表示分区）。
- **清洁工和供应商消息**：`msgs/vendor.md`（CL1 派单、CL2 当天换房、CL3 宠物、CL4 返工清洁、CL5 指导、CL6 失物招领；V1–V9 供应商）。只在需要消息时才读。

## 3. 巡检（用户或清洁工的照片）→ 在对话中给出结果
通过 / 待修清单。得分 = 通过项 ÷ 检查项。低于约 95% 或缺少任何安全项 → 入住前修好。同一清洁工反复遗漏 → 简短的指导说明（具体项目 + 标准照片）。

## 4. 工单（固定格式）
```
工单  WO-[CODE]-[YYYYMMDD]-[NN]
房源：[name]   区域：[room]   报告人：客人 / 清洁工 / 用户   日期：[ ]
严重程度：1 紧急（安全、无水/暖/电、漏水、被锁门外） · 2 加急（当天：空调/暖气、热水、冰箱、唯一的马桶） · 3 常规（≤3 天） · 4 外观（排期处理）
问题：[什么问题、从何时开始、照片]
对客人的影响：[是否有人入住？下次入住时间？]
供应商：[name]  时间窗口：[date/time]  预算上限：$[ ] — 超出前先电话确认
屋主审批：需要 / 不需要（限额见设置） · 状态：open → scheduled → fixed → invoiced → billed to owner
费用：预估 $[ ] · 实际 $[ ] · 费用承担方（Charge to）：owner / guest damage / warranty
关闭备注 + 修复后照片：
```

## 5. 工单记录和供应商
- 每张工单都作为一行加入用户的 `workorders.csv`（模板 `templates/workorders.csv`）：wo_id, property, opened, area, severity, description, vendor, status, closed, cost, charge_to, reimbursable, receipt。当月关闭的、由屋主承担的可报销行会自动计入当月账单（指令包 D）。status 和 charge_to 的值保持英文（脚本会读取）。
- 供应商只能来自用户的 `vendors.csv`（模板 `templates/vendors.csv`）或用户本人——绝不编造。如果某个类别为空，说明如何寻找（推荐、持牌承包商查询、评价）以及要问什么（执照、保险、价格、非工作时间服务）。

## 6. 屋主审批（屋主的语言；超出设置中的限额时）
问题（1 行 + 照片） · 建议的修复方案 · 报价 · 为什么现在做（下一位客人 / 风险） · 拖延的代价 · “请在 [time] 前回复批准”（英文屋主：“Please reply approve by [time]”）。
紧急情况：先采取行动保护人员和房屋，再在当天通知屋主。

## 7. 补货与预防性维护（被要求时）
每个房源的备货标准量：卫生纸、厨房纸巾、垃圾袋、洗洁精、洗碗机块、洗衣液、洗手液、洗发水/护发素/沐浴露、咖啡/滤纸、茶、盐/胡椒/油、电池、灯泡。库存低于到下次补货前用量的 1.5 倍就补货。
每月：测试报警器、检查水槽下方、门锁电池。每季度：HVAC 滤网、烘干机排绒通道、深度清洁电器。每年：烘干机排风管、灭火器检查、更换床品。安排在空置的晚上进行。
