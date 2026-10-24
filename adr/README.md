# 架构决策记录（ADR）

本目录只存**已经发生并影响后续实现**的决策，不存「打算做什么」。每条固定四段：
背景 / 决策 / 后果 / 证据。证据一律指向可复现的材料（`test-evidence.md` 章节、契约条款、脚本路径），不写「据说」。

| 编号 | 标题 | 状态 | 一句话结论 |
|---|---|---|---|
| [ADR-0001](ADR-0001-purchase-limit-scope.md) | 限购口径变更 | 已采纳 | 同一就诊人同一就诊日 1 单，跨院区共享额度；旧的「同医生同日一次 / 最多 3 单」废弃 |
| [ADR-0002](ADR-0002-suspend-two-phase-and-batch-idempotency.md) | 停诊两段式与批号幂等 | 已采纳 | 登记与处理分两步，批量按批号幂等，重复提交不放大影响面 |
| [ADR-0003](ADR-0003-active-flag-and-unique-index.md) | `active_flag` 与唯一索引 | 已采纳 | 号源不物理删除，用 `active_flag` 表达失效；唯一索引只约束有效行 |
| [ADR-0004](ADR-0004-scope-value-composite-key.md) | `scopeValue` 复合键 | 已采纳 | 停诊范围用 `scope_type + scope_value` 表达，复合键曾两次串号，现由构造器统一生成 |
| [ADR-0005](ADR-0005-time-point-format.md) | `timePoint` 统一口径 | 已采纳 | 后端统一 `HH:mm` 序列化，前端不再自行截断 `HH:mm:ss` |
| [ADR-0006](ADR-0006-three-layer-defense.md) | 三层防线 | 已采纳 | Redis 预扣 → DB 单柱 CAS → 应用重试；摘掉任一层都由压测给出对照结论 |

## 什么时候该加一条

- 决策改变了**数据形状、状态机、并发策略或契约语义**，且看代码看不出来「为什么这样」；
- 推翻过既有实现（例如口径变更），需要留下「为什么改」以免后人改回去；
- 取舍有真实代价（一致性 vs 吞吐、复杂度 vs 幂等）。

## 什么时候不该加

- 纯样式、命名、目录调整 → 走 commit message；
- 还在讨论中的方案 → 走 `ROADMAP.md` §6 待决项，定稿后再落 ADR。
