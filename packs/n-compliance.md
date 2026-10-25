# N · 合规登记表和续期（定期）

只跟踪日期；规则本身在需要时按 `ref/south-bay.md`（或用户自己的 `ref/market-*.md`） 去查（深度，注明来源）。

## 到期检查（每月，或与月报一起）
`python3 scripts/tools.py expiry compliance.csv [--as-of YYYY-MM-DD] --days <settings 到期警告窗口，默认 60>`
汇报警告行（已过期 / 在提醒窗口内）以及任务负责人。超过一年前核实的条目 → 给一条可选提示，建议重新核对规则。

## compliance.csv 里要记录什么（每个房源每个事项一行）
短租登记 / 许可证（号码存在文件里，不写在聊天里）· 营业执照 · 住宿税（transient occupancy tax）账户（仅作参考）和申报频率 · HOA 批准文件日期 · 屋主短租保险到期日 · 烟雾 / 一氧化碳报警器测试（每月）· 灭火器保养 · 安全检查（如果城市要求）。列：property,item,number_ref,issued,expires,renew_lead_days,task_owner,source,verified_on,notes（模板：`templates/compliance.csv`）。

## 有事项到期时
起草办理步骤（在哪里续期、需要的文件、费用 —— 来自今天查看过的官方页面，注明来源），如果需要屋主操作，再起草一条给屋主的消息。绝不凭记忆说出费用或规则。

## 新城市或规则变化（深度）
使用 `ref/south-bay.md`（或用户自己的 `ref/market-*.md`） 里的检查清单并联网搜索（额度 ≤ 6），每条规则都注明来源和日期，把核实过的事实加到 `settings.md` → 已核实事实记录（用户更新自己保存的那份）。
