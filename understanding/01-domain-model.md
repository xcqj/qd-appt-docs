# 01 · 业务领域模型

> 上游依据：PRD §4.1 概念层级 / §4.2 表清单 · database-design.md §1–§3 · 技术方案 §1.2 · api-contract.md §2.7
> 本文描述**业务实体之间的关系**（领域层）；物理表、索引与约束见 `02-database-erd.md`。

## 1. 领域模型图

```mermaid
erDiagram
    CAMPUS {
        bigint id PK
        string name "院区名（虚构，3 个）"
        string status "char(1) 0正常/1停用"
    }
    CLINIC_TYPE {
        bigint id PK
        string code UK "NORMAL普通/NIGHT夜间延时/EXPERT知名专家"
        string name "中文名"
    }
    DEPARTMENT {
        bigint id PK
        bigint parent_id "父级，根节点为 0"
        string name "科室名"
        int level "1/2/3 三级树，全局统一不挂院区"
    }
    MEDICAL_STAFF {
        bigint id PK
        bigint campus_id "所属院区（单值）"
        bigint dept_id "所属科室（叶子）"
        string title "职称线值 CHIEF/ASSOC_CHIEF/ATTENDING/PHYSICIAN/ASSOC_CHIEF_NURSE"
        string type "DOCTOR医生/NURSE护士"
        string clinic_type "门诊类型码（D-S1-7）"
    }
    SLOT_TEMPLATE {
        bigint id PK
        bigint staff_id "挂在医务人员个人"
        string period "AM上午/PM下午/NIGHT夜间"
        string clinic_type "门诊类型码"
        time start_time "午别起始"
        time end_time "午别结束"
        int step_minutes "步长 4/5~6/6~7/10 分钟"
    }
    FEE_STANDARD {
        bigint id PK
        string title "职称线值"
        string clinic_type "门诊类型码"
        decimal fee "挂号费 decimal(10,2)"
    }
    SCHEDULE {
        bigint id PK
        bigint staff_id
        bigint dept_id
        bigint campus_id "冗余自 staff"
        date visit_date "就诊日期"
        string period "午别"
        string status "NORMAL正常/SUSPENDED已停诊"
    }
    SLOT {
        bigint id PK
        bigint schedule_id
        datetime time_point "完整时刻，显式落库（D-S1-1）"
        decimal fee "生成时金额快照（I2）"
        string status "AVAILABLE/TAKEN/SUSPENDED/EXPIRED"
        string source "NORMAL正常/EXTRA加号"
        bigint registration_id "占用时回写、回池置 NULL"
    }
    SLOT_LEDGER {
        bigint id PK
        bigint slot_id
        string action "GENERATE/OCCUPY/RELEASE/REFILL/SUSPEND/EXPIRE"
        string before_status
        string after_status
        string batch_no "任务批号"
    }
    ACCOUNT {
        bigint user_id PK "账号 = sys_user（框架表）"
    }
    PATIENT {
        bigint id PK
        bigint user_id "归属账号"
        string id_type "IDCARD身份证/CARD就诊卡"
        string id_no_hash "HMAC-SHA256 摘要（D-S1-3）"
        string is_default "1默认/NULL非默认（D-S1-8）"
    }
    STAFF_FAVORITE {
        bigint id PK
        bigint user_id
        bigint staff_id
    }
    REGISTRATION {
        bigint id PK
        string registration_no UK "R+yyyyMMdd+6位序列（D-S1-4）"
        bigint user_id "账号口径（红线 14）"
        bigint patient_id
        bigint slot_id
        decimal fee "金额快照（I2）"
        string active_flag "1有效/NULL终态（M1）"
        string status "八态（契约 §2.7）"
        string settle_status "NONE/WAIT_REFUND/REFUNDED"
        string sign_type "SCAN/MANUAL"
        string cancel_type "ACTIVE/PASSIVE"
    }
    PAYMENT {
        bigint id PK
        string payment_no UK "P+yyyyMMdd+6位序列"
        bigint registration_id
        decimal amount "= registration.fee"
        string channel "MOCK（本期唯一）"
        string status "WAIT_PAY/PAID/CLOSED/REFUNDED"
        datetime expire_time "创建时间 + 15 分钟"
        string trade_no "渠道流水号"
    }
    REFUND {
        bigint id PK
        string refund_no UK "F+yyyyMMdd+6位序列"
        bigint payment_id
        bigint registration_id
        decimal amount "一律全额"
        string status "WAIT_REFUND/REFUNDED/FAILED（终态）"
    }
    BLACKLIST {
        bigint id PK
        bigint user_id "账号级（M13）"
        bigint patient_id "关联就诊人（可空）"
        datetime start_time
        datetime end_time "限制半年"
    }
    NOTICE {
        bigint id PK
        bigint user_id
        string type "通知场景（线值待确认 Q3）"
        string read_flag "1已读/0未读"
    }
    SUSPEND_RECORD {
        bigint id PK
        string batch_no UK "幂等锚点（I7）"
        string scope_type "SCHEDULE/STAFF_DATE/CAMPUS_DATE"
        string scope_value
        bigint staff_id "SCHEDULE/STAFF_DATE 必填"
        string status "PENDING待处理/HANDLED已处理"
    }
    RECONCILE_RESULT {
        bigint id PK
        string batch_no "对账批次"
        string check_type "R1~R7"
        bigint target_id "slot/registration/refund，类型由 check_type 决定"
        string action "AUTO_FIX/ALERT"
        string status "OK/FIXED/ALERT"
    }
    JOB_LOG {
        bigint id PK
        string job_name
        string batch_no UK
        string status "RUNNING/SUCCESS/FAIL/SKIPPED"
        int affected_rows
    }
    PAYMENT_CALLBACK {
        bigint id PK
        string payment_no
        string trade_no "可空"
        string notify_id "可空"
        string process_status "PENDING/SUCCESS/IGNORED/FAILED"
    }

    DEPARTMENT ||--o{ DEPARTMENT : "父子（parent_id，根为 0）"
    CAMPUS ||--o{ MEDICAL_STAFF : "归属（campus_id 单值，M7 边界 Q6）"
    DEPARTMENT ||--o{ MEDICAL_STAFF : "所属科室（叶子节点）"
    CLINIC_TYPE ||--o{ MEDICAL_STAFF : "门诊类型码（staff.clinic_type）"
    MEDICAL_STAFF ||--o{ SLOT_TEMPLATE : "个人时段模板（午别×步长）"
    MEDICAL_STAFF ||--o{ SCHEDULE : "排班（人×日期×午别，稀疏）"
    FEE_STANDARD ||--o{ MEDICAL_STAFF : "按 (title, clinic_type) 定价匹配"
    SCHEDULE ||--|{ SLOT : "生成号源（一个排班 = 一个午别的若干时间点）"
    SLOT ||--o{ SLOT_LEDGER : "每次状态变迁一条（append-only）"
    SLOT ||--o| REGISTRATION : "被挂号占用（registration_id 回写）"
    ACCOUNT ||--o{ PATIENT : "名下就诊人（每人 ≤10）"
    ACCOUNT ||--o{ REGISTRATION : "提交挂号（user_id 口径）"
    PATIENT ||--o{ REGISTRATION : "作为就诊人"
    REGISTRATION ||--o| PAYMENT : "一单一付（挂号即建支付单）"
    PAYMENT ||--o{ REFUND : "退款单（FAILED 终态后再退须另建单）"
    ACCOUNT ||--o{ BLACKLIST : "黑名单（账号级统计 M13）"
    ACCOUNT ||--o{ NOTICE : "站内信接收人"
    ACCOUNT ||--o{ STAFF_FAVORITE : "收藏人"
    MEDICAL_STAFF ||--o{ STAFF_FAVORITE : "被收藏的医生"
    MEDICAL_STAFF ||--o{ SUSPEND_RECORD : "停诊登记对象（staff_id）"
    RECONCILE_RESULT }o--o{ SLOT : "修复对象（R1→slot）"
    RECONCILE_RESULT }o--o{ REGISTRATION : "修复对象（R4/R6→registration）"
    RECONCILE_RESULT }o--o{ REFUND : "修复对象（R5→refund）"
    JOB_LOG }o--o{ SLOT_LEDGER : "批号可倒查（ledger.batch_no）"
    PAYMENT_CALLBACK }o--|| PAYMENT : "按 payment_no 关联（去重）"
```

