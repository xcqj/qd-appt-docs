# 号源 QueueDepth · 切片排期（ROADMAP）

> **本文档是「什么时候做、做到什么算完」的单一权威。**
> 「做什么 / 不做什么 / 为什么」在 `PRD.md` §13.1（MVP 范围）与 §13.2（后续迭代），此处不重复。
> 排期为参考节奏，**非硬性期限**（PRD §13.3）。字段级设计看 `database-design.md`，接口看 `api-contract.md`，红线看 `redlines.md`。
>
> **协作约定（2026-10-19）**：每个 S/E 切片由用户**显式开启**才进入开发；切片收尾后必须停止，**不自动进入下一片**。开场卡/收尾协议见 `AGENTS.md`（项目级）。

- 项目：号源 QueueDepth（代码缩写 `appt`），四仓：`qd-appt-{backend,admin,app,docs}`
- 建档：2026-10-18 ｜ 状态：v0.7.10（2026-10-30，S1–**S16.1** 已完成；S16.2 未开始，阻塞于服务器）

---

## 1. 文档分工（避免双权威漂移）

| 问题 | 权威位置 |
|---|---|
| 做什么 / 不做什么 / 为什么 | `PRD.md` §13.1 / §13.2 |
| **顺序 / 验收 / 进度 / 完成与否** | **本文件** |
| 字段怎么存 | `database-design.md` |
| 接口长什么样 | `api-contract.md` |
| 代码红线与坑位 | 各仓根目录 `AGENTS.md` |

判据：含「范围 / 边界 / 不做」的留 PRD；含「顺序 / 时间 / 进度」的来这里。两处都能改必然漂移。

---

## 2. 切片总览

状态：完成 / 进行中 / 未开始。

| 切片 | 内容 | 里程碑（验收口径） | 涉及仓库 | 前端归属 | 集成测试 | 状态 |
|---|---|---|---|---|---|---|
| **S1** | 数据建模 + 建表 + 基础数据维护（院区 / 门诊类型 / 科室树 / 医务人员 / 收费标准 / 时段模板） | 后台可维护基础数据 | docs / backend / admin | plus-ui：六实体维护页 | — | **已完成 2026-10-19** |
| **S2** | 排班生成（`SlotTemplate` → 批量生成 `time_point`）+ 放号任务（**停诊登记移至 S6b**） | 能按时刻生成并开放号源 | docs / backend / admin | plus-ui：排班生成页 | ④ | **已完成 2026-10-20** |
| **S3** | 挂号链路 + 并发三道防线 + 限购与冲突校验 | 高并发争抢正确性达标 | docs / backend（admin 只读页） | uni-app（**延后**） | ① | **已完成 2026-10-20** |
| **S4** | **支付链路**：支付单 + 渠道抽象 + 模拟渠道 + 回调幂等 + 超时关单与回补 | 交易链路闭环 | docs / backend | uni-app（**延后**） | ②③ | **已完成 2026-10-20** |
| **S5** | 排班/医生查询接口 + 午别余量批量聚合 + 缓存 | 性能对比可演示 | docs / backend / admin | plus-ui：排班页余量 | ⑤ | **已完成 2026-10-20** |
| **S6a** | 退号与退款、签到（分诊端扫码）、爽约扫描 | 状态机闭环（除停诊） | docs / backend / admin | uni-app（**延后**） | ⑥ | **已完成 2026-10-20** |
| **S6b** | 停诊批量流转、黑名单、分诊台模式 | 批量操作不重不放 | docs / backend / admin | uni-app（**延后**） | — | **已完成 2026-10-21** |
| **S7** | 对账（号源 + 支付）+ 台账 + 看板 + 业务数据 seed | **后端 + 后台 v1 可交付**（移动端见 S10/S11） | docs / backend / admin | plus-ui：看板与对账页 | — | **已完成 2026-10-21** |
| **S8** | 患者辅助组：收藏 D1–D3 / 消息 D4–D6 / 分诊当日签到列表 E3 | uni-app（E5）前补齐最后 7 个 P1 端点 | docs / backend | — | — | **已完成 2026-10-21** |
| **S9** | 就诊人管理 B6–B10（列表/新增/修改/删除/设默认） | E5 最后一个后端硬前置（B1 挂号必须传 `patientId`） | docs / backend | — | — | **已完成 2026-10-22** |
| **S10** | 患者端主链路：登录 + 双角色骨架 + 首页/院区/科室/医生/排班/选时间/确认预约/支付/我的预约 | 可演示「挂号 → 支付 → 我的预约」全链路 | docs / app（+backend 两处补口） | uni-app（患者端） | — | **已完成 2026-10-22** |
| **S11** | 患者端辅助页 + 分诊台：我的就诊人/我的医生/消息/预约详情（就诊码）/扫码签到/手动补签/当日签到列表 | 双角色页面全齐，接口全部有来源 | docs / app（+backend 两处口径收口） | uni-app（患者端 + 分诊台） | — | **已完成 2026-10-23** |
| **S12** | **品牌与首屏**：logo / favicon / tabBar 图标；后台品牌变量与登录页；**后台首页换预约运营看板**；患者端首页·详情·我的三屏抛光 | 三端有统一标识，首屏不再像脚手架 | docs / app / admin | uni-app + plus-ui | — | **已完成 2026-10-24** |
| **S12.5** | **全站视觉统一**：后台主题色/表格/状态标签/空态；移动端剩余 7 屏走查 | 后台与移动端「像一套产品」 | docs / app / admin | uni-app + plus-ui | — | **已完成 2026-10-24** |
| **S13** | **门面与物料**：根 README / `DEMO.md` 剧本 / 截图与 GIF / ADR 索引 / SpringDoc 入口 | 30 分钟能跑起来，5 分钟能讲完 | docs / app / admin / backend / showcase | — | — | **已完成 2026-10-24** |
| **S14** | **一键演示**：`demo.sh` + 镜像构建 workflow（api / snailjob / admin / h5 四枚）+ 环境变量模板 | 空机器一条命令起全栈 | docs / backend / app / admin / showcase | docker compose | — | **已完成 2026-10-25** |
| **S15** | **医院感细节**：流程引导条 / 院区信息页 / 须知与规则页 / 免责与急诊提示 | 不像 demo，像一家医院的系统 | docs / app | uni-app | — | **已完成 2026-10-26** |
| **S15.1** | **SnailJob 任务补种**：爽约扫描 / 置完成 / 日终对账三条任务固化进 seed | 换机或起 demo 容器即按 cron 自动跑，不再靠手工点 | backend / docs | SnailJob | S14 边界欠账 | **已完成 2026-10-26** |
| **S15.2** | **已签到入口补口**：我的预约四个 tab 不含 `SIGNED`，已签到的预约在列表里没有入口 | 患者能在列表里找到已签到的预约 | docs / app | uni-app | S15 验收发现 | **已完成 2026-10-26** |
| **S15.3** | **终态号源释放**：`NOSHOW` / `COMPLETED` 不迁 Slot，对账 R1 每天报几百条幽灵占号 | 终态流转即释放号源，R1 只剩真脏数据 | backend / docs | — | S15.1 实测发现 | **已完成 2026-10-26** |
| **S16.1** | **部署形态与 wsl 发布链**（不依赖服务器）：compose 去 `build:` + 统一部署入口 `deploy.sh` + 镜像首推 GHCR + 备份 / 健康检查 / 日志轮转 | 拉同一镜像一次起全栈、可回滚、可重来 | docs / backend / showcase | docker compose / GHCR | S16 拆分（2026-10-29） | **已完成 2026-10-30** |
| **S16.2** | **云目标与公网 HTTPS**（依赖服务器）：服务器 + 域名 + HTTPS + 反代 + 小程序合法域名 +（可选）监控 | 公网 HTTPS 可访问、小程序真机扫码 | docs / backend / app / admin | Caddy / SSH | S16 拆分（2026-10-29） | **未开始（阻塞：服务器未就绪）** |

**阶段划分（2026-10-24 定）**：S1–S11 为「功能阶段」（可演示全链路，已完成）；**S12–S16 为「交付阶段」**（品牌、视觉、门面、一键演示、线上部署）。
交付阶段的共同验收口径：**① 三端截图对照通过 ② 无框架默认文案残留 ③ 门禁全绿 ④ 文档与实现零偏差**。S16 已拆为 **S16.1**（不依赖服务器：compose 去 `build:` / 部署脚本 / 镜像首推 / wsl 发布链）与 **S16.2**（依赖服务器：云目标 + 公网 HTTPS）；前者可立即开工，后者等服务器到位。

**集成测试**（定义见 PRD §12，此处绑定切片）：
- ① 50 并发争抢同一时间点，恰好 1 笔成功 —— S3（**2026-10-20 通过**：1 成交 / 49 `SLOT_GONE`）
- ② 超时关单 → 号源回补 → 可被再次预约 —— S4（**2026-10-20 通过**）
- ③ 支付回调重复 3 次仅入账 1 次 —— S4（**2026-10-20 通过**：回调记录 1 条、入账 1 条）
- ④ 同一医生/同一天重复执行排班生成，第二次新增 0 条（幂等）—— S2（**2026-10-20 通过**：80/2820 → 0/0/2820）
- ⑤ 余量缓存写入后与 DB 聚合差值在读路径/TTL 内收敛为 0 —— S5
- ⑥ 爽约扫描某一轮被跳过，下一轮全量兜底不漏判 —— **S6a（2026-10-20 通过**：−3h 陈旧单由兜底批判为 `NOSHOW`）

**前端归属说明**：PRD §13.3 原注只写了「uni-app 患者端页面穿插于 S3~S6；分诊台模式在 S6」，**未写 plus-ui 后台页面的切片归属**。上表按里程碑反推补齐（见待决项 5）。**患者端（uni-app）整体延后**：2026-10-19 拍板「先完成后端与后台管理，再做患者端」，故 S3/S4/S6a/S6b 的患者端归属标「延后」——这些切片的验收以 **API 级集成测试**为准，不依赖 UI 完成。

---

## 3. 逐切片验收清单

### S1 数据建模与基础数据（已完成 2026-10-19）

- [x] `database-design.md` v0.1（20 表字段级设计 + 索引总表 + 不变量映射）
- [x] `appt_schema.sql` 20 表在 `appt` 库建成（2026-10-18，backend `0f0bfff`）
- [x] I1 兜底实测：同一 slot 有效单成功 / 终态单（`active_flag=NULL`）共存 / 第二笔有效单被 `uk_reg_slot_active` 以 1062 拒
- [x] 20 张表走 RuoYi 生成器，按 `backend/AGENTS.md` **§6** 坑位手工校正（§4 是领域红线，生成器坑位在 §6）——2026-10-19 六个坑位全部处理（append-only 删写端点 / 删除前引用校验 / 唯一键重新启用 / import 清单 / 输入侧类型 / 注释内嵌字典）
- [x] 后台六实体维护页可用（院区 / 门诊类型 / 科室树 / 医务人员 / 收费标准 / 时段模板）——2026-10-19 六页 CRUD + 导出走查通过
**三条实现约束落地**（不设 `del_flag` 的还债，缺一即出 bug；三条中 2 条已完成，第 2 条待 S9）：
  1. [x] 物理删除前做引用校验——被 `schedule` / `slot` / `registration` 引用的基础数据拒绝删除并提示先停用（2026-10-19：campus / clinicType / department / medicalStaff 已实现；slot_template、fee_standard 无被引用表）
  2. [ ] 前台下拉（院区 / 科室 / 医生 / 就诊人）一律带 `status='0'`；后台列表不过滤（否则无法恢复）——院区/科室/医生下拉已随 S2/S5 带过滤；**就诊人下拉待 S9**（B6 落地后补）
  3. [x] 唯一键冲突走「命中停用行则重新启用」而非 insert（`uk_clinic_type_code` / `uk_template_staff_period_type` / `uk_fee_title_type` / `uk_patient_id_hash`）——**四条全部实现**（`uk_patient_id_hash` 于 2026-10-19 随 `IdNoEncryptor` 接入：新增时算 HMAC-SHA256 摘要，撞停用行复用原 id 并重启）
- [x] 初始数据脚本（S1 六表基础数据，2026-10-19 `appt_s1_seed.sql`：3 门诊类型 / 3 院区 / 40 科室三级树 / 60 医务人员 / 15 收费标准 / 80 时段模板；业务数据 seed 随各切片）

### S2 排班生成与放号（已完成 2026-10-20）

- [x] 前置（2026-10-19）：`slot` 删除校验有效挂号（契约 §8.1-7）、`slot_template` 删除校验已生成排班（§8.1-5）
- [x] 模板 → 批量生成 slot，`UNIQUE(schedule_id, time_point)` 防重，并发撞键重算重试 —— 2026-10-19：`SlotGenerateService` 两阶段（plan 只读 → apply 落库），按 (staff, 日期) 一事务，撞键跳过并计 `skippedCount`，重跑新增 0
- [x] 放号按 D1：可约 `[今日+1, 今日+7]`，每日 08:00 放第 7 天，策略可配 —— 2026-10-19：`@JobExecutor(name="apptReleaseJob")` + Redisson `tryLock(0,-1)` + `appt_job_log` 留痕 + 启动补偿；**2026-10-20 控制台验收通过**：首轮 80 排班 / 2820 号源，连跑两次均 `SUCCESS` 且新增 0 / 跳过 2820（幂等生效，集成测试④达成）
- [ ] 停诊**登记**（E5/F2 登记端点 + `suspend_record` 落库，批号预生成，按日拆分共用批号）—— **2026-10-19 确认移至 S6b**：与批量处理一并做（S2 只做生成与放号）

### S3 挂号链路与并发

- [x] 三道防线：Redis 占位 → DB CAS → 唯一索引兜底 —— 2026-10-20：`SlotStateService`（`SET NX EX 15min` 占位 / `AVAILABLE→TAKEN` CAS + 台账 / Lua 比对 value 安全释放；Redis 异常降级为纯 DB）
- [x] 限购三条（同人同时段 / 同人同科室同日 / 号源唯一）—— 2026-10-20：`sys_user` 账号行 `FOR UPDATE` 串行化 + 锁内精查（精确错误码）+ 三条复合唯一索引兜底
- [x] 集成测试① —— 2026-10-23 复跑通过：`PASS=11 FAIL=0 SKIP=0`（50 并发 1 成交 + 49 `SLOT_GONE`；同 key 双击 `duplicate=true` 且仅 1 单；**限购改为「同一就诊人同一就诊日 1 单」后同日跨科室被 `LIMIT_PATIENT_DAY` 拦下、不同就诊日各下 1 单均可成功**；窗口外 `OUT_OF_WINDOW`；占位键存在）。断言数由 14 → 11 是因为原「限购三条」合并为一条规则，脚本 `backend/script/test/s3_b1_concurrency.sh`
- [x] 降级对照实验 —— 2026-10-20：`--appt.slot-hold.enabled=false` 摘除防线① 后重跑，仍 `PASS=14 FAIL=0`（1 成交 / 49 由 DB CAS 拒绝，无占位键），证据见 `test-evidence.md` §3
- [ ] 患者端主链路页面（uni-app）—— **归 S10**（2026-10-21 排片），本项不再在 S3 跟踪

### S4 支付链路（已完成 2026-10-20）

- [x] `PaymentChannel` 接口 + `MockPaymentChannel` —— 2026-10-20：create/query/close/refund 四方法，tradeNo 由支付单号确定性派生（保证回调去重键非空稳定）
- [x] 回调：验签 → append-only 落库 → 立即 ack → 异步入账；「钱到了号没了」分支 —— 2026-10-20：C1/C5 共用 `PaymentCallbackDispatcher`，入账走有界线程池 + 新事务；关单后回调 → 自动建退款单 → 退款回调 CAS 置 `REFUNDED`
- [x] 超时关单与号源回补（30 秒巡检两段式）—— 2026-10-20：`apptPaymentCloseJob`（近过期查单 + 到期关单）+ 三步 CAS + `RELEASE` 台账 + 释放占位；C2 `TIMEOUT` 复用同一关单服务
- [x] 集成测试②③ —— 2026-10-20 实测 `PASS=20 FAIL=0 SKIP=0`（回调 3 次仅 1 次入账、关单回补后可再约、关单后回调走退款、并发 5 次关单仅 1 次生效、篡改签名被拒）

### S5 查询聚合与缓存

- [x] 公共查询组 A1–A7（`/appt/public/**`，全匿名）—— 2026-10-20：`PublicCatalogService`（院区 / 科室树剪枝 / 医生分页与主页 / 可约时间点）+ `PublicScheduleQueryService`（日期栏双模式 / 当日出诊医生 + 午别余量）；5 个 `schedule/controller/Public*Controller`；`security.excludes` 原有 `/appt/public/**` 白名单即可，未改配置；图片字段按项目约定返回**原始值 + `coverImageUrl`/`avatarUrl`**（`@Translation` 翻译 ossId，前端按 `*Url || *` 兜底）
- [x] 午别余量一次批量聚合（动态分组，不写死上午/下午）—— `ApptSlotMapper.countByScheduleGroupPeriod`：`GROUP BY schedule_id, period` 一条 COUNT，走 `idx_slot_schedule_status`；单屏 `/schedule/staffs` ≤3 条 SQL（排班 + 医生资料 + 余量）
- [x] Redis `appt:remain:` 缓存，写路径唯一入口 + Lua EXISTS 守卫 —— `RemainService`：MGET 批量读 → 未命中回源聚合 → `SETNX` 回填 TTL 600s；`SlotStateService.occupy / releaseToPool` 在事务 `afterCommit` 经 Lua `EXISTS → INCRBY ±1`（无键不创建）；`appt.remain.cache=redis|db` 开关，db 模式读写两侧旁路
- [x] 写路径增量语义按 target 分支：可约→已占 −1、已占→可约 +1、已占→已过期 0（红线 9，过期不是回池）
- [x] admin 排班页「余量」列（与患者端同一 `RemainService`/缓存口径；`@ExcelIgnoreUnannotated` 保证不进导出）
- [x] 手工验收 2026-10-20：A1 封面 ossId 翻译 / A3 分页+关键字 / A4 匿名 200 + 不存在 404 / A5 医生模式定长 7 项 / A6 下单 −1 与 `remain=0` 仍返回 / 参数缺失与类型错误 400 / 后台余量列与导出
- [x] 验收：单屏由 M×2 次 COUNT 降至 1 次聚合，压测对比留档 —— 2026-10-20 实测：冷启动 3 条 SQL / 缓存命中 2 条 / `db` 3 条（与医生数无关）；100 并发 ×1000 样本，`redis` p95 9.3ms、`db` p95 10.6ms、命中率 100%；1000 次挂号/关单后缓存 vs DB 差值 0（`PASS=11 FAIL=0`）；S3 `PASS=14`、S4 `PASS=21` 回归通过。详见 `test-evidence.md` §7

### S6a 状态机闭环（退号 / 退款 / 签到 / 爽约）

> **顺序（2026-10-20 定）**：先 S6a 后 S6b，不合并。S6b 的停诊处理 = 批量「被动退号 + 退款」，必须复用 S6a 的退号单柱；黑名单的计数来源（退号 / 爽约）也全在 S6a 产生。

- [x] 退号与退款（含 `settle_status` 流转）、签到（扫码 + 手动补签）、爽约扫描（半开窗口 + 全量兜底）—— 2026-10-20：`RegistrationCancelService`（单柱 CAS + 回池 + 事务内建退款单 + 事务外渠道退款 + `CANCEL_SUCCESS` 站内信）、`SignService`（E1/E2 同一边，仅 `sign_type` 区分）、`ApptNoShowJobService`（主批 `[now-35m, now-30m)` + 全量兜底 `<= now-35m`，同轮扫号源过期）
- [x] 6 种状态覆盖：`BOOKED→CANCELED_ACTIVE / SIGNED / NOSHOW`、`SIGNED→COMPLETED` —— 2026-10-20：四条边全部收敛到 `RegistrationStateService`（`markCanceledActive/markSigned/markNoShow/markCompleted`），`ApptCompleteJobService` 每日 23:30 置完成
- [x] 集成测试 ⑥：某轮扫描被跳过，下一轮全量兜底不漏判 —— 2026-10-20 实测通过：脚本用「`time_point=now-3h` 的陈旧单」等价模拟窗口已滑过，兜底批判为 `NOSHOW`（`s6a_state_machine.sh` `PASS=19 FAIL=0`，见 `test-evidence.md` §8）
- [x] 退号时限语义：截止 `visit_date - 1 天 23:00:00`，`now < 截止` 才可退；截止后不提供该分支（PRD §6.7 / 契约 §4.5）—— 用例 2 断言 `REFUND_DEADLINE_PASSED`
- [x] 状态流转**显式写 `update_time`**：黑名单按「状态流转时间近 180 天」统计，而 MyBatis-Plus 自动填充对 `update(null, wrapper)` **不生效**，不显式 `set` 就没有窗口基准（PRD §6.9）—— 四条新边与既有 `markBooked/markClosed/markSettled` 全部补上
- [x] `RemainService` 接入两个新调用点：退号回池 `TAKEN→AVAILABLE` **+1**、过期扫描 `AVAILABLE→EXPIRED` **−1**；`TAKEN→EXPIRED` 保持 0（技术方案 §3.2）—— `SlotStateService.expire()` 与 `releaseToPool` 分属两个方法，语义不合并
- [x] 后台手动退号（管理端）：不受 23:00 限制，状态记 `CANCELED_ACTIVE` 且**计入**黑名单统计（避免成为绕过口）—— `POST /appt/admin/registration/{id}/cancel` + 挂号单列表「退号」按钮
- [x] 附带：B2 我的预约列表 / B3 预约详情（含就诊码、证件号脱敏）—— 患者端退号链路的入口
- [x] 附带：`POST /appt/admin/job/{jobName}/run` 任务手动重跑（白名单 4 个任务 + `appt:job:run`），解决 SnailJob 无法从 HTTP 触发、脚本无法自验的问题（技术方案 §3.3 原本要求）
- [x] 联调数据：`appt_s6a_seed.sql` 造 `triage` 角色 + `appt_triage` 账号 + 两个按钮权限（缺任一则签到 403 / 后台按钮不显示）

