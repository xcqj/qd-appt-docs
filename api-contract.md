# 号源 QueueDepth · API 契约

> 文档状态：v0.1（2026-10-17 定稿）：四层契约全量；P1 端点条目（B8–B10 / C4 / D1–D6 / E3 / F3–F4 / F8–F30）待对应切片联调前补，占位见 §10
> 用途：作为 `appt` 模块后端 API 的业务契约，供开发、Review、测试和 AI Agent 实现时使用。
>
> 本文定义接口契约与业务语义，不规定具体 Java 类名、RuoYi 返回包装类型、MyBatis-Plus 调用方式、异常类等实现细节。实现时以当前 RuoYi-Vue-Plus 源码中的真实模式为准。
> 业务规则权威在 `docs/PRD.md`；实现方案权威在 `docs/技术方案.md`。本文与它们冲突时：业务语义以 PRD 为准、接口形态以本文为准；**冲突先报告再修订**，不得默默偏离。

---

## 1. 总体原则

### 1.1 API 分层（四层）

```text
/appt/public/...    公开 API（匿名）：院区 / 科室 / 医生 / 排班 / 号源查询 + 支付回调
/appt/patient/...   患者 API（登录）：就诊人 / 挂号 / 支付 / 退号 / 收藏 / 消息
/appt/triage/...    分诊 API（登录 + triage 角色）：签到 / 补签 / 加号 / 停诊上报
/appt/admin/...     管理 API（登录 + 按钮权限）：基础数据 / 排班 / 停诊 / 交易 / 对账 / 看板
```

- 公共 API 与管理 API 不混用；多个 Controller 可复用同一个领域 Service，API 边界通过 Controller 划分，业务能力通过 Service 复用。
- **路径层与领域节解耦**：渠道回调端点虽在 `/appt/public/` 前缀下，语义归「支付组」（§5）。
- 数据归属与权限一律由服务端按当前登录用户强制校验，不信任前端传入的任何 ID（红线 10）。

### 1.2 身份与权限标注法

每个端点条目固定一行 `**身份：**`，取值四值：

```text
公开           匿名可访问，需加入 application.yml 的 security.excludes 白名单
登录           仅要求登录，数据归属由服务端按当前用户强制过滤，不设按钮级权限
triage         登录 + triage 角色
appt:xxx:yyy   管理端点按钮权限，标识遵循 appt:资源:动作
```

### 1.3 公共约定

- 所有时间均为 **Asia/Shanghai 本地时区**（单时区部署，不做跨区转换）。
- 金额单位为元（CNY），**JSON 字符串**（框架全局将 `BigDecimal` 序列化为字符串，防 JS 精度丢失；2026-10-19 由 JSON number 修订），两位小数。
- 资源路径用英文单数（`/slot` 不用 `/slots`）；路径参数用 `{id}` 样式。
- 全部数据虚构，不使用真实医院 / 科室 / 医务人员名称（PRD §11 红线）。

### 1.4 契约先行纪律

- 实现与契约冲突时先报告再修订；契约变更记入文档状态行。
- 影响状态机的契约变更，须同步检查 PRD §7 与技术方案 §3 是否有对应修订。

---

## 2. 统一请求响应约定

### 2.1 响应结构

成功 / 失败的响应 envelope 遵循当前 RuoYi-Vue-Plus 项目惯例（`R<T>`）。本文只约定业务字段与语义，不规定包装类型与异常类。

> **业务码位置（2026-10-20 补，S3）**：框架 `R.code` 是 `int`，装不下 §2.2 的字符串业务码。因此业务失败统一返回 `code = 400`（传输层）、`msg = 中文文案`，**业务码放在 `data.bizCode`**（如 `{"bizCode":"SLOT_GONE"}`）。前端按 `data.bizCode` 分支渲染，不要解析 `msg`。

### 2.2 业务错误码（P0 最小集）

业务失败返回的 `code` 使用下表业务码；`message` 由前端按码渲染对应文案。传输层通用码（401 / 403 / 参数校验 / 500）遵循框架惯例，不列入本表（见 §11）。

| code | 含义 | 触发端点 |
|---|---|---|
| `SLOT_GONE` | 号源已被预约或已消失（并发防线②③失败） | §4 B1 |
| `SCHEDULE_SUSPENDED` | 该排班已停诊，不可预约 | §4 B1 |
| `OUT_OF_WINDOW` | 不在可约窗口 [今日+1, 今日+7] | §4 B1 |
| `LIMIT_HOLD_MAX` | 同时持有有效预约已达 3 单上限（账号口径） | §4 B1 |
| `LIMIT_DEPT_DAY` | 同一就诊人同科室同日已挂 | §4 B1 |
| `LIMIT_TIME_CONFLICT` | 同一就诊人同一时间点已挂其他医生 | §4 B1 |
| `BLACKLISTED` | 账号处黑名单限制期 | §4 B1 |
| `DUPLICATE_SUBMIT` | 幂等键命中，返回首次结果（**非失败语义**，前端直接展示首次结果） | §4 B1 |
| `PAYMENT_CLOSED` | 支付单已关闭或不存在，不能支付 | §5 C2 / C3 |
| `CALLBACK_SIGN_INVALID` | 回调验签失败（拒绝 + 记录 + 告警） | §5 C1 |
| `REFUND_DEADLINE_PASSED` | 已过退号时限（就诊前一日 23:00） | §4 B5 |
| `REG_STATE_INVALID` | 挂号单状态不允许当前操作（如已退号再退号） | §4 B4 / B5 |
| `SIGN_TOO_EARLY` | 未到可签到时间（就诊日 00:00 前） | §7 E1 |
| `SIGN_WINDOW_CLOSED` | 已过爽约判定点或该单已签到 | §7 E1 |
| `EXTRA_SLOT_INVALID` | 加号目标午别不存在或已停诊 | §7 E4 |
| `PATIENT_LIMIT_EXCEEDED` | 就诊人已达 10 人上限 | §4 B7 |

> B1（提交挂号）集中了 8 个码：限购三条 + 黑名单 + 号源争抢的失败面全在该端点，前端必须按码分支渲染文案（"已被抢" / "您已有 3 单待就诊" / "黑名单期"）——这是错误码进契约而非留在实现层的原因。

### 2.3 分页约定

- `pageNum` 默认 1；`pageSize` 默认 10，上限 100。
- 分页返回 `rows` / `total`，与框架统一分页对象一致。
- 公开查询组除 `staff/list`（`pageSize` 默认 20）外**不分页**——数据量被 7 天窗口天然封顶（3 院区 / ~40 科室 / 每科 2~4 人 / 单午别 12~20 个号）；管理端列表统一分页。

### 2.4 时间与金额格式

| 类型 | 格式 | 示例 |
|---|---|---|
| 就诊日期 `visitDate` | `yyyy-MM-dd` | `2026-10-21` |
| 时间点 `timePoint` | `HH:mm`（**展示线值**；DB 以 `datetime` 存完整时刻，服务端格式化后输出——见 `database-design.md` D-S1-1） | `09:51` |
| 完整时间戳 | `yyyy-MM-dd HH:mm:ss` 本地时区 | `2026-10-21 09:51:00` |
| 金额 | JSON 字符串，两位小数 | `"22.00"` |

### 2.5 幂等与防重

