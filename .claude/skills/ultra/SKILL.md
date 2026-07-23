---
# .claude/skills/ultra/SKILL.md
name: ultra
description: 極限謹慎模式，僅用於極度複雜的一次性重大決策，日常不使用
model: opus
effort: xhigh
disable-model-invocation: true
---

這是最高規格的審慎模式，僅在使用者明確呼叫時啟動，請依以下原則進行：

1. 這是最高規格的審慎模式，僅在使用者明確呼叫時啟動
2. 對每個關鍵假設都要交叉驗證，窮盡列出可能的邊界情況與風險
3. 涉及不可逆動作（資料庫遷移、正式環境部署、金鑰異動）時，要求先產出完整計畫並列出回滾方案，再詢問是否執行
4. 完成後主動提醒使用者：這次分析已使用最高強度資源，建議切回 /normal 或 /strict 繼續日常工作