### S6b 停诊批量与风控（处理 / 黑名单 / 分诊台）

- [x] 停诊**处理**（F2）：批量被动退号 + 退款 + 通知，批号 CAS 守卫、分批事务（≤100/批）；**复用** S6a 的 `RegistrationStateService`（被动退号），不另写状态 UPDATE；`RemainService` 接入 `AVAILABLE→SUSPENDED` **−1** —— 2026-10-21：`SuspendHandleService`（Redisson 批号锁 + 每批一事务 + 完成后 CAS `PENDING→HANDLED`）、`markCanceledPassive`、`ScheduleStateService.markSuspended`、`SlotStateService.suspendAvailable/suspendTaken`；`WAIT_PAY` 单同步关支付单、已签到单跳过并在摘要计数
- [x] 停诊**登记**（E5，S2 移入）：区间支持 + 同范围幂等 + S 前缀批号 —— 2026-10-21：`SuspendScopeParser` 把区间编码进 `scope_value`（一条登记一个批号，规避 `uk_suspend_batch` 与「拆 N 条」的冲突）；起止跨度 ≤31 天、起始日不早于今天
- [x] 黑名单（半年内退号+爽约 ≥6 → 限制半年）+ 限购校验接入；统计口径见 PRD §6.9 / 契约 §4.5：计入 `CANCELED_ACTIVE` + `NOSHOW`，不计 `CANCELED_PASSIVE` + `CLOSED`，按 `user_id` + `update_time` 近 180 天（**D-S6-1**）—— 2026-10-21：`BlacklistService` 下单前惰性判定（账号行锁内计数，达阈值走 `REQUIRES_NEW` 独立事务建名单 + `BLACKLIST_HIT`，避免被外层回滚带走）；到期按 `end_time` 自然失效，人工解除沿用后台编辑 `status='1'`
- [x] 站内信：`SUSPEND_CANCEL`（按账号聚合，一账号一条）+ `BLACKLIST_HIT` —— 页面「运维对账 → 站内信」可见「停诊取消 / 黑名单生效」两类
- [x] 验收 2026-10-21：`s6b_suspend_blacklist.sh` `PASS=25 FAIL=0 SKIP=0`（登记幂等 / 处理 8 项 / 已签到跳过 / 余量 5→4 / 重复处理 / 黑名单拦截与建单）；后台「处理」按钮摘要「排班 1 / 号源 2 / 被动退号 1 / 退款 1 / 跳过已签到 1」，挂号单（已退号(被动)+停诊批号）、退款单、站内信、排班（已停诊）四处页面与接口一致；回归全绿：S6a `PASS=19 FAIL=0`、S4 `PASS=21 FAIL=0`、S3 `PASS=14 FAIL=0`（后者同时修了 `LIMIT_HOLD_MAX` 的选号脚本）
- [ ] 分诊台模式（uni-app 同仓按角色切换，**延后**）

### S7 对账与交付

- [x] 号源 + 支付对账（七查）、台账、看板 —— 2026-10-21：`reconcile` 包（`ReconcileCheck` 扩展点 + 七个实现 + `ReconcileResultRecorder` + `ReconcileService` 单项隔离）、`POST /appt/admin/reconcile/run`（`appt:reconcile:run`）、`apptReconcileJob`（03:00，已加入任务手动重跑白名单）；`SlotStateService.reclaimGhost`（幽灵占号回收，无有效单才动手）；`dashboard` 包（7 指标 + 科室 TOP5）+ 后台看板页（卡片 + echarts 柱图）+ 对账页「立即对账」按钮
- [x] 业务数据 seed（~500 排班 / ~9000 号源 / ~2000 挂号单覆盖 8 状态）—— `appt_s7_business_seed.sql`：500 排班 / **9000 号源** / **2000 挂号单**（8 状态齐全）+ 2000 支付单 / 360 退款单 / 620 台账；先清业务表后灌、可重复执行，灌完自洽性检查 `ghost_slots=0 / unoccupied=0`（实测耗时 ~45s）。**踩坑记录**：有效单受 `uk_reg_patient_time` 约束，2 位就诊人只能撑 288 张，必须补到 10 位就诊人（PRD §6.5 上限）
- [x] 交付验收：README 启动步骤可用 + 三条集成测试留档 —— `docs/README.md` 增「三步启动 + 演示入口」，`test-evidence.md` 增 §10；集成测试 ①–⑦ 均已留档（S3/S4/S5/S6a/S6b/S7）；`docker-compose` 已由 **E2** 交付（`backend/deploy`，2026-10-21）

**验收实测（2026-10-21）**：`s7_reconcile.sh` `PASS=22 FAIL=0 SKIP=0` —— 批次 `RC20261021000004`、耗时 **1774ms**（预算 60s）、摘要「发现 14 / 修复 12 / 告警 2 / 跳过 0」（多出的 7 条是 R6 按排班级连带清扫，属设计意图）；二次跑 R1/R2/R3/R6 归零、R5 `found=1`（仍 `WAIT_REFUND`，重试属预期）。看板接口与 SQL 逐项一致（`todaySlots=9000` / `todayBooked=60` / `paySuccessRate=74.00` / TOP5 各 10 单）。**脚本修两处**：造数改为「每排班取 1 条候选、四用例跨排班分配 + 自检」，以及 `set -u` 下 `R3_SCHED` 先解析后使用（否则 R4 会重复选中 R3 的排班，去重只剩 3 个）。

### S8 患者辅助组（收藏 / 消息 / 分诊签到列表）

> **为什么插这一片**：E5（uni-app）延后，但患者端「我的医生 / 消息」与分诊台「今日签到」所需的 7 个端点一直是 P1 占位；不做完，E5 会做出「有页面没接口」。

- [x] D1–D3 收藏：`GET /appt/patient/favorite/list`（分页 + 收藏时间倒序 + 医生信息/`avatarUrl` 批量回填）、`POST/DELETE /{staffId}`（**幂等靠唯一键**，不做「先查再插」）
- [x] D4–D6 消息：列表（`readFlag` 可选过滤、时间倒序）、未读数、标记已读（三态：命中成功 / 已读幂等 / **别人的或不存在一律 404**，不用 403）
- [x] E3 分诊签到列表：`GET /appt/triage/sign/list?date=`（`@SaCheckRole("triage")`，按院区→科室→时刻排序）；**本期不按在岗院区过滤**（`sys_user` 无院区字段，契约 §11 #7 未决）
- [x] PRD §6.12 剩余三类站内信：`BOOK_SUCCESS`（B1 落单）、`PAY_SUCCESS`（C1 入账 CAS 命中）、`PAY_TIMEOUT`（关单成功；超时与主动取消共用入口，文案兼容）
- [x] 契约 §6 / §7.3 从「简条/占位」升级为字段级（参数、响应字段、幂等与 404 语义、分页默认值、数据范围与索引说明）
- [x] 验收 2026-10-21：`s8_patient_aux.sh` **`PASS=29 FAIL=0 SKIP=0`**（收藏 6 项 / 消息 10 项 / E3 4 项 / 三类通知 6 项 / 清理 1 项）
- [x] 顺带修种子数据缺陷（**S7 遗留，不影响 S7 结论但要记**）：seed 原来把 2000 张单和 10 位就诊人全挂在**真实登录账号**名下 → 演示账号被「同时持有 ≤3」与「同科室同日」直接挡死（下单恒 `LIMIT_HOLD_MAX` / `LIMIT_DEPT_DAY`）。现改为**虚拟数据账号 `…3199` + 专属就诊人 `3301–3310`**，真实账号 `appt_patient` 名下 0 张单、0 条黑名单计数

### S9 就诊人管理（B6–B10）

> **为什么必须单独一片**：B1 挂号入参是 `patientId`，而患者端此前**只有后台** `/appt/admin/patient`，前端连"选就诊人"这条路都没有。

- [x] B6 列表：`GET /appt/patient/patient/list`（本人 `status='0'`、`is_default DESC, create_time DESC`、只回 `idNoMasked`）
- [x] B7 新增：`POST /appt/patient/patient`（`id_no_hash` = HMAC-SHA256 查重、`encrypt` 落库、10 人上限 `PATIENT_LIMIT_EXCEEDED`、`isDefault` 同事务互斥）
- [x] B8 修改：`PUT /{id}`（属主校验；`idNo` 留空不改、非空重算 hash；只改 `idType` 不传证件号 → 400）
- [x] B9 删除：`DELETE /{id}`（`active_flag=1` 存在 → `PATIENT_IN_USE`；物理删除）
- [x] B10 设默认：`PUT /{id}/default`（同事务先清后设 + 唯一键兜底；幂等）
- [x] 契约收口：§2.2 补 `PATIENT_IN_USE` / `PATIENT_ID_CONFLICT`；§4.6/§4.7 字段级；§4.8 由占位转正；§10 去掉「待实现」
- [x] 脱敏统一：抽出 `common/PiiUtils.maskIdNo`（前 4 + 10 个 `*` + 后 4，**长度 < 12 全遮**），`RegistrationQueryService` 改为调用它
- [x] 单测：`PiiUtilsTest`（5 例：18 位掩码 / <12 全遮 / 空值 / 加密后解密再掩码 / hash 确定性）
- [x] 验收 2026-10-22：`s9_patient_crud.sh` **`PASS=23 FAIL=0 SKIP=0`**（列表 / 新增默认互斥 / 查重 / 留空不改 / 改号重算 / 越权 404 / 有效预约拒删 / 10 人上限 / 设默认幂等 / 清理）
- [x] **`status` 语义复核（2026-10-22）**：S9 报告里曾说生成器 `ApptPatientServiceImpl.insertByBo` 的 `Boolean.TRUE.equals(status)` 判反了——**复核结论：写法正确**（库列 `char(1)`，`'0'`=正常映射 `false`、`'1'`=停用映射 `true`）。`RegistrationBookingService` 也早已校验「就诊人已停用」（B1 第 4 步），无需新增改动；该语义坑已写入 `backend/AGENTS.md` §6，避免再读反

### S10 患者端主链路（uni-app）—— 已完成 2026-10-22

> **前置**：E5（`qd-appt-app` 建仓 + 脚手架）与 **S9**（就诊人）。行号接 S9，页面对应的接口全部已在 S1–S8 落地。

- [x] 登录与 token：复用 E5 的 `/auth/login` 加密登录 + storage + 401 自动跳登录；微信登录本片未动（仍只留接口位）
- [x] 双角色骨架：E5 已落地，本片未改（患者原生四项 / 分诊自绘底栏）
- [x] 页面 9 屏：9.1 首页（品牌区 + 院区卡 + 上次院区快捷科室）→ 9.2 选院区 → 9.3 选科室（一级栏 + 三级下钻 + 搜索）→ 9.4 医生列表（两列卡）→ 9.5 医生主页（满诊/无号 + 收藏只读）→ 9.6A 排班（医生视角 / 科室视角双口径）→ 9.6B 选时间点 → 9.7 确认预约（就诊人切换 + 内嵌新增，带 `Idempotency-Key`）→ 9.8 支付（C2 受理 + C3 每 2s 轮询 / 60s 两出口 / 离开即停）→ 9.9 我的预约（待支付/已预约/已完成/退号·爽约四 tab + 触底分页 + 去支付/取消）
- [x] 交互红线：余量只按 A5/A6 渲染，前端不自己算；「有排班/无排班」只在排班页、「满诊/无号」只在医生主页；金额与雪花 id 全程字符串
- **验收**：H5（8084）跑通「首页 → 选院区 → 科室 → 医生 → 排班 → 选时间 → 确认预约 → 支付（Mock）→ 我的预约状态可见」。**预约详情（就诊码）与退号归 S11**
- [x] 实测 2026-10-22：`type-check` 0 错 / `lint` 0 错 / `build:h5` DONE；后端 `mvn -pl ruoyi-modules/appt -am test` 13 例全绿；接口链路用真实加密登录直打：A6 `periods[].scheduleId` 有值 → A7 出号 → B1 建单 `R20261022000001`（金额 `22.00`）→ C2 受理 `accepted=true` → C3 `PAID` → B2 `BOOKED` 1 条；B4 取消另一单 → `CLOSED`、二次调用幂等、号源可约数 8→8
- [x] 本片后端补两处（均经用户批准）：A6 `periods[].scheduleId`（公开组此前无任何端点能给 A7 传参）；B4 `POST /appt/patient/payment/{paymentNo}/cancel`（契约 §4.4 早有定义、后端缺入口）+ 患者端三 VO `timePoint` 补 `@JsonFormat(pattern="HH:mm")` 对齐契约 §2.4

### S11 患者端辅助页 + 分诊台（uni-app）—— 已完成 2026-10-23

> **前置**：S10。接口来源：S9（就诊人）、S8（收藏 D1–D3 / 消息 D4–D6 / 签到列表 E3）、S6a（B5 退号、E1/E2 签到）。

- [x] 我的就诊人：列表（默认置顶）/ 新增（证件号输入 + 脱敏回显）/ 改名 / 改证件（留空=不改，禁「只改类型不填号」）/ 删除 / 设默认
- [x] 我的医生：收藏列表（20/页触底）+ 取消收藏（二次确认）；医生主页「收藏/已收藏」可点（未登录跳登录）
- [x] 消息：全部 / 未读双 tab + 未读蓝点 + 点开进详情并标记已读 + tabBar 未读数角标（D5）
- [x] 预约详情：状态头（状态色 12% 底）+ 就诊码（**`visitCode` 为准，仅有效态渲染**）+ 信息卡 + 退款块 + 退号（过「就诊前一日 23:00」置灰并给具体截止日）
- [x] 分诊台：扫码签到（`registrationNo`，小程序）/ 手动补签（H5 主路径）/ 当日签到列表（按院区分组、前后 3 天可切、行内补签）
  - [x] **小程序真机扫码已验收（2026-10-23）**：微信 8.0.66 / 基础库 3.17.5，患者端详情二维码（`visitCode`）→ 分诊端「扫一扫」→ E1 → `SIGNED` 端到端通过；同一码二次扫报 `SIGN_WINDOW_CLOSED`
- **验收**：双角色切换正常；分诊账号看不到患者 tab；退号后状态与退款入口正确
- [x] 实测 2026-10-23：`type-check` 0 错 / `lint` 0 错 / `build:h5` DONE；后端 `mvn compile` + `doc_audit` 5 项全 PASS；接口链路真实登录直打：B3 详情（`visitCode=R2026…`、`timePoint=17:20`）、B5 退号（`CANCELED_ACTIVE` + `refundNo`，重复退号 `REG_STATE_INVALID`）、D1→D2→D1→D3、D5/D4、D6 三态（未读→200 / 已读→200 / 不存在→**404**）、E1 扫码签到 + 重复 `SIGN_WINDOW_CLOSED`、E2 手动补签、E3 当日 183 条
- [x] 本片范围外的两处收口（用户点单）：**限购改为「同一就诊人同一天 1 个预约」**（`LIMIT_PATIENT_DAY`，原三条停用）+ **站内信时间格式去 `T`/纳秒、午别转中文**（`ApptDisplayUtils`）
- [x] **停诊上报页（S11.1，2026-10-23 补）**：范围三选一（院区某日 / 某医生某日 / 单个午别）+ 院区→科室→日期→医生→午别级联 + E5 提交 + 批号结果卡；页面上明示「上报后由后台停诊处理执行退号与退款」
- **未做（明确不在本片）**：加号登记（E4 后端未实现）。**分诊底栏已隐藏「加号」入口**（2026-10-23 定，用户确认不做），底栏现为 3 项；将来实现 E4 时在 `TriageTabbar` 的 `items` 加回一行即可

### S12 品牌与首屏（已完成 2026-10-24）

> **前置**：S11（三端页面已齐）。目标是把"能用的 demo"变成"有品牌感的产品"。
> 视觉口径一律以 `app/DESIGN.md` 为准，本片新增的 logo 用法、图标规格、配色沿用规则需同步回 DESIGN。

- [x] **品牌资产**：`app/scripts/gen-brand-assets.mjs`（`cd app && pnpm brand:gen`）一条命令重出全部产物——母标三档 SVG/PNG（16–512）、反白 4 档、横版「图形 + 号源」、`favicon.ico`（16/32/48 PNG-in-ICO）、`cover-144` / `cover-520x280`；落 `app/src/static/brand/`、`admin/src/assets/logo/`、`admin/public/`（app `9c1a1ea`）
- [x] **移动端 tabBar 图标**：4 项 × 选中/未选中 8 张 81×81 PNG（24 网格 / stroke 2 / 圆头），`pages.json` 补 `iconPath` / `selectedIconPath`，小程序 `app.json` 产物核对一致；**分诊台自绘底栏另加 3 项 6 张**（扫码框 / 列表 / 暂停）替换原小圆点
- [x] **患者端首屏抛光**：首页（240rpx 通栏品牌区内加反白母标）/ 预约详情（退款块只与退号终态同屏、证件号独立成行）/ 我的（三块卡：账户组 · 角色组 · 退出登录 + 二次确认），裸 hex 全换 `--appt-*`
- [x] **后台品牌**：`VITE_APP_TITLE=号源预约挂号管理后台`、`VITE_APP_LOGO_TITLE=号源`；登录页 / 注册页母标 + 业务文案；侧栏与顶栏改 48px 简化档并去掉「框套框」外框；favicon 与 loader 配色（`#7171c6`→`#1F7A8C`）；移除顶栏上游仓库/文档入口与两个无引用组件；`grep -ri ruoyi admin/src` 仅剩 `@/utils/ruoyi` 与 `RuoYiAjaxResult` 类型名（admin `7c47190`）
- [x] **后台首页**：`admin/src/views/index.vue` 重写为运营看板（今日预约 / 今日签到 / 支付成功率 / 待处理停诊 + 科室 TOP5 + 四枚快捷入口 + 关于本项目小卡），数据取既有 `GET /appt/admin/dashboard` 与 `GET /appt/admin/suspend/list?status=PENDING` 的 `total`，**后端零改动**
- [x] **DESIGN 补「品牌与图标」小节**：§12.1 修三点负形（预览稿三点与牌同色不可见）、§12.2 尺寸→档位映射表、§12.3 实际落盘清单、§12.5 tabBar 图标规格、§12.6 生成命令；另补 §9.11「我的」blueprint 与 §9.1 / §9.10 的 Stitch 出图校准
- **验收**（2026-10-24 通过）：三端截图对照；`grep -ri ruoyi admin/src` 仅剩必要依赖引用；tabBar 图标 H5 / 小程序一致；`type-check` / `lint` / `build:h5` / `build:mp-weixin` 与 admin `vue-tsc` / `oxlint` / `vite build` 全绿。证据见 `test-evidence.md` §16

### S12.5 全站视觉统一（已完成 2026-10-24）

> 与 S12 分开排期：S12 定"第一眼"，S12.5 收"每一页"。**后台不逐页重写**，靠主题变量 + 公共样式覆盖。