- **B1 提交挂号强制要求 `Idempotency-Key` 请求头**（客户端生成 UUID）；缺失返回 400。服务端以该键在 Redis 存首次结果（TTL 24h），重复提交直接返回首次结果并附 `DUPLICATE_SUBMIT`——防用户双击造出两笔待支付单。
- 其余写操作**不要求**幂等键：退号 / 取消 / 签到 / 关单 / 停诊均以状态 CAS 为天然幂等（技术方案 §3.1 / §3.4）。
- 回调侧以 `payment_no` + 状态 CAS 幂等（见 §5.1）。

### 2.6 上传与导出

本期不做：医生头像等用占位图（PRD §11）；OSS 上传复用 RuoYi 现有能力，不在本契约展开；导出功能本期不做。

### 2.7 状态枚举线值

状态字段在请求 / 响应中的线值（PRD §7 状态机中文名 → wire value 映射，前后端以此为准）：

| 实体 | 线值 |
|---|---|
| Registration 挂号单 | `WAIT_PAY` 待支付 / `BOOKED` 已预约 / `SIGNED` 已签到 / `COMPLETED` 已完成 / `CLOSED` 已关闭 / `CANCELED_ACTIVE` 已退号(主动) / `CANCELED_PASSIVE` 已退号(被动) / `NOSHOW` 已爽约 |
| Payment 支付单 | `WAIT_PAY` 待支付 / `PAID` 已支付 / `CLOSED` 已关闭 / `REFUNDED` 已退款 |
| Slot 号源 | `AVAILABLE` 可约 / `TAKEN` 已占 / `SUSPENDED` 已停诊 / `EXPIRED` 已过期 |
| 挂号单 settleStatus | `NONE` 无结算 / `WAIT_REFUND` 待退费 / `REFUNDED` 已退费 |

公开查询组（§3）只暴露 `AVAILABLE` 的号源；其余态不出现在公开响应中。

**基础数据枚举线值**（S1 补充，权威定义见 `database-design.md` §2）：

| 实体/字段 | 线值 |
|---|---|
| 午别 `period` | `AM` 上午 / `PM` 下午 / `NIGHT` 夜间（数量 2~3 可变，严禁写死两列，PRD §4.2-2） |
| 门诊类型 `clinicType` | `NORMAL` 普通 / `NIGHT` 夜间延时 / `EXPERT` 知名专家（展示用中文名，见 §3.4） |
| 职称 `title` | `CHIEF` 主任医师 / `ASSOC_CHIEF` 副主任医师 / `ATTENDING` 主治医师 / `PHYSICIAN` 医师 / `ASSOC_CHIEF_NURSE` 副主任护师（D-S1-6；PRD §6.4「副主任护师（夜间）¥7.00」需护理职称也能在 `fee_standard` 定价；本期只用这一档护理职称） |
| 号源来源 `source` | `NORMAL` 正常 / `EXTRA` 加号 |
| 证件类型 `idType` | `IDCARD` 身份证 / `CARD` 就诊卡 |
| 号源台账 `action` | `GENERATE` / `OCCUPY` / `RELEASE` / `REFILL` / `SUSPEND` / `EXPIRE` |
| 取消类型 `cancelType` | `ACTIVE` 主动 / `PASSIVE` 被动 |
| 停诊范围 `scopeType` | `SCHEDULE` 单个午别 / `STAFF_DATE` 某医生某日 / `CAMPUS_DATE` 院区某日（E5 请求线值，前端分诊台传入；日期区间停诊按日拆 N 条登记，D-S1-5） |
| 排班状态 `schedule.status` | `NORMAL` 正常 / `SUSPENDED` 已停诊 |
| 定时任务 `job.status` | `RUNNING` 执行中 / `SUCCESS` 成功 / `FAIL` 失败 / `SKIPPED` 未抢到锁或本轮任务未结束，**跳过本轮**（红线 13） |
| 退款单 `refund.status` | `WAIT_REFUND` 待退款 / `REFUNDED` 已退款 / `FAILED` 退款失败（退避重试耗尽后置此态，进人工队列 + 告警，PRD §6.6；对账 R5 复查） |
| 支付回调 `callback.processStatus` | `PENDING` 待处理 / `SUCCESS` 已入账 / `IGNORED` 重复丢弃 / `FAILED` 处理失败 |
| 对账结果 `reconcile.status` | `OK` 正常 / `FIXED` 已自动修复 / `ALERT` 待人工 |

> 院区 / 门诊类型 / 科室 / 医务人员 / **收费标准** / 时段模板 / 就诊人 / 黑名单的**启停**用 `char(1)`（`'0'` 正常 / `'1'` 停用），不属契约线值，仅后台管理使用，前端不感知。

---

## 3. 公开查询组 `/appt/public/**`（A1–A7）

> 组首说明：挂号前置链路，S2 / S3 / S5 共用；全部匿名（`security.excludes` 白名单）。
> 只返回可约状态的数据：被占用的时间点不出现（PRD §6.2），已停诊的排班不返回。

### 3.1 院区列表

```http
GET /appt/public/campus/list
```

**身份：** 公开。

**返回至少：**

```text
campusId
name
address
coverUrl
```

定长 3 项，不分页。

### 3.2 科室三级树（按院区过滤）

```http
GET /appt/public/dept/tree?campusId=
```

**身份：** 公开。

**请求参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| campusId | 是 | 院区 ID |

**业务行为：** 从全局科室树中剪出该院区有出诊医务人员的节点——判定依据为医务人员关联 `(campus_id, dept_id)`（PRD §2 D5）；无出诊人员的枝整枝剪掉。

**返回至少：**

```text
deptId
parentId
name
level       1 / 2 / 3
children    树形嵌套
```

### 3.3 医生列表

```http
GET /appt/public/staff/list?deptId=&campusId=&keyword=&pageNum=&pageSize=
```

**身份：** 公开。

**请求参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| deptId | 是 | 科室 ID |
| campusId | 是 | 院区 ID（医务人员归属院区） |
| keyword | 否 | 医生姓名模糊搜索（MySQL LIKE，PRD §6.13）；科室名搜索在科室树前端过滤，不走本端点 |
| pageNum / pageSize | 否 | 本组唯一分页端点，pageSize 默认 20 |

**返回至少：**

```text
staffId
name
avatar
title       职称
degree      学位
campusName  就诊地点（所属院区名）
```

### 3.4 医生主页

```http
GET /appt/public/staff/{id}
```

**身份：** 公开。

**返回至少：**

```text
staffId
name
avatar
title
degree
deptId
deptName
campusId
campusName
clinicType      普通 / 夜间延时 / 知名专家
intro           简介
favorited       当前登录用户是否已收藏；未登录固定 false
```

**约束：**

- `favorited` 由服务端按当前登录态计算，不信任前端传入的用户标识。
- 一行医务人员 = 一个出诊身份（campus_id 单值）；跨院区出诊为已知边界（PRD §14.3）。

### 3.5 日期栏（双模式）

```http
GET /appt/public/schedule/dates?deptId=&staffId=
```

**身份：** 公开。

**请求参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| deptId / staffId | 二选一 | 两种渲染模式，语义不同（技术方案 M8） |

**业务行为：** 定长返回窗口 `[今日+1, 今日+7]` 共 7 项：

