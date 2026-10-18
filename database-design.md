# 数据库设计 · 号源 QueueDepth（qd-appt）

> **定位**：字段级设计的**唯一权威**。API 契约 §8 明确「基础数据六实体的字段级归 `database-design.md` 与生成器表单配置」，本文件即该指向的落点。
>
> **上游**：PRD §4.1 概念层级、§4.2 表清单与 7 条约束、§7 状态机、§11 初始数据、§14.5（M1–M13）；技术方案 §2 核心不变量 I1–I8、§3 六个难点、§6.1 表结构增量、§6.2 核心索引清单；API 契约 §2.4 / §2.7。
>
> **下游**：`qd-appt-backend/script/sql/appt_schema.sql`（本文件的可执行形态，字段与索引以本文件为准）。
>
> **执行顺序**：`ry_vue.sql`（框架）→ `appt_schema.sql`（本设计）→ `appt_s0_cleanup.sql`（演示数据清理）→ 各切片的 seed 脚本。

---

## 1. 全局约定

| # | 约定 | 理由 |
|---|---|---|
| 1 | 字符集 `utf8mb4` / 排序 `utf8mb4_general_ci` | 与框架库 `ry_vue` 一致（`appt` 库已按此建） |
| 2 | 主键 `bigint`，**雪花**（`mybatis-plus.global-config.db-config.idType: ASSIGN_ID`，见 `ruoyi-common-mybatis/common-mybatis.yml`） | 跟随框架默认，**不自增**——自增在分库分表/数据合并时会撞号，且不必要地暴露业务量 |
| 3 | 公共字段五件套 `create_dept` / `create_by` / `create_time` / `update_by` / `update_time`（Java 侧 `extends BaseEntity`） | 框架审计字段，后台列表与数据权限依赖 |
| 4 | **不设 `del_flag`** | 逻辑删除会让终态行**仍留在唯一索引里**，直接击穿 `UNIQUE(slot_id, active_flag)` 的 NULL 兜底（M1）。业务终态一律用 `status` + `active_flag` 表达。**注（2026-10-18 更正）**：6.0.0 的 `BaseEntity` 确实不再内置 `delFlag`，但 `SysUser`/`SysDept`/`SysRole`/`SysPost`/`SysClient` **各自单独声明了该列**、代码生成器 也认 `del_flag`——**框架仍完全支持**，不是「已无此列」。不用它的理由是 M1，不是框架不支持。**代价**：过滤必须每个查询手工带 `status='0'`（`del_flag` 由框架自动注入），见 §6 边界 |
| 5 | 状态字段分两类：**契约涉及的**用 `varchar(16)` 存契约线值（`WAIT_PAY`/`AVAILABLE`/…）；**纯后台启停**用 `char(1)` `'0'`正常/`'1'`停用 | 前者与契约 §2.7 线值一一对应，MyBatis 零转换、排查直观、导出即语义；后者是 RuoYi 惯例且代码生成器原生识别，不值得为它破坏惯例 |
| 6 | 金额 `decimal(10,2)`，Java `BigDecimal` | 与契约 §2.4「金额两位小数」一致；**不存分**——挂号费档位 15~300 元，decimal 语义直白，简历上讲得清楚，且避免分/元转换在回调与对账处出错 |
| 7 | 时间 `datetime`（秒级）；纯日期 `date`；模板内时刻 `time` | 与 `LocalDateTime` 对应。秒级足够——`time_point` 最小步长 4 分钟，无亚秒语义 |
| 8 | **`slot.time_point` / `registration.time_point` = `datetime`（完整时刻）** | 见 §1.1 决策 D-S1-1 |
| 9 | **`appt_slot` 冗余 `staff_id` / `dept_id` / `campus_id` / `visit_date` / `period`** | 见 §1.1 决策 D-S1-2 |
| 10 | **`appt_patient` 增 `id_no_hash` 列** | 见 §1.1 决策 D-S1-3 |
| 11 | 业务单号 = `前缀 + yyyyMMdd + 6 位当日序列`，`varchar(32)` | 见 §1.1 决策 D-S1-4 |
| 12 | **不建外键** | RuoYi 惯例；外键会让 `slot_ledger` 这类 append-only 表与批量任务相互牵制，且妨碍演示数据的批量清理 |
| 13 | **不使用 `@Version` 乐观锁**，并发一律用条件 CAS（`WHERE status = 期望态`）+ 三条联合唯一索引 | 技术方案 §2 的 I1/I3/I5/I7 全部按条件 CAS 设计；再引入 `@Version` 等于同一行上并存两套并发机制，排查时无法判断是版本冲突还是状态不匹配 |

### 1.1 本轮新增决策（S1 拍板，2026-10-18）