- [x] **后台主题**：三层同源——`tokens/_sass-vars.scss` 语义色换 `DESIGN §2.1`、`settings.ts` 首屏默认主色 `#1F7A8C`、`tokens/_theme.scss` 补 `--el-color-{success,warning,danger,info}` 全阶桥接；`rgba(53,109,255,…)` / `rgba(64,158,255,…)` 共 20 个文件收口为主色 RGB；圆角归一（卡片 16px、输入按钮 8px、标签 4px），阴影两档（admin `c630354`）
- [x] **表格密度与空态**：表头 `#f5f7fa` + 13px 次色、单元格 `padding: 12px 0` + 13px、空态块最小高 160px；挂号/支付/退款/停诊/号源/台账六张表补业务化 `empty-text`（不再裸「暂无数据」）
- [x] **状态标签统一**：`views/appt/options.ts` 的 `ApptOption` 增 `type` 语义字段（挂号 8 态 / 支付 4 态 / 退款 3 态 / 结算 3 态 / 停诊 2 态 / 回调 4 态），新增 `components/ApptStatusTag.vue` 统一 `el-tag` 渲染，替换 5 个列表页的纯文本状态列；色值映射写入 `admin/AGENTS.md` §13.2
- [x] **表单与弹窗**：规范写入 `admin/AGENTS.md` §13.4（`label-width` 统一、必填由 `rules` 出红星、错误文案在控件下方 12px、弹窗 ≤720px、危险操作二次确认）；抽查挂号单与停诊登记两页无结构违规（既有 `el-form` + `rules` 已满足）
- [x] **移动端剩余 7 屏走查**：院区 / 科室 / 医生列表 / 医生主页 / 排班 / 选时间 / 消息详情逐屏对照 `DESIGN §9.2–§9.6 / §9.14`——蓝图取值（封面 120rpx、侧栏 180rpx、医生卡两列、日期格 120rpx、号源格 88rpx、午别余量）已全部在位，本轮补的是缺的点击态（号源格、医生主页收藏）与消息详情的返回入口/正文换行（app `4042127`）
- [x] **补 404 与网络异常页**：移动端 `pages/fallback/index.vue` 单页两模式（`notfound` / `offline`），母标十字水印 + 标题 + 说明 + 主按钮 + 文字链；H5 启动校验 hash 路由、首页首屏失败进 offline，**不做全局自动跳转**；后台 404 页去掉卡通云图改同口径（app `4042127` / admin `c630354`）
- **验收**（2026-10-24）：后台抽查登录页 / 运营看板 / 挂号单 / 停诊登记 / 404 五页 + 移动端兜底两页与六屏走查；`grep -rn "#409EFF\|53, 109, 255" admin/src` 为 0；DESIGN §9.12–§9.14 与 `admin/AGENTS.md` §13 已落地。证据见 `test-evidence.md` §17

### S13 门面与物料（已完成 2026-10-24）

> 这一片决定"别人愿不愿意看第二眼"。所有物料必须可复现（脚本产出），不接受手工截图。

- [x] **门面 README**（改为第 5 仓 `qd-appt-showcase`，`showcase/README.md`）：定位 + mermaid 架构图 + 真实截图 + 三端启动 + 账号表 + 已知边界 + 仓库对照表（根目录不建伞仓，避免父仓把四子仓当 gitlink）
- [x] **`docs/DEMO.md`**：5 分钟剧本（患者下单 → 支付 → 就诊码 → 分诊签到 → 停诊两段式 → 看板与对账），逐步写「点哪里 / 看到什么 / 卡点怎么办」+ 附录小程序真机截图清单（8 屏 + 尺寸与命名规范）
- [x] **截图脚本**：`showcase/tools/screenshots`（Playwright），已产出 **10 张**单页截图（患者 5 / 分诊 2 / 后台 3），`--shots` 可重复跑；免 root 解决 WSL 缺库与缺中文字体
- [x] **15 秒 GIF**：`node gif.mjs` 产出 `assets/demo.gif`（14 秒 / 168 帧 / 5.0 MB，上限 10 MB）——患者路径「首页 → 院区 → 科室 → 医生 → 排班 → 选时间」，**停在「下一步」前不提交**，绕开限购额度问题；录制用「先无录像登录拿 storageState → 再开录像上下文」，开头白屏按内容比例自动裁掉。转码不用 ffmpeg 一步到位（Playwright 自带 ffmpeg 是无 gif muxer / 无 palettegen 的精简构建），改为抽 PNG 帧 + `gifenc` 量化
- [x] **ADR 六篇**：`docs/adr/`（限购口径 / 停诊两段式与批号幂等 / `active_flag` 与唯一索引 / `scopeValue` 复合键 / `timePoint` 口径 / 三层防线）+ 索引，结论均挂 test-evidence 章节或契约条款
- [x] **接口文档入口**：README 给 OpenAPI JSON 与四分组；实测本仓未引 Swagger UI，**`/doc.html` 不存在**（如实写进 README 与 DEMO）
- **验收**：10 张截图 + 1 个 GIF 全部由脚本产出 ✅；DEMO 剧本可照做 ✅；新人 30 分钟跑通 — 待按 README 实测（`assets/` 共 6.8 MB，未入库 node_modules）

### S14 一键演示（已完成 2026-10-25）

> 不依赖服务器：先把"一条命令起全栈"和"出镜像"做掉，S16 只加部署步骤。

- [x] **`demo.sh`**（showcase 仓）：预检 Docker / compose ≥2.20 / 仓库布局 / 端口 → 拉取或本地构建四镜像 → 起依赖 → `init-db.sh --full` 建库导数据 → 建 MinIO bucket → 起 SnailJob → 起三端 → 逐端探活；任一步失败打印「失败步骤 + 修复命令 + 看日志命令」；**默认端口被占用时按 `+10000` 自动避让并打印实际地址**（显式指定的端口不擅自更换，直接报错给解法）；附 `down` / `reset` / `logs` 三个子命令
- [x] **镜像构建 workflow**：后端两份 + 前端两份（api / snailjob / admin / h5），tag `v*` 构建并推 `ghcr.io/xcqj/appt-*`（内置 `GITHUB_TOKEN` + `packages: write`），`workflow_dispatch` 默认只 build（`push` 开关才推）；本地四镜像 `docker build` 均通过
- [x] **环境变量模板**：`backend/.env.example`（数据源 / Redis / 端口 / SnailJob 开关）、`admin/.env.example`（构建期 `VITE_*` + 运行期 `APPT_API_UPSTREAM`）、`app/.env.example`（H5 前缀 / 小程序产物目录 / 运行期上游），逐项标注默认值与生效位置
- [x] **干净机菜单树补齐**：新增 `appt_s14_menu_pages.sql`（19 个页面菜单 + 63 个按钮权限，来自代码生成器「生成菜单」、此前只存在于开发库）+ `appt_s2_menu_generate.sql`，纳入 `--full` 链路；修掉「侧栏只有二级、点进去空白页」
- [x] **去上游框架名**：`GET /` 改为「号源演示后端已启动，请通过前端地址访问。」；登录欢迎通知改为「…欢迎登录号源预约挂号管理后台」
- [x] **镜像 UI 验收修复**：① `SvgIcon` 提权（生产 CSS 顺序让 Element Plus 的 `height: inherit` 生效，svg 退回 300×150，把登录输入框撑到 152px）；② 恢复「运维对账 → 任务调度中心」入口（`appt_s13_menu_showcase.sql` 第 5 段）+ admin nginx `/snail-job/` 反代；③ 侧栏默认由 S13 的浅色改回深蓝（与项目既有观感一致，浅色仍可切换），并加一次性迁移对齐旧 localStorage
- [x] **SnailJob 服务端随 demo 发布**：新增 `Dockerfile.snailjob` + `image-snailjob.yml` → `ghcr.io/xcqj/appt-snailjob`；compose 起 `snailjob` 服务（宿主 18800 控制台 / 27888 gRPC），`init-db.sh --full` 追加 `ry_job.sql` + `appt_s14_snailjob_seed.sql`（把开发期手工建的「每日放号」「apptPaymentCloseJob」固化，`next_trigger_at` 重置到次日避免启动即跑，并清掉无执行器的框架 `demo-job`）；后台客户端默认 `APPT_SNAILJOB_ENABLED=true` 连 `snailjob:17888`，namespace `dev`
- **验收**：空机器（有 Docker）一条命令起全栈 — **2026-10-25 实测** `./demo.sh` 首次 **1m44s** / 复跑 **58s**，八步全绿（明细见 `test-evidence.md` §19）；四镜像可 `docker run` 独立启动：admin 把 `APPT_API_UPSTREAM` 指向错误地址返回 **502**、指向正确地址返回 **200**，证明后端地址来自运行时环境变量而非镜像内写死；**验证码接口 `/auth/code` 200 + 两套账号按真实「验证码 + RSA/AES 加密」链路登录 200**；**SnailJob 控制台（18800）登录可见 2 个任务、5 个业务执行器在线**
- **边界**：不含 HTTPS / 域名 / nginx 统一反代 / 服务器部署（归 **S16.2**）；SnailJob 任务在 S14 只固化了 2 条（放号 / 关单），爽约 / 置完成 / 对账三条由 **S15.1** 补进同一 seed（2026-10-26 已完成）；小程序包不在镜像内（需真实 AppID 与微信开发者工具）；`ghcr` 推送需在远端打 tag 后由 workflow 执行，本地只验证 `docker build` 与 `docker run`（**真推归 S16.1**）

### S15 医院感细节

> 成本低、观感强。文案一律走 `DESIGN §8` 的官方书面语口径。

- [x] **就诊流程引导条**：预约 → 支付 → 签到 → 候诊 → 就诊，患者端详情页与首页各一处 —— 新增 `components/StepGuide.vue`，节点名唯一出处是 `utils/appt.ts` 的 `REG_STEPS`，状态映射是同文件 `regStepProgress()`（纯函数）；首页为静态五步说明（不发请求、未登录可见），详情页三态（`WAIT_PAY` 支付当前 / `BOOKED` 签到当前 / `SIGNED` 候诊当前 / `COMPLETED` 全部完成），四个终态只给一句终止说明且不点亮任何节点
- [x] **院区信息页**：地址 / 联系电话 / 门诊时间 / 交通（数据虚构，页脚声明）—— 新增 `pages/campus/info.vue`（A1 四态：骨架 / 正常 / 查无该院区 / 异常重试）+ `utils/campusProfile.ts`（**按院区名称匹配**虚构电话·门诊时间·交通指引，未命中走通用兜底，不编造具体线路）；首页院区卡加「院区信息」次入口（`@click.stop`，卡片主体仍是选院区进科室），「我的」加常驻入口「院区与就诊指南」
- [x] **须知与规则页**：挂号须知、退号规则、退款到账时效（1–3 个工作日）、爽约规则 —— 新增 `pages/guide/rules.vue` 五组条款（挂号 / 退号 / 退款到账 / 签到与爽约 / 限购与违约），数字逐条对齐 PRD §6.7 / §6.8 / §6.9 / §14.1：支付 15 分钟、退号截止就诊前一日 23:00、签到自就诊日 00:00 起、爽约判定就诊时刻后 30 分钟、半年 6 次限制半年、同时持有 ≤3 单且同人同科室同日 1 单、退款 1–3 个工作日
- [x] **免责与急诊提示**：页脚常驻「演示系统 · 数据虚构 · 不提供医疗服务」；首页/详情加急诊提示 —— 新增 `components/AppFooter.vue`（首页 / 我的 / 就诊指南 / 院区详情 / 须知与规则五页）与 `components/EmergencyTip.vue`（首页 / 预约详情 / 就诊指南三页）；另新增 `pages/guide/index.vue` 就诊指南（院区信息 + 规则入口 + 急诊提示 + 页脚）
- [x] **验收发现并修复（文案）**：预约详情「就诊医生」行原样输出了职称线值（`PHYSICIAN`），改为统一走 `titleLabel()` 中文映射——正落在验收口径 ②「不出现英文代号与内部状态名」上；同时确认「已完成的预约仍显示就诊码」**不是缺陷**：契约 §4.3 规定 `visitCode` 在 `BOOKED / SIGNED / COMPLETED` 返回，`DESIGN §9.10` 四态同口径
- **验收**：新增页面四态齐全；全站文案无口语化表达；`doc_audit` 全绿 —— **2026-10-26 实测**：`pnpm type-check` → `pnpm lint`（`Found 0 warnings and 0 errors`）→ `pnpm build:h5`（`DONE Build complete`）三条按序通过；`python3 script/doc_audit.py` 五项 PASS、0 警告；四入口与八状态核对表见 `test-evidence.md` §20

### S15.1 SnailJob 任务补种（S14 边界欠账）

> **起因（2026-10-26 实测）**：开发库 `sj_job` 只有 3 条（框架 `demo-job` + 每日放号 + 支付关单），**爽约扫描从未注册过** → 301 条 `BOOKED` 里 299 条就诊时刻已过仍显示「已预约」，admin 主账号的列表与详情页照常出现（详情页还会给就诊码）。手工跑一轮后数据自愈，但换机或起 demo 容器会原样复现。
> **为什么不能用启动自建任务**：SnailJob 客户端的 `@JobExecutor` 只注册**执行器**，任务定义（cron / 组 / 路由）只存在于服务端 `sj_job`；应用启动不会建任务，客户端写服务端库又有多命名空间撞车风险 → 唯一稳妥做法是 seed（与 S14 对「放号 / 关单」的处理一致）。

- [x] **三条任务固化进 `appt_s14_snailjob_seed.sql`**（沿用同一文件管 `sj_job`，`init-db.sh --full` 无需改）：`apptNoShowJob` `0 */5 * * * ?`（id 4）、`apptCompleteJob` `0 30 23 * * ?`（id 5）、`apptReconcileJob` `0 0 3 * * ?`（id 6）；字段形状与既有 2 条一致（`namespace_id='dev'` / `group_name='ruoyi_group'` / `task_type=1` / `trigger_type=3` / `executor_info` = 执行器名）
- [x] **幂等**：`DELETE ... job_name IN (五个任务名)` 后再插入，可重复执行；`demo-job` 继续清掉（无对应执行器）
- [x] **`next_trigger_at` 分策略**：爽约扫描设**下一个 5 分钟整点**——它必须持续跑，延到次日会让演示当天的过期单继续堆「已预约」（本次就是被这个坑到的现象）；放号 / 关单 / 置完成 / 对账仍延到**次日**，避免容器一起来就改动演示数据
- [x] **本机 dev 库同步**：直接补 id 4–6 三行（`biz_id` 与 seed 一致），不重置既有 id 2/3
- [x] **顺带修 seed 一处口径**：`apptPaymentCloseJob` 首触发原为「次日同一时刻」，全新环境会**整整 24 小时不关单/不回补号源** → 改 `+30s`（与爽约任务同理：巡检类必须尽快起跑）；`ApptJobRunService` 的 javadoc 白名单补上 `apptReconcileJob`（代码第 65 行本就支持，注释漏写）
- **验收**：`sj_job` 共 5 条（id 2–6）；新任务到点**自动触发**并落 `appt_job_log`；重导 seed 幂等；`doc_audit.py` 五项 0 警告 —— **2026-10-26 实测**：`apptNoShowJob` 于 **01:00:00 自动执行**（批号 `J20261026000125`，`affected=0`，因数据已在此前两轮手工里清空），执行后 `next_trigger_at` 自动推进到 **01:05:00**；同批日志可见完整序列：**00:46:20 `爽约=299 / 号源过期=2000`** → **00:52:06 `号源过期=2000`** → **00:52:30 `1135`** → **00:52:36 `0`** → **01:00:00 自动 `0`**，正好印证「单轮 2000 条上限（`SCAN_BATCH_SIZE=100` × `MAX_ROUNDS=20`）+ 不足一批即收尾」；`apptCompleteJob` / `apptReconcileJob` 的 `next_trigger_at` 落在 **2026-10-27 00:56:29**（次日同一时刻首触发，随后按 cron）；另测两项：**置完成**手动执行 `affected=206`（批号 `J20261026000234`，`SIGNED` 206 → 0、`COMPLETED` 498 → 704）；**对账**「立即对账」批次 `RC20261026000001`、耗时 **14950ms**、七查「发现 507 / 修复 507 / 告警 0 / 跳过 0」（R1 幽灵占号 505 + R3 补退 2，成因见 `test-evidence.md` §21.5）
- **边界**：只补任务定义，**不改任务代码与 cron 语义**；已签到的「置完成」与 03:00 对账在本轮没有等到触发点，逻辑沿用 S6a/S7 已验收实现；`sj_job` 的 `next_trigger_at` 仍按 S14 口径「次日同一时刻」而非 cron 时刻首触发（既有行为，本片不改）

### S15.2 已签到入口补口（未开始，2026-10-26 登记）

> **来源**：S15 验收时发现——「我的预约」四个 tab（待支付 / 已预约 / 已完成 / 退号·爽约）**不含 `SIGNED`**，已签到的预约在列表里没有任何入口，只能直链或看后端日志。B2 的 `status` 必填、一次只查一个状态（契约 §4.2），不能靠一次查询合并。

- [x] **入口形态定案（2026-10-26 拍板）**：「已预约」tab 内加子筛选「已预约 / 已签到」（默认已预约），复用 `CANCELED` tab 的子筛选结构与 `.record__subs` 样式 —— 不加第五个 tab（五等分后四字标签过挤）、不做两次请求合并（两套分页游标与排序要前端自维护，且与契约「一次一个状态」相背）
- [x] **实现**：`SUBS` 拆成 `CANCELED_SUBS` / `BOOKED_SUBS`，`activeSub` 换成按 tab 分组的 `subState` + `currentSubs` / `currentSub` 两个 computed；`queryStatus` 三分支（`CANCELED` → 子状态、`BOOKED` → 子状态、其余 → tab 本身），B2 仍只收到一个 `status`
- [x] **顺带修两处行为**：① `SIGNED` 原来落进 `else` 分支会显示「再次预约」，改为与 `BOOKED` 共用「查看就诊码」（契约 §4.3：两者都返回 `visitCode`）；② 已签到子筛选为空时改用「暂无已签到预约 / 到院签到后，预约会显示在这里」，不再说「请选择科室与医生完成预约」
- [x] **`DESIGN §9.9` 同步**：布局段补两行子筛选；「tab 与线值映射」补 `SIGNED`、子状态按 tab 记忆与「外部落点复位」；「状态 → 动作」段按实现订正（原文写「其余只展示状态标签」，与代码不符）
- **验收**：`SIGNED` 单能在列表点开、四条 tab 原有行为不变、未登录不发请求 —— **2026-10-26 实测**：`pnpm type-check` → `pnpm lint`（`Found 0 warnings and 0 errors`）→ `pnpm build:h5`（`DONE Build complete`）按序通过；查询/空态/动作的代码路径核对表见 `test-evidence.md` §22；admin 名下 `RS70000003376` 的肉眼走查由用户在演示环境执行（该单现挂虚拟账号，验证前需临时改归属）
- **边界**：不改 B2 接口（一次仍只查一个状态）、不动其余 tab 的口径与动作、不动详情页；子状态「按 tab 记住上次所选」只对用户手动切换生效，从支付成功等外部落点进入时复位到默认子状态

### S15.3 终态号源释放（未开始，2026-10-26 登记）

> **来源**：S15.1 核对对账结果时发现——批次 `RC20261026000001` 报 R1 幽灵占号 **505** 条，正好等于本轮「299 转爽约 + 206 转完成」。**不是脏数据，是终态没释放号源**：`RegistrationStateService` 的 `markNoShow` / `markCompleted` 只改挂号单与 `active_flag`，Slot 仍停在 `TAKEN`；而 `TAKEN → EXPIRED` 的唯一调用点是 `SlotStateService.reclaimGhost()`（对账 R1），所以只能等 03:00 对账来扫。

- [x] **终态流转即释放号源**：`SlotStateService` 新增 `expireTaken(slotId, registrationId)`（`TAKEN → EXPIRED`、清 `registration_id`、写 `EXPIRE` 台账、**余量 0** 不发缓存增量）；`RegistrationStateService.markNoShow` / `markCompleted` 签名加 `slotId`，**CAS 命中后同一事务调用**，避免「单已爽约、号仍占用」的中间态
- [x] **两个任务的查询多取 `slot_id`**（`ApptNoShowJobService` 两处、`ApptCompleteJobService` 一处）并传入，不额外查库
- [x] **回归四条状态边**：退号（`releaseToPool`）与停诊（`suspendTaken`）一行未动，四条边互斥、不会重复写台账；`expireTaken` 的 CAS 带 `registration_id`，重复调用或号源已被对账回收时影响 0 行、不写台账
- **验收**：连跑「爽约扫描 + 置完成」后对账 R1 归零或只剩真脏数据；`appt_reconcile_result` 结果行从 507 降到个位；台账 `EXPIRE` 落在状态流转时刻 —— **2026-10-26 实测**：用两条「回滚式」夹具（`R20261023000016` 退回 `BOOKED` + slot `TAKEN`、`RS70000003876` 退回 `SIGNED` + slot `TAKEN`），跑爽约扫描 **affected=1** → `NOSHOW` + slot `EXPIRED` + 台账 `EXPIRE (TAKEN→EXPIRED)` @**02:47:13**；跑置完成 **affected=1** → `COMPLETED` + slot `EXPIRED` + 台账 `EXPIRE` @**02:47:59**；「立即对账」批次 `RC20261026000002` **907ms、七查全 0、新批次结果 0 行**（旧批 507 行保留作历史）；幽灵占号复核 **0**（基线亦为 0，说明本轮未产生新的，505 那批已由上一轮对账修掉）；`mvn -pl ruoyi-modules/appt -am clean compile` 通过
- **边界**：不改对账口径（R1 仍保留兜底）、不动余量语义（`TAKEN → EXPIRED` 恒 0）、不改 A7/B2 的展示与查询条件；本片只处理 `NOSHOW` / `COMPLETED` 两条终态，退号与停诊的释放路径保持原样

### S16.1 部署形态与 wsl 发布链（不依赖服务器，2026-10-29 由 S16 拆出）

> 拆片理由：S16 原 5 条 checkbox 全部以"有服务器"为前提，但"compose 能拉镜像部署 + 镜像能推到 registry + 能回滚 + 能备份"**全部不需要服务器**，且是 S16.2 的前置。原表述"阻塞：服务器"会把这些活长期挂在"未开始"里。