- **deptId 模式**（科室排班页）：`hasSchedule` = 该科室该日存在任一医务人员的排班；`periods` = 全部出诊人员**各午别可约数求和**（按 period 动态分组，午别数量 2~3 可变，严禁写死两列）。
- **staffId 模式**（医生主页）：`hasSchedule` = 该医生该日有排班；`periods` = 该医生各午别可约数。

**返回至少：**

```text
visitDate     yyyy-MM-dd
hasSchedule   true / false
periods       [{ period, remain }]；无排班日为空数组
```

**前端标签映射（红线 6，两套语义严禁混用）：**

```text
科室排班页：hasSchedule = true →「有排班」；false →「无排班」
医生主页：  hasSchedule = false →「无号」；true 且 remain 合计 = 0 →「满诊」
```

### 3.6 按排班：当日出诊医生 + 午别余量

```http
GET /appt/public/schedule/staffs?deptId=&date=
```

**身份：** 公开。

**请求参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| deptId | 是 | 科室 ID |
| date | 是 | 就诊日期，须在可约窗口内，否则按无数据处理 |

**业务行为：** 单屏一次聚合完成（技术方案 §3.2）：该科室该日出诊医生列表 + 每人各午别余量——`status='可约'` 按 `(schedule_id, period)` 分组 COUNT，回填 Map；余量读路径先读 Redis 缓存、未命中回源聚合并回填。

**返回至少：**

```text
staffs: [{
  staffId
  name
  avatar
  title
  degree
  periods: [{ period, remain }]
}]
```

**约束：**

- `remain = 0` 的午别**仍然返回**（前端置灰禁用，PRD §6.3），与 3.7「被占用不出现」是两种语义，不得混用。
- 单屏 SQL 次数 ≤ 3（出诊医生 + 一次聚合 + 附属查询），性能验收见 PRD §9.2。

### 3.7 可约时间点

```http
GET /appt/public/slot/list?scheduleId=&period=
```

**身份：** 公开。

**请求参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| scheduleId | 是 | 排班 ID |
| period | 是 | 午别：上午 / 下午 / 夜间（可变枚举） |

**业务行为：** 只返回 `status = 可约` 的号源（被占用的不出现，PRD §6.2），按 `time_point` 升序。

**返回至少：**

```text
slots: [{
  slotId
  timePoint    HH:mm
  fee         元，两位小数
}]
```

---

## 4. 挂号组 `/appt/patient/**`（B1–B10）

> 组首说明：挂号单生命周期，全部登录（`@SaCheckLogin`），数据范围按 `user_id` 服务端强过滤（不信任前端传入的任何 ID，红线 10）。
> 限购与黑名单均按账号（`user_id`）口径（PRD §6.5 / §6.9、红线 14）；状态机依据 PRD §7.2，线值见 §2.7。

### 4.1 提交挂号（B1）

```http
POST /appt/patient/registration
```

**身份：** 登录。

**请求头：**

| 头 | 必填 | 说明 |
|---|---|---|
| Idempotency-Key | 是 | 客户端生成的 UUID；缺失返回 400 |

**请求：**

```json
{
  "slotId": 1001,
  "patientId": 88
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| slotId | 是 | 目标号源；scheduleId / visitDate / period / timePoint / fee 全部由服务端从 slot 推导，请求体不带 |
| patientId | 是 | 就诊人，必须属于当前账号 |

**业务行为：**（单事务，顺序见技术方案 §3.1）

```text
① Redis 占位：SET appt:slot:hold:{slotId} {registrationNo} NX EX 15min
   失败 → SLOT_GONE（快速失败，不打到 DB）
② BEGIN
③ SELECT sys_user WHERE user_id = 当前用户 FOR UPDATE
   ——账号行锁：串行化同一用户的并发挂号，使 ④ 的检查精确
④ 锁内精查：黑名单 / 有效预约计数（WAIT_PAY+BOOKED+SIGNED）≥ 3 /
   号源 AVAILABLE + 排班未停诊 + 日期在窗口内
⑤ INSERT registration（registration_no 预生成；status=WAIT_PAY；
   active_flag=1；fee = slot.fee 快照）
   撞 UNIQUE(slot_id, active_flag) → SLOT_GONE
   撞限购联合唯一 → LIMIT_DEPT_DAY / LIMIT_TIME_CONFLICT
⑥ UPDATE slot SET status=TAKEN, registration_id=? WHERE id=? AND status=AVAILABLE
   影响行数 0 → SLOT_GONE，整体回滚
⑦ INSERT payment（payment_no；amount = registration.fee；
   expire_time = now + 15min；status=WAIT_PAY）
