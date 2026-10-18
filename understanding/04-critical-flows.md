# 04 · 关键流程时序图

> 依据：api-contract.md §4–§5 / §7（端点契约）· 技术方案 §3.1 / §3.3 / §3.4 / §3.5（事务顺序、CAS、巡检）· PRD §6.5 / §6.6 / §6.7 / §6.8。
>
> **实现状态声明（重要）**：`ruoyi-modules/appt` 当前仅有 `.gitkeep` 骨架（**已核实代码**），以下三张图描述的是**契约 + 技术方案规定的设计态行为**，不是已运行代码的实测路径。图中组件只出现项目真实存在或明确选型的：MySQL / Redis（已存在）、Spring Boot 框架与 Sa-Token（已存在）、uni-app / plus-ui（uni-app 仓待建）、mock 渠道 / snail-job / `@Async` 线程池（设计态）。**不出现 MQ / ES**（红线 16）。

## 1. 创建预约（B1，并发重点）

```mermaid
sequenceDiagram
    autonumber
    participant C as 客户端（uni-app 患者端，仓待建）
    participant API as RegistrationController<br>/appt/patient/registration
    participant SVC as RegistrationService.book()
    participant RDS as Redis（StringRedisTemplate）
    participant DB as MySQL（appt 库）
    participant NT as NoticeService

    C->>API: POST，请求头 Idempotency-Key: UUID
    API->>SVC: 接参校验 + 预约窗口 [今日+1, 今日+7] + 黑名单初查
    SVC->>RDS: SET appt:slot:hold:{slotId} NX EX 15min（value = registrationNo）
    alt ① 占位失败 → 快速失败，不打 DB
        RDS-->>API: 0（key 已存在）
        API-->>C: SLOT_GONE「该时间点已被预约」
    else ① 占位成功
        SVC->>DB: BEGIN
        SVC->>DB: SELECT sys_user WHERE user_id = 当前用户 FOR UPDATE（账号行锁：串行化同一用户的并发挂号，使「同时持有 ≤3」计数精确，M3/红线 14）
        SVC->>DB: 锁内精查：黑名单 / 持有数(WAIT_PAY+BOOKED+SIGNED) ≥3 / slot=AVAILABLE / schedule 未停诊
        alt 精查不通过
            DB-->>SVC: BLACKLISTED / LIMIT_HOLD_MAX / OUT_OF_WINDOW / SCHEDULE_SUSPENDED
            SVC->>DB: ROLLBACK
            SVC->>RDS: Lua 比对 value 后删占位 key（防误删新占用者）
        else 精查通过
            SVC->>DB: INSERT registration（registration_no 预生成，status=WAIT_PAY，active_flag=1，fee=slot.fee 快照）
            alt 撞 UNIQUE(slot_id, active_flag) → 防线③
                DB-->>SVC: SLOT_GONE
            else 撞限购联合唯一
                DB-->>SVC: LIMIT_DEPT_DAY / LIMIT_TIME_CONFLICT
            else 正常
                SVC->>DB: UPDATE slot SET status=TAKEN, registration_id=? WHERE id=? AND status=AVAILABLE
                alt ② 影响 0 行 → 防线②失败
                    DB-->>SVC: SLOT_GONE，ROLLBACK + 删占位 key
                else ② 成功
                    SVC->>DB: INSERT payment（payment_no，amount=registration.fee，expire_time=now+15min，status=WAIT_PAY）
                    SVC->>DB: COMMIT
                end
            end
        end
    end
    SVC->>RDS: afterCommit：余量缓存 DECR（Lua EXISTS 守卫，无键不创建）
    SVC->>NT: 站内信「挂号成功待支付」
    SVC-->>C: registrationNo / paymentNo / amount / expireTime / staffName / visitDate / timePoint
    Note over C,API: 幂等键命中 → 返回首次受理结果并附 DUPLICATE_SUBMIT（非失败语义，前端直接渲染）
    Note over SVC,RDS: Redis 不可用 → 跳过①，降级纯 DB CAS，正确性不降（PRD §9.7）
```