- [x] **compose 去 `build:`**：`showcase/deploy` 拆成 `compose.yml`（纯镜像）+ `compose.deps.yml` + `compose.{wsl,cloud}.yml` + `compose.build.yml`；`demo.sh` 改为引用新文件且行为不回退
- [x] **统一部署入口**：`deploy/deploy.sh`（up / adopt / down / rollback / backup / restore / status）+ `.state/{current,previous}` 记录镜像 digest
- [x] **镜像首推 GHCR**：打 `v0.1.0` 让四枚 `appt-*` 镜像真推到 `ghcr.io/xcqj`（清 S14 边界欠账：本地只验证过 `docker build` / `docker run`）；验收含"本机 `docker rmi` 后从 registry 冷拉回来能跑"
- [x] **wsl 发布链**：`release.yml`（`deploy_target=wsl`，唯一入口 `workflow_dispatch`）+ 仓库级 self-hosted runner（不接 PR）
- [x] 数据备份与恢复演练、发布探活门禁、日志轮转（本机即可验收）
- [x] 端口按方案 §7.6 钉进 `showcase/deploy/.env`（开发 8xxx / 演示 18xxx）
- **2026-10-30 实测（wsl 目标，全套跑通）**：发布 `v0.1.0` **39s**（7 容器 healthy / 五条业务探针全绿）→ 回滚 `latest` **42s** → 前滚 **46s**；备份 **1s**（MySQL 761K + MinIO 7.4K）→ 恢复 **62s**，恢复前后行数一致（注册单 2001 / 号源 20040 / 支付 2001 / 站内信 122）。公网 `admin` / `demo` 两域名全程 200。CI 侧 `release.yml` run #4 **1m09s 全绿**（preflight 37s + deploy 24s，自托管 runner），`.state/current` 由 CI 写入并含四镜像 digest。
- **踩到并修掉的三个真问题**：① 演示栈 redis 宿主口撞开发态 6380 → 默认改 **16380**；② 从 `~/qd-appt-deploy` 起栈时 `../data` 解析到 `~/data`，空库导致 api crash loop → `deploy.sh` 加**数据目录守卫**（有部署记录但无 `$DATA_DIR/mysql` 直接拒绝启动），数据目录统一为绝对路径；③ preflight 跑在托管 runner 上读不到跨仓私有包 → 挪到自托管 runner。
- **边界**：不做云服务器、不做域名 HTTPS 反代（归 S16.2）；不改业务代码，`appt` 模块与 20 张表零改动；SSE 连接 55s 被中间层回收属已知现象，**先记录不修**（`deployment-cicd-plan.md` §2.8 第 9 条）。
- **验收**：`./deploy.sh wsl up --tag v0.1.0` 一次起全栈、探针全绿；`rollback` 演练成功再前滚；四枚镜像可从 GHCR 冷拉 —— **全部达成**

### S16.2 云目标与公网 HTTPS（阻塞：服务器未就绪，2026-10-29 由 S16 拆出）

- [ ] 服务器与域名、HTTPS 证书、nginx 反代（H5 / admin / api 同域不同路径）
- [ ] `release.yml` 的 cloud 分支：SSH + `known_hosts` + ufw 暴露面自检（`nmap` 只看到 22/80/443）
- [ ] 小程序后台配置 request 合法域名（扫码需 HTTPS）
- [ ] 演示数据重置入口（管理员专用，避免公开危险操作）——**属应用功能**，落地时可按需单列
- [ ] 可选：Prometheus + Grafana 与告警
- **边界**：不含 compose 改造与 wsl 发布链（归 S16.1）；`cloud` 的 compose 覆盖文件在 S16.1 已留好结构，本片只做验收与加固
- **验收**：公网 HTTPS 可访问、两个角色都能登录、小程序真机扫码可用、暴露面自检通过

### 3.9 核心亮点 ↔ 切片 ↔ 验收证据

> 亮点不单独排期：**结构性亮点随功能同步落地**（S1–S6b），**展示型亮点集中交付**（S7）。每行必须有可执行证据，否则视为未完成。

| 亮点 | 切片 | 验收证据（可执行） | 现状 |
|---|---|---|---|
| `active_flag` NULL 语义 + `UNIQUE(slot_id, active_flag)` | S1（建）/ S3（用） | I1 实测：终态单共存、第二笔有效单报 1062 | ✅ |
| 三道防线防超卖（Redis → DB CAS → 唯一索引） | S3 | 50 并发：1 成功 + 49 返回 1062/已被预约，`registration` 仅 1 行 `active_flag=1` | ✅ 2026-10-20 实测（1 成交 / 49 SLOT_GONE，`active_flag=1` 仅 1 行，payment 1 笔；**摘除防线① 对照组同样 1 成交**） |
| 条件 CAS 即幂等 | S3 / S4 / S6a / S6b | 重复请求第二次 `affected rows = 0` | S3 号源 + S4 支付/退款/关单 + S6a 退号/签到/爽约/置完成 + S6b 停诊排班/号源/被动退号 CAS 全部落地（2026-10-20/21），停诊重复处理 `handled=false` 已实测 |
| 停诊两段式 + 批号幂等 | S6b（登记 + 处理） | 同一批号二次执行全部影响 0 行 | ✅ 2026-10-21 实测（`s6b_suspend_blacklist.sh` `PASS=25 FAIL=0`）：E5 只登记不动数据、同范围 `duplicate=true`、F2 后登记 `HANDLED`、重复处理 `handled=false` 且退款单仍 1 条；后台页面点「处理」摘要「排班 1 / 号源 2 / 被动退号 1 / 退款 1 / 跳过已签到 1」，三处页面（挂号单/退款单/站内信）与接口一致。**区间停诊改「一条登记承载区间」**（原「按日拆分共用批号」与 `uk_suspend_batch` 唯一键冲突，已废止） |
| 放号滚动窗口 D1（可配） | S2（任务侧）/ S5（查询侧） | 窗口外不可约；08:00 任务只生成「今日+N」 | ✅ 任务侧 2026-10-20 验收（只生成目标日、重跑 0 新增）；查询侧过滤归 S5 |
| 余量聚合 M×2 → 1 + Lua EXISTS 守卫 | S5 | 单屏 1 次聚合 SQL + 压测对比表 | ✅ 2026-10-20 实测（单屏冷启动 3 条 / 命中 2 条，与医生数无关；`redis` p95 9.3ms 命中率 100% / `db` p95 10.6ms；1000 次挂号关单后差值 0，删键不创建） |
| 回调幂等 + 「钱到了号没了」 | S4 | 回调 3 次仅 1 次入账；关单后回调 → 自动退款 + 告警 | ✅ 2026-10-20 实测（3 次投递回调记录仅 1 条、payment 仅 1 次 PAID；关单后回调 → refund REFUNDED、payment 保持 CLOSED） |
| 对账七查 + 保守修复 | S7 | R1 幽灵占号自动回池；R4 只告警不自动修 | ✅ 2026-10-21 实测（`s7_reconcile.sh` `PASS=22 FAIL=0`：批次 `RC…0004` / 1774ms；R1 回池 + `RELEASE` 台账、R2 补占用、R3 自动补退、R4 仅 `ALERT` 且支付单未改、R5 重发、R6 排班级补退号、R7 余量键归零；二次跑可修项归零） |
| 看板口径写死 + 科室 TOP5 | S7 | 接口 = SQL = 页面 | ✅ 2026-10-21：`todaySlots=9000` / `todayBooked=60` / `paySuccessRate=74.00`（1480/2000）/ TOP5 各 10 单，三处一致 |
| 爽约半开窗口 + 全量兜底 | S6a | 跳过一轮后下一轮补判，漏判 0 | ✅ 2026-10-20：主批 `[now-35m, now-30m)` + 兜底 `<= now-35m`，脚本用 −3h 陈旧单等价模拟「窗口已滑过」，兜底命中并判 `NOSHOW` |
| 单号规则（前缀 + 日期 + Redis INCR） | S3 | 并发 50 单号不重复、跨日重置 | 代码完成 2026-10-20（R/P 前缀 + `SequenceUtils` 每日重置；并发 50 未出现重号） |
| `Idempotency-Key`（仅 B1） | S3 | 同 key 双击只产生一笔待支付 | ✅ 2026-10-20 实测（第二次 `data.duplicate=true`，DB 仍 1 单） |
| 限购三条 + 账号行 `SELECT ... FOR UPDATE` | S3 | 同账号并发 3 单仅 1 笔成功 | ✅ 2026-10-20 实测（三条各命中：DEPT_DAY / TIME_CONFLICT / HOLD_MAX） |
| SnailJob + Redisson `tryLock` 防叠加 | S2 / S4 / S6a | 双实例同时触发，任务只执行一次 | S2 放号、S4 关单已落地 2026-10-20（`tryLock(0,-1)` 拿不到即记 SKIPPED）；S6a 爽约扫描沿用 |
| 一条命令起全栈 + 四镜像可独立运行 | S14 | `showcase/demo.sh` 全流程实跑；四镜像各自 `docker run` 探活 | ✅ 2026-10-25 实测（首次 1m44s / 复跑 58s；api 793MB / snailjob 638MB / admin 109MB / h5 95.1MB；admin 上游改错 502、改对 200；真实验证码登录两账号 200；SnailJob 控制台 2 任务 + 5 执行器在线） |
| 医院感说明层（流程条 / 院区信息 / 须知规则 / 免责急诊） | S15 | 三条质量门槛按序通过 + `doc_audit` 五项 0 警告 + 四入口与八状态流程条核对 | ✅ 2026-10-26（`type-check` 通过、`lint` 0 warnings 0 errors、`build:h5` DONE；`doc_audit` 5 PASS / 0 WARN；流程条 4 在途 + 4 终态按 `regStepProgress` 逐条核对，页脚只出现在 5 个信息展示型页面，`/appt/public/**` 之外零新增接口） |
| 终态即释放号源（对账 R1 只剩真脏数据） | S15.3 | 爽约 / 置完成后 slot 不再停 `TAKEN`，台账记在流转时刻 | ✅ 2026-10-26 实测：两条夹具分别跑爽约与置完成（各 `affected=1`），slot 均 `TAKEN→EXPIRED`、台账 `EXPIRE` 时间 02:47:13 / 02:47:59；随即「立即对账」`RC20261026000002` 七查全 0、**结果 0 行**（S15.1 时同一动作是 507 条）；幽灵占号复核 0 |

---

## 4. 非功能需求（PRD 第 9 章）挂钩

PRD §13.1 末条「第 9 章全部非功能需求」是兜底条款，原 §13.3 未挂任何切片——**这是最容易静默漏掉的一类**，此处逐一挂钩：

| PRD | 非功能需求 | 挂哪个切片 | 验收口径（PRD 原文） |
|---|---|---|---|
| §9.1 | 号源争抢并发与一致性 | S3 | 50 并发同一时间点恰好 1 笔成功，其余返回「已被预约」，数据无异常 |
| §9.2 | 午别余量聚合性能 | S5 | 单屏由 M×2 次 COUNT 降至 1 次聚合；压测对比留档 |
| §9.3 | 定时任务与状态流转（爽约/过期） | S6a | 漏判率 0（含某轮被跳过的兜底） |
| §9.4 | 超时关单与库存回补 | S4 | 同一订单多次触发只生效一次；回补数量与关单数量一致 |
| §9.5 | 支付回调幂等与补偿 | S4 | 回调 3 次仅 1 次入账；挂号单状态只流转一次 |
| §9.6 | 数据一致性：对账 | S7 | 每日 03:00 执行；手动触发 + 结果列表可用 |
| §9.7 | 可靠性（Redis 降级 / 渠道不可用 / 任务幂等 / 批量分批） | 横切 S2·S3·S4·S6a·S6b·S7 | 逐条自测留档 |

---

## 5. 进度记录