| # | 决策 | 结论与理由 |
|---|---|---|
| **D-S1-1** | `time_point` 落库类型 | **存 `datetime`**。契约 §2.4 的 `HH:mm` 是**对外线值**（VO 层格式化），不是存储形态。若存 `TIME`：技术方案 §3.3 的两条扫描 SQL（`time_point <= NOW() - 30min`、`time_point < NOW()`）与 §6.2 索引 `(time_point, status)` 全部失效，且 `UNIQUE(patient_id, time_point, active_flag)` 会跨日期误判限购（不同天的 09:51 互相冲突）。存 `datetime` 后技术方案**零改动**、限购语义天然正确。→ 需回写契约 §2.4 加一句「`timePoint` 为展示线值，DB 存完整 datetime」 |
| **D-S1-2** | `appt_slot` 冗余列 | **冗余 `staff_id`/`dept_id`/`campus_id`/`visit_date`/`period`**。真实用途两条：① §3.3 爽约/过期按 `time_point` 扫描、停诊按 (staff, date, period) 定位，免 join `schedule` 的 N+1；② 契约 §3.5 `dates` / §3.7 `staffs` 的 staffId 模式要按「某医生某日各午别」聚合余量（M8），依赖 `(staff_id, visit_date, period, status)` 索引。
> **注**：本条初版把理由写成「技术方案 §3.2 余量聚合按 (staff, 日期, 午别) 分组」，与 §3.2 的实际 SQL（按 `(schedule_id, period)` 分组，契约 §3.6 同）不符——**结论成立但依据写错了，已更正**，勿再引旧依据。
> 排班生成后这五个值**不再变更**（唯一变更源是停诊，走 `status`）；staff 主数据变更是否追溯另见 §6。→ 已回写 PRD §4.2 `appt_slot` 行 |
| **D-S1-3** | 就诊人证件号唯一性 | **增 `id_no_hash` 列（HMAC-SHA256 确定性摘要）**，唯一索引建在 `(id_type, id_no_hash)`；`id_no` 存 AES 密文（演示期明文）仅用于脱敏展示。理由：PRD §4.2 约束 6（证件号唯一）与约束 7（生产加密）在随机 IV 加密下**互斥**——密文既不能建唯一索引也不能等值查询。hash 列让两条约束同时成立。→ 需回写 PRD §4.2 约束 7 与技术方案 M11 |
| **D-S1-4** | 业务单号规则 | **`前缀 + yyyyMMdd + 6 位当日序列`**（如 `R20261018000001`），序列用 Redis `INCR` 每日重置，`varchar(32)`。理由：可读、按日期可排序、演示与排查时肉眼可核对，符合真实医院单号习惯；雪花/UUID 都丢掉了这层信息。代价是一次 Redis 调用，挂号链路本就要访问 Redis（占位 + 余量），可忽略 |
| **D-S1-5** | 停诊范围的结构化表达 | **`appt_suspend_record` 增 `staff_id` 列**（`SCHEDULE`/`STAFF_DATE` 必填、`CAMPUS_DATE` 可空）；`scope_type` 统一为 `SCHEDULE` / `STAFF_DATE` / `CAMPUS_DATE`（契约 §7.5 的 `DAY`/`RANGE` 一并改）。理由：E5 请求带 `staffId` 而原表无此列，只能把 staffId 拼进 `scope_value` 字符串再反解——F2 要按 staff 定位 schedule，靠字符串解析是脆的；契约 `RANGE` 要求 `scopeValue` 是 `{startDate,endDate}` 对象，塞不进 `varchar(64)`。代价：区间停诊要登记 N 条，换来「同一 `batch_no` 幂等归并」天然可用。**✅ 已于 2026-10-18 落地（appt_schema.sql + 库内重建 + 契约 §7.5 同步，PRD §6.10 同步）** |
| **D-S1-6** | 护士 / 护师的挂号费档位 | **`title` 线值增护师系列**（与既有四个医师系列并列），使 `medical_staff.type = NURSE` 的医务人员也能在 `appt_fee_standard` 上定价。理由：PRD §6.4 有「副主任护师（夜间）¥7.00」，但既有 `title` 只有 `CHIEF`/`ASSOC_CHIEF`/`ATTENDING`/`PHYSICIAN` 四个医师系列——不补则 S2 给护士生成 slot 时取不到 `fee` 档位。**✅ 已于 2026-10-18 同步** |
| **D-S1-7** | 医生的门诊类型归属 | **`appt_medical_staff` 增 `clinic_type varchar(32)` 列**。理由：契约 §3.4 医生主页要返回 `clinicType`，但门诊类型原本只挂在 `appt_slot_template` / `appt_schedule` 上，一个医生可有多模板多门诊类型，取哪个未定义。PRD §14.3 已定「一行 = 一个出诊身份」，staff 行本身就该带门诊类型，模板只是它的时段配置。**✅ 已于 2026-10-18 落地（appt_schema.sql + 库内重建）** |
| **D-S1-8** | 默认就诊人的唯一性 | **改造 `appt_patient.is_default`：由 `tinyint(1) NOT NULL DEFAULT 0` 改为可空、`DEFAULT NULL`，语义变为「1 = 默认 / NULL = 非默认」，并在 `(user_id, is_default)` 上建唯一索引**——沿用 M1 的「NULL 互不冲突」手法，让「一个账号最多一个默认就诊人」成为 DB 事实而非应用约定。理由：原设计只有应用层「同事务取消其它默认」，并发下两个请求可同时设成两个默认。**未采纳「新增 `default_flag` 列」方案**——那会引入第二个语义相同的列并要求手工同步两者，多一列 + 一处不一致风险；直接改造 `is_default` 是单列单真相。代价：VO 的 `isDefault` 对非默认就诊人返回 `null` 而非 `false`，前端需按 falsy 处理；批量取消默认要两步（先置 `NULL` 再置 1），不能一次 `UPDATE SET is_default=0`。**✅ 已于 2026-10-18 落地（appt_schema.sql + 库内重建）** |

---

## 2. 枚举线值（补 API 契约 §2.7 未覆盖部分）

契约 §2.7 只定义了 Slot / Registration / Payment / settleStatus 四组线值。以下为本设计新增（**回写契约 §2.7 已于 2026-10-18 完成**，其中 `scope_type` 因 E5 是前端请求线值于同日补入契约 §2.7，见 §7）：