**图说明**：系统并发正确性（G2：同一时间点只成交一人）的完整落地。回答「一笔挂号在哪些防线被拦、事务里做什么、失败怎么补偿」。
**涉及的业务规则**：三道防线顺序不可省——Redis 占位（优化层，可摘除）→ DB 行级 CAS（真相层）→ 唯一索引（兜底层）（红线 3）；限购三条 + 黑名单前置校验、服务端不信任前端（PRD §6.5、红线 10）；金额只认 `slot.fee` 快照，请求体携带金额一律忽略（契约 §4.1）；一个 Slot = 一个号（红线 2）。
**实现状态**：**设计态**（契约 §4.1 + 技术方案 §3.1 规定的事务顺序）；验收口径：50 并发争抢同一时间点恰好 1 笔成功（PRD §9.1，集成测试①绑 S3）。

## 2. 取消 / 退号（B5，含退款异步链路；「改约」= 本流程 + 重新挂号）

```mermaid
sequenceDiagram
    autonumber
    participant C as 客户端（患者端）
    participant API as RegistrationController<br>/appt/patient/registration/{id}/cancel
    participant SS as RegistrationStateService（状态单柱）
    participant DB as MySQL（appt 库）
    participant RDS as Redis（余量缓存 / 占位 key）
    participant PS as RefundService
    participant CH as MockPaymentChannel（渠道适配器，设计态）
    participant CB as PaymentCallbackDispatcher<br>/appt/public/refund/callback/{channel}
    participant NT as NoticeService

    C->>API: POST 退号
    API->>SS: 校验归属（user_id）+ status=BOOKED + now < 就诊前一日 23:00
    alt 前置不满足
        SS-->>C: REFUND_DEADLINE_PASSED（已过退号时限）/ REG_STATE_INVALID
    else 前置满足
        SS->>DB: BEGIN
        SS->>DB: CAS：reg BOOKED → CANCELED_ACTIVE（active_flag=NULL，cancel_type=ACTIVE）
        SS->>DB: CAS：slot TAKEN → AVAILABLE（time_point 已过 → EXPIRED）+ registration_id=NULL
        alt 已支付（payment = PAID）
            SS->>DB: INSERT refund（refund_no 唯一，WAIT_REFUND）+ reg settle_status=WAIT_REFUND
        end
        SS->>DB: COMMIT
        SS->>RDS: afterCommit：余量缓存 +1（Lua 守卫）+ Lua 比对 value 删占位 key
        SS-->>C: 退号成功（已支付则提示退款中）
        opt 已支付且 refund.auto-enabled = true
            SS->>PS: 触发渠道退款（异步）
            PS->>CH: refund(refundNo, amount)
            CH-->>CB: 异步回调（C5）：验签 → 落 appt_payment_callback → ack → 异步入账
            CB->>DB: CAS：refund WAIT_REFUND → REFUNDED（影响 1 行才继续）
            CB->>DB: payment PAID → REFUNDED；reg settle_status → REFUNDED
            CB->>NT: 站内信「退款成功」
        end
        opt 退款失败
            CB->>DB: 退避重试（次数可配）耗尽 → refund = FAILED（终态）
        end
    end
    Note over CB,DB: FAILED 后如需再退：人工另建退款单（refund_no 重新取号），不在原单回滚复用（契约 §5.5）；对账 R5 复查
    Note over C,API: 「改约」本期不做（PRD D4/§13.2）：本流程 + 重新提交挂号（B1）即覆盖
```