| 日期 | 事件 | 产出 |
|---|---|---|
| 2026-10-17 | 项目命名拍板（号源 / QueueDepth / `appt`）、M1–M13 确认 | `PRD.md` v0.5、`技术方案.md` v0.3 |
| 2026-10-17 | docs / backend / admin 三仓建立并推送 | 基线提交 |
| 2026-10-18 | `api-contract.md` v0.1 定稿 | 契约 §1–§11 |
| 2026-10-18 | **S1 建表完成**：20 表 + I1 实测 | backend `0f0bfff`、docs `1ec0d0d` |
| 2026-10-18 | 环境就绪：库 `appt`、Redis db1、后端 8082、plus-ui 8081、全链路加密冒烟全绿 | backend `50b75d5`/`1c85bc2`、admin `fb7fcdd` |
| 2026-10-18 | **P1 修复轮**（实体生成前置复查闭环）：契约 §7.5 scope_type 对齐 `SCHEDULE`/`STAFF_DATE`/`CAMPUS_DATE`（D-S1-5 落地补全）；PRD §6.4 补挂号费矩阵规则、§6.10 粒度同步；`suspend_record` 归属 triage；database-design §5 补 I6 映射；backend AGENTS §6 补三条生成器坑位；`title` 注释补 `ASSOC_CHIEF_NURSE`（DDL + 库同步 ALTER） | docs / backend 各一轮提交 |
| 2026-10-18 | **P2 清理轮**（12 条，纯文档）：契约 §9.1 补 F2 触发源、§2.7 补 `scope_type`、§8.5 F8–F22 编号分配（F16/F22 锁定）；PRD §1.4/§13.2 清单互覆、§4.2-5 索引指针、§10.2 菜单改「号源查看与删除」、§11 补 seed 硬约束、§14.3 标题；database-design §2 补 6 组枚举、§3 补行数量级、§4 补 payment_callback 索引登记、§7 标题；技术方案 §6.2 索引指针；ROADMAP §4 §9.7 横切补 S2/S7 | docs 单提交 |
| 2026-10-19 | **S1 实体生成轮**：20 表走 RuoYi 生成器（`appt_s1_gen_config.sql` 配置一次到位，替代逐表编辑）；菜单父节点 SQL + 20 C/120 F 菜单已执行；生成代码落位 backend/appt + admin（140 java + 20 XML + 20 vue + 40 ts）；构建修复：appt pom 补 excel/translation 依赖（此前 `mvn clean compile` 224 错）；包结构定**方案 A**（生成器平坦 + 领域包放手写代码） | backend / docs 各一轮提交 |
| 2026-10-19 | **B2–B5 改造轮**（生成器产物按契约收口）：端点路径 `/appt/admin/{entity}`（20 controller + 20 api.ts + export 下载路径）；10 张只读表删 add/edit/remove（Service 三件套同步）、slot 保留 remove（契约 §8.4 F7）；staffFavorite 无契约端点整套删（后端 8 + 前端 3 + 菜单 6 行）；Vue 死代码清理（空对话框/按钮/操作列/死函数）；VO 金额类型字符串化（Form/Query 输入侧保持 number，`GenTableColumn.getTsInputType` 根因修复）；菜单清理 38 行（C 20→19、F 120→63）；验证：appt 与 ruoyi-gen 双编译 BUILD SUCCESS、vue-tsc 61→0、vite build 通过 | backend `9403f56`、admin `4eda2a4`、docs 单提交 |
| 2026-10-19 | **六实体维护页可用性修复**：① 生成器默认「列名以 `type` 结尾 → select」，无字典时渲染「请选择字典生成」坏控件、页面无法提交（O5 覆写漏网）——11 列改 `input` 并固化 `appt_s2_gen_column_fix.sql`，存量 7 页 16 处 el-select→el-input；② el-switch 初值 `undefined` 触发必填校验失败（红字「不能为空」）——8 个 CRUD 页 `initFormData.status` 默认 `false`（= DB `'0'` 正常）；③ AGENTS §6 记第五坑（同步/重新导入会重置 `html_type`）；验证：vue-tsc 0 错、vite build 通过 | backend + admin 各一提交 |
| 2026-10-19 | **导出空列修复**：生成器把「注释含全角（」误判为注释内嵌字典——17 个 VO、54 个字段被加上 `ExcelDictConvert` + 假 `readConverterExp`，Excel 导出整列空白；`vo.java.ftl` 移除该分支（只认 `dict_type`），存量 19 个 VO 还原普通 `@ExcelProperty`；AGENTS §6 记第六坑。附：时段模板时间列须填 `HH:mm`（LocalTime，填数字报参数格式错误）；科室 `parent_id` 下拉/树选择为后续手写任务 | backend 单提交 |
| 2026-10-19 | **S1 收尾轮**：删除前引用校验（campus / clinicType / department / medicalStaff，含 staff_favorite 与下级科室自引用）；唯一键撞停用行「重新启用」+ 同键冲突预检（clinicType / slotTemplate / feeStandard）；`DuplicateKeyException` 全局友好化（1062 由 500 改为 400 提示）；日期/时刻文本框加格式提示（模板 + 存量 4 页）；六页 CRUD + 导出走查全过 | backend + admin + docs 各一提交 |
| 2026-10-19 | **雪花 id 引用修复**：实测手输 id 被 JS 精度压成 `Number.MAX_SAFE_INTEGER`（9007199254740991）→ 引用校验查不到匹配、删除产生孤儿。① 医务人员（院区/科室）与时段模板（医务人员）改下拉，value 用接口返回的字符串 id；② 服务端加引用存在性校验（须存在且状态正常）；③ 清理孤儿 1 条；④ AGENTS §6 记第七坑 | backend + admin 各一提交 |
| 2026-10-19 | **S1 基础数据 seed**：`appt_s1_seed.sql`（3 门诊类型 / 3 院区 / 40 科室三级树 10+20+10 / 60 医务人员 / 15 收费标准全组合 / 80 时段模板）；固定 id 段可重跑；全部虚构数据、status 正常；执行后引用完整性四项自检全 0、层级分布 10/20/10；待决项 4 改为「基础数据已做，业务数据 seed 归 S7」 | backend + docs 各一提交 |
| 2026-10-19 | **UI 体验轮**（S1 维护页可用性收口）：20 页筛选区去噪（移除主键/内部 id/排序/简介/学位等，保留合理日期范围）；枚举全改固定 options 下拉（`options.ts` 线值取自 DDL 注释）；关联字段下拉联动（院区/科室/医务人员，`useApptOptions`）；时间日期控件（LocalTime→`el-time-picker`、visitDate→`date-picker`、科室上级→`el-tree-select`）；列表列名 UI 化 + 枚举中文映射 + 状态 tag；菜单 `order_num` 重排为 1..n；`timePoint` 显示改 `HH:mm` | admin + backend + docs 各一提交 |
| 2026-10-19 | **导出翻译轮**：20 个 VO 共 47 个枚举字段加 `ExcelDictConvert` + `readConverterExp`（Boolean 用 `false=`/`true=`，String 用线值；未命中→空、null→空），表头同步 UI 化；探针反射调用框架 `convertByExp` 验证 26 例（`MOCK=Mock` 为预期非中文）；不引入 sys_dict；副产物：枚举副本增至三处（§2 权威 / options.ts / VO 注解），已在 AGENTS §9 记同步要求 | backend + admin + docs 各一提交 |
| 2026-10-19 | **下拉收尾**：引用下拉统一过滤停用项（`useApptOptions` 过滤 `status===true`，staff/slotTemplate 改用 composable 去重）；科室父级树保留停用节点并标记 `disabled`；黑名单表单的账号/就诊人由 id 输入改为下拉（用户列表 / 就诊人列表） | admin 提交 |
| 2026-10-19 | **会话上下文机制 + S1 残留 + S2 配置前置**：① `docs/AGENTS.md` 扩为 §0–§8（最小输入 / 切片闸门 / 开场卡+阅读回执 / 基线自查 / 最小必读集 / 收尾 / 5 条判定 / 环境事实），两仓 AGENTS 顶部加摘要，README 文档地图补该文件；② 补 `slot_template.clinic_type == staff.clinic_type` 校验（database-design §6 早已写明但未实现，S2 生成依赖）；③ 新增 `BookingProperties`（`booking.window.days` / `release.strategy` / `release.cron`，技术方案 §1.4），yml 同步 | docs + backend + admin 各一提交 |
| 2026-10-19 | **ROADMAP 结构调整**：S1 标记完成；切片表增「涉及仓库」列；S6 拆 **S6a**（退号/退款/签到/爽约）/ **S6b**（停诊处理/黑名单/分诊台）；S2 明确停诊**登记**边界（处理在 S6b）；补集成测试 ④⑤⑥；新增「§3.9 亮点 ↔ 切片 ↔ 验收证据」矩阵（13 条）；§7 改为 **E 系列**（E1–E5）；患者端（uni-app）整体延后至后端/后台完成后 | docs 单提交 |
| 2026-10-19 | **S1 数据完整性补强**（进 S2 前审计发现）：① 时段模板校验起止时刻（`end > start`）与步长（`> 0` 且 `≤ 时长`）——**S2 生成的硬前置**（否则死循环/0 号源）；② 医务人员 / 收费标准 / 时段模板 的 `clinic_type` 必须存在且启用；③ 科室 `parent_id` 校验（不存在 / 自身 / 成环），`level` 由父级推导（忽略手填）；④ 门诊类型 `code` 被引用后禁改；⑤ 存量 SQL 自查：模板/科室 0 异常，清理 1 条 `clinic_type` 失配的测试医务人员 | backend + docs 各一提交 |
| 2026-10-19 | **S2 前置收尾**：`slot` 删除增「有有效挂号则拒绝」（契约 §8.1-7 / PRD §6.2）；`slot_template` 删除增「已生成排班则拒绝」（§8.1-5，按 staff_id+period+clinic_type 判定）；ROADMAP 状态修正（S1 完成、`uk_patient_id_hash` 已接 `IdNoEncryptor`） | backend + docs 各一提交 |
| 2026-10-19 | **图片字段 ossId 翻译修复**：实测 `image-upload` 回填的是 **ossId** 而非 URL（库里存成 `2111926308599402498`，列表把纯数字当相对地址 → 图片裂开）；按框架约定给 `ApptMedicalStaffVo` 加 `avatarUrl`、`ApptCampusVo` 加 `coverImageUrl`（`@Translation(OSS_ID_TO_URL)`），列表绑 `xxxUrl || xxx` 兜底历史 URL 数据；导出移除图片列（翻译只在 JSON 序列化生效）；实测 MinIO 匿名 GET 返回 200（此前 400 是我 curl 拼错前缀） | backend + admin + docs 各一提交 |
| 2026-10-19 | **枚举三处副本对账**：新增 `backend/script/enum_sync_audit.py`（options.ts ↔ VO 注解 ↔ §2/契约 §2.7/技术方案 §3.6）——首跑抓出 8 处不一致：`PAY_CHANNEL` 缺 `alipay`、`CHECK_TYPE` 标签带 R 编号差异、`level/isDefault/signFlag/activeFlag` 无 UI 映射、`staffFavoriteVo` 残留假注解 `s=ys_user`；**并发现 R6/R7 中文名错位**（应为停诊漏处理 / 余量缓存漂移）——已全部修正，复跑「全部一致」 | backend + admin + docs 各一提交 |
| 2026-10-19 | **就诊人证件号加密器**：`IdNoEncryptor`（HMAC-SHA256 摘要 + 可选 AES，`appt.security.id-no.*`）落地 D-S1-3/M11；`ApptPatientServiceImpl` 新增/修改计算 `id_no_hash`、`uk_patient_id_hash` 撞停用行重新启用；VO 不返回证件号（红线 15）→ 编辑留空即不修改；就诊人页账号改下拉；摘要与 Python 独立计算比对一致（`a222…3a9c`） | backend + admin + docs 各一提交 |
| 2026-10-19 | **图片上传接入**：复用项目一 MinIO（`blog-minio:9000`，独立 bucket `appt` + prefix `appt/`，公有只读，匿名 GET 实测 200）；`sys_oss_config` 新增 `minio` 行（`status='Y'` 默认配置）；医务人员「头像」、院区「封面图」改 `<image-upload :limit="1">`、列表改 `<image-preview>`；gen `html_type` 两列回 `imageUpload`（`appt_s2_oss_config.sql` 固化，防同步/重新导入回退）；字段仍存 URL 字符串 | backend + admin + docs 各一提交 |
| 2026-10-19 | **通知场景线值定义**：`notice.type` 7 个线值（`BOOK_SUCCESS` / `PAY_SUCCESS` / `PAY_TIMEOUT` / `CANCEL_SUCCESS` / `SUSPEND_CANCEL` / `NOSHOW_RECORD` / `BLACKLIST_HIT`）按「事件」命名写入 database-design §2；`options.ts` 加 `NOTICE_TYPE_OPTIONS`、notice 页补回筛选下拉 + 列翻译；`ApptNoticeVo` 加 `@ExcelDictFormat`（探针 7/7 命中）；退款通知 PRD §6.12 未列，预留 `REFUND_SUCCESS` 说明 | backend + admin + docs 各一提交 |
| 2026-10-19 | **S2 开发轮（排班生成与放号）**：`SlotGenerateService` 两阶段（plan 只读 → apply 按 (staff, 日期) 一事务）；模板仲裁为「优先 `staff.clinic_type`，否则 id 最小」；fee 按 (职称, 门诊类型) 预加载、缺档位直接报错；`slot_ledger(GENERATE)` 与新增号源 1:1；F1 两端点 `POST /appt/admin/schedule/generate` + `GET /appt/admin/schedule/preview`（`appt:schedule:add`）；`apptReleaseJob` 执行器 + Redisson tryLock + `appt_job_log` 留痕 + 启动补偿；admin 排班页「生成排班」对话框（预览 / 生成 / 全体有模板人员）+ 菜单脚本 `appt_s2_menu_generate.sql`；停诊登记经确认整体移至 S6b | backend + admin + docs 各一提交 |
| 2026-10-20 | **S2 验收与体验收口**：控制台「执行一次」连跑两次均 SUCCESS（首轮 80 排班 / 2820 号源，重跑 0 / 0 / 跳过 2820，集成测试④达成）；启动补偿加 `booking.release.compensate-after-time`（默认 08:00，防 08:00 前重启提前放号）；排班 / 号源列表的医务人员·科室·院区由 id 改名称（`ApptNameFiller` 服务端批量回填，导出同步改名称）；号源页与导出去掉内部外键「排班」列；S2 标记完成，停诊登记整体归 S6b | backend + admin + docs 各一提交 |
| 2026-10-20 | **S3 开发轮（挂号链路与并发）**：B1 `POST /appt/patient/registration` 全链路 —— 幂等三键（执行锁 30s / 结果 24h）+ Redis 占位（15min、Lua 安全释放、异常降级纯 DB）+ `sys_user` 账号行 `FOR UPDATE` + 限购三条锁内精查 + `AVAILABLE→TAKEN` CAS（含 OCCUPY 台账）+ `payment(WAIT_PAY)`；`ApptBizException` + `BizCode` 统一 `data.bizCode`；`payment.expire-minutes` 配置化；患者账号与 2 就诊人 seed + 集成测试脚本（并发/幂等/限购/窗口外）；挂号单列表补就诊人与医生/科室/院区名称；集成测试① 实测 `PASS=14 FAIL=0 SKIP=0`；摘除防线①（`appt.slot-hold.enabled=false`）对照组同样 1 成交 / 49 由 DB CAS 拒绝；新增 `docs/test-evidence.md` 沉淀 S2/S3 数字 | backend + admin + docs 各一提交 |
| 2026-10-20 | **S4 开发轮（支付链路）**：`PaymentChannel` 抽象 + Mock 渠道；C1/C5 回调共用 `PaymentCallbackDispatcher`（验签 → `appt_payment_callback` 三列去重 → 立即 ack → 有界线程池 + 新事务异步入账）；C2 模拟支付三分支（SUCCESS 合成回调 / FAIL 只留痕 / TIMEOUT 复用关单服务）；C3 状态查询 + 5 秒节流主动查单；`apptPaymentCloseJob` 两段式关单（近过期查单 + 到期关单，三步 CAS + RELEASE 台账 + 释放占位）；「钱到了号没了」自动建退款单走 C5 闭环保留 `payment=CLOSED`；支付/退款只读页补单号与名称；集成测试 `PASS=20 FAIL=0 SKIP=0` | backend + admin + docs 各一提交 |
| 2026-10-19 | **导出 LocalTime 修复**：fesod 2.0.2 无 `LocalTime` 转换器（`LocalDate`/`LocalDateTime` 有内置），时段模板导出抛 `ExcelWriteDataConvertException`；新增 `appt.excel.LocalTimeConvert`（导出 `HH:mm:ss`、导入兼容 `HH:mm[:ss]`），`slotTemplate.startTime/endTime` 挂载；AGENTS §6 记第八坑；探针真实写 xlsx：slotTemplate/schedule/slot/registration/campus 五个 VO 全部 PASS | backend + docs 各一提交 |
| 2026-10-20 | **S5 开发轮（查询聚合与余量缓存）**：A1–A7 公共查询组（院区 / 科室树按「该院区有出诊医务人员」剪枝 / 医生分页与主页（`favorited` 可选登录，未登录 false 不 401）/ 日期栏双模式 / 当日出诊医生 + 午别余量 / 可约时间点），D1 窗口统一取 `booking.window.days`，窗口外按无数据返回空集合；余量改「一次聚合」`GROUP BY schedule_id, period`；`RemainService` 读（MGET → 回源 → SETNX 回填 600s）写（`SlotStateService` afterCommit → Lua `EXISTS→INCRBY`，无键不创建，过期 0 增量）+ `appt.remain.cache=redis\|db` 开关；admin 排班页余量列；新增两个脚本（读压测 / 1000 次一致性） | backend + admin + docs 各一提交 |
| 2026-10-20 | **S5 验收实测**：读压测 100 并发 ×1000 样本 ×3 轮 —— 单屏 SQL 冷启动 3 条 / 命中 2 条 / `db` 3.2 条（与医生数无关），`redis` p95 9.3ms、命中率 100%，`db` p95 10.6ms（差距 14%，落在波动内，默认保持 `redis`）；一致性 1000 次「挂号 → 超时关单回补」差值恒 0 + 删键不创建（`PASS=11 FAIL=0`）；回归 S3 `PASS=14`、S4 `PASS=21`；压测脚本修两处健壮性（跳过无人员的残留院区、`date +%s%N` 计时）与 token 兼容（`APPT_TOKEN` 或 `TOKEN`） | backend + docs 各一提交 |
| 2026-10-20 | **S6a 开发轮（状态机闭环与售后链路）**：退号 B5（单柱 CAS + 回池 + 事务内建退款单 + 事务外渠道退款 + `CANCEL_SUCCESS` 站内信）、签到 E1/E2（`@SaCheckRole("triage")`，同一条状态边）、爽约+过期合并扫描（主批 + 全量兜底 + `NOSHOW_RECORD` 站内信 + `SlotStateService.expire` 余量 −1）、置完成 23:30、B2 我的预约列表 / B3 详情（就诊码、证件号脱敏）、后台手动退号 F10、任务手动重跑端点（白名单 4 任务）、`appt_s6a_seed.sql`（triage 角色/账号 + 两个按钮权限）、`s6a_state_machine.sh` | backend + admin + docs 各一提交 |
| 2026-10-21 | **E 系列收尾（E2/E3/E4）**：E4 核查后直接销项（`appt_s0_cleanup.sql` 已含「AI控制台」且库内 15 个残留菜单 id 全为空、`pnpm-lock.yaml` 早已入库）；E2 新增 `backend/deploy`（compose 三件套 + `init-db.sh` 一键导 8 个 SQL，端口避让既有容器，SnailJob 标注为外部依赖）；E3 新增两个 GitHub Actions 工作流 + 首个单测 `SuspendScopeParserTest`（8 例全绿） | backend + admin + docs 各一提交 |
| 2026-10-23 | **两条遗留收口**：① `request.ts` 空 body 不再吞状态码，非 200 报「服务不可达（404），请检查接口地址或网络」并 toast —— 正是这次被 QQ 占用 8082 误导的那条文案；② `jsencrypt` 一度改动态加载，**随即回滚**（见下一行） | app + docs 各一提交 |
| 2026-10-24 | **Logo 方向筛选与决策（未开工，仅定方案）**：出 13 个候选（A 号牌族 / B 字母 Q / C 日历族），逐个渲染三色态比对，淘汰 `A3e`（叠层会把挖空填平）、`A3f`（近圆+底部缺口读作聊天气泡）、`B2`（十字断口像救生圈）、`B4`（缺口像破损）；**选定 `A3c` 十字牌·点阵为母标**，并确定 responsive logo 三档简化规则（≥48 完整 / 24–48 去点阵 / ≤24 仅十字）。同时把「Stitch 只作版式参考、必做四类回调、结论回写 DESIGN」固化为 `app/DESIGN.md` §13。**踩坑**：多张 SVG 内联时 `<mask id>` 重名会让所有图形共用第一个 mask → 改用 `fill-rule="evenodd"` 挖空 | app + docs 各一提交 |
| 2026-10-24 | **交付阶段规划（S12–S16）**：功能阶段 S1–S11 结束，按"先做不依赖服务器的、且演示当天能被看见的"排出六个切片——S12 品牌与首屏（logo / tabBar 图标 / 后台首页换运营看板）、S12.5 全站视觉统一（后台主题+表格+状态、移动端剩余 7 屏）、S13 门面与物料（根 README / DEMO 剧本 / 脚本化截图 / ADR）、S14 一键演示（`demo.sh` + 镜像 workflow）、S15 医院感细节（流程条 / 院区信息 / 须知页）、S16 线上部署（阻塞：服务器）。明确不做：微服务拆分、K8s、真实支付、多租户、i18n、暗色模式 | docs 提交 |
| 2026-10-24 | **收尾两处偏差**：① `SignListVo` / `SignResultVo` 的 `timePoint` 补 `@JsonFormat(pattern="HH:mm")` —— 此前 E1/E2/E3 返回完整时间戳、与契约 §2.4「对外恒为 HH:mm」不一致（靠前端 `timePointText()` 兜底）；补齐后全仓 `timePoint` 统一，`signTime` 仍保留完整时间戳（事件时间，前端 `shortDateTime()` 渲染）。② `deploy/docker-compose.yml` 的 `mysql`(3307) / `minio`(9010-9011) 标注**当前未启用**（复用宿主机 `blog-mysql:3306` 与外部 MinIO，后端也仍指向它们），并写明启用前需同步 `application-dev.yml`；`deploy/README.md` 同步 | backend + app + docs 各一提交 |
| 2026-10-23 | **全项目体检轮（限购改口径后的回归补齐）**：`s3_b1_concurrency.sh` 实跑 **`PASS=11 FAIL=0`**（原 14 条因「限购三条」合并为一条而减少；同日跨科室 `LIMIT_PATIENT_DAY`、不同就诊日各 1 单均验证），并修脚本头部说明与章节跳号（3→4→6 改为 3→4→5）；`s8_patient_aux.sh` 实跑发现 **1 处不兼容**（第二笔下单假设可同日下两单；收尾退号深夜必失败导致残留单抬高下一轮限购）→ 改为「第二笔换就诊日 + 前/后置 SQL 作废回池 + `window_slot` 按就诊人口径排除」，复跑 **`PASS=29 FAIL=0 SKIP=0`**；`s9_patient_crud.sh` 复跑 **`PASS=23 FAIL=0`** | backend + docs 各一提交 |
| 2026-10-23 | **回滚 `jsencrypt` 动态 import（小程序登录必崩）**：静态 `import { JSEncrypt }` 时正常；改成 `await import()` 后，uni 的 **mp-weixin 构建把 `import()` 编成 `require(...)` 再 `.then(...)`**，`require` 返回模块对象不是 Promise → 真机/工具登录报 `"/common/vendor.js" is not a function`。已回滚并在 `encrypt.ts` 注释里写明禁止原因；H5 分包收益远小于该坑 | app + docs 各一提交 |
| 2026-10-23 | **小程序真机扫码签到验收通过**：微信 8.0.66 / 基础库 3.17.5，用真实 AppID + `portproxy` 18082；患者端详情二维码（`visitCode=R20261023000099`）→ 分诊端「扫一扫」→ E1 → `SIGNED` 成功，同一码二次扫报 `SIGN_WINDOW_CLOSED`。小程序链路与 H5 手动补签共用同一状态机，至此 S11 分诊台三项（签到/当日/停诊）全部端到端可用 | docs 提交 |
| 2026-10-23 | **小程序真机联调的最后一道坎：Windows 8082 被 QQ 占用**：`Test-NetConnection` 通但接口 404 空 body、后端日志无请求 → `tasklist` 显示 `QQ.exe(31612)` 占 `0.0.0.0:8082`，`netsh portproxy` 静默绑定失败。改用 `listenport=18082`（→ WSL `172.31.124.129:8082`）后 `curl.exe` 返回 200；`dev:mp-wsl` 默认 baseApi 同步改为 `http://192.168.0.108:18082`，README 补「connectaddress 必须填 WSL IPv4」「空 body 404 = 端口被占」两条判定 | app + docs 各一提交 |
| 2026-10-23 | **小程序真机白屏定位与修复**：真机（微信 8.0.66 / 基础库 3.17.5）除导航栏与 tabBar 外全白，真机调试 Console 报 `ReferenceError: TextEncoder is not defined`（栈 `crypto.js → request.js → 页面`）。根因：`utils/crypto.ts` **模块顶层** `new TextEncoder()`，而它被 `request.ts` 顶层 import、`request` 又被所有页面 import → 页面求值阶段抛错。修：改纯 JS UTF-8 编解码（Node 直跑 AES 往返 4/4、产物 0 引用）。顺带补 `mp-weixin.setting` 的 `enhance/es6/postcss`、`dev:mp-wsl` 默认 baseApi 改局域网地址、README 补 WSL2 `portproxy` 口径（`connectaddress` 必须填 WSL IPv4，`127.0.0.1` 不通是因为 localhost 走 `::1`） | app + docs 各一提交 |
| 2026-10-23 | **s6b 回归补齐三种停诊范围**：原脚本只造 `SCHEDULE` 一种登记（`scopeValue` 即排班 id），恰好绕过「`staffId` 在独立列」这一类缺陷，导致两处停诊 bug 漏网。补 `STAFF_DATE`（同医生同日复用批号 / **换医生同日必须新批号** / 处理按 `staff_id` 展开且不误伤同院区其他医生）与 `CAMPUS_DATE`（`campusId:日期` 规范化 + 按院区展开）两个用例，**+17 条断言**，实测 `PASS=42 FAIL=0 SKIP=0`；造数取 +40/+41 天并前置校验无同域排班，退出自动清理 | backend + docs 各一提交 |
| 2026-10-23 | **分诊底栏隐藏「加号」**（用户确认 E4 不做）：`TriageTabbar` 由 4 项改 3 项（签到 / 当日 / 停诊），移除 `extra` 项与 `is-pending` 灰态逻辑；将来实现 E4 时加回一行即可 | app + docs 各一提交 |
| 2026-10-23 | **S11.1 停诊上报页的两处后端缺陷修复**（用户实测暴露）：① `SuspendReportService` 幂等去重只比 `scopeType+scopeValue`，而 `STAFF_DATE` 的 `scopeValue` 只编码日期、医生在独立列 → **换医生同一天被判「该范围已上报」**，已把 `staffId` 纳入判定键；② `SuspendHandleService.handle` 重新 `parse(scopeValue)` 时**不回填 `staffId`** → 排班展开变成 `staff_id = null`，命中 0 条 → **「处理成功」但一个号都没退**，已从记录回填并加空值保护。证据：用户那次 `S20261023000004`（STAFF_DATE / 10-24 / 演示医生01）状态 `HANDLED` 但该医生排班仍 `NORMAL`、停诊号源 0 条（空转无副作用）。前端同时清掉「换对象后旧批号仍挂着」的误导，结果卡增「停诊对象」行 | backend + app + docs 各一提交 |
| 2026-10-23 | **S11.1 停诊上报页**（用户按「A 方案」追加）：分诊台底栏「停诊」接上真实页面——范围三选一 + 院区/科室/日期/医生/午别级联（数据源 A1/A2/A6）+ E5 提交 + 批号结果卡，页面上明示「上报后由后台停诊处理执行退号与退款」。**零后端改动**；实测三种 `scopeValue`（`campusId:date` / `date~date` / `scheduleId`）与同范围幂等复用批号（`duplicate=true`）。分诊台可用项 2/4 → 3/4，仅剩「加号」依赖 E4 | app + docs 各一提交 |
| 2026-10-23 | **S11 患者端辅助页 + 分诊台**：5 屏落地（预约详情含就诊码与退号 / 我的就诊人 / 我的医生 / 消息列表+详情 / 分诊签到+当日列表）；顺带两处收口：**限购改「同一就诊人同一天 1 个预约」**（`LIMIT_PATIENT_DAY`，原「持有 3 单 / 同科室同日 / 同时间点」三条停用，`uk_*` 索引留作兜底）、**站内信时间格式去 `T` 与纳秒、午别转中文**（`ApptDisplayUtils`）；另修三处体验缺陷（`wd-popup` `z-index` 被底栏遮挡导致「保存」点不到、医生页进排班却列全科、支付回跳未落「已预约」tab）；全站文案统一为医院官方书面语（DESIGN §8.1 新增语气规则）。**踩坑**：`@click="fn"` 会把事件对象作为第一参数传入，落点意图被存成 MouseEvent → tab 全不匹配且列表为空 | app + backend + docs 各一提交 |
| 2026-10-22 | **S10 患者端主链路（9 屏 + 两处后端补口）**：Phase 0 用 Stitch 审 4 屏并修订 `DESIGN.md`（hero 240rpx 消歧、§9.1 快捷科室口径、§9.3 无医生数、§9.4/§9.6 字段下调、§9.8 端点出处、§9.9 四 tab + 默认落点）；实现 9.1–9.9 与基座（`store/booking`、`api/appt/{public,patient,payment}`、`utils/appt`、`useAsyncData`、6 个公共组件、`styles/appt.scss`）；后端补 A6 `periods[].scheduleId` + B4 待支付取消端点 + 患者端三 VO `timePoint` 加 `@JsonFormat(pattern="HH:mm")`。**踩坑四条**：`wd-popup` 默认 `z-index:10` 被底部固定条（20）压住 →「保存」点不到、从医生页进排班页却列全科医生（改医生/科室双视角）、tabBar 页带不了 query（落点改走 store 一次性意图）、`timePoint` 契约与实现不一致 | app + backend + docs 各一提交 |
| 2026-10-22 | **E5 设计规范**：`app/DESIGN.md` 十个页面 blueprint + 11 段 Stitch prompt + 8 状态色映射 + 12 类组件规格 + 10 条禁止项；README/AGENTS 加指向。用 Google Stitch 实跑 9.1 首页验证：主题色（#1F7A8C）与结构还原正常，但 Stitch 自行加入「步行距离 / 专病门诊 / 医保定点 / 今日有号」等契约外字段与装饰纹样 —— 前者由 §10「不臆造字段」覆盖，后者已补进禁止项 | app 2 提交（`2c753f1` / `89c6e20`，均已推送） |
| 2026-10-22 | **S9 就诊人管理**：患者端 `/appt/patient/patient/**` 五个端点（列表/新增/修改/删除/设默认）+ `PiiUtils` 统一脱敏 + 2 个新错误码 + `PiiUtilsTest`(5 例) + `s9_patient_crud.sh`；`PASS=23 FAIL=0`。**实跑方式**：因 token 过期，用 `GET /auth/code` 的 uuid 从 Redis 读验证码后完成一次真实加密登录再跑脚本 | backend + docs 各一提交 |
| 2026-10-22 | **E5 建仓**：`qd-appt-app` 从官方 vite-ts 模板起，I1 双角色导航 / I2 请求与加密登录 / I3 路由守卫 / I4 构建与类型 / I5 门禁与 CI + 6 个骨架页；H5 起在 8084 走 `/dev-api` 代理，双角色切换可用。**踩坑三条**：pnpm 12 需 `allowBuilds` 白名单、`types/api.d.ts` 里的 class 不能被运行时导入、`pages.json` 漏 add（已补提交） | app 6 提交 + backend `942e690` |
| 2026-10-21 | **文档门禁上线**：`docs/script/doc_audit.py` 五类检查 + docs CI + AGENTS §5 Definition of Done；首跑捕获并修复 3 处（S1 父项未勾、S3 页面项无归属、§8 历史行误报）；README 索引补脚本行并刷新版本号 | docs 一提交 |
| 2026-10-21 | **排片：新增 S9、S10、S11，E5 收窄**（仅文档）：S9 = 就诊人管理 B6–B10（盘点发现患者端只有后台 `/appt/admin/patient`，B1 挂号依赖 `patientId`，是 E5 最后一个后端硬前置）；E5 收窄为「建仓 + 脚手架」，页面拆为 S10（患者端主链路）与 S11（辅助页 + 分诊台）——功能切片仍全部 S 编号，E 系列只管工程基线；核实小程序账号可开发不可发布（未备案/未认证/医疗类目需资质） | docs 一提交 |
| 2026-10-21 | **S8 开发与验收（患者辅助组）**：收藏三件套 / 消息三件套 / 分诊当日签到列表 + 三类站内信补齐 + 契约 §6/§7.3 字段级；`s8_patient_aux.sh` `PASS=29 FAIL=0`。**修脚本 4 处**：把 HTTP 200 当业务成功（RuoYi 业务码在 body）、收藏 `status` 语义反了（`'0'`=正常却判成停诊）、第二笔下单撞同科室同日（改为「按账号真实可约」选号）、残留占位键导致 `SLOT_GONE`（下单前清 `appt:slot:hold:*`）。**修种子 2 处**：注册单与就诊人一并隔离到虚拟账号，避免演示账号被限购/黑名单锁死 | backend + docs 各一提交 |
| 2026-10-21 | **S7 验收实测**：`s7_reconcile.sh` `PASS=22 FAIL=0`（批次 `RC20261021000004` / 1774ms / 发现 14 修复 12 告警 2；二次跑归零、R5 重试 ≤1）；看板接口与 SQL 逐项一致；seed 500 排班 / 9000 号源 / 2000 单（8 状态齐全）灌入 ~45s、自洽性 `ghost=0 / unoccupied=0`。**修脚本两处**：① 造数跨排班隔离（R6 是排班级，同排班会把 R2/R4 的断言对象一并退掉，产生假 FAIL）+ 去重自检；② `set -u` 下 `R3_SCHED` 先解析后使用（否则 R4 重复选中 R3 的排班） | backend + docs 各一提交 |
| 2026-10-21 | **S7 开发轮（对账与交付）**：七查 R1–R7（`ReconcileCheck` 扩展点、单项 try/catch 隔离、`RC` 批号、异常一行一记录）、`SlotStateService.reclaimGhost`（幽灵占号，无有效单才回池）、`POST /appt/admin/reconcile/run` + `apptReconcileJob`（03:00，白名单可手动重跑）、看板 7 指标 + 科室 TOP5（口径写死 `visit_date=CURDATE()`）+ 后台卡片/柱图页 + 对账页「立即对账」、`appt_s7_business_seed.sql`（500/9000/2000，8 状态自洽）、`appt_s7_seed.sql`（看板菜单 + 两个权限点）、`s7_reconcile.sh`、`docs/README.md` 三步启动 | backend + admin + docs 各一提交 |
| 2026-10-21 | **S6b 验收实测**：`s6b_suspend_blacklist.sh` `PASS=25 FAIL=0`（E5 登记与幂等 / F2 八项副作用 / 已签到跳过 / 余量 5→4 / 重复处理 `handled=false` / 黑名单拦截+建单+通知）；页面验收「停诊登记 → 处理」摘要与挂号单、退款单、站内信、排班四处一致；黑名单页显示 `system` 自动行、站内信 `BLACKLIST_HIT` 内容正确。**修脚本四处**：断言查错列（`appt_registration` 无 `registration_id`）、黑名单用例漏 `Idempotency-Key`、手工造数 SQL 误依赖已删除的临时排班、S3 的 `LIMIT_HOLD_MAX` 选号（原按「每科室首个号源」挑，候选全挤在同一天 08:00，去重后凑不满 3 笔；改为「科室 × 就诊日」组合后 `PASS=14`） | backend + docs 各一提交 |
| 2026-10-21 | **S6b 开发轮（停诊批量与黑名单）**：E5 登记（区间编码 / 同范围幂等 / S 批号）+ F2 处理（批号锁、≤100/批、排班/号源停诊、被动退号、退款、WAIT_PAY 关单、已签到跳过、`SUSPEND_CANCEL` 通知）+ 黑名单惰性判定（账号行锁内计数、`REQUIRES_NEW` 建名单、`BLACKLIST_HIT`）+ 后台「处理」按钮 + `appt_s6b_seed.sql` + `s6b_suspend_blacklist.sh` | backend + admin + docs 各一提交 |
| 2026-10-20 | **S6a 验收实测**：`s6a_state_machine.sh` `PASS=19 FAIL=0 SKIP=0`（退号 7 项含余量 −1 再 +1 / 截止 `REFUND_DEADLINE_PASSED` / 签到与重复签到 / 爽约主批 2 条 + 全量兜底 / 过期 `EXPIRE` / 置完成）；回归 S4 `PASS=21`、S3 `PASS=13 SKIP=1`（窗口外样本缺失，非回归）。脚本修两处：造数 SQL 误取 `appt_slot` 不存在的 `user_id/patient_id` 列、23 点后退号用例须取「今日+2」号源 | backend + docs 各一提交 |
| 2026-10-20 | **S5 手工验收收口**：A1 封面 `coverImageUrl` 翻译（ossId → URL，直链数据回空串由前端 `\|\|` 兜底）、A3 分页与中文关键字、A4 匿名 200/不存在 404、A5 医生模式定长 7 项、A6 下单 48→47 与关单回 47→48、`remain=0` 午别仍返回、后台余量列与导出（无该列）全部通过；发现并修两处：① 缺必填参数/参数类型不合法由框架 500 收口为 **400**（`ApptExceptionHandler` 加两个 handler 并按 appt 包限定 + 最高优先级）；② `releaseToPool` CAS 未命中时**仍释放本单占位键**（Lua 比对 value），消除「DB 可约 + Redis 仍占用」的孤儿键导致的持续 `SLOT_GONE`；重启后复跑 `s4_payment.sh` 仍 `PASS=21 FAIL=0` | backend + docs 各一提交 |
| 2026-10-24 | **S12 品牌与首屏完成**：A3c 母标脚本化（`pnpm brand:gen` 重出 30+ 产物：三档 SVG/PNG、反白、横版、favicon、封面）、患者端 tabBar 8 图标 + 分诊底栏 6 图标、后台品牌位（标题/母标/登录页/favicon/loader）与运营看板首页、患者端三屏抛光。副产修两处既有缺陷——① 母标三点与牌同色不可见（改 evenodd 负形子形状）② Wot 按钮主色取 `--wot-primary-6` 色阶而非 `--wot-color-theme`，未覆盖时落框架蓝（补主色阶与危险色） | app `9c1a1ea`、admin `7c47190`、docs 本提交 |
| 2026-10-24 | **S12.5 全站视觉统一完成**：后台主色三层收口（SCSS 变量 / settings 默认值 / Element 全阶桥接）+ 20 文件框架蓝替换、状态标签组件化（6 组状态 → `el-tag` 语义色）、表格密度与业务化空态、登录页青白两栏改版、404 与网络异常兜底页（移动端单页两模式 + 后台同口径）；四屏 Stitch 差异表结论回填 DESIGN §9.12–§9.14 与 `admin/AGENTS.md` §13 | app `4042127`、admin `c630354`、backend `cfcefad`（枚举审计兼容 `type` 字段）、docs 本提交 |
| 2026-10-24 | **S13 门面与物料完成**：新增第 5 仓 `qd-appt-showcase`（README + 10 张脚本截图 + Playwright 基建，免 root 补浏览器依赖库与中文字体）；`docs/DEMO.md` 五分钟剧本 + 小程序真机清单；`docs/adr/` 六篇 ADR 与索引；后台清残留（注册页页脚、第三方登录、示例菜单、演示账号昵称）与侧栏改浅色；SpringDoc 四分组 + `application-screenshot.yml`（只关验证码、关 snail-job）；修首页冷启动误跳兜底页。15 秒 GIF 亦已由 `node gif.mjs` 产出（14s / 5MB） | app `43036c1`、admin `30d46f4`、backend `5ae5c55`、showcase `604a07b`、docs 本提交 |
| 2026-10-25 | **S14 一键演示完成**：showcase 新增 `demo.sh` + demo compose（`include` 复用 `backend/deploy` 依赖，容器名与数据卷独立，可与开发机并存）；`init-db.sh` 加 `--full` 干净机全序导入（补 `ry_vue.sql` / `s0_cleanup` / `s13_menu_showcase` / `e5_client_access` / `oss_config`）并覆盖 OSS 地址；三仓各加 Dockerfile（后端多阶段 + `application-docker.yml` 全环境变量化；前端 nginx 模板运行时注入上游）+ `.env.example` + `image.yml`（tag 推 ghcr，手动默认只 build）。实测 `./demo.sh` 首次 1m44s / 复跑 58s，两套账号按「真实验证码 + RSA/AES 加密」登录 200；镜像 api 793MB / snailjob 638MB / admin 109MB / h5 95.1MB。**踩坑**：Alpine(musl) JRE 的 fontconfig 在本项目不可用（库与字体齐全仍报 `Fontconfig head is null`）→ `/auth/code` 500、验证码裂图；改 glibc 基底（`eclipse-temurin:21-jre-jammy` + fontconfig + DejaVu）修复。**追加**：SnailJob 服务端容器化（`Dockerfile.snailjob` + `appt_s14_snailjob_seed.sql` 固化手工建的任务 + compose 服务，宿主 18800/27888），demo 八步含 SnailJob | showcase + backend + admin + app + docs 各一提交 |
| 2026-10-26 | **S15 医院感细节完成**：患者端补四层说明信息——① `StepGuide` 五节点流程条（首页静态说明 / 详情页三态，四个终态只留终止说明）；② 就诊指南 + 院区详情（A1 四态，电话·门诊时间·交通指引按院区名称匹配虚构常量）；③ 须知与规则五组条款（数字对齐 PRD §6.7/§6.8/§6.9/§14.1）；④ `AppFooter`（5 页）与 `EmergencyTip`（3 页）。三页入匿名白名单（未登录可读），`pages.json` 21 → 24 页；DESIGN 补 §8.3 固定文案与 §9.15–§9.17 blueprint。**零后端接口、零表结构改动** | app + docs 各一提交 |
| 2026-10-26 | **S15 验收收口 + 登记 S15.2**：验收发现预约详情「就诊医生」行把职称线值（`PHYSICIAN`）直接显示出来 → 统一走 `titleLabel()`；确认「已完成仍显示就诊码」符合契约 §4.3 与 `DESIGN §9.10`，不是缺陷；另发现「我的预约」缺 `SIGNED` 入口，登记为 **S15.2（未开始）** | app + docs 各一提交 |
| 2026-10-26 | **S15.1 SnailJob 任务补种完成**：`appt_s14_snailjob_seed.sql` 由 2 条扩到 5 条（新增 `apptNoShowJob` / `apptCompleteJob` / `apptReconcileJob`，id 4–6），`next_trigger_at` 按任务分策略（爽约取下个 5 分钟整点，其余延次日）；dev 库同步补 3 行。**数据侧同步收口**：手工跑满爽约扫描（299 条过期 `BOOKED` → `NOSHOW`、5255 条 `AVAILABLE` → `EXPIRED`、补发 299 封 `NOSHOW_RECORD`），并把 admin 名下 6 条测试单改归属到造数虚拟账号 `1761400000000003199`，避免主账号违约计数触线被锁半年。实测 `apptNoShowJob` 于 01:00:00 自动触发并推进到 01:05:00 | backend + docs 各一提交 |
| 2026-10-26 | **登记 S15.3 + 环境清理**：对账实测暴露「终态不释放号源」（R1 报 505 = 299 爽约 + 206 完成），登记为 **S15.3（未开始）**，写明修法与回归四条状态边；dev 库顺手删掉没有执行器的框架 `demo-job`，`sj_job` 归一为 5 条业务任务（id 2–6）；`appt_reconcile_result` 只有本轮 `RC20261026000001` 一批（507 条），无历史批次可清 | docs 提交 |
| 2026-10-26 | **S15.2 已签到入口完成**：「我的预约」的「已预约」tab 内加子筛选「已预约 / 已签到」（`subState` 按 tab 记忆 + `queryStatus` 三分支，B2 仍一次一个状态）；`SIGNED` 行由错误的「再次预约」改为「查看就诊码」；已签到空态改专用文案；`DESIGN §9.9` 的两级结构与「状态 → 动作」口径按实现订正。零后端改动 | app + docs 各一提交 |
| 2026-10-26 | **S15.3 终态号源释放完成**：`SlotStateService.expireTaken()`（`TAKEN → EXPIRED`、清占用、写 `EXPIRE` 台账、余量 0）+ `RegistrationStateService.markNoShow / markCompleted` 同事务调用；两个任务查询补 `slot_id`。实测两条夹具各 `affected=1`，台账时间落在流转时刻（02:47:13 / 02:47:59），随后「立即对账」七查全 0、结果 0 行（S15.1 时为 507 条），幽灵占号 0 | backend + docs 各一提交 |
| 2026-10-29 | **部署方案 + wsl 公网联调 + S16 拆片**：新增 `deployment-cicd-plan.md`（只写"怎么做"，进度以本文件为准；sd-blog 降为附录 C，不并行）；本机手工打通 wsl 目标——DNSHE 免费域名 `qdappt.us.ci` 接入 Cloudflare、Named Tunnel systemd 常驻、`admin`/`demo` → 容器 18083/18084、HTTPS + 验证码 + RSA/AES 登录、下单 → Mock 支付 → 站内信；SSE 通道可用但连接约 55 s 被中间层回收（心跳 60 s），**决定先记录不修**。**S16 拆为 S16.1（不依赖服务器）/ S16.2（依赖服务器）**，原 5 条 checkbox 按"是否需要服务器"重新归属。未勾任何框、未推镜像、未改代码 | 仅 docs 仓 |
| 2026-10-30 | **S16.1 完成**：compose 五件套去 `build:`（部署机只 clone showcase）；`deploy.sh` 七子命令 + `.state` 回滚 + 数据目录守卫；四枚镜像首推 GHCR `v0.1.0`；`release.yml` 走自托管 runner（run #4 1m09s 全绿）。实测：发布 39s / 回滚 42s / 前滚 46s / 备份 1s / 恢复 62s（行数前后一致），公网两域名全程 200。三个真问题已修：redis 6380 撞车、`../data` 解析成空库、preflight 读不到跨仓私有包 | showcase 5 提交 + backend 1 提交 + docs |
| 2026-10-30 | **重启后自启复验 + 部署文档纠偏**：整机重启后演示栈 7 个容器自动恢复（`Up 3 minutes`、六项 healthy）、五项业务探活全绿、数据目录 `/home/user01/qd-appt-data` 266M；同时暴露两处口径问题——`.state` 随脚本位置分裂（`~/qd-appt-deploy` 与 `showcase/deploy` 各一份，后者显示「版本为空」、`rollback` 会报没有 previous）、`curl -sI ... \| head -1` 在代理下把 `HTTP/1.1 200 Connection established` 当成站点 200。`deployment-cicd-plan.md` 同步：命令行统一子命令式、公网探活改 `--noproxy` + 状态码、§7.6 补「执行入口唯一」、Q4 与 Phase 1–3 标已闭环 | 仅 docs 仓 |

