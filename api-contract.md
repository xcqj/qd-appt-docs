# 号源 QueueDepth · API 契约

> 文档状态：v0.1（2026-10-17 创建；§1–§5 定稿：总体约定 + 公开查询组 + 挂号组 + 支付组；§6–§11 按四次会话计划推进中）
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
- 金额单位为元（CNY），JSON number，两位小数。
- 资源路径用英文单数（`/slot` 不用 `/slots`）；路径参数用 `{id}` 样式。
- 全部数据虚构，不使用真实医院 / 科室 / 医务人员名称（PRD §11 红线）。

### 1.4 契约先行纪律

- 实现与契约冲突时先报告再修订；契约变更记入文档状态行。
- 影响状态机的契约变更，须同步检查 PRD §7 与技术方案 §3 是否有对应修订。

---

## 2. 统一请求响应约定

### 2.1 响应结构

成功 / 失败的响应 envelope 遵循当前 RuoYi-Vue-Plus 项目惯例（`R<T>`）。本文只约定业务字段与语义，不规定包装类型与异常类。

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
| 时间点 `timePoint` | `HH:mm` | `09:51` |
| 完整时间戳 | `yyyy-MM-dd HH:mm:ss` 本地时区 | `2026-10-21 09:51:00` |
| 金额 | JSON number，两位小数 | `22.00` |

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

**状态：** Registration `BOOKED → CANCELED_ACTIVE`（`cancel_type = 主动`）；Slot `TAKEN → AVAILABLE`（已过 `time_point` → `EXPIRED`）；已支付 → 新建 Refund（`WAIT_REFUND`）+ `settleStatus = WAIT_REFUND`。

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

### 4.7 新增就诊人（B7）

```http
POST /appt/patient/patient
```

**身份：** 登录。

**请求：**

```json
{
  "name": "林晚晴",
  "idType": "ID_CARD",
  "idNo": "370102199001011234",
  "isDefault": false
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| name | 是 | 就诊人姓名 |
| idType | 是 | `ID_CARD` 身份证 / `CARD_NO` 就诊卡 |
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

**状态：** Refund `WAIT_REFUND → REFUNDED`；Payment `PAID → REFUNDED`；Registration `settleStatus → REFUNDED`。

**业务行为：** 与 C1 同构：验签 → 落库 → ack → 异步（查单确认 → `UPDATE refund SET status=REFUNDED WHERE refund_no=? AND status=WAIT_REFUND` → 回写支付单与挂号单结算态 → 站内信）。

**约束：**

- 失败（`result=FAIL`）→ 退款单按退避重试（次数可配），仍失败标记失败并进后台人工队列 + 告警（PRD §6.6；对账 R5 复查）。
- 重复回调：`refund_no` + 状态 CAS 天然幂等，第二次影响 0 行。

---

## 待完成（按四次会话计划推进）

- §6 患者辅助组（会话 4）
- §7 分诊组 `/appt/triage/**`（会话 4）
- §8 管理组 `/appt/admin/**`，含 §8.1 生成器约定节（会话 4）
- §9 API 与业务状态的边界（会话 4）
- §10 P0 API 一览表（会话 4）
- §11 待实现层确定事项（会话 4）