**图说明**：售后退款的完整链路（交易链最大亮点之一）。回答「退号先动什么、退款为什么必须异步、重复退款怎么防」。
**涉及的业务规则**：退号时限就诊前一日 23:00（PRD §6.7）；回池时 `time_point` 已过 → 置「已过期」而非「可约」（红线 9）；已支付则自动全额退（PRD §6.6 退款规则：主动退号 ✅）；主动退号**计入**黑名单统计口径（PRD §6.9）；退款回调必须真异步：验签 → 落库 → ack → 异步入账（红线 7）；`refund_no` 唯一 + 状态 CAS 防重退（PRD §6.6）。
**实现状态**：**设计态**（契约 §4.5 / §5.5 + 技术方案 §3.5）；待支付状态的取消（B4）与本流程同事务形状（三步 CAS 以待支付为条件，不涉及退款，契约 §4.4）。

## 3. 扫码核销（E1，与爽约扫描的竞争）

```mermaid
sequenceDiagram
    autonumber
    participant T as 分诊台（uni-app triage 模式，仓待建）
    participant API as SignController<br>/appt/triage/sign
    participant SS as RegistrationStateService（状态单柱）
    participant DB as MySQL（appt 库）
    participant JOB as 爽约/过期扫描任务（snail-job 2.0.2，计划载体）

    T->>API: POST { registrationNo }（二维码内容 = registration_no）
    API->>SS: @SaCheckRole("triage")；数据范围 = 账号在岗院区（Q1）
    SS->>SS: 校验 now ≥ 就诊日 00:00（放宽，避免提前到院无法签到）
    alt 未到可签到时间
        SS-->>T: SIGN_TOO_EARLY
    else 已可签到
        SS->>DB: CAS：UPDATE registration SET status=SIGNED, sign_time=now,<br/>sign_type=SCAN WHERE registration_no=? AND status=BOOKED<br/>AND now < time_point + 30min
        alt 影响 1 行
            SS-->>T: 签到成功（patientName / staffName / visitDate / timePoint / signTime）
        else 影响 0 行
            SS-->>T: SIGN_WINDOW_CLOSED（已过爽约判定点或该单已签到）
        end
    end
    Note over JOB,DB: 竞争同一行：扫描先到 → 签到被拒（单已 NOSHOW）；<br/>签到先到 → 扫描影响 0 行（先到先得，PRD §6.8）
    Note over API,DB: 手动补签 E2 同一条状态边，仅 sign_type=MANUAL；<br/>已判 NOSHOW 的单不可补签（爽约判定权威，契约 §7.2）
    Note over JOB,DB: 爽约扫描：time_point ∈ [now-35min, now-30min) 半开窗口主批<br/>+ time_point <= now-35min 全量兜底（M2，红线 13）
```

**图说明**：履约侧的正确性竞争。回答「签到和系统判爽约谁说了算、为什么必须 CAS 而不是先查后改」。
**涉及的业务规则**：可签到时间就诊日当天 00:00 起（PRD §6.8）；超时判定点 `time_point + 30min`（PRD §6.8、§14.2-5）；签到与扫描竞争同一 CAS，先到先得（PRD §6.8、技术方案 §3.3）；补签只覆盖「患者已到院但扫码失败」。
**实现状态**：**设计态**（契约 §7.1 / §7.2 + 技术方案 §3.3）；E3 当日签到列表端点为 P1 占位（契约 §7.3，Q1/Q15）。

## 4. 其他流程的图在哪

| 流程 | 说明位置 |
|---|---|
| 超时关单与号源回补（30s 巡检两段式） | `03-appointment-state-machine.md` §2（`WAIT_PAY→CLOSED`、`TAKEN→AVAILABLE` 边）+ `05-business-rule-matrix.md` §3 |
| 支付回调幂等（C1，含「钱到了号没了」分支） | `03-appointment-state-machine.md` §4（Payment 状态机注记） |
| 停诊批量处理（F2：退号 + 退款 + 通知，批号幂等） | `03-appointment-state-machine.md` §2（`BOOKED→CANCELED_PASSIVE` 边）+ `05-business-rule-matrix.md` §7 |
| 日终对账七查（R1–R7） | `05-business-rule-matrix.md` §8 + `00-project-map.md` 业务闭环图 |
