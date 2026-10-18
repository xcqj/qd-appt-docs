# 号源 QueueDepth · 切片排期（ROADMAP）

> **本文档是「什么时候做、做到什么算完」的单一权威。**
> 「做什么 / 不做什么 / 为什么」在 `PRD.md` §13.1（MVP 范围）与 §13.2（后续迭代），此处不重复。
> 排期为参考节奏，**非硬性期限**（PRD §13.3）。字段级设计看 `database-design.md`，接口看 `api-contract.md`，红线看 `redlines.md`。

- 项目：号源 QueueDepth（代码缩写 `appt`），四仓：`qd-appt-{backend,admin,app,docs}`
- 建档：2026-10-18 ｜ 状态：v0.1

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

| 切片 | 内容 | 里程碑（验收口径） | 前端归属 | 集成测试 | 状态 |
|---|---|---|---|---|---|
| **S1** | 数据建模 + 建表 + 基础数据维护（院区 / 门诊类型 / 科室树 / 医务人员 / 收费标准 / 时段模板） | 后台可维护基础数据 | plus-ui：六实体维护页 | — | 进行中 |
| **S2** | 排班生成（`SlotTemplate` → 批量生成 `time_point`）+ 放号任务 | 能按时刻生成并开放号源 | plus-ui：排班生成页 | — | 未开始 |
| **S3** | 挂号链路 + 并发三道防线 + 限购与冲突校验 | 高并发争抢正确性达标 | uni-app：选院区→科室→医生→排班→时间点→确认 | ① | 未开始 |
| **S4** | **支付链路**：支付单 + 渠道抽象 + 模拟渠道 + 回调幂等 + 超时关单与回补 | 交易链路闭环 | uni-app：支付页 + 轮询 | ②③ | 未开始 |
| **S5** | 排班/医生查询接口 + 午别余量批量聚合 + 缓存 | 性能对比可演示 | 两端共用 | — | 未开始 |
| **S6** | 退号与退款、签到（分诊端扫码）、爽约扫描、停诊批量流转、黑名单 | 状态机闭环 | uni-app：分诊台模式 + 退号 | — | 未开始 |
| **S7** | 对账（号源 + 支付）+ 台账 + 看板 + 初始数据脚本 + README | **可交付**（= 本期结束） | plus-ui：看板与对账页 | — | 未开始 |

**集成测试**（定义见 PRD §12，此处绑定切片）：
- ① 50 并发争抢同一时间点，恰好 1 笔成功 —— S3
- ② 超时关单 → 号源回补 → 可被再次预约 —— S4
- ③ 支付回调重复 3 次仅入账 1 次 —— S4

**前端归属说明**：PRD §13.3 原注只写了「uni-app 患者端页面穿插于 S3~S6；分诊台模式在 S6」，**未写 plus-ui 后台页面的切片归属**。上表按里程碑反推补齐（见待决项 5）。

---

## 3. 逐切片验收清单

### S1 数据建模与基础数据（进行中）

- [x] `database-design.md` v0.1（20 表字段级设计 + 索引总表 + 不变量映射）
- [x] `appt_schema.sql` 20 表在 `appt` 库建成（2026-10-18，backend `0f0bfff`）
- [x] I1 兜底实测：同一 slot 有效单成功 / 终态单（`active_flag=NULL`）共存 / 第二笔有效单被 `uk_reg_slot_active` 以 1062 拒
- [x] 20 张表走 RuoYi 生成器，按 `backend/AGENTS.md` **§6** 坑位手工校正（§4 是领域红线，生成器坑位在 §6）——2026-10-19 六个坑位全部处理（append-only 删写端点 / 删除前引用校验 / 唯一键重新启用 / import 清单 / 输入侧类型 / 注释内嵌字典）
- [x] 后台六实体维护页可用（院区 / 门诊类型 / 科室树 / 医务人员 / 收费标准 / 时段模板）——2026-10-19 六页 CRUD + 导出走查通过
- [ ] **三条实现约束落地**（不设 `del_flag` 的还债，缺一即出 bug）：
  1. [x] 物理删除前做引用校验——被 `schedule` / `slot` / `registration` 引用的基础数据拒绝删除并提示先停用（2026-10-19：campus / clinicType / department / medicalStaff 已实现；slot_template、fee_standard 无被引用表）
  2. [ ] 前台下拉（院区 / 科室 / 医生 / 就诊人）一律带 `status='0'`；后台列表不过滤（否则无法恢复）——**依赖前台端点（E 系列），随 S2+ 端点落地**
  3. [x] 唯一键冲突走「命中停用行则重新启用」而非 insert（`uk_clinic_type_code` / `uk_template_staff_period_type` / `uk_fee_title_type` / `uk_patient_id_hash`）——前三者已实现；`uk_patient_id_hash` 待 `IdNoEncryptor`（S6）具备后再接（当前 patient 新增因 `id_no_hash` NOT NULL 尚不可用）