**图说明**：这张图回答「业务世界有哪些概念、彼此什么关系」。要点：① 号源供给链是 `医务人员 → 时段模板 → 排班 → 号源`；② 交易链是 `挂号单 → 支付单 → 退款单`；③ 治理对象（黑名单 / 停诊 / 对账 / 任务日志 / 回调）都以账号或号源为锚点。
**涉及的业务规则**：一行医务人员 = 一个出诊身份（PRD §14.3、技术方案 M7）；「一个 Slot = 一个号」无容量计数器（PRD §4.2-2、红线 2）；限购与黑名单按账号 `user_id` 口径（PRD §6.5/§6.9、红线 14）；证件唯一性走 `(id_type, id_no_hash)`（PRD §4.2-7、D-S1-3）。
**实现状态**：领域划分 = 设计态（技术方案 §1.2，`appt` 模块为空骨架）；`ACCOUNT` 即 `sys_user` 为**已核实代码**（RuoYi 框架表，患者复用，PRD §12）；所有关系均为业务逻辑关联，**库中无物理外键**（database-design §1 公约 12）——物理层面见 `02-database-erd.md`。

## 2. 实体业务含义速查

| 实体 | 业务含义 | 关键设计 | 来源 |
|---|---|---|---|
| Campus 院区 | 3 个院区，医务人员的属性与筛选维度 | 科室树**全局统一**，不按院区建树（切换院区按出诊人员过滤科室） | PRD §2、D5 |
| ClinicType 门诊类型 | 普通 / 夜间延时 / 知名专家，独立维度 | `code` 唯一 | PRD §2 |
| Department 科室 | 三级树（~40：8 一级/15 二级/20 叶子） | `parent_id` 根为 0；不挂院区 | PRD §4.1/§11 |
| MedicalStaff 医务人员 | ~60 人，关联 (campus_id, dept_id) | **一行 = 一个出诊身份**；`clinic_type` 为staff 自身属性（D-S1-7）；跨院区出诊为已知边界（M7） | PRD §4.1/§14.3 |
| SlotTemplate 时段模板 | 人 × 午别 × 起止 × 步长，~180 条 | 无容量字段，生成量 = 时长/步长；步长差异化（4/5~6/6~7/10 分钟） | PRD §4.2-4、§11 |
| FeeStandard 收费标准 | 职称 × 门诊类型 → 挂号费 | 快照不追溯（I2）；停用行仍占唯一键 → 重新启用而非 insert | PRD §6.4、database-design §6 |
| Schedule 排班 | 人 × 日期 × 午别，~500 条稀疏 | 无排班的日子不建记录；`UNIQUE(staff_id, visit_date, period)` 保幂等 | PRD §6.2/§11 |
| Slot 号源 | **一个 Slot = 一个号**，~9,000 条 | `time_point` 显式落库（红线 1）；5 列冗余免 join（D-S1-2）；`fee` 快照 | PRD §4.2、红线 1/2 |
| SlotLedger 号源台账 | 号源每次状态变更一条 | append-only；对账倒查依据 | 技术方案 §3.6 |
| Account 账号 | 复用 `sys_user`（专属角色，实名） | 患者不新建账号体系 | PRD §12 |
| Patient 就诊人 | 每账号 ≤10；卡号院内唯一 / 身份证全局唯一 | `id_no_hash` 让「证件唯一」与「加密存储」共存；`is_default` NULL 语义保一账号一默认 | PRD §4.2-6/7、D-S1-3/8 |
| Registration 挂号单 | 核心交易实体，八态 | `fee` 金额快照；`active_flag` 1/NULL + `chk_reg_active`；6 列冗余快照 | PRD §4.2/§7.2、M1 |
| Payment 支付单 | 15 分钟时限，本期仅 mock 渠道 | `expire_time` 派生自同一配置项；回调幂等 CAS | PRD §6.6 |
| Refund 退款单 | 挂号场景一律全额退 | `FAILED` 终态；再退须人工另建单 | PRD §6.6、契约 §5.5 |
| Blacklist 黑名单 | 半年内退号+爽约合计 6 次 → 限制半年 | **账号级**（M13）；到期自动解除 | PRD §6.9 |
| Notice 站内信 | 七种通知场景 | 无写端点，系统事件触发；`type` 线值待确认（Q3） | PRD §6.12、database-design §6 |
| SuspendRecord 停诊登记 | 停诊范围 + 批号幂等锚点 | E5 登记、F2 处理两段式；区间停诊拆 N 条共用批号（D-S1-5） | 契约 §7.5/§8.3 |
| ReconcileResult 对账结果 | 七查 R1–R7 落库 | `target_id` 无类型列，按 `check_type` 分派（Q9） | 技术方案 §3.6 |
| JobLog 任务日志 | 定时任务批号/起止/影响行数 | `SKIPPED` 承载红线 13；启动补偿检查 | 红线 13、技术方案 §3.3 |
| PaymentCallback 回调记录 | 渠道回调原始报文 | append-only；`(payment_no, trade_no, notify_id)` 去重（NULL 缺口见 Q14） | 技术方案 §3.5 |

## 3. 三个必须理解的领域设计

1. **快照冗余**：`registration` 冗余 staff/dept/campus/visit_date/period/time_point 六列 + `fee` 金额快照；`slot` 冗余五列。排班生成后不再变更（唯一变更源是停诊走 `status`）；后台改医生科室/院区**不追溯**已生成号源——「该医生已调至 B 院区但历史号源仍挂 A」属预期不是 bug（database-design §6、D-S1-2）。
2. **`active_flag` 的 NULL 技巧**：`UNIQUE(slot_id, active_flag)` 中 active_flag=1 有效、终态置 NULL，MySQL 唯一索引 NULL 互不冲突 → 号源回池复用不撞键（M1，红线 4）；`chk_reg_active` CHECK 约束把「状态 ↔ active_flag」绑定成 DB 事实（database-design §3.3）。
3. **账号口径**：限购「同时持有 ≤3」与黑名单统计均按 `user_id`（防多就诊人绕过，M13/红线 14）；同科室同日、同时间点两条限购按 `patient_id` + 联合唯一索引兜底（PRD §6.5）。