⑧ COMMIT
⑨ afterCommit：余量缓存 DECR + 发「挂号成功待支付」站内信
```

**状态：** Slot `AVAILABLE → TAKEN`；Registration（新建）`WAIT_PAY`；Payment（新建）`WAIT_PAY`。

**前置条件：**

- 已登录，`patientId` 归属当前账号
- 号源可约、排班未停诊、`visit_date ∈ [今日+1, 今日+7]`
- 账号未命中黑名单；同时持有有效预约 < 3
- 该就诊人同科室同日未挂；同一时间点未挂其他医生

**返回至少：**

```text
registrationId
registrationNo     就诊码内容
paymentNo
amount             挂号费快照（元）
expireTime         支付截止（yyyy-MM-dd HH:mm:ss）
staffName
deptName
campusName
visitDate
period
timePoint
```

**约束：**

- 幂等键命中 → 返回**首次受理结果**并附 `DUPLICATE_SUBMIT`（非失败语义，前端直接渲染结果，不报错）。
- 金额只认 `slot.fee` 快照；请求体携带金额一律忽略。
- Redis 不可用 → 跳过 ①，降级为纯 DB CAS（正确性不降，PRD §9.7）。
- ⑤~⑦ 任一步失败 → 整体回滚 + Lua 比对 value 后删除占位 key（TTL 兜底）。

**实现口径（2026-10-20，S3）**

- **幂等命中不发 `DUPLICATE_SUBMIT` 错误码**：响应仍是 `code=200`，`data.duplicate=true` 表示回放首次结果（前端据此提示「已提交过」而不报错）。`DUPLICATE_SUBMIT` 只用于「同键请求正在处理中、暂无结果」的并发场景。
- **限购判定顺序**：账号行锁内先查持有数（`LIMIT_HOLD_MAX`），再查同科室同日（`LIMIT_DEPT_DAY`），最后查同时间点（`LIMIT_TIME_CONFLICT`）；三条复合唯一索引仍保留，撞键时按索引名映射同一组错误码。
- **账号行锁**：`SELECT user_id FROM sys_user WHERE user_id = ? FOR UPDATE`（单行、不 JOIN），使同一账号的并发挂号串行化。
- **占位 TTL** = `payment.expire-minutes`（默认 15 分钟），与支付截止时间等长；成功后 key 保留至 TTL 自然过期，关闭/退号路径的主动释放归 S4/S6a。
- **支付单**：本切片只落 `payment(WAIT_PAY)`，`expire_time = now + payment.expire-minutes`；支付动作与回调归 S4。

### 4.2 我的预约列表（B2）

```http
GET /appt/patient/registration/list?status=&patientId=&pageNum=&pageSize=
```

**身份：** 登录。

**请求参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| status | 是 | Registration 线值之一（§2.7），对应前端「我的预约」状态 tab |
| patientId | 否 | 就诊人 ID；传入则按该就诊人过滤（账号名下，切换就诊人视角） |
| pageNum / pageSize | 否 | 默认 1 / 10 |

**返回至少：**

```text
rows: [{
  registrationId
  registrationNo
  patientId
  patientName
  staffName
  deptName
  campusName
  visitDate
  period
  timePoint
  fee
  status
  settleStatus
  signTime        已签到才有
  cancelType      已退号才有（主动 / 停诊）
}]
total
```

### 4.3 预约详情（B3）

```http
GET /appt/patient/registration/{id}
```

**身份：** 登录。

**业务行为：** 仅返回当前 `user_id` 名下的挂号单；不匹配按「资源不存在」处理（不泄露存在性）。

**返回至少：**

```text
registrationId / registrationNo
status / settleStatus / cancelType
patient: { patientId, name, idType, idNoMasked }
staff: { staffId, name, title, deptName, campusName }
visitDate / period / timePoint / fee
payment: { paymentNo, amount, status, expireTime, payTime }
refund: { refundNo, amount, status, reason }    有退款单才有
visitCode                                    就诊码（= registrationNo）
signTime
```

**约束：**

- `idNoMasked` 脱敏展示（如 `3701**********41`）；完整证件号不进任何响应（仅 B7 / B8 传输）。
- `visitCode` 仅 `status ∈ {BOOKED, SIGNED, COMPLETED}` 时返回；`WAIT_PAY` / `CLOSED` / 已退号 / `NOSHOW` 不返回。

### 4.4 待支付取消（B4）

```http
POST /appt/patient/payment/{paymentNo}/cancel
```

**身份：** 登录。

**状态：** Payment `WAIT_PAY → CLOSED`；Registration `WAIT_PAY → CLOSED`；Slot `TAKEN → AVAILABLE`（`time_point` 已过则 `→ EXPIRED`）。

**前置条件：** 支付单属于当前用户且 `status = WAIT_PAY`（否则 `PAYMENT_CLOSED` / `REG_STATE_INVALID`）。

**业务行为：** 与超时关单同一事务形状（技术方案 §3.4）：三步 CAS 均以 `WAIT_PAY` 为条件（重复触发第二次全部影响 0 行）+ 台账 + afterCommit 余量 +1 + 关单站内信。**不涉及退款**（未发生支付）。

### 4.5 退号（B5）

```http
POST /appt/patient/registration/{id}/cancel
```

**身份：** 登录。

**状态：** Registration `BOOKED → CANCELED_ACTIVE`（`cancel_type = ACTIVE`）；Slot `TAKEN → AVAILABLE`（已过 `time_point` → `EXPIRED`）；已支付 → 新建 Refund（`WAIT_REFUND`）+ `settleStatus = WAIT_REFUND`。

**前置条件：**

- 属于当前用户
- `status = BOOKED`（否则 `REG_STATE_INVALID`）
- `now < 就诊前一日 23:00`（否则 `REFUND_DEADLINE_PASSED`，PRD §6.7）

**业务行为：** 退号事务 → 已支付则创建退款单（`refund_no` 唯一 + 状态 CAS 防重退）→ 渠道退款走异步链路（§5）→ 回调入账后 `settleStatus = REFUNDED` + 站内信。

**约束：**

- 主动退号**计入**黑名单统计口径（半年内退号 + 爽约合计，PRD §6.9）；停诊被动退号不计入。
- 爽约由扫描判定（PRD §6.8），不经过本端点。

### 4.6 就诊人列表（B6）

```http
GET /appt/patient/patient/list
```

**身份：** 登录。

**返回至少：** `patientId / name / idType / idNoMasked / isDefault`，按 `is_default` 倒序 + 创建时间排序。

**过滤（2026-10-18 补）**：**仅返回 `status = '0'`（正常）的就诊人**，`status = '1'`（停用）的不返回。
后台管理端（F 系列）列表**不加此过滤**——否则停用后从后台也看不见，无法恢复。

### 4.7 新增就诊人（B7）

```http
POST /appt/patient/patient
```

**身份：** 登录。

**请求：**

```json
{
  "name": "林晚晴",
  "idType": "IDCARD",
  "idNo": "370102199001011234",
  "isDefault": false
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| name | 是 | 就诊人姓名 |
| idType | 是 | `IDCARD` 身份证 / `CARD` 就诊卡 |
| idNo | 是 | 完整证件号（仅本端点与 B8 传输；身份证号全局唯一、就诊卡号院内唯一，PRD §4.2-6） |
| isDefault | 否 | 默认 false；true 则同事务取消其它默认 |

**前置条件：** 当前账号就诊人 < 10（否则 `PATIENT_LIMIT_EXCEEDED`）；证件未被其他账号绑定（本期不做解绑流程，已知边界见 PRD §14.3）。

**约束：** `idNo` 禁止进日志（红线 15）；存储按技术方案 M11 预留加密位。

### 4.8 修改 / 删除 / 设默认就诊人（B8–B10）——P1 占位

`PUT /appt/patient/patient/{id}`、`DELETE /appt/patient/patient/{id}`、`PUT /appt/patient/patient/{id}/default`：登录；数据范围按 `user_id`；删除约束（名下有挂号单的就诊人禁止删除）与字段语义在 S3 前端联调前补条目。

---

## 5. 支付组（C1–C5）

> 组首说明：交易链路——本项目最大亮点。渠道回调端点（C1 / C5）虽在 `/appt/public/` 前缀下（§1.1 已说明路径层与领域节解耦），语义归本组。
> **mock 与真实渠道共用同一 `PaymentCallbackDispatcher`**（验签 → 落库 → ack → 异步入账），差异只在 `PaymentChannel` 适配器；真实渠道签约（需企业主体，PRD D7）后业务链路不改。

### 5.0 交易链路时序（文字版）

```text
患者确认支付（C2 mock 按钮 / 真实渠道收银台）
    ↓
渠道侧产生交易，异步发送回调（C1）
    ↓
C1 入口：HMAC-SHA256 验签
   失败 → 拒绝 + 落 appt_payment_callback(sign_flag=失败) + 告警，不入账
    ↓ 通过
落 appt_payment_callback（append-only；UNIQUE(payment_no, trade_no, notify_id) 去重）
    ↓
立即 ack 返回渠道          ← 真异步：渠道不因我们慢而重发
    ↓
异步入账（线程池）：
   ① 查单确认：向渠道查询核对金额与状态，与回调体双事实一致才继续；
      不一致 → 记异常 + 告警，不入账
   ② 幂等入账：UPDATE payment SET status=PAID, trade_no, pay_time
      WHERE payment_no=? AND status=WAIT_PAY
      影响 0 行分流：
        已是 PAID   = 重复回调，ack 结束
        已是 CLOSED = 钱到了号没了 → 记异常 + 自动全额退 + 告警（见 5.1 约束）
   ③ Registration WAIT_PAY → BOOKED
   ④ 发「支付成功」站内信
    ↓ 处理失败
退避重试 3 次（1s / 5s / 15s）→ 标记 process_status=失败
    ↓
巡检任务主动查单兜底（见 5.3）
```

### 5.1 渠道回调（C1）

```http
POST /appt/public/payment/callback/{channel}
```

**身份：** 公开（**验签即身份**——无有效签名一律拒绝；mock 与真实同构 HMAC-SHA256 + 按渠道配置的密钥）。

**路径参数：**

| 参数 | 必填 | 说明 |
|---|---|---|
| channel | 是 | `mock`（本期唯一实现）；真实渠道按适配器接入，链路不变 |

**请求：**（渠道协议体，mock 与真实同构）

```json
{
  "paymentNo": "P20261017093000123",
  "tradeNo": "MOCK20261017093000999",
  "notifyId": "N-8f3a2c",
  "amount": 22.00,
  "result": "SUCCESS",
  "payTime": "2026-10-17 09:30:12",
  "sign": "hmac-sha256-hex"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| paymentNo | 是 | 支付单号（幂等键之一） |
| tradeNo | 是 | 渠道侧交易号（幂等键之一） |
| notifyId | 是 | 回调通知 ID（幂等键之一） |
| amount | 是 | 渠道确认金额；入账前与 `registration.fee` 快照核对，不一致 → 记异常 + 告警 |
| result | 是 | `SUCCESS` / `FAIL` |
| payTime | 是 | 渠道支付时间 |
| sign | 是 | HMAC-SHA256 十六进制；验签失败 → `CALLBACK_SIGN_INVALID`：拒绝 + 落库 + 告警，**不入账** |

**状态：** Payment `WAIT_PAY → PAID`；Registration `WAIT_PAY → BOOKED`。

**业务行为：** 见 5.0 时序图。

**约束：**

- **落库去重后立即 ack**：重复 notify（同 payment_no + trade_no + notify_id）直接 ack，不进入账。
- **竞态分支（钱到了号没了）**：入账 CAS 发现 payment 已是 `CLOSED`（关单先于回调到达）→ 记异常 + **自动全额退 + 告警**，不是返回成功就算了（红线 7；对账 R3 兜底复查）。
- 集成测试③按本契约造数据：同一支付单回调 3 次，仅 1 次入账（PRD §12）。

**签名与幂等口径（2026-10-20 补，S4 实现）**

- 待签串：支付 `paymentNo|tradeNo|notifyId|amount|result|payTime`；退款 `refundNo|paymentNo|amount|result|refundTime`；金额为两位小数字符串。
- 签名：`HMAC-SHA256(待签串, payment.mock.sign-secret)` 的小写十六进制；验签失败 → `CALLBACK_SIGN_INVALID`（`code=400` + `data.bizCode`），落库 `sign_flag='1'`，不入账。
- 应答体：`{accepted, duplicate, processStatus}`；`duplicate=true` 表示命中三列唯一键，直接 ack、不重复入账。
- 回调记录状态：`PENDING`（已受理待入账）→ `SUCCESS`（入账完成）/ `IGNORED`（重复或渠道明确失败）/ `FAILED`（重试耗尽，等巡检查单兜底）。
- 入账前置：回调金额必须等于 `registration.fee` 快照；渠道查单有记录时状态与金额须与回调体一致（双事实），渠道无记录时按回调体处理并记告警。

### 5.2 模拟支付（C2）

```http
POST /appt/patient/payment/{paymentNo}/mock-pay
```

**身份：** 登录。

**请求：**

```json
{
  "result": "SUCCESS"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| result | 是 | `SUCCESS` / `FAIL` / `TIMEOUT`，对应支付页三个手动按钮（PRD §6.6） |

**业务行为：**（三分支均经 mock 渠道适配器 → dispatcher，与 C1 同一入口）

```text
SUCCESS → mock 渠道登记交易（trade_no），按 C1 协议体合成回调 → dispatcher 全链路。
          本端点只返回「已受理」，结果由 C3 轮询呈现——保真演示真异步。
FAIL    → 落失败回调记录（验签通过、result=FAIL）；Payment 保持 WAIT_PAY 可重试；
          Registration 无流转（支付单状态机无「失败」态，PRD §7.3）。
TIMEOUT → 直接调用关单服务（技术方案 §3.4 事务形状）：
          Payment WAIT_PAY→CLOSED；Registration WAIT_PAY→CLOSED；Slot 回补。
          演示压缩路径；真实超时由 30 秒巡检任务驱动，不经本端点。
```

**前置条件：** 支付单属于当前用户且 `status = WAIT_PAY`（否则 `PAYMENT_CLOSED`）。

**约束：** 仅 `payment.channel = mock` 且 `appt.mock-pay.enabled = true` 时可用（非演示环境关闭）。

**返回至少：**

```text
paymentNo
accepted     是否已受理（SUCCESS 分支的 true 表示「已受理」，非「已支付」）
status       支付单当前状态
```

### 5.3 支付状态查询（C3）

```http
GET /appt/patient/payment/{paymentNo}
```

**身份：** 登录。

**业务行为：** 返回支付单当前状态；**可触发一次主动查单**——服务端按节流控制：同一 `payment_no` 距上次查单 ≥ 5 秒才向渠道查询（Redis 记录 last-query 时间），否则直接返回本地状态。巡检任务（30 秒一轮）对近过期单（`expire_time ∈ [now, now+2min]`）的批量主动查单属任务侧，不占本端点节流额度（技术方案 §3.4）。

**返回至少：**

```text
paymentNo
amount
status
expireTime    支付截止（yyyy-MM-dd HH:mm:ss）
payTime       已支付才有
tradeNo       已支付才有
```

### 5.4 退款单查询（C4）——P1 占位

患者视角退款单列表 `GET /appt/patient/refund/list`：退款信息当前已内嵌于 B3 预约详情的 `refund` 字段；独立列表端点等真实需求出现再补条目。

### 5.5 退款回调（C5）

```http
POST /appt/public/refund/callback/{channel}
```

**身份：** 公开（验签即身份，同 C1）。

**请求：**

```json
{
  "refundNo": "R20261017103000456",
  "paymentNo": "P20261017093000123",
  "amount": 22.00,
  "result": "SUCCESS",
  "refundTime": "2026-10-17 10:30:05",
  "sign": "hmac-sha256-hex"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| refundNo | 是 | 退款单号（幂等键） |
| paymentNo | 是 | 关联支付单 |
| amount | 是 | 退款金额；挂号场景一律全额（PRD §6.6） |
| result | 是 | `SUCCESS` / `FAIL` |
| refundTime | 是 | 渠道退款时间 |
| sign | 是 | 同 C1 验签规则 |

**状态：** Refund `WAIT_REFUND → REFUNDED`（退款回调 `result=SUCCESS`）或 `WAIT_REFUND → FAILED`（退避重试耗尽）；Payment `PAID → REFUNDED`；Registration `settleStatus → REFUNDED`（仅成功分支，失败态不回写结算态）。

**业务行为：** 与 C1 同构：验签 → 落库 → ack → 异步（查单确认 → `UPDATE refund SET status=REFUNDED WHERE refund_no=? AND status=WAIT_REFUND` → 回写支付单与挂号单结算态 → 站内信）。

**约束：**

- 失败（`result=FAIL`）→ 退款单按退避重试（次数可配），仍失败则 Refund 置 `FAILED` 并进后台人工队列 + 告警（PRD §6.6；对账 R5 复查）。`FAILED` 为**终态**：如确需再退，由人工触发另建退款单（`refund_no` 重新取号），不在原单上回滚复用——保证退款幂等链可追溯。
- 重复回调：`refund_no` + 状态 CAS 天然幂等，第二次影响 0 行。

**实现口径（2026-10-20 补，S4 实现）**

- `refund_no` 前缀用 **`F`**（`F + yyyyMMdd + 6 位`，以 `database-design.md` 的 DDL 注释为准；上文示例的 `R` 与挂号单号冲突，已作废）。
- 本期不新增退款回调表：复用 `appt_payment_callback`，字段映射为「`payment_no` = 关联支付单号、`trade_no` = 退款单号、`notify_id` = `REFUND-{refundNo}`」，保证三列唯一键对退款回调同样生效。
- 「钱到了号没了」自动退款：payment 保持 `CLOSED`（不回写 `PAID`），退款成功后仅回写 `registration.settle_status=REFUNDED` 与 refund 状态。

---

## 6. 患者辅助组 `/appt/patient/**`（D1–D6）——v0.1 简条

| 端点 | 身份 | 说明 |
|---|---|---|
| GET `/appt/patient/favorite/list` | 登录 | 我的医生（收藏列表），返回 staffId + 基本信息 + 收藏时间 |
| POST `/appt/patient/favorite/{staffId}` | 登录 | 收藏；重复收藏幂等（`UNIQUE(user_id, staff_id)`） |
| DELETE `/appt/patient/favorite/{staffId}` | 登录 | 取消收藏 |
| GET `/appt/patient/notice/list` | 登录 | 消息列表，分页，按时间倒序 |
| GET `/appt/patient/notice/unread-count` | 登录 | 未读数（tab 红点） |
| PUT `/appt/patient/notice/{id}/read` | 登录 | 标记已读；仅本人消息 |

> 通知场景七种（PRD §6.12）：挂号成功（待支付）/ 支付成功 / 超时关单 / 退号成功 / 停诊取消 / 爽约记录 / 黑名单生效。`notice.type` 线值在 S6 补条目时定义。字段级条目在 S5 / S6 前端联调前补。

---

## 7. 分诊组 `/appt/triage/**`（E1–E5）

> 组首说明：登录 + `triage` 角色（`@SaCheckRole`）。数据范围 = 账号在岗院区（本期简化，PRD §14.3）；**请求不带 campusId，服务端从账号解析**（红线 10）。

### 7.1 扫码签到（E1）

```http
POST /appt/triage/sign
```

**身份：** triage。

**请求：**

```json
{
  "registrationNo": "G20261017093000123"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| registrationNo | 是 | 二维码内容 = `registration_no`（PRD §6.8） |

**状态：** Registration `BOOKED → SIGNED`（`sign_type = 扫码`）。

**前置条件：**

- `now ≥ 就诊日 00:00`（否则 `SIGN_TOO_EARLY`，PRD §6.8）
- `now < time_point + 30min` 且 `status = BOOKED`（否则 `SIGN_WINDOW_CLOSED`）

**业务行为：** `UPDATE registration SET status=SIGNED, sign_time=now WHERE registration_no=? AND status=BOOKED`；影响 0 行 → `SIGN_WINDOW_CLOSED`（与爽约扫描竞争同一 CAS，**先到先得**，技术方案 §3.3）。

**返回至少：**

```text
registrationId / registrationNo
patientName / staffName
visitDate / period / timePoint
signTime
```

### 7.2 手动补签（E2）

```http
POST /appt/triage/sign/manual
```

**身份：** triage。

**请求：** 同 E1（`{ registrationNo }` 或 `{ registrationId }`）。

**状态：** 同 E1（`BOOKED → SIGNED`，`sign_type = 手动`）。

**约束：**

- 前置条件同 E1：仅当日、未过爽约判定点。**已判 `NOSHOW` 的单不可补签**——爽约判定权威，扫描先到先得；补签只覆盖「患者已到院但扫码失败」。
- 与 E1 共用同一状态边与 CAS，仅 `sign_type` 区分，便于后台签到记录统计。

### 7.3 当日签到列表（E3）——P1 占位

`GET /appt/triage/sign/list?date=`：本人在岗院区当日挂号单（含签到态与签到方式）。字段条目在 S6 分诊端联调前补。

### 7.4 加号登记（E4）

```http
POST /appt/triage/extra-slot
```

**身份：** triage。

**请求：**

```json
{
  "scheduleId": 5001,
  "period": "AM"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| scheduleId | 是 | 目标排班 |
| period | 否 | 午别；缺省取该排班当前会话中的午别（与模板一致） |

**状态：** 新建 Slot（`source = 加号`，`status = AVAILABLE`）。

**前置条件：** 排班存在且未停诊（否则 `EXTRA_SLOT_INVALID`）；该午别号源已满（满才加号，PRD §6.11）。

**业务行为：** 取该午别 `MAX(time_point)` + 模板步长 → INSERT slot（`UNIQUE(schedule_id, time_point)` 防重；并发加号撞键 → 重算重试）。

**返回至少：** `slotId / scheduleId / timePoint / fee / source`。

**约束：** 加号 Slot 与普通 Slot 走同一预约三道防线（§4.1），无第二套逻辑。

### 7.5 停诊上报（E5）

```http
POST /appt/triage/suspend
```

**身份：** triage。

**请求：**

```json
{
  "staffId": 301,
  "scopeType": "STAFF_DATE",
  "scopeValue": "2026-10-22",
  "reason": "医生临时会议"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| staffId | 是 | 停诊对象医务人员 |
| scopeType | 是 | `SCHEDULE` 单个午别 / `STAFF_DATE` 某医生某日 / `CAMPUS_DATE` 院区某日 |
| scopeValue | 是 | SCHEDULE → scheduleId；STAFF_DATE → visitDate；CAMPUS_DATE → `campusId:date` |
| reason | 是 | 停诊原因（进站内信通知患者） |

**业务行为：** INSERT `appt_suspend_record`（`batch_no` 预生成，`operator = 当前账号`，`status = 待处理`）→ 返回批号。**本端点只登记、不执行退号**——执行是管理端 F2 的职责（两段式）。日期区间停诊按日拆分为 N 条 `STAFF_DATE` 登记，共用同一 `batch_no` 幂等归并（D-S1-5）。

**约束：** 同一范围存在未处理的登记时返回已登记批号，不重复建单。

---

## 8. 管理组 `/appt/admin/**`（F1–F30）

### 8.1 管理端通用约定 + RuoYi 生成器约定（P0）

- 路径模板：`/appt/admin/{entity}/...`；权限命名空间 `appt:{entity}:{list|query|add|edit|remove}`（`@SaCheckPermission`）。
- 基础数据六实体（院区 `campus` / 门诊类型 `clinicType` / 科室 `dept` / 医务人员 `staff` / 收费标准 `feeStandard` / 时段模板 `slotTemplate`）的标准 CRUD 由 RuoYi 代码生成器产出，**契约不逐个写字段**（字段级归 `database-design.md` 与生成器表单配置）。
- 以下七项特有约束生成器不会产生，必须遵守：

| # | 约束 |
|---|---|
| 1 | **科室树**：树形端点（嵌套 `children`），非标准分页 CRUD；增改父节点时防成环 |
| 2 | **医务人员**：一行 = 一个出诊身份（`campus_id` 单值）；跨院区出诊为已知边界（PRD §14.3） |
| 3 | **收费标准**：`UNIQUE(title, clinic_type)`；增改撞键返回明确错误，不静默覆盖 |
| 4 | **编辑不追溯**：时段模板与收费标准的增改不影响已生成 Slot 的 `fee` 与 `time_point`（金额快照原则，PRD §4.2-5） |
| 5 | **删除引用约束**：院区下有医务人员 / 科室有下级或关联人员 / 模板已生成排班 → 拒绝删除并提示 |
| 6 | **路径命名与 public 层对齐**：public 用 `dept / staff / slot`，管理端生成器默认产出 `department / medicalStaff` 等——契约统一前者，前后端一套心智 |
| 7 | **号源删除约束**：无有效挂号的 Slot 允许单删；有有效挂号 → 拒绝，走停诊流程（PRD §6.2） |

### 8.2 排班生成（F1）

```http
POST /appt/admin/schedule/generate
```

**身份：** `appt:schedule:add`。

**请求：**

```json
{
  "staffId": 301,
  "startDate": "2026-10-24",
  "endDate": "2026-10-30"
}
```

**业务行为：** 按该人员的 `SlotTemplate`（午别 × 起止 × 步长 × 门诊类型）为范围内每个有模板的日期批量生成 Schedule + Slot（直接 `AVAILABLE`）；`UNIQUE(staff_id, visit_date, period)` + 批号保证重跑不重复生成。放号策略 `rolling` 下新生成Slot 直接可约；`immediate` 模式同效果（PRD §6.1）。

**多模板仲裁：** 同一人员同一午别存在多个模板（`uk(staff_id, period, clinic_type)` 允许门诊类型不同）时，取 `clinic_type = medical_staff.clinic_type` 的那条，无匹配则取 **id 最小**者；落选模板计入 `arbitratedCount`（D-S1-7「一行 = 一个出诊身份」）。

**窗口：** 生成**不受 D1 可约窗口限制**（任意日期区间，单次 ≤ 31 天），生成的号源一律 `AVAILABLE`；`[今日+1, 今日+N]` 的窗口过滤由查询侧负责（S5）。

**批号：** `G + yyyyMMdd + 6 位当日序列`（如 `G20261019000001`，长度 15）；同一批号写入 `slot_ledger.batch_no`，供台账倒查。

**返回：** `batchNo / scheduleCount / slotCount / skippedCount / arbitratedCount / elapsedMs`。`skippedCount` = 计划内已存在的号源数（同参数重跑时为计划总量，新增为 0）；`scheduleCount` / `slotCount` 只统计**本次新增**。

**预览：** `GET /appt/admin/schedule/preview?staffId=&startDate=&endDate=` —— 与生成共用同一套展开规则（同一 `plan` 函数），**不落库、不占批号**。返回 `staffId / staffName / startDate / endDate / plannedSchedule / plannedSlot / existingSchedule / existingSlot / newSchedule / newSlot / arbitratedCount / items[]`；`items` 逐 (日期 × 午别)：`visitDate / period / clinicType / fee（字符串） / startTime / endTime（HH:mm） / plannedSlot / existingSlot / newSlot`。

### 8.3 停诊处理（F2）

```http
POST /appt/admin/suspend/handle
```

**身份：** `appt:suspend:handle`。

**请求：**

```json
{
  "suspendId": 12
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| suspendId | 是 | E5 停诊上报的登记 ID。**入参是登记行 ID，不是批号**——服务端按此 ID 取登记行，取其 `batch_no` 作为幂等锚点，并把该行 `status` 由 `PENDING` 置 `HANDLED`；重复提交命中 `HANDLED` 直接返回成功不重做（PRD §6.10 幂等） |

**状态：** Schedule `正常 → 已停诊`；范围内 `WAIT_PAY / BOOKED` 的 Registration → `CANCELED_PASSIVE`（`cancel_type = PASSIVE`，**不计爽约**）；未预约 Slot → `SUSPENDED`；已支付 → 批量新建 Refund（`WAIT_REFUND`）。

**业务行为：** 分批事务（≤100/批，红线 12）+ 批号 CAS 守卫；**重复执行第二次全部影响 0 行**（不重复退号 / 退款 / 通知，PRD §6.10）；全部受影响患者发站内信；退款走 §5.5 异步链路。

**约束：** **已签到的单不参与批量退号**（患者已在院，现场人工协调；本期简化边界，PRD §6.10 / §14.3）。

### 8.4 排班与号源查看（F5 / F6 / F7）

| 端点 | 身份 | 说明 |
|---|---|---|
| GET `/appt/admin/schedule/list` | `appt:schedule:list` | 排班列表，分页；筛选 staffId / date / period / status |
| GET `/appt/admin/suspend/list` | `appt:suspend:list` | 停诊登记记录，分页；status = 待处理 / 已处理 |
| GET `/appt/admin/slot/list` | `appt:slot:list` | 号源查看，分页；筛选 scheduleId / status / source；含 registration_id 关联 |
| DELETE `/appt/admin/slot/{id}` | `appt:slot:remove` | P1：仅无有效挂号的 Slot 可删（§8.1 约束 7）；编号归 F7 |

### 8.5 其余管理端点——P1 占位

- **F3 对账触发** `POST /appt/admin/reconcile/run`：`appt:reconcile:run`；同步执行、60 秒预算，返回 R1–R7 各查异常数摘要；明细走 F22 结果列表。若实测超时改异步，契约预留说明。
- **F4 数据看板** `GET /appt/admin/dashboard`：`appt:dashboard:query`；今日放号 / 已预约 / 已签到 / 爽约率 / 退号率 / 支付成功率 / 科室 TOP5（PRD §10.2）。
- **F8–F22 编号分配**（字段级条目均在 S5–S7 联调前补；F16 / F22 编号已被 §11 待确认 #8 与 F3 条目引用，**锁定不变**；F15 / F21 / F23–F24 预留）：
  - F8 挂号单列表 / F9 挂号单详情（数据范围按 `user_id` 服务端强过滤，红线 10）
  - F10 手动退号（复用 B5 服务端逻辑）
  - F11 签到记录 / F12 加号记录
  - F13 支付单列表 / F14 退款单列表
  - F16 渠道配置（落业务表还是 `sys_config` 见 §11 待确认 #8）
  - F17 黑名单管理 / F18 限购规则 / F19 就诊人管理 / F20 任务日志
  - F22 对账结果列表（F3 明细入口）
- **F25–F30** 六实体基础数据 CRUD：走 §8.1 生成器约定。

---

## 9. API 与业务状态的边界

### 9.1 四张状态机 × 触发源矩阵

| 状态边 | API 端点 | 定时任务 | 对账修复 |
|---|---|---|---|
| Slot `AVAILABLE→TAKEN` | B1 提交挂号 | — | R2 号源未占用 |
| Slot `TAKEN→AVAILABLE` | B4 取消 / B5 退号 / F2 停诊处理（被动退号回池） | 关单巡检（30s） | R1 幽灵占号 |
| Slot `AVAILABLE→EXPIRED` | — | 爽约/过期扫描（5min） | — |
| Slot `TAKEN→EXPIRED` | B4 取消 / B5 退号（回池时 `time_point` 已过，红线 9） | 关单巡检（30s）回补时同上判定 | — |
| Slot `AVAILABLE→SUSPENDED` | F2 停诊处理 | — | R6 停诊漏处理 |
| Slot 新建 `AVAILABLE` | F1 排班生成 / E4 加号 | 放号任务（每日 08:00） | — |
| Reg `WAIT_PAY→BOOKED` | C1 回调入账 | 巡检主动查单 | R4 告警（给了号没收钱） |
| Reg `WAIT_PAY→CLOSED` | B4 / C2 TIMEOUT | 关单巡检 | — |
| Reg `BOOKED→SIGNED` | E1 签到 / E2 补签 | — | — |
| Reg `BOOKED→CANCELED_ACTIVE` | B5 退号 | — | — |
| Reg `BOOKED→CANCELED_PASSIVE` | F2 停诊处理 | — | R6 |
| Reg `BOOKED→NOSHOW` | — | 爽约扫描（5min） | — |
| Reg `SIGNED→COMPLETED` | — | 置完成（每日 23:30） | — |
| Payment `WAIT_PAY→PAID` | C1 回调 | 巡检主动查单 | — |
| Payment `WAIT_PAY→CLOSED` | B4 / C2 TIMEOUT | 关单巡检 | — |
| Payment `PAID→REFUNDED` | C5 退款回调 | — | R3 应退未退 |
| Refund `WAIT_REFUND→REFUNDED` | C5 退款回调（`result=SUCCESS`） | — | R3 / R5 |
| Refund `WAIT_REFUND→FAILED` | 退款重试耗尽（退避次数用尽） | — | R5 重试 → 仍失败进人工队列 |

### 9.2 无端点的状态流转与可观测面

放号（每日 08:00）/ 关单巡检（30s）/ 爽约与过期扫描（5min）/ 置完成（23:30）/ 日终对账（03:00）没有入站 API；契约只覆盖其可观测端点：

- `GET /appt/admin/job-log/list`（任务日志：批号 / 起止 / 影响行数 / 结果 / `job.status` 含 `SKIPPED`）
- `POST /appt/admin/job-log/{id}/rerun`（P1：手动重跑）
- `GET /appt/admin/reconcile/results`（P1：对账结果列表）

### 9.3 写操作并发与幂等语义总表

| 机制 | 覆盖端点 | 语义 |
|---|---|---|
| 三道防线（Redis 占位 → DB CAS → 联合唯一索引） | B1 | 同时间点仅 1 笔成交；Redis 可整体摘除 |
| 账号行 `FOR UPDATE` | B1 | 限购三条精确判定（竞争只发生在同一用户自身） |
| `Idempotency-Key`（仅 B1 强制） | B1 | 双击不造两笔待支付单 |
| CAS 条件即幂等 | B4 / B5 / C1 / C2 / E1 / E2 / F2 | 重复触发第二次影响 0 行 |
| 批号 + CAS 守卫 | F2 停诊 | 不重复退号 / 退款 / 通知 |
| `UNIQUE` + 状态 CAS | C1 / C5 回调 | 重复回调只入账一次 |

---

## 10. P0 API 一览表

权限列约定：

- `匿名`：公开接口，需加入 `application.yml` 的 `security.excludes` 白名单
- `登录`：`@SaCheckLogin`，数据归属服务端按当前用户强过滤
- `triage`：`@SaCheckRole("triage")`
- `appt:xxx:yyy`：`@SaCheckPermission`

| 场景 | Method | Endpoint | 身份/权限 | 绑定状态流转 |
|---|---|---|---|---|
| 院区列表 | GET | `/appt/public/campus/list` | 匿名 | — |
| 科室树 | GET | `/appt/public/dept/tree` | 匿名 | — |
| 医生列表 | GET | `/appt/public/staff/list` | 匿名 | — |
| 医生主页 | GET | `/appt/public/staff/{id}` | 匿名 | — |
| 日期栏 | GET | `/appt/public/schedule/dates` | 匿名 | — |
| 出诊医生 + 午别余量 | GET | `/appt/public/schedule/staffs` | 匿名 | — |
| 可约时间点 | GET | `/appt/public/slot/list` | 匿名 | — |
| 提交挂号 | POST | `/appt/patient/registration` | 登录 | Slot `AVAILABLE→TAKEN`；Reg / Payment 新建 `WAIT_PAY` |
| 我的预约 | GET | `/appt/patient/registration/list` | 登录 | — |
| 预约详情 | GET | `/appt/patient/registration/{id}` | 登录 | — |
| 待支付取消 | POST | `/appt/patient/payment/{paymentNo}/cancel` | 登录 | Payment / Reg `→CLOSED`；Slot 回补 |
| 退号 | POST | `/appt/patient/registration/{id}/cancel` | 登录 | Reg `→CANCELED_ACTIVE`；Slot 回池；退款单新建 |
| 就诊人列表 | GET | `/appt/patient/patient/list` | 登录 | — |
| 新增就诊人 | POST | `/appt/patient/patient` | 登录 | — |
| 渠道回调 | POST | `/appt/public/payment/callback/{channel}` | 匿名（验签） | Payment `→PAID`；Reg `→BOOKED` |
| 模拟支付 | POST | `/appt/patient/payment/{paymentNo}/mock-pay` | 登录 | 同 C1 / FAIL 无流转 / TIMEOUT 走关单 |
| 支付状态查询 | GET | `/appt/patient/payment/{paymentNo}` | 登录 | — |
| 退款回调 | POST | `/appt/public/refund/callback/{channel}` | 匿名（验签） | Refund / Payment `→REFUNDED` |
| 扫码签到 | POST | `/appt/triage/sign` | triage | Reg `BOOKED→SIGNED` |
| 手动补签 | POST | `/appt/triage/sign/manual` | triage | 同 E1（sign_type=手动） |
| 加号登记 | POST | `/appt/triage/extra-slot` | triage | Slot 新建 `AVAILABLE`（加号） |
| 停诊上报 | POST | `/appt/triage/suspend` | triage | 新建停诊登记（批号） |
| 排班生成 | POST | `/appt/admin/schedule/generate` | `appt:schedule:add` | Schedule / Slot 新建 |
| 停诊处理 | POST | `/appt/admin/suspend/handle` | `appt:suspend:handle` | Schedule `→已停诊`；Reg `→CANCELED_PASSIVE`；Slot `→SUSPENDED` |
| 排班列表 | GET | `/appt/admin/schedule/list` | `appt:schedule:list` | — |
| 停诊记录 | GET | `/appt/admin/suspend/list` | `appt:suspend:list` | — |
| 号源查看 | GET | `/appt/admin/slot/list` | `appt:slot:list` | — |

**P1 端点（一览表占位，条目待切片联调前补）**：B8–B10 就诊人改删默认、C4 退款查询、D1–D6 收藏与消息、E3 当日签到列表、F3 对账触发、F4 看板、F8–F24 预约/交易/规则/运维管理、F25–F30 六实体生成器 CRUD。

---

## 11. 待实现层确定事项

1. RuoYi 响应包装与异常类的具体类型（`R<T>` 的当前项目用法）。
2. HTTP 层通用码（401 / 403 / 参数校验 / 500）的框架级映射。
3. Sa-Token 登录态获取方式与 token 传递细节（与项目一同款推迟）。
4. OSS 上传接口复用细节（头像占位图落地前的过渡）。
5. SpringDoc 分组配置：新增 `appt` 模块后追加 `packages-to-scan: org.dromara.appt`，否则接口不出现在 API 文档。
6. 渠道密钥管理：mock 演示环境的配置写法；真实渠道的密钥注入方式。
7. E3 / 分诊数据范围的实现在岗院区存储方式（sys_user 扩展字段 or 数据权限）。
8. F16 渠道配置落业务表还是 `sys_config`。
