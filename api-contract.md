# 号源 QueueDepth · API 契约

> 文档状态：v0.1（2026-10-17 创建；§1–§3 定稿：总体约定 + 公开查询组；§4–§11 按四次会话计划推进中）
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

## 待完成（按四次会话计划推进）

- §4 挂号组 `/appt/patient/**`（会话 2）
- §5 支付组（会话 3）
- §6 患者辅助组（会话 4）
- §7 分诊组 `/appt/triage/**`（会话 4）
- §8 管理组 `/appt/admin/**`，含 §8.1 生成器约定节（会话 4）
- §9 API 与业务状态的边界（会话 4）
- §10 P0 API 一览表（会话 4）
- §11 待实现层确定事项（会话 4）