| 实体/字段 | 线值 | 说明 |
|---|---|---|
| 午别 `period` | `AM` 上午 / `PM` 下午 / `NIGHT` 夜间 | 契约 §7.4 加号请求示例已用 `AM`；数量 2~3 可变，严禁写死两列（PRD §4.2-2） |
| 门诊类型 `clinic_type`（code） | `NORMAL` 普通 / `NIGHT` 夜间延时 / `EXPERT` 知名专家 | 契约 §3.4 用中文名展示，此处的 code 为存储与筛选值 |
| 职称 `title` | `CHIEF` 主任医师 / `ASSOC_CHIEF` 副主任医师 / `ATTENDING` 主治医师 / `PHYSICIAN` 医师 / `ASSOC_CHIEF_NURSE` 副主任护师（D-S1-6） | 与 `appt_fee_standard` 定价键联动；副主任医师 ¥15.00（PRD §14.2-12）；副主任护师 ¥7.00（PRD §6.4）。护理职称本期只用到这一档，其余按同一命名规则扩展 |
| 号源来源 `source` | `NORMAL` 正常 / `EXTRA` 加号 | 加号登记见契约 §7.4 |
| 证件类型 `id_type` | `IDCARD` 身份证 / `CARD` 就诊卡 | 身份证全局唯一、就诊卡院内唯一（PRD §4.2-6） |
| 号源台账 `action` | `GENERATE` 生成 / `OCCUPY` 占用 / `RELEASE` 释放 / `REFILL` 回补 / `SUSPEND` 停诊 / `EXPIRE` 过期 | 台账倒查（技术方案 §3.6） |
| 取消类型 `cancel_type` | `ACTIVE` 主动 / `PASSIVE` 被动 | 与 status 的 `CANCELED_ACTIVE`/`CANCELED_PASSIVE` 同源，保留供后台按取消渠道统计 |
| 排班状态 `schedule.status` | `NORMAL` 正常 / `SUSPENDED` 已停诊 | 停诊上报见契约 §7.5 |
| 任务日志 `status` | `RUNNING` / `SUCCESS` / `FAIL` / `SKIPPED` 跳过本轮 | 后台「定时任务日志」菜单；`SKIPPED` 承载红线 13「拿不到锁跳过本轮并记日志」 |
| 退款单 `status` | `WAIT_REFUND` / `REFUNDED` / `FAILED` | 退避重试耗尽置 `FAILED`，终态；如需再退另建退款单，不在原单回滚 |
| 回调处理 `process_status` | `PENDING` / `SUCCESS` / `IGNORED` 重复丢弃 / `FAILED` | 回调去重与重放（技术方案 §3.5） |
| 对账 `status` | `OK` 正常 / `FIXED` 已自动修复 / `ALERT` 待人工 | 后台「运维对账」菜单（技术方案 §3.6） |
| 医务人员类型 `medical_staff.type` | `DOCTOR` 医生 / `NURSE` 护士 | 一行 = 一个出诊身份（PRD §14.3）；护士亦可在 `fee_standard` 定价（D-S1-6） |
| 站内信场景 `notice.type` | `BOOK_SUCCESS` 挂号成功 / `PAY_SUCCESS` 支付成功 / `PAY_TIMEOUT` 支付超时关单 / `CANCEL_SUCCESS` 退号成功 / `SUSPEND_CANCEL` 停诊取消 / `NOSHOW_RECORD` 爽约记录 / `BLACKLIST_HIT` 黑名单生效 | PRD §6.12 的 7 个场景（2026-10-19 定义线值）。按**事件**命名而非状态，避免与 `registration.status` / `payment.status` 同名不同义。退款成功通知 PRD §6.12 未列，本期不做；后续若要加，补 `REFUND_SUCCESS` |
| 签到方式 `registration.sign_type` | `SCAN` 扫码 / `MANUAL` 手动补签 | 契约 §7.1 E1 / §7.2 E2；仅 `SIGNED` 态有值 |
| 停诊登记状态 `suspend_record.status` | `PENDING` 待处理 / `HANDLED` 已处理 | 契约 §8.4 列表按此筛选；F2 处理后置 `HANDLED` |
| 停诊范围 `suspend_record.scope_type` | `SCHEDULE` 单排班 / `STAFF_DATE` 某医生某日 / `CAMPUS_DATE` 院区某日 | D-S1-5；契约 §7.5 E5 请求线值（前端分诊台传入） |
| 对账动作 `reconcile_result.action` | `AUTO_FIX` 自动修复 / `ALERT` 告警 | 与 `status` 的 `FIXED`/`ALERT` 对应；R4 只告警不自动修 |
| 支付渠道 `payment.channel` | `MOCK`（本期唯一实现）/ `alipay`（预留） | 真实渠道按适配器接入（PRD D7），业务链路不变 |
| 退号/退款原因 `reason` | 自由文本 | 不做枚举，避免枚举膨胀 |

**启停类**（不出现在契约中）：`char(1)` `'0'` 正常 / `'1'` 停用——院区、门诊类型、科室、医务人员、**收费标准**、时段模板、就诊人、黑名单（**8 张基础表全部有此列**；`fee_standard` 于 2026-10-18 补，此前遗漏——见 §1 公约 4 与 §6 边界）。

---

## 3. 表设计