- [x] 初始数据脚本（S1 六表基础数据，2026-10-19 `appt_s1_seed.sql`：3 门诊类型 / 3 院区 / 40 科室三级树 / 60 医务人员 / 15 收费标准 / 80 时段模板；业务数据 seed 随各切片）

### S2 排班生成与放号

- [ ] 模板 → 批量生成 slot，`UNIQUE(schedule_id, time_point)` 防重，并发撞键重算重试
- [ ] 放号按 D1：可约 `[今日+1, 今日+7]`，每日 08:00 放第 7 天，策略可配
- [ ] 停诊前置能力（批量流转本体在 S6）

### S3 挂号链路与并发

- [ ] 三道防线：Redis 占位 → DB CAS → 唯一索引兜底
- [ ] 限购三条（同人同时段 / 同人同科室同日 / 号源唯一）
- [ ] 集成测试①
- [ ] 患者端主链路页面

### S4 支付链路

- [ ] `PaymentChannel` 接口 + `MockPaymentChannel`
- [ ] 回调：验签 → append-only 落库 → 立即 ack → 异步入账；「钱到了号没了」分支
- [ ] 超时关单与号源回补（30 秒巡检两段式）
- [ ] 集成测试②③

### S5 查询聚合与缓存

- [ ] 午别余量一次批量聚合（动态分组，不写死上午/下午）
- [ ] Redis `appt:remain:` 缓存，写路径唯一入口 + Lua EXISTS 守卫
- [ ] 验收：单屏由 M×2 次 COUNT 降至 1 次聚合，压测对比留档

### S6 状态机闭环

- [ ] 退号与退款、签到（分诊端扫码）、爽约扫描（半开窗口 + 全量兜底）、停诊批量流转、黑名单
- [ ] 8 种挂号状态全覆盖：`WAIT_PAY / BOOKED / SIGNED / COMPLETED / CLOSED / CANCELED_ACTIVE / CANCELED_PASSIVE / NOSHOW`
- [ ] 分诊台模式（uni-app 同仓按角色切换）

### S7 对账与交付

- [ ] 号源 + 支付对账（七查）、台账、看板
- [ ] 初始数据脚本终版、README

---

## 4. 非功能需求（PRD 第 9 章）挂钩

PRD §13.1 末条「第 9 章全部非功能需求」是兜底条款，原 §13.3 未挂任何切片——**这是最容易静默漏掉的一类**，此处逐一挂钩：

| PRD | 非功能需求 | 挂哪个切片 | 验收口径（PRD 原文） |
|---|---|---|---|
| §9.1 | 号源争抢并发与一致性 | S3 | 50 并发同一时间点恰好 1 笔成功，其余返回「已被预约」，数据无异常 |
| §9.2 | 午别余量聚合性能 | S5 | 单屏由 M×2 次 COUNT 降至 1 次聚合；压测对比留档 |
| §9.3 | 定时任务与状态流转（爽约/过期） | S6 | 漏判率 0（含某轮被跳过的兜底） |
| §9.4 | 超时关单与库存回补 | S4 | 同一订单多次触发只生效一次；回补数量与关单数量一致 |
| §9.5 | 支付回调幂等与补偿 | S4 | 回调 3 次仅 1 次入账；挂号单状态只流转一次 |
| §9.6 | 数据一致性：对账 | S7 | 每日 03:00 执行；手动触发 + 结果列表可用 |
| §9.7 | 可靠性（Redis 降级 / 渠道不可用 / 任务幂等 / 批量分批） | 横切 S2·S3·S4·S6·S7 | 逐条自测留档 |

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

## 7. 工程基线待办（不属于任何切片，但阻塞体验）

按当前顺序建议：

- [ ] 补 `appt_s0_cleanup.sql`：漏了 `1761400000000000121「AI控制台」`（隐藏+停用，无害但脏）
- [ ] 处理 `admin` 仓未提交的 `pnpm-lock.yaml`（`pnpm install` 产物）
- [ ] B2：`admin/AGENTS.md`（从 `redlines.md` 拆公共核心 + vite 端口坑）
- [ ] E1：backend / admin 两仓 README 重写
- [ ] E2：CI（PRD §12：编译 + 单元测试）
- [ ] C3：`qd-appt-app` 仓（uni-app，患者端 + 分诊台）

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