---

## 6. 待决项（阻塞或不明确，需拍板）

| # | 事项 | 影响 | 现状 |
|---|---|---|---|
| 1 | ~~定时任务载体~~ | §9.3 §9.4 §9.6 | **已定 2026-10-18：snail-job 2.0.2**（框架自带；保留 Redisson tryLock 防叠加，职责不重叠）。落地步骤：导入 `ry_job.sql` 建 `sj_*` 库 → 启动 `ruoyi-snailjob-server` → 任务类改用 `@JobExecutor`。技术细节见 `技术方案.md` §1.2 / §3.3 |
| 2 | ~~`appt_fee_standard` 缺 `status`~~ | 与启停类公约不一致 | **已闭环 2026-10-18**：DDL + 库内 ALTER 已加 `status char(1) DEFAULT '0'`；`database-design.md` 启停类清单（8 张表）、字段表、索引总表、已知边界同步 |
| 3 | ~~就诊人停用过滤未写进契约~~ | 停用就诊人仍可被选中挂号 | **已闭环 2026-10-18**：契约 §4.6 补「仅返回 `status='0'`；后台管理端不加此过滤以便恢复」 |
| 4 | 初始数据（seed）**何时生成** | S5 性能对比、集成测试、S7 对账都依赖 | **已部分闭环 2026-10-19**：S1 六表基础数据 seed 已落地（`appt_s1_seed.sql`，固定 id 段可重跑）；**业务数据 seed**（~500 排班 / ~9000 号源 / ~2000 挂号单覆盖 8 状态）仍归 S7，S5 提前需要量级数据时再议。规模见 PRD §11 |
| 5 | plus-ui 后台页面**无切片归属** | 排期可能漏 | 本文件 §2 已按里程碑反推补齐，**待确认** |
| 6 | ~~PRD §13.3 是否改为指针~~ | 双权威漂移 | **已闭环 2026-10-18**：PRD §13.3 已改为指向本文件 |
| 7 | seed 数据规模与虚构医院名 | PRD §11 红线 | 3 院区 / ~40 科室 / ~60 医务人员 / ~500 排班 / ~9000 号源 / ~2000 挂号单，覆盖 8 种状态 |

---

## 7. E 系列：工程基线切片（横切，不属于 S 系列）

> 横切工作不再塞进功能切片，统一编号 E。每片只跨必要仓库，验收独立。