> 字段表说明：`空` 列中 `NOT NULL` 表示必填，空白表示可空。所有表默认带公约 3 的五件套字段（下表不再重复列出），`create_time` 默认 `CURRENT_TIMESTAMP`、`update_time` 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`。
>
> **行数量级**：仅 PRD §11 给出估计的表在各表下方标注；PRD §11 未给估计的表（`staff_favorite` / `fee_standard` / `slot_ledger` / `blacklist` / `notice` / `job_log` / `payment_callback` / `reconcile_result` / `suspend_record`）均为演示量级——事件 / 任务驱动积累，不设估计。

### 3.1 基础数据域

#### `appt_campus` 院区

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | 雪花 |
| name | varchar(64) | NOT NULL | 院区名（**虚构**，PRD §11 红线） |
| address | varchar(255) | | 地址 |
| cover_url | varchar(255) | | 封面图（占位图） |
| sort | int | | 排序 |
| status | char(1) | NOT NULL | `'0'`正常 / `'1'`停用 |

索引：`(status, sort)`。行数量级 3。

#### `appt_clinic_type` 门诊类型

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| code | varchar(32) | NOT NULL | `NORMAL`/`NIGHT`/`EXPERT` |
| name | varchar(64) | NOT NULL | 普通 / 夜间延时 / 知名专家 |
| sort | int | | |
| status | char(1) | NOT NULL | |

索引：`UNIQUE(code)`。行数量级 3。

#### `appt_department` 科室三级树（全局，不挂院区）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| parent_id | bigint | NOT NULL | 根节点为 0 |
| name | varchar(64) | NOT NULL | |
| level | tinyint | NOT NULL | 1/2/3 |
| sort | int | | |
| status | char(1) | NOT NULL | |

索引：`(parent_id, sort)`、`(level, status)`。行数量级 ~40（8 一级 / 15 二级 / 20 叶子，PRD §11）。

> 科室是**全局统一**的，不按院区建树（PRD §4.1）；院区作为医务人员的属性与筛选维度。

#### `appt_medical_staff` 医务人员

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| campus_id | bigint | NOT NULL | 所属院区（**单值**，PRD §14.3 已知边界：跨院区出诊本期不表达） |
| dept_id | bigint | NOT NULL | 所属科室（挂叶子节点） |
| name | varchar(64) | NOT NULL | |
| avatar | varchar(255) | | 占位图 |
| title | varchar(32) | NOT NULL | 职称线值（§2） |
| degree | varchar(64) | | 学位（展示用，契约 §3.3） |
| type | varchar(16) | NOT NULL | `DOCTOR` 医生 / `NURSE` 护士 |
| **clinic_type** | varchar(32) | NOT NULL | **门诊类型 code**（D-S1-7；契约 §3.4 医生主页需返回 `clinicType`）。与 `slot_template.clinic_type` / `schedule.clinic_type` 的一致性约定见 §6 |
| intro | varchar(2000) | | 简介 |
| sort | int | | |
| status | char(1) | NOT NULL | |

索引：`(dept_id, status)`、`(campus_id, dept_id, status)`、`(name)`（搜索用 LIKE，PRD §14.2-10）。行数量级 ~60。

#### `appt_staff_favorite` 医生收藏

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | NOT NULL | |
| staff_id | bigint | NOT NULL | |

索引：**`UNIQUE(user_id, staff_id)`**（PRD §4.2 未列，技术方案 §6.2 亦未列——**本设计补齐**，否则重复收藏会插入多行，契约 §3.4 的 `favorited` 语义失真）。

#### `appt_slot_template` 时段模板

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| staff_id | bigint | NOT NULL | |
| period | varchar(16) | NOT NULL | `AM`/`PM`/`NIGHT` |
| clinic_type | varchar(32) | NOT NULL | 门诊类型 code |
| start_time | time | NOT NULL | 午别起始时刻（如 08:00） |
| end_time | time | NOT NULL | 结束时刻（如 12:00） |
| step_minutes | int | NOT NULL | 步长；**4 / 5~6 / 6~7 / 10 分钟均会出现**（PRD §4.2-1） |
| status | char(1) | NOT NULL | |

索引：**`UNIQUE(staff_id, period, clinic_type)`**。行数量级 ~180。

> **不设容量字段**——生成数量 = `(end_time - start_time) / step_minutes`（PRD §4.2-4）。

#### `appt_fee_standard` 收费标准

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| title | varchar(32) | NOT NULL | 职称线值 |
| clinic_type | varchar(32) | NOT NULL | 门诊类型 code |
| fee | decimal(10,2) | NOT NULL | |
| status | char(1) | NOT NULL | `'0'` 正常 / `'1'` 停用。**2026-10-18 补**——此前遗漏，导致错误录入的收费标准无法下线（只能改价或物理删除）。历史金额不受影响（`registration.fee` 快照） |

索引：**`UNIQUE(title, clinic_type)`**（PRD §4.2-5；增改撞键返回明确错误，不静默覆盖——契约 §8-3）。

### 3.2 排班与号源域

#### `appt_schedule` 排班

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| staff_id | bigint | NOT NULL | |
| dept_id | bigint | NOT NULL | |
| campus_id | bigint | NOT NULL | 冗余自 staff，供停诊按院区范围筛选 |
| clinic_type | varchar(32) | NOT NULL | |
| visit_date | date | NOT NULL | 就诊日期 |
| period | varchar(16) | NOT NULL | 午别 |
| status | varchar(16) | NOT NULL | `NORMAL` / `SUSPENDED`（契约涉及的语义，故用线值而非 char(1)） |

索引：**`UNIQUE(staff_id, visit_date, period)`**（PRD §4.2-5，排班生成幂等）、`(visit_date, status)`。行数量级 ~500（**稀疏**，约 40% 医务人员每日出诊，PRD §11）。

#### `appt_slot` 号源（一个 Slot = 一个号）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| schedule_id | bigint | NOT NULL | |
| **staff_id** | bigint | NOT NULL | 冗余（D-S1-2） |
| **dept_id** | bigint | NOT NULL | 冗余 |
| **campus_id** | bigint | NOT NULL | 冗余 |
| **visit_date** | date | NOT NULL | 冗余（与 `time_point` 的日期部分一致） |
| **period** | varchar(16) | NOT NULL | 冗余 |
| time_point | datetime | NOT NULL | **完整时刻**（D-S1-1） |
| fee | decimal(10,2) | NOT NULL | 生成时的金额快照（I2） |
| status | varchar(16) | NOT NULL | `AVAILABLE`/`TAKEN`/`SUSPENDED`/`EXPIRED` |
| source | varchar(16) | NOT NULL | `NORMAL`/`EXTRA` |
| registration_id | bigint | | **占用时回写、回池时置 NULL**；I1 的 CAS 目标列 |

索引：
- **`UNIQUE(schedule_id, time_point)`**——生成幂等 + 加号防重（PRD §4.2-5、技术方案 §3.1 加号路径）
- **`(time_point, status)`**——爽约/过期扫描（技术方案 §3.3、M9）
- **`(staff_id, visit_date, period, status)`**——余量聚合（技术方案 §3.2），因冗余列存在才可能单表命中
- `(schedule_id, status)`——单排班号源列表（契约 §3.7）
- `(registration_id)`——I1 兜底与对账反查（R1 幽灵占号）

行数量级 ~9,000（每 staff×日×午别 12~20 个号，PRD §11）。

> `fee` 落 Slot 并冗余至 Registration（PRD §4.2-3），`fee_standard` 变更**不追溯**已生成 Slot（技术方案 I2）。

#### `appt_slot_ledger` 号源台账（append-only）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| slot_id | bigint | NOT NULL | |
| action | varchar(16) | NOT NULL | §2 台账线值 |
| before_status | varchar(16) | | 生成时为空 |
| after_status | varchar(16) | NOT NULL | |
| registration_id | bigint | | |
| batch_no | varchar(32) | | 任务批号；批量操作（停诊/关单）可倒查 |

索引：`(slot_id, create_time)`（技术方案 §6.2 台账倒查）、`(batch_no)`。

> 演示量级不分区、不归档；生产需按月分区 + 冷归档（记入「已知边界」§6）。

### 3.3 交易域

#### `appt_registration` 挂号单

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| registration_no | varchar(32) | NOT NULL | `R + yyyyMMdd + 6 位序列`（D-S1-4） |
| user_id | bigint | NOT NULL | 账号（复用 `sys_user`）；**限购与黑名单均按 user_id 统计**（M13） |
| patient_id | bigint | NOT NULL | 就诊人 |
| slot_id | bigint | NOT NULL | |
| staff_id | bigint | NOT NULL | 以下 6 列为**冗余快照**（PRD §4.2） |
| dept_id | bigint | NOT NULL | |
| campus_id | bigint | NOT NULL | |
| visit_date | date | NOT NULL | |
| period | varchar(16) | NOT NULL | |
| time_point | datetime | NOT NULL | 与 slot 一致（D-S1-1） |
| fee | decimal(10,2) | NOT NULL | **金额快照**（I2） |
| **active_flag** | tinyint(1) | | **1 = 有效 / NULL = 终态**（M1；MySQL 唯一索引中 NULL 互不冲突，号源回池复用天然成立）。**默认 1**——漏写时朝「仍然设防」而非「静默失效」的方向偏。组合合法性由 `chk_reg_active` 兜底（见表下） |
| settle_status | varchar(16) | NOT NULL | `NONE`/`WAIT_REFUND`/`REFUNDED`（契约 §2.7） |
| status | varchar(16) | NOT NULL | 契约 §2.7 八态 |
| sign_time | datetime | | 签到时间 |
| **sign_type** | varchar(16) | | **签到方式**：`SCAN` 扫码 / `MANUAL` 手动补签（契约 §7.1 E1 / §7.2 E2）；仅 `SIGNED` 态有值 |
| cancel_type | varchar(16) | | `ACTIVE`/`PASSIVE` |
| suspend_batch_no | varchar(32) | | 停诊批号回写，批量流转幂等（I7） |

索引：
- **`UNIQUE(registration_no)`**
- **`UNIQUE(slot_id, active_flag)`**——I1 终极兜底（M1）
- **`UNIQUE(patient_id, dept_id, visit_date, active_flag)`**——I4 同人同科室同日限 1
- **`UNIQUE(patient_id, time_point, active_flag)`**——I4 同人同时间点限 1 医生
- `(user_id, status)`——「同时持有 ≤3」计数 + 黑名单统计（M3/M13）
- `(status, time_point)`——爽约扫描（技术方案 §3.3）

行数量级 ~2,000（PRD §11；seed 硬约束见该节）。

> 三条联合唯一索引的列**一律 `NOT NULL`**（`active_flag` 除外，它靠 NULL 生效）。`cancel_type`/`sign_time`/`sign_type`/`suspend_batch_no` 可空，不参与唯一键。
>
> **`CHECK chk_reg_active`（P0，必须有）**：`status ∈ {WAIT_PAY, BOOKED, SIGNED}` ⇔ `active_flag = 1`；`status ∈ {COMPLETED, CLOSED, CANCELED_ACTIVE, CANCELED_PASSIVE, NOSHOW}` ⇔ `active_flag IS NULL`。
> **为什么必须有**：三条唯一索引**只认 `active_flag`、不认 `status`**，DB 侧若无此约束则零校验——① 终态迁移漏置 `NULL` → 终态单永久占住 `active_flag=1`，号源**无法回池复用**（I1 的反向击穿，不是超卖而是号源废掉），且该就诊人同科室同日永久挂不上；② 插入漏置 `1` → 三条限购唯一索引同时静默失效。加了它，任何绕过 `*StateService` 的 UPDATE 都会报 3819 而不是留下脏数据。

#### `appt_payment` 支付单

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| payment_no | varchar(32) | NOT NULL | `P + yyyyMMdd + 6 位序列` |
| registration_id | bigint | NOT NULL | |
| amount | decimal(10,2) | NOT NULL | = `registration.fee`（I2） |
| channel | varchar(16) | NOT NULL | 本期仅 `MOCK`（PRD §12） |
| status | varchar(16) | NOT NULL | `WAIT_PAY`/`PAID`/`CLOSED`/`REFUNDED` |
| trade_no | varchar(64) | | 渠道流水号 |
| expire_time | datetime | NOT NULL | = 创建时间 + 支付时限 15 分钟（PRD §14.2-3） |
| pay_time | datetime | | |

索引：**`UNIQUE(payment_no)`**（I5）、`(status, expire_time)`（关单巡检，技术方案 §3.4）、`(registration_id)`。行数量级 ~2,000（PRD §11）。

#### `appt_refund` 退款单

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| refund_no | varchar(32) | NOT NULL | `F + yyyyMMdd + 6 位序列` |
| payment_id | bigint | NOT NULL | |
| registration_id | bigint | NOT NULL | |
| amount | decimal(10,2) | NOT NULL | |
| status | varchar(16) | NOT NULL | `WAIT_REFUND` / `REFUNDED` / `FAILED`（退避重试耗尽；对账 R5 复查） |
| reason | varchar(255) | | |
| refund_time | datetime | | |

索引：**`UNIQUE(refund_no)`**（I5）、`(status, create_time)`（退款重试扫描；`FAILED` 态同样被此索引覆盖）。行数量级 ~300（PRD §11）。

### 3.4 账号与运营域

#### `appt_patient` 就诊人

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | NOT NULL | 归属账号 |
| name | varchar(64) | NOT NULL | |
| id_type | varchar(16) | NOT NULL | `IDCARD`/`CARD` |
| id_no | varchar(255) | NOT NULL | **密文列**：生产 AES 加密，演示期明文（M11）；**日志禁止打印** |
| **id_no_hash** | varchar(64) | NOT NULL | **HMAC-SHA256 确定性摘要**（D-S1-3）；唯一性与等值查询走此列 |
| **is_default** | tinyint(1) | | **1 = 默认 / NULL = 非默认**（D-S1-8；每人 ≤10 个就诊人，PRD §14.2-9）。**非默认一律存 `NULL`，不可存 `0`**——`UNIQUE(user_id, is_default)` 中 0 与 0 会互相冲突，只有 NULL 互不冲突 |
| status | char(1) | NOT NULL | |

索引：**`UNIQUE(id_type, id_no_hash)`**（D-S1-3）、**`UNIQUE(user_id, is_default)`**（D-S1-8：一个账号至多一个默认就诊人）、`(user_id, status)`。行数量级 35（20 账号 / 35 就诊人，PRD §11）。

> 接口位预留：`IdNoEncryptor`（加解密 + 脱敏）在 `appt/account` 包留空实现，生产替换为 AES/GM；**查询路径一律经 hash**，密文列只用于展示脱敏。

#### `appt_blacklist` 爽约黑名单

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | NOT NULL | **账号级**（M13） |
| patient_id | bigint | | 关联就诊人（可空：账号级判定时不针对具体人） |
| reason | varchar(255) | | |
| start_time | datetime | NOT NULL | |
| end_time | datetime | NOT NULL | 半年内退号 + 爽约合计 6 次 → 限制半年（PRD §14.2-6） |
| operator | varchar(64) | | |
| status | char(1) | NOT NULL | |

索引：`(user_id, status)`、`(end_time)`（到期扫描解冻）。

#### `appt_notice` 站内信

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| user_id | bigint | NOT NULL | |
| type | varchar(32) | NOT NULL | 通知场景（PRD §6.12） |
| title | varchar(200) | NOT NULL | |
| content | varchar(2000) | | |
| read_flag | tinyint(1) | NOT NULL | 1 已读 / 0 未读 |

索引：`(user_id, read_flag, create_time)`。

### 3.5 支撑域（M10 新增四表）

#### `appt_job_log` 定时任务日志

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| job_name | varchar(64) | NOT NULL | |
| batch_no | varchar(32) | NOT NULL | 批号（I8） |
| start_time | datetime | NOT NULL | |
| end_time | datetime | | |
| status | varchar(16) | NOT NULL | `RUNNING`/`SUCCESS`/`FAIL`/`SKIPPED` |
| affected_rows | int | | |
| message | varchar(2000) | | |

索引：`(job_name, start_time)`、`UNIQUE(batch_no)`。

#### `appt_payment_callback` 支付回调原始记录（append-only）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| payment_no | varchar(32) | NOT NULL | |
| trade_no | varchar(64) | | |
| notify_id | varchar(64) | | 渠道通知唯一 id |
| channel | varchar(16) | NOT NULL | |
| raw_body | text | | 原始报文（排查依据） |
| sign_flag | char(1) | | `'0'`验签通过 / `'1'`失败 |
| process_status | varchar(16) | NOT NULL | `PENDING`/`SUCCESS`/`IGNORED`/`FAILED` |

索引：**`UNIQUE(payment_no, trade_no, notify_id)`**（回调去重，技术方案 §6.2）、`(process_status, create_time)`。

> 三条唯一列中 `trade_no`/`notify_id` 可空——MySQL 唯一索引中 NULL 互不冲突，**Mock 渠道无 notify_id 时会失去去重能力**。补偿：Mock 渠道回调必带 `trade_no` 且同一单的 `trade_no` 恒定（真实渠道亦如此），去重实际落在 `(payment_no, trade_no)` 上；对账 R3 兜底重复入账。

#### `appt_reconcile_result` 对账结果

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| batch_no | varchar(32) | NOT NULL | |
| check_type | varchar(32) | NOT NULL | R1~R7（技术方案 §3.6） |
| target_id | bigint | | **目标 id。类型由 `check_type` 唯一决定**，不另设 `target_type` 列——见 §6 已知边界 |
| action | varchar(32) | | `AUTO_FIX` / `ALERT` |
| status | varchar(16) | NOT NULL | `OK`/`FIXED`/`ALERT` |
| detail | varchar(2000) | | |

索引：`(batch_no)`、`(check_type, status, create_time)`。

#### `appt_suspend_record` 停诊批号

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | bigint | PK | |
| batch_no | varchar(32) | NOT NULL | 幂等锚点（I7） |
| scope_type | varchar(16) | NOT NULL | `SCHEDULE` 单排班 / `STAFF_DATE` 某医生某日 / `CAMPUS_DATE` 院区某日（D-S1-5） |
| scope_value | varchar(64) | NOT NULL | `SCHEDULE` 存 scheduleId；`STAFF_DATE` 存 visitDate；`CAMPUS_DATE` 存 `campusId:date`（D-S1-5） |
| **staff_id** | bigint | | **医务人员 id**（D-S1-5；`SCHEDULE`/`STAFF_DATE` 必填，`CAMPUS_DATE` 为空）——F2 处理时要按 staff 定位 schedule，不能靠解析 `scope_value` 字符串 |
| **reason** | varchar(255) | | **停诊原因**（契约 §7.5 E5；用于向受影响患者发站内信） |
| **status** | varchar(16) | NOT NULL | **`PENDING` 待处理 / `HANDLED` 已处理**（契约 §8.4 停诊登记列表按此筛选；同一范围已存在 `PENDING` 时返回已登记批号，不重复建单） |
| operator | varchar(64) | | |

索引：`UNIQUE(batch_no)`、`(scope_type, scope_value)`、**`(status, create_time)`**（§8.4 列表按状态筛选，D-S1-5 新增）。

---

## 4. 索引总表（合并 PRD §4.2-5 + 技术方案 §6.2 + 本设计新增）

| 表 | 索引 | 服务的不变量/难点 |
|---|---|---|
| campus | `(status, sort)` | 院区列表排序（§3.1） |
| clinic_type | `UNIQUE(code)` | 门诊类型字典唯一 |
| department | `(parent_id, sort)` / `(level, status)` | 科室树展开、按层级筛选（§3.1） |
| medical_staff | `(dept_id, status)` / `(campus_id, dept_id, status)` / `(name)` | 医生列表 / 院区筛选 / 姓名 LIKE 搜索（PRD §14.2-10） |
| slot_template | `UNIQUE(staff_id, period, clinic_type)` | 模板不重复（本设计新增） |
| fee_standard | `UNIQUE(title, clinic_type)` | 定价唯一（PRD §4.2-5）；**停用行仍占键** → 重新录入同键走「重新启用」而非 insert |
| **staff_favorite** | **`UNIQUE(user_id, staff_id)`** | **防重复收藏（本设计补 PRD/技术方案遗漏）** |
| schedule | `UNIQUE(staff_id, visit_date, period)` | 排班生成幂等 |
| schedule | `(visit_date, status)` | 按日筛选、停诊范围定位 |
| slot | `UNIQUE(schedule_id, time_point)` | 生成幂等 + 加号防重 |
| slot | `(time_point, status)` | 爽约/过期扫描（§3.3） |
| slot | **`(staff_id, visit_date, period, status)`** | **余量聚合（§3.2），依赖 D-S1-2 冗余列** |
| slot | `(schedule_id, status)` | 单排班号源列表（契约 §3.7） |
| slot | `(registration_id)` | 幽灵占号反查（R1） |
| slot_ledger | `(slot_id, create_time)` / `(batch_no)` | 台账倒查（§3.6） |
| registration | `UNIQUE(registration_no)` | 单号唯一 |
| registration | `UNIQUE(slot_id, active_flag)` | I1 兜底（M1） |
| registration | `UNIQUE(patient_id, dept_id, visit_date, active_flag)` | I4 同科室同日限 1 |
| registration | `UNIQUE(patient_id, time_point, active_flag)` | I4 同时间点限 1 |
| registration | `(user_id, status)` | 「同时持有 ≤3」+ 黑名单统计（M3/M13） |
| registration | `(status, time_point)` | 爽约扫描（§3.3） |
| **registration** | **`CHECK chk_reg_active`** | **状态 × `active_flag` 组合合法性（I1/I4 的 DB 侧兜底，见 §3.3 表下）** |
| payment | `UNIQUE(payment_no)` / `(status, expire_time)` / `(registration_id)` | I5；关单巡检（§3.4） |
| refund | `UNIQUE(refund_no)` / `(status, create_time)` / **`(registration_id)`** | I5；退款重试扫描；**`(registration_id)` 供对账 R3 判「无退款单」，缺则全表扫** |
| **patient** | **`UNIQUE(id_type, id_no_hash)`** | **证件唯一 + 加密共存（D-S1-3）** |
| **patient** | **`UNIQUE(user_id, is_default)`** | **一账号至多一个默认就诊人（D-S1-8）** |
| patient | `(user_id, status)` | 就诊人列表（契约 §4.6） |
| blacklist | `(user_id, status)` / `(end_time)` | 限购拦截；到期解冻 |
| notice | `(user_id, read_flag, create_time)` | 站内信列表 |
| job_log | `UNIQUE(batch_no)` / `(job_name, start_time)` | I8 不重跑、漏跑可补 |
| payment_callback | `UNIQUE(payment_no, trade_no, notify_id)` / `(process_status, create_time)` | 回调去重（§3.5）/ 失败回调重试扫描 |
| reconcile_result | `(batch_no)` / `(check_type, status, create_time)` | 对账结果查询 |
| suspend_record | `UNIQUE(batch_no)` / `(scope_type, scope_value)` / **`(status, create_time)`** | I7 停诊幂等；**`(status, create_time)` 供 §8.4 登记列表按待处理筛选** |

---

## 5. 不变量 → DDL 保证映射

| 不变量（技术方案 §2） | 承载它的 DDL |
|---|---|
| I1 一个号源最多一笔有效挂号 | `slot.registration_id` + **`UNIQUE(registration(slot_id, active_flag))`** |
| I2 金额 = 挂号时快照 | `slot.fee` + `registration.fee` + `payment.amount` 三处快照 |
| I3 三张状态机只走合法边 | 状态列 `varchar(16)` 存线值 + 条件 CAS（非 DDL 层，但线值收敛是前提） |
| I4 限购三条 | 两条联合唯一索引 + `UNIQUE(id_type, id_no_hash)`（就诊人唯一是限购前提） |
| I5 回调至少处理一次、状态只流转一次 | `UNIQUE(payment_callback(payment_no, trade_no, notify_id))` + `UNIQUE(payment_no)` |
| I6 号源与资金最终一致（该退的退、该占的占） | `appt_reconcile_result`（七查结果落库：批号/类型/目标/动作/状态）+ `appt_slot_ledger`（修复倒查依据）——非单点 DDL，靠对账任务 + 每条修复 CAS 守卫保证（技术方案 §3.6） |
| I7 停诊/退款批量不重不放 | `UNIQUE(suspend_record(batch_no))` + `UNIQUE(refund_no)` + `registration.suspend_batch_no` |
| I8 定时任务不重跑、漏跑可补 | `UNIQUE(job_log(batch_no))` |

---

## 6. 已知边界与待验证

| 项 | 处理 |
|---|---|
| `slot_ledger` / `payment_callback` 数据量 | 演示量级不分区；生产需按月分区 + 冷归档（PRD §13.2 本期不做） |
| `payment_callback` 的 NULL 去重缺口 | Mock 渠道以 `(payment_no, trade_no)` 实际去重，对账 R3 兜底（见 §3.5 表下说明） |
| 就诊人证件被其他账号绑定 | 本期不做解绑流程（PRD §14.3） |
| 启停类基础表停用后重新录入 | `uk_clinic_type_code` / `uk_template_staff_period_type` / `uk_fee_title_type` / `uk_patient_id_hash` 四个唯一键在停用后**仍占位** → 一律走「命中停用行则重新启用」，不走 insert（否则 1062） |
| 基础数据物理删除 | **不建外键**，删掉被 `schedule` / `slot` / `registration` 引用的基础数据会**静默产生孤儿** → 删除前必须做引用校验（有引用则拒绝并提示先停用）；从没被引用的新记录才允许物理删除 |
| `status` 过滤的两套查询 | 前台下拉（院区 / 科室 / 医生 / 就诊人）一律带 `status='0'`；**后台管理列表不带**（否则停用后从后台也看不见，无法恢复）。生成代码不会自动带此条件，漏写即 bug |
| 医务人员跨院区出诊 | 本期一行 = 一个出诊身份；后续拆 `staff_campus` 链接表（M7） |
| 停诊时已签到挂号单 | 本期不参与批量退号（PRD §14.3） |
| 索引体积 | `varchar` 状态列比 `tinyint` 每索引项多约 15 字节；演示量级（万级）无影响，生产量级需复核（§1-5 的取舍） |
| **`appt_slot` 冗余列的同步边界** | D-S1-2 说「排班生成后五个冗余值不再变更」，那只覆盖了单次业务操作；**后台修改 `appt_medical_staff.campus_id` / `dept_id`（医生换科室、换院区）时不追溯**已生成的 `appt_slot` 与 `appt_registration` 冗余列——与 `fee` 快照同一原则（保护历史单可倒查）。因此可能出现「该医生已调至 B 院区，但历史号源仍挂在 A」的查询结果，**属预期不是 bug**；S1 生成代码时不得当作数据不一致去修 |
| **`medical_staff.clinic_type` 与 `slot_template.clinic_type` 的冗余** | D-S1-7 给 staff 加了 `clinic_type`，与 `slot_template.clinic_type` / `schedule.clinic_type` 构成一对新冗余。`UNIQUE(staff_id, period, clinic_type)` 允许同一 staff 有多个不同 `clinic_type` 的模板，与「一行 = 一个出诊身份」（PRD §14.3）相冲突。**约定：同一 staff 的所有 `slot_template.clinic_type` 必须等于 `staff.clinic_type`**，`appt_schedule.clinic_type` 同理从 staff 取值；由 Service 层校验（跨表无法用 CHECK）。不遵守则医生主页的 `clinicType` 与排班实际不符 |
| **`appt_patient.is_default` 的 NULL 语义** | 非默认必须存 `NULL`，**不可存 `0`**——`UNIQUE(user_id, is_default)` 中 0 与 0 会互相冲突，只有 NULL 才互不冲突。代价：VO 的 `isDefault` 对非默认就诊人返回 `null` 而非 `false`，前端按 falsy 处理；批量取消默认要两步（先置 `NULL` 再置 1），不能一次 `UPDATE SET is_default=0` |
| **状态列 `varchar(16)` 的零余量** | 最长线值 `CANCELED_PASSIVE` 恰好 16 字符，与列宽相等——**当前不会截断**（MySQL 8 严格模式下超长会直接报错，不是静默截断）。**本期不放宽列宽**：改动要再动一次 DDL 与实体，收益只是防一个还没发生的未来值。若将来新增 >16 字符的状态线值，必须同步 `ALTER` 放宽列宽并更新 `chk_reg_active`，否则 INSERT/UPDATE 会报 1406 |
| **对账结果 `target_id` 的目标类型** | `target_id` 单列混装 slot / registration / refund 三类 id，**目标类型由 `check_type` 唯一决定**：R1→slot、R4/R6→registration、R5→refund、R7→无目标（缓存无 id）。未另设 `target_type` 列——省一列，代价是读结果时必须按 `check_type` 分派，不能只看 id |
| **`appt_notice` / `appt_slot_ledger` / `appt_payment_callback` 无管理端点** | 三张表**均无写入端点**：`notice` 由系统事件触发（PRD §6.12 七种场景），`slot_ledger` 由状态单柱 append，`payment_callback` 由回调入口 append。读侧也只有 `appt_notice` 有患者端 D4/D5/D6 三个端点，`slot_ledger` 与 `payment_callback` **连查询端点都没有**（排查靠直连库）。PRD §10.2 菜单树同样没有对应页面——S7 需决定补不补「站内信管理 / 台账查询 / 回调记录」页，不补则维持此边界 |
| **`medical_staff` 删除的引用校验范围** | 上一条「基础数据物理删除」的校验清单只覆盖 `appt_schedule` / `appt_slot` / `appt_registration`。删除 `appt_medical_staff` 前还须额外校验 `appt_staff_favorite.staff_id` 与 `appt_slot_template.staff_id`，否则留下孤儿收藏与孤儿模板 |

---

## 7. 已回写上游文档的记录（2026-10-18 完成）

1. **API 契约 §2.4**：补一句「`timePoint`(`HH:mm`) 为展示线值，DB 以 `datetime` 存储完整时刻」（D-S1-1）。
2. **PRD §4.2 `appt_slot` 行**：补冗余列 `staff_id`/`dept_id`/`campus_id`/`visit_date`/`period`（D-S1-2）。
3. **PRD §4.2 约束 7 与技术方案 M11**：补 `id_no_hash` 列与「唯一性走 hash、密文只用于展示」（D-S1-3）。

另外 **API 契约 §2.7** 需补 §2 的基础数据枚举线值表（period / clinic_type / title / source / id_type / action / schedule.status / job status / callback status / reconcile status）——**已于 2026-10-18 完成**；本轮另随退款失败链路增补 `refund.status` 一项。