- [x] **E1 仓库规范**：`backend/AGENTS.md`、`admin/AGENTS.md` 已建；docs 以 `redlines.md` + 本文件为准
- [x] **E2 启动与部署基线** —— 2026-10-21：`backend/deploy/{docker-compose.yml, init-db.sh, README.md}`。MySQL 8.4 / Redis 8 / MinIO 三件套，宿主机端口刻意错开既有 `blog-*` 容器（**3307 / 6380 / 9010-9011**）；`init-db.sh` 等健康检查后按序导入 8 个 SQL（结构 → 基础数据 → 菜单 → 账号 → 各切片 seed → 演示业务数据，幂等）；`docker compose config` 校验通过。**SnailJob 不纳入**（无稳定公共镜像，按官方发行包单独部署，缺它后端仍可启动、任务可手动重跑）
- [x] **E3 CI** —— 2026-10-21：`backend/.github/workflows/ci.yml`（JDK 21 + `mvn -B -pl ruoyi-modules/appt -am clean test`）、`admin/.github/workflows/ci.yml`（`pnpm install --frozen-lockfile` → `vue-tsc` → `oxlint` → `vite build`）。同时补上本仓**第一个单测** `SuspendScopeParserTest`（8 例，纯逻辑不连库：单日/区间/院区编码、SCHEDULE 拒区间、倒序/超跨度/早于今天/未知类型），`mvn test` 通过
- [x] **E4 数据脚本收尾** —— 2026-10-21 核查：两项在 S 系列期间已顺手完成（`appt_s0_cleanup.sql` 已含 `1761400000000000121` 且库内该菜单与其余 14 个残留 id 均查询为空；`admin` 仓 `pnpm-lock.yaml` 早已入库且未被 `.gitignore` 命中），本轮只更新状态与留档
- [x] **E5 `qd-appt-app` 建仓 + uni-app 脚手架**（**只做基线，不含业务页面**）—— 2026-10-22 完成
  - 模板：`dcloudio/uni-preset-vue#vite-ts`（upstream `6fb81ac3`，首提交记录来源）；实测版本 uni-app `3.0.0-5020420260813003` / vite `5.2.8` / vue `3.5.44` / TS `5.9.3` / vue-tsc `2.2.12` / `@wot-ui/ui` `2.3.2` / pinia `2.3.1` / pnpm `12.4.1` / node `24.21.0`
  - 基础设施：I1 双角色导航（患者原生 tabBar 四项 + 分诊自绘底栏 + `reLaunch` 互跳）、I2 请求与鉴权（`body.code` 语义、401 并发只跳一次、加密登录 AES-ECB + RSA 公钥、`Idempotency-Key` 降级）、I3 路由守卫（`uni.addInterceptor` 四类跳转）、I4 构建与类型（`Components()` 在 `uni()` 之前、`.npmrc` hoist、TS/`vue-tsc` 升级、8084 + `/dev-api` 代理、H5 hash 路由）、I5 门禁（`type-check` / `lint` / `build:h5` + CI + AGENTS 红线 6/10/15/16/17）
  - 骨架页 6 个：登录（图形验证码 + 加密）/ 首页（真实调 A1 院区）/ 我的（角色切换 + 退出）/ 预约与消息占位 / 分诊签到占位
  - 验收：`pnpm install --frozen-lockfile`、`type-check`、`lint`、`build:h5` **四条全绿**；`build:mp-weixin` 通过；`dev:h5` 起在 8084，`/dev-api` 代理取回 3 个院区；以 app clientid + 前端同算法加密报文直打 `/auth/login` 返回「验证码已失效」→ 证明放行与解密链路通
  - 配套（backend 仓）：`script/sql/appt_e5_client_access.sql` 把 `sys_client.app.access_path` 放行 `/appt/**,/auth/**,/system/**,/resource/**`（该值写进 token，改后必须重新登录）
  - 踩坑：pnpm 12 默认忽略依赖构建脚本（需 `pnpm-workspace.yaml` 的 `allowBuilds`）；`@/types/api` 写成 `.d.ts` 会被 vite 判为「模块不存在」；`pages.json` 一度漏 add（已补 `fix(e5)` 提交）
- **页面开发不属 E 系列**：患者端主链路见 **S10**、辅助页与分诊台见 **S11**（§3）

> **小程序可用性（2026-10-21 核实）**：该小程序已存在、类目已选，但**未备案、未认证、基本信息未填** —— 开发者工具调试 / 真机预览 / 体验版可用，**不可提交审核发布**（医疗类目需执业许可证，且本仓为虚构演示数据）。
> **为什么页面不进 E 系列**：E 系列的定义是「工程基线、横切、不属于 S 系列」；页面属于功能交付，且 §2 总表本就有「前端归属」列，故归 S10/S11。

---

## 8. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-10-18 | 建档：切片总览 + 验收清单 + 第 9 章挂钩 + 待决项 + 工程待办 |
| v0.2 | 2026-10-18 | 待决项 1/2/3 闭环：定时任务定 **snail-job 2.0.2**；`appt_fee_standard` 补 `status`；契约 §4.6 补就诊人停用过滤；待决项 4 记入「seed 先不生成」 |
| v0.1.1 | 2026-10-18 | PRD §13.3 切片表删除、改为指向本文件（排期单一权威）；待决项 1 更正事实：框架自带 snail-job 2.0.2，`ry_job.sql` 即其 `sj_*` 建表脚本 |
| v0.2.1 | 2026-10-18 | P1 修复（生成实体类前置）：契约 §7.5 停诊 `scope_type` 对齐 `SCHEDULE`/`STAFF_DATE`/`CAMPUS_DATE`（D-S1-5 落地补全，PRD §6.10 同步）；PRD §6.4 补挂号费矩阵规则；技术方案 §1.2 `suspend_record` 归属 triage；database-design §5 补 I6 映射；backend AGENTS §6 补三条生成器坑位；`appt_schema.sql` title 注释补 `ASSOC_CHIEF_NURSE`（DDL + 库同步 ALTER） |
| v0.2.2 | 2026-10-18 | P2 清理 12 条：契约 §9.1 `TAKEN→AVAILABLE` 补 F2 触发源、§2.7 补 `scope_type` 请求线值、§8.5 F8–F22 编号分配（F16 渠道配置 / F22 对账结果锁定，F15/F21/F23–F24 预留）；PRD §1.4 补两行范围外、§13.2 医保措辞、§4.2-5 与 §10.2 菜单「号源查看与删除」、§11 补 seed 三条硬约束、§14.3 标题改「待验证项与已知边界」；database-design §2 补 6 组次要枚举、§3 补行数量级口径、§4 补 payment_callback 索引登记、§7 标题改「已回写」；技术方案 §6.2 加索引权威指针；ROADMAP §4 §9.7 横切补 S2/S7 |
| v0.2.3 | 2026-10-19 | 实体生成前置（P2 收尾）：契约 §1.3/§2.4 金额线值由 JSON number 修订为 **JSON 字符串**——生成器实测确认框架全局将 `BigDecimal` 序列化为字符串（`JacksonConfig`，防 JS 精度丢失），原「number」表述与框架行为冲突；`fee_standard.fee` / `slot.fee` / `registration.fee` / `payment.amount` / `refund.amount` 五个字段响应即为字符串，前端按字符串处理 |
| v0.2.4 | 2026-10-19 | S1 实体生成落地：20 表生成器配置与菜单父节点 SQL（backend `d6e1bd6`）；包结构定**方案 A**——生成器产物落平坦包 `org.dromara.appt.{domain,domain.bo,domain.vo,mapper,service,service.impl,controller}`（与框架 demo 同形态；Mapper 扫描 `org.dromara.**.mapper` 兼容子包但重新生成会覆盖落盘），九包划分享写业务代码（技术方案 §1.2 / AGENTS §2 / §6 同步修订）；appt pom 补 `ruoyi-common-excel` + `ruoyi-common-translation`（生成代码默认带导出能力，此前 Maven 构建 224 错，IDEA 内可编译是增量跳过假象） |
| v0.2.5 | 2026-10-19 | B2–B5 改造（生成器产物按契约收口）：① 路径 `/appt/admin/{entity}`（契约 §8.1，20 controller + 20 api.ts + export 下载路径）；② 只读表端点剔除——10 表删 add/edit/remove（Controller/Service 接口/ServiceImpl 三处同步）、slot 保留 remove（契约 §8.4 F7）、staffFavorite 无契约端点整套删；③ Vue 死代码清理（空对话框/写按钮/操作列/选择列/死函数，slot 保留删除链路）；④ VO 金额 `string`（契约 §2.4）而 Form/Query 输入侧保持 `number`——`GenTableColumn.getTsInputType` + `types.ts.ftl` 根因修复（存量 20 types.ts 同步修，vue-tsc 61→0）；⑤ 菜单清理 `appt_s2_menu_cleanup.sql`（删 38 行，C 20→19、F 120→63，已核实无角色授权孤儿） |
| v0.2.6 | 2026-10-19 | 六实体维护页可用性修复（走查发现）：① 生成器默认「列名以 `type` 结尾 → select」，无字典时渲染「请选择字典生成」坏控件致页面无法提交（O5 覆写只覆盖 `*_status`，漏 `*_type`/`clinic_type`/`id_type`）——11 列改 `input`，固化 `appt_s2_gen_column_fix.sql`（同步/重新导入后需重跑），存量 7 页 16 处 el-select→el-input；② el-switch 初值 `undefined` 致必填校验失败——8 个 CRUD 页 `initFormData.status` 默认 `false`（= DB `'0'` 正常）；③ backend AGENTS §6 记第五坑位 |
| v0.2.7 | 2026-10-19 | Excel 导出空列修复：生成器原逻辑「注释含全角（ → 注释内嵌字典」，本库散文体注释（如「主键（雪花）」）被误判，17 个 VO / 54 字段套上 `ExcelDictConvert` + 假 `readConverterExp`，导出时查不到映射输出空；`vo.java.ftl` 移除该分支只认 `dict_type`，存量 19 个 VO 还原为普通 `@ExcelProperty`（编译双绿）。另确认：时段模板 `start_time/end_time` 为 `LocalTime`，须填 `HH:mm`（非缺陷）；科室 `parent_id` 下拉选择属后续手写任务 |
| v0.2.8 | 2026-10-19 | S1 收尾（AGENTS §6 第二条/第三条落地）：① 删除前引用校验——campus（医务人员/排班/号源/挂号）、clinicType（按 code：医务人员/时段模板/收费标准/排班）、department（医务人员/排班/号源/挂号 + 下级科室自引用）、medicalStaff（排班/号源/挂号/收藏/时段模板）；slot_template、fee_standard 无被引用表；`appt_staff_favorite` 恢复实体+Vo+Mapper 仅作校验用（不恢复端点）；② 唯一键「撞停用行重新启用」+ 同键冲突预检（clinicType / slotTemplate / feeStandard），`DuplicateKeyException` 全局友好化（1062 由 500 改为 400）；③ `uk_patient_id_hash` 待 `IdNoEncryptor`（S6）；④ 日期/时刻文本框格式提示（生成器模板 + 存量 4 页）；S1 清单 4/6 项打勾 |
| v0.2.9 | 2026-10-19 | 雪花 id 引用修复（走查发现）：手输 19 位 id 在浏览器被压成 `Number.MAX_SAFE_INTEGER`（9007199254740991），引用校验因此查不到匹配、删除产生孤儿。① 前端：医务人员（院区/科室）、时段模板（医务人员）改 `el-select`，value 直接用接口返回的字符串 id，types 输入侧放宽为 `string \| number`；② 后端：医务人员与时段模板的 `validEntityBeforeSave` 增加引用存在性校验（须存在且状态正常）；③ 清理孤儿医务人员 1 条；④ AGENTS §6 记第七坑（引用字段禁用文本输入雪花 id） |
| v0.3.0 | 2026-10-19 | S1 基础数据 seed（`appt_s1_seed.sql`）：3 门诊类型 / 3 院区 / 40 科室（三级树 10+20+10，parent 正确挂树）/ 60 医务人员（3 院区轮转、30 叶子科室轮转、5 职称轮转、每 10 人 1 护士）/ 15 收费标准（5 职称 × 3 门诊类型，内嵌 PRD §6.4 的 22/15/6/7 四个已定价位）/ 80 时段模板（NIGHT 门诊走 18:00-21:00）；固定 id 段先删后插可重跑；数据自检：引用完整性 4 项全 0、层级 10/20/10；待决项 4 更新为「基础数据已做、业务数据 seed 归 S7」 |
| v0.3.1 | 2026-10-19 | UI 体验轮（S1 维护页可用性收口）：① `src/views/appt/options.ts` 统一线值选项（取自 DDL 注释）+ `labelOf/statusText`；`useApptOptions` 统一加载院区/科室/医务人员选项；② 20 页筛选区去噪与枚举下拉、关联联动、时间日期控件、科室父级树选择（顶级节点 0）；③ 列表列名 UI 化、枚举中文映射、状态 `el-tag`；④ 菜单 `order_num` 由全 1 重排 1..n（`appt_s2_menu_order.sql`）；⑤ `timePoint` 列表显示 `HH:mm`（契约 §2.4）。未做：导出枚举翻译（TRUE/FALSE 与线值）、引用下拉过滤停用项 |
| v0.3.2 | 2026-10-19 | 导出翻译：20 个 VO / 47 个枚举字段加 `@ExcelDictFormat(readConverterExp=...)`（Boolean 走 `false=`/`true=`；未命中返回空、null 返回空），表头同步 UI 化；反射探针调用框架 `convertByExp` 验证 26 例通过（`MOCK=Mock` 预期非中文）；未引入 sys_dict。副作用：枚举副本三处（database-design §2 权威 / options.ts / VO 注解），改枚举需三处同步（AGENTS §9 已记） |
| v0.3.3 | 2026-10-19 | 导出 `LocalTime` 修复：fesod 2.0.2 仅内置 `LocalDate`/`LocalDateTime` 转换器，`time` 列（LocalTime）导出抛 `Can not find 'Converter' support class LocalTime`（时段模板实测，伴 POI `Stream closed` 噪音）；新增 `org.dromara.appt.excel.LocalTimeConvert`（导出 `HH:mm:ss`，导入兼容 `HH:mm[:ss]`），`slotTemplate.startTime/endTime` 挂载；AGENTS §6 记第八坑（新表 time 列必须挂转换器）；验证：真实写 xlsx 的 5 个 VO 探针全 PASS |
| v0.3.4 | 2026-10-19 | 下拉收尾：① `useApptOptions` 统一过滤停用项（停用数据不可被新引用），staff/slotTemplate 改用 composable；② 科室父级树保留停用节点但 `disabled`（子节点不断链）；③ 黑名单表单账号/就诊人改下拉（`listUser` / `listPatient`），types 放宽 `string \| number`，校验文案去开发用语 |
| v0.3.5 | 2026-10-19 | 通知场景线值：7 个事件线值（`BOOK_SUCCESS` 挂号成功 / `PAY_SUCCESS` 支付成功 / `PAY_TIMEOUT` 支付超时关单 / `CANCEL_SUCCESS` 退号成功 / `SUSPEND_CANCEL` 停诊取消 / `NOSHOW_RECORD` 爽约记录 / `BLACKLIST_HIT` 黑名单生效）——按事件命名而非状态，避免与 `registration.status` / `payment.status` 同名不同义；三处同步（database-design §2 权威 / `options.ts` / `ApptNoticeVo` 注解），notice 页筛选与列表恢复中文；导出探针 7/7 命中 |
| v0.3.6 | 2026-10-19 | 图片上传接入：OSS 配置入库 `sys_oss_config`（`minio` / `status='Y'` / `access_policy=2` 公有只读 / bucket `appt` / prefix `appt/`），复用项目一 MinIO；`medical_staff.avatar`、`campus.cover_url` 改 `imageUpload` 控件（表单 `image-upload`、列表 `image-preview`），gen 配置两列同步（`appt_s2_oss_config.sql` 尾部固化的 UPDATE 防回退）；字段仍存 URL 字符串，契约 §2.6 语义不变 |
| v0.3.7 | 2026-10-19 | 就诊人证件号加密器：`IdNoEncryptor`（HMAC-SHA256 摘要 / 可选 AES / 演示期明文）落地 D-S1-3 与 M11；Service 层新增必填校验 + 摘要计算 + `uk_patient_id_hash` 撞停用行重新启用；因 VO 不返回证件号（红线 15），约定「编辑留空 = 不修改」；就诊人页账号字段改用户下拉；摘要与 Python 独立实现交叉验证一致 |
| v0.3.8 | 2026-10-19 | 枚举三处副本对账：新增审计脚本 `backend/script/enum_sync_audit.py`（31 组常量 / 47 个注解字段 / 文档语料含 §2、契约 §2.7、技术方案 §3.6）。首跑修 8 处：`PAY_CHANNEL` 补 `alipay`、`CHECK_TYPE` 与 §3.6 对齐（**R6/R7 此前中文名错位**：余量偏差→停诊漏处理、缓存无源→余量缓存漂移）、新增 `SIGN_FLAG/REG_ACTIVE_FLAG/IS_DEFAULT` 常量与三页列表映射、清理 `staffFavoriteVo` 假注解；AGENTS 把脚本纳入枚举改动验证门槛 |
| v0.4.0 | 2026-10-20 | **S2 文档**：S2 清单与切片表标完成、停诊登记改判 S6b、§3.9 放号窗口 ✅；契约 §8.2 补多模板仲裁（优先 `staff.clinic_type`，否则 id 最小）、生成不受窗口限制、批号形制、`skippedCount/arbitratedCount`、preview 全字段；技术方案 §1.4 补 `booking.release.compensate-after-time` |
| v0.4.1 | 2026-10-20 | **S3 文档**：契约 §2.1 增「业务码在 `data.bizCode`」、§4.1 补实现口径（幂等回放 `duplicate=true`、限购判定顺序、账号行锁、占位 TTL、payment 只落单）；ROADMAP S3 勾选与 §3.9 六行；新增 `test-evidence.md`（S2 放号幂等 + S3 并发/降级对照） |
| v0.6.1 | 2026-10-24 | **母标定版与设计协作规则**：`DESIGN.md` 新增 §12「品牌与图标」（A3c 母标几何参数、responsive logo 三档、导出清单、禁止事项）与 §13「Stitch 使用边界」（定位 / 四类回调 / 四步流程 / 记录位置）；ROADMAP S12 标注母标已定 |
| v0.6.0 | 2026-10-24 | **进入交付阶段**：新增 S12（品牌与首屏）/ S12.5（全站视觉统一）/ S13（门面与物料）/ S14（一键演示）/ S15（医院感细节）/ S16（线上部署，阻塞于服务器）六个切片，含范围、验收标准与依赖顺序；明确"不做"清单（微服务 / K8s / 真实支付 / 多租户 / i18n / 暗色）；`docs/README.md` 仓库状态与启动说明同步 |
| v0.5.18 | 2026-10-24 | **收尾偏差**：分诊 `SignListVo`/`SignResultVo` 补 `@JsonFormat(HH:mm)`（全仓 timePoint 统一，`signTime` 保持完整时间戳）；compose 的 mysql/minio 标注未启用并说明启用前置；契约 §2.4 补注记；前端注释同步 |
| v0.5.17 | 2026-10-23 | **体检轮**：`s3` 复跑 `PASS=11`（限购合并后断言数 14→11，脚本头部与章节号修正）；`s8` 修限购兼容与清理策略后复跑 `PASS=29 FAIL=0 SKIP=0`；`s9` 复跑 `PASS=23 FAIL=0`；`test-evidence` §11.3 记录 s8 的三处修法 |
| v0.5.16 | 2026-10-23 | **回滚 `jsencrypt` 动态 import**：mp-weixin 把 `import()` 编成 `require().then()` → 登录报 `"/common/vendor.js" is not a function`；回到静态 import 并在 `encrypt.ts` 注释禁止该写法。`request.ts` 的「空 body 带状态码」保留；`test-evidence.md` §15.6 修正 |
| v0.5.15 | 2026-10-23 | **遗留清零**：`jsencrypt` 按需加载（H5 独立 chunk、小程序不进启动链路，三种导出形态兜底）；`request.ts` 空 body 带 HTTP 状态码 + toast；`test-evidence.md` §15.6 记录处理与验证 |
| v0.5.14 | 2026-10-23 | **小程序真机扫码验收通过**：微信 8.0.66 / 基础库 3.17.5 端到端跑通「详情二维码 → 扫一扫 → E1 → SIGNED」；S11 分诊台三项全部可用；`test-evidence.md` §15.5 记录验收步骤与二次扫的 `SIGN_WINDOW_CLOSED` |
| v0.5.13 | 2026-10-23 | **小程序真机联调收口**：Windows 8082 被 `QQ.exe` 占用 → portproxy 静默失败、接口返回空 body 404；改用 18082 转发并同步 `dev:mp-wsl` 默认 baseApi；README/test-evidence 补判定口诀（`netsh show` 复核、后端日志无请求即未到达） |
| v0.5.12 | 2026-10-23 | **小程序真机可运行**：修 `crypto.ts` 顶层 `TextEncoder`（小程序无此全局对象，导致所有页面模块求值失败白屏）；补 `mp-weixin.setting` 的 `enhance/es6/postcss`；`dev:mp-wsl` 默认 baseApi 改局域网地址；README 补「小程序端真机调试」与 WSL2 portproxy 说明；`test-evidence.md` §15 |
| v0.5.11 | 2026-10-23 | **s6b 脚本覆盖三种停诊范围**：补 `STAFF_DATE` / `CAMPUS_DATE` 用例（含「换医生同日必须新批号」与「处理按 staff 展开不误伤」两条缺陷回归），`PASS=42 FAIL=0 SKIP=0`；`script/test/README.md` 与 `test-evidence.md` §14.5.2 同步 |
| v0.5.10 | 2026-10-23 | **分诊底栏减项**：`TriageTabbar` 去掉「加号」（E4 未实现，避免演示点到「暂未开放」），底栏 4 项 → 3 项；ROADMAP S11「未做」与 test-evidence 同步 |
| v0.5.9 | 2026-10-23 | **停诊两处后端缺陷修复**：`SuspendReportService` 幂等键纳入 `staffId`（修「不同医生同日误判同范围」）；`SuspendHandleService` 从记录回填 `staffId`（修「处理空转、号源与预约未变」）；`app` 停诊页换对象清结果卡 + 结果卡增「停诊对象」；`test-evidence.md` §14.5 补缺陷与验收步骤 |
| v0.5.8 | 2026-10-23 | **S11.1 停诊上报页**：`app` 新增 `pages/triage/suspend.vue`（范围三选一 + 级联 + E5 提交 + 批号结果卡）、`api/appt/triage.ts` 补 `reportSuspend`、`TriageTabbar` 停诊项接线；ROADMAP S11 勾选补该项（分诊台 3/4 可用）；`test-evidence.md` §14.5 补三种范围与幂等实测；**零后端改动** |
| v0.5.7 | 2026-10-23 | **S11 患者端辅助页 + 分诊台落地**：`app` 新增 5 屏（9.10 预约详情·就诊码 / 我的就诊人 / 我的医生 / 消息+详情 / 分诊签到·当日列表）+ `useUnreadBadge` + 3 个 API 文件，`DESIGN.md` 补 §8.1 语气规则、§8.2 文案表重写、§8.3 固定文案、§9.10 回调 Stitch 4 处；`backend` 限购改为「同一就诊人同一天 1 单」（`LIMIT_PATIENT_DAY`，三条旧码 `@Deprecated`）、站内信时间/午别格式化（`ApptDisplayUtils`）；契约 §2.2/§4.1 与 PRD §6.5 同步；`s3_b1_concurrency.sh` 限购断言改写；ROADMAP S11 全项勾选 + 实测；`test-evidence.md` §14 |
| v0.5.6 | 2026-10-22 | **S10 患者端主链路落地**：`app` 新增 9 屏页面 + 基座（store/composable/utils/6 组件/全局 token），`DESIGN.md` 六处规范修订；`backend` 补 A6 `periods[].scheduleId`（A7 唯一入参来源）与 B4 取消端点（契约早有定义、实现缺入口），患者端 B1/B2/B3 `timePoint` 补 `@JsonFormat` 对齐契约 §2.4；契约 §3.5/§3.6/§4.4/§2.4 字段级回填；ROADMAP S10 全项勾选 + 实测；`test-evidence.md` §13 |
| v0.5.5 | 2026-10-22 | **移动端设计规范落地（E5 配套）**：`app/DESIGN.md`（约 450 行）——15 个色板 token（含用途与禁止用途）、挂号 8 状态色映射（唯一出处）、字号/间距/圆角/阴影阶梯、12 类组件规格（只用实测存在的 Wot UI 2.x 组件）、S10 十屏 blueprint（含契约字段出处与四态）+ 11 段可直接粘贴的 Stitch prompt、业务码→中文唯一映射、10 条禁止项；`app/README.md` 与 `AGENTS.md` 加指向。**Stitch 实测反馈**：9.1 首页出图确认主色与 token 生效，但它自行加入距离/专病门诊/「今日有号」等契约外字段与装饰圆点/波纹 → 已并入 §10 禁止项第 2 条 |
| v0.5.4 | 2026-10-22 | **S9 就诊人管理落地**：契约 §2.2 +2 码、§4.6/§4.7 字段级、§4.8 转正、§10 去占位；PRD §4.2-6 实现进度；ROADMAP S9 全项勾选与实测；`PiiUtils` 抽公共脱敏（口径收紧为「<12 全遮」）；复核生成器侧 `status` 语义（结论：写法正确，坑位已入 AGENTS） |
| v0.5.3 | 2026-10-22 | **E5 建仓（移动端骨架）**：新建 `qd-appt-app`（uni-app+vite-ts+Wot UI 2.x），落地 I1–I5 与 6 个骨架页，四条 DoD 全绿；backend 补 `appt_e5_client_access.sql`（app 客户端 access_path 放行，注明需重新登录）；ROADMAP §7 E5 勾选并记录实测版本 |
| v0.5.2 | 2026-10-21 | **新增文档一致性门禁**：`docs/script/doc_audit.py`（过期表述 / §2 与 §3 状态传播 / test-evidence 章节编号 / 契约 P1 清单 / 复用字典审计）+ docs CI；AGENTS §5 改写为 Definition of Done（状态传播表 + 「未来时须带归属」+ §8 为历史快照）；顺带修正 S1「三条约束」父项、S2 停诊登记、S3 患者端页面三处遗留项的归属标注 |
| v0.5.1 | 2026-10-21 | **排片：新增 S9 / E5 收窄 / 新增 S10·S11**：S9 = 就诊人管理 B6–B10（E5 前最后一个后端硬前置，B1 挂号依赖 `patientId`）；E5 收窄为「建仓 + 脚手架」（E 系列只管工程基线），页面拆为 **S10 患者端主链路**、**S11 辅助页 + 分诊台**；记录小程序现状（未备案/未认证 → 仅开发与体验版可用） |
| v0.5.0 | 2026-10-21 | **S8 实现与文档（患者辅助组）**：新增 `account/FavoriteService`+`PatientFavoriteController`（D1–D3）、`notice/PatientNoticeService`+`PatientNoticeController`（D4–D6）、`SignService.listByDate`+`TriageSignController`（E3）；`NoticeSender` 补 `BOOK_SUCCESS`/`PAY_SUCCESS`/`PAY_TIMEOUT` 三处调用；契约 §6 升级字段级、§7.3 补字段与数据范围、§11 #7 标注现状；PRD §6.12 改为 7 类全齐；ROADMAP 新增 S8 段与 §2 状态；test-evidence §11；`appt_s7_business_seed.sql` 把种子单与就诊人隔离到虚拟账号；新增 `s8_patient_aux.sh` | 
| v0.4.9 | 2026-10-21 | **工程基线收尾（E2/E3/E4）**：E4 销项（核查后两项早已完成）；E2 新增 `backend/deploy/{docker-compose.yml,init-db.sh,README.md}`（三件套 + 一键导 8 个 SQL，端口避让，SnailJob 明确为外部依赖）；E3 新增 backend/admin 两条 GitHub Actions 工作流与首个单测 `SuspendScopeParserTest`；`docs/README.md` 启动段补「一键（推荐）」并保留手工兜底 |
| v0.4.8 | 2026-10-21 | **S7 实现与文档**：契约 §8.5 F3/F4 落响应结构、F22 补按 `batch_no` 过滤；PRD §9.6 补修复边界与结果字段、§10.2 补看板口径；技术方案 §3.5 验证数据换为「脚本入口 + 待实测」；ROADMAP S7 勾选与状态、§5 开发轮、§7 E2 注明 README 已交付；`docs/README.md` 增三步启动与演示入口；test-evidence 增 §10；**验收实测回填**：`s7_reconcile.sh` `PASS=22 FAIL=0`（1774ms / 发现 14 修复 12 告警 2）、看板与 SQL 一致、seed 规模 500/9000/2000；`script/test/README.md` 增 s7 段落（含「R6 是排班级 / 造数必须跨排班 / 跑完 reseed」） |
| v0.4.7 | 2026-10-21 | **S6b 实现与文档**：契约 §7.5 改「一条登记承载区间（`endDate` + `scope_value` 编码）」并补 E5 响应字段、§8.3 补实现口径（批号锁 / `PENDING→HANDLED` / `TAKEN→SUSPENDED` 余量 0 / WAIT_PAY 关单 / 已签到跳过 / 通知聚合）；PRD §6.10 补区间承载与「已签到跳过」计数；database-design §3.2 补 `scope_value` 编码说明（不改表）；ROADMAP S6b 勾选 + §2 状态 + §3.9 停诊行修订 + §5 进度；新增 `appt_s6b_seed.sql`（`appt:suspend:handle`）与 `s6b_suspend_blacklist.sh`；**验收实测**：脚本 `PASS=25 FAIL=0`，页面「停诊登记 → 处理」与挂号单/退款单/站内信/排班四处一致，黑名单页自动行与 `BLACKLIST_HIT` 通知正确（`test-evidence.md` §9） |
| v0.4.6 | 2026-10-20 | **S6a 实现与文档**：退号/签到/爽约/置完成四条状态边落 `RegistrationStateService`（全部显式 `update_time`）、`SlotStateService.expire`（余量 −1，与 `releaseToPool` 分离）、`RefundService` 拆 `createForPayment`/`dispatch` 并新增 `createPaidRefund`（PAID 入口）、`NoticeSender`、B2/B3 我的预约、后台手动退号 F10、任务手动重跑端点；契约 §4.5 补实现口径、§8.5 落 F10 与任务重跑；ROADMAP S6a 全项勾选 + §2 状态 + §3.9 两行 + §5 进度；新增 `appt_s6a_seed.sql` 与 `s6a_state_machine.sh` |
| v0.4.5 | 2026-10-20 | **S6 口径决策（D-S6-1）**：① 停诊被动退号**不计入**黑名单；② 黑名单保留「退号 + 爽约」双计数（计入 `CANCELED_ACTIVE` + `NOSHOW`，不计 `CANCELED_PASSIVE` + `CLOSED`；按 `user_id`、`update_time` 近 180 天），理由见 PRD §6.9；③ 明确「23:00 后不可退号」是**不允许退**而非不计（该路径不存在，只落爽约）；④ 后台手动退号不受 23:00 限制但记 `CANCELED_ACTIVE` 且计入，避免绕过；⑤ ROADMAP S6a/S6b 补顺序说明（先 a 后 b）、`update_time` 显式写入坑位、`RemainService` 两处新接入点与 S6b `AVAILABLE→SUSPENDED −1`；⑥ 契约 §4.4 补「CLOSED 不计入」、§4.5 补截止语义与计数口径 |
| v0.4.4 | 2026-10-20 | **S5 实现与文档 + 验收实测**：`/appt/public` 落地 A1–A7（匿名）、余量一次聚合（`GROUP BY schedule_id, period`）+ `appt:remain:{scheduleId}:{period}` 缓存（MGET 批量读 / SETNX 回填 600s / afterCommit + Lua EXISTS 守卫 / 双模式开关）、D1 窗口过滤；技术方案 §3.2 验证数据回填（SQL 3/2/3.2 条、`redis` p95 9.3ms 命中率 100%、`db` p95 10.6ms、一致性差值 0）与默认值裁决；`test-evidence.md` 增 §7（含 S3/S4 回归、手工验收、参数 400 语义、占位键释放修复）；`script/test/README.md` 增两脚本前置与留档口径；admin 排班页余量列 |
| v0.4.2 | 2026-10-20 | **S4 文档 + 文档对账**：契约 §5.1 补待签串/ack 结构/入账前置、§5.5 订正 `refund_no` 前缀为 F 与退款回调复用 `appt_payment_callback` 的字段映射；ROADMAP S4 完成与 ①②③④ 通过标记；技术方案 §1.4 补 `payment.refund.auto-enabled`/`max-retry`/`retry-backoff-seconds` 并去除重复行、§3.1/§3.3/§3.4/§3.5 验证数据回填；database-design §3.5 补退款回调复用说明；backend AGENTS §6 补三条坑位（JDT 与 javac 对非法字符差异 / MP 批量插入不参与外层事务 / `@Async` 默认无界执行器） |
| v0.3.9 | 2026-10-19 | 图片字段 ossId 翻译：`image-upload` 回填 ossId（非 URL），VO 增 `avatarUrl` / `coverImageUrl` 并用 `@Translation(OSS_ID_TO_URL)` 翻译；列表 `xxxUrl || xxx` 兜底旧 URL 数据；导出不含图片列；AGENTS 前后端同步纠正"字段存 URL"的错误表述 |
| v0.4.0 | 2026-10-19 | S2 前置收尾：`ApptSlotServiceImpl` 删除前校验有效挂号（`active_flag=1`），`ApptSlotTemplateServiceImpl` 删除前按 `(staff_id, period, clinic_type)` 校验是否已生成排班；ROADMAP S1 标记完成、`uk_patient_id_hash` 状态更正（随 `IdNoEncryptor` 已实现） |
| v0.4.1 | 2026-10-19 | S1 数据完整性补强（S2 前置）：① 模板时间/步长校验（`end > start`、`step > 0` 且 `≤ 时长`，防生成死循环）；② `clinic_type` 引用存在性（staff / fee_standard / slot_template 三处）；③ 科室 `parent_id` 防自指/防成环 + `level` 由父级推导；④ 门诊类型 `code` 被引用禁改；⑤ 存量自查：模板/科室 0 异常，清理 1 条测试医务人员 |
| v0.4.2 | 2026-10-19 | ROADMAP 结构调整：① §2 增「涉及仓库」列、S1 置「已完成」、患者端标注延后（2026-10-19 拍板「先后端/后台，后患者端」）；② S6 拆 S6a/S6b，S2 停诊改为「登记」语义；③ 集成测试补 ④（S2 幂等）/⑤（S5 缓存一致）/⑥（S6a 漏判 0）；④ 新增 §3.9「核心亮点 ↔ 切片 ↔ 验收证据」13 条矩阵；⑤ §7 工程基线改为 E1–E5 编号 |
| v0.4.3 | 2026-10-19 | 会话上下文机制（§0–§8：最小输入/闸门/开场卡+阅读回执/基线自查/最小必读集/收尾/5 条判定/环境事实）；补 `slot_template.clinic_type` 与 `medical_staff.clinic_type` 一致性校验（存量 0 条不一致）；新增 `BookingProperties`（3 个 S2 开关） |
| v0.6.1 | 2026-10-24 | S12 品牌与首屏：品牌资产脚本化（`gen-brand-assets.mjs` + `brand:gen` + `@resvg/resvg-js`）、母标三点负形修正、患者端 tabBar 与分诊底栏图标化、Wot 主色阶覆盖、后台品牌位与运营看板首页、DESIGN §12 尺寸映射与 §9.11「我的」、患者端三屏抛光 |
| v0.6.2 | 2026-10-24 | S12.5 全站视觉统一：后台主色/语义色/圆角/表格密度收口、`ApptStatusTag` 状态标签组件、登录页两栏改版、404 与网络异常兜底页、`admin/AGENTS.md` §13 后台视觉基线、DESIGN §9.12–§9.14 |
| v0.6.3 | 2026-10-24 | S13 门面与物料：第 5 仓 showcase（README / 10 张脚本截图 / 14 秒 GIF / Playwright 基建）、DEMO 五分钟剧本、ADR 六篇、后台残留清理与浅色侧栏、SpringDoc 四分组与截图 profile、菜单与演示账号昵称去上游化 |
| v0.7.0 | 2026-10-25 | S14 一键演示：`showcase/demo.sh`（八步 + 失败修复提示 + down/reset/logs）、demo compose（include 依赖、独立容器名与数据卷、SnailJob 服务）、`init-db.sh --full`（补框架表 / SnailJob 表 / 菜单树 / 收尾脚本、覆盖 OSS 地址）、后端 `application-docker.yml` 与多阶段 Dockerfile、admin/H5 nginx 运行时反代镜像、四枚镜像的 `image*.yml`、四份 `.env.example`；`docker run` 独立启动、真实验证码登录与 SnailJob 控制台实测通过 |
| v0.7.1 | 2026-10-26 | S15 医院感细节：新增 `StepGuide` / `AppFooter` / `EmergencyTip` 三个展示组件与 `utils/campusProfile.ts`、`REG_STEPS` + `regStepProgress`；新增就诊指南 / 须知与规则 / 院区详情三页（`pages.json` 24 页、三页进匿名白名单）；首页加院区信息次入口与静态流程条，详情页加三态流程条，我的加就诊指南入口并统一页脚；DESIGN 补 §8.3 固定文案与 §9.15–§9.17 blueprint。**不改后端接口与表结构** |
| v0.7.3 | 2026-10-26 | S15 验收收口：修复预约详情「就诊医生」把职称线值（`PHYSICIAN`）直接显示的问题（改走 `titleLabel()`）；确认「已完成仍显示就诊码」属契约 §4.3 与 `DESIGN §9.10` 口径、不是缺陷；登记 **S15.2**（我的预约缺 `SIGNED` 入口，含两个候选方案与验收样本） |
| v0.7.4 | 2026-10-26 | S15.3 登记（未开始）：终态 `NOSHOW` / `COMPLETED` 不迁号源，导致对账 R1 每天报几百条幽灵占号（本轮 505 = 299 + 206）；修法与回归范围写进 §3 S15.3。README 仓库状态同步为「S15.2 / S15.3 与 S16 待做」 |
| v0.7.5 | 2026-10-26 | S15.2 已签到入口：「已预约」tab 内加子筛选「已预约 / 已签到」（`subState` 按 tab 记忆 + `queryStatus` 三分支），`SIGNED` 行改「查看就诊码」、空态改专用文案；`DESIGN §9.9` 补两级结构并订正「状态 → 动作」段（原文与实现不符）。零后端改动 |
| v0.7.6 | 2026-10-26 | S15.3 终态号源释放：新增 `SlotStateService.expireTaken()`（`TAKEN → EXPIRED`，余量 0，写 `EXPIRE` 台账），`markNoShow` / `markCompleted` 同事务调用；两个任务查询补 `slot_id`。实测对账 R1 从 505 条降到 **0 行**，台账时间从「对账时刻」回到「状态流转时刻」；§21.5 的问题观察同步标注为已修 |
| v0.7.2 | 2026-10-26 | S15.1 SnailJob 任务补种：`appt_s14_snailjob_seed.sql` 补齐 `apptNoShowJob` / `apptCompleteJob` / `apptReconcileJob`（2 → 5 条），`next_trigger_at` 按任务分策略（爽约取下个 5 分钟整点，其余延次日）；S14 边界那处欠账同步改写；dev 库同步插入 3 行；数据侧把 299 条过期 `BOOKED` 转 `NOSHOW`、5255 条号源转 `EXPIRED`，admin 名下 6 条测试单改归属虚拟账号避免违约触线 |
| v0.7.7 | 2026-10-29 | **部署方案 + wsl 公网联调**：新增 `deployment-cicd-plan.md`（**方案文档，只写「怎么做」，进度以本文件为准**；sd-blog 降为附录 C，本轮不并行）；本机实测打通 `wsl` 目标——DNSHE 免费域名 `qdappt.us.ci` 接入 Cloudflare（NS 纯化为两台 CF）、Named Tunnel 以 systemd 常驻、`admin`/`demo` 两域名分别指向容器 18083/18084、HTTPS + 验证码 + RSA/AES 登录、下单→Mock 支付→站内信；SSE 通道可用但连接约 55 s 被中间层回收（服务端心跳 60 s），**先记录不修**。**未勾 S16 任何 checkbox、未推镜像、未改任何代码**；S16 是否拆 S16.1/S16.2 待拍板 | 仅 docs 仓 |
| v0.7.8 | 2026-10-29 | **S16 拆分拍板**：按"是否需要服务器"拆为 **S16.1**（compose 去 `build:` / 统一部署入口 `deploy.sh` / 镜像首推 GHCR / wsl 发布链 / 备份与日志轮转——本机即可验收）与 **S16.2**（服务器 + 域名 + HTTPS + 反代 + 小程序合法域名 + 可选监控——阻塞于服务器）。§2 增两行、§3 拆两节并按归属重排原 5 条 checkbox（演示数据重置入口归 S16.2 并标注属应用功能）、§5/§8 同步、README 与 `test-evidence` §24 口径对齐；**两片均保持「未开始」，不预勾任何项** | 仅 docs 仓 |
| v0.7.9 | 2026-10-30 | **S16.1 完成**：showcase 编排拆五件套（`compose.yml` / `compose.deps.yml` / `compose.wsl.yml` / `compose.cloud.yml` / `compose.build.yml`，删除跨仓 include 的旧文件）、`demo.sh` 改多 `-f`（行为不回退）、新增 `deploy.sh`（up/adopt/down/rollback/backup/restore/status + `.state` digest + 数据目录守卫）、新增 `release.yml`（dispatch 唯一入口，preflight 与部署均走自托管 runner）；backend `init-db.sh` 支持冒号分隔多编排。四枚镜像首推 GHCR `v0.1.0` 并冷拉验证；wsl 目标实跑发布 39s / 回滚 42s / 前滚 46s / 备份 1s / 恢复 62s，CI 发布 run #4 1m09s 全绿。**S16.2 仍未开始（等服务器）**。§3 六条 checkbox 全部勾选，实测数字见 `test-evidence.md` §25 | showcase + backend + docs |
| v0.7.10 | 2026-10-30 | **部署方案文档纠偏 + 重启自启复验**：`deployment-cicd-plan.md` 命令行统一为子命令式（旧式 `deploy.sh wsl --tag` / `--rollback` 照敲会打印「未知子命令」并退出 2，共修 10 处）、公网探活从 `curl -sI ... \| head -1` 改为 `--noproxy '*' -w '%{http_code}'`（走代理时 CONNECT 行会被误判为 200）、§7.6 第 4 条补「执行入口唯一」（`.state` / `backup` 随脚本位置分裂，两个入口各自记忆）、Q4 与 Phase 1–3 同步为已闭环（GHCR 已首推 `v0.1.0`）；`test-evidence.md` 增 §26 记录整机重启后自启实测（7 容器、5 探针全绿、数据目录 266M） | 仅 docs 仓 |
