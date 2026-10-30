# 测试证据（S2 – S5）

> 目的：把「设计承诺」变成「可复核的数字」。每条 = 场景 → 复现命令 → 实测输出 → 结论。
> 环境：backend `084fbe0`+（2026-10-20 本地），MySQL `appt`、Redis db1、患者账号 `appt_patient`、单机 50 并发。
> 复现入口：`backend/script/test/`（`s3_b1_concurrency.sh` / `s4_payment.sh` / `s5_read_bench.sh` / `s5_remain_consistency.sh`，前置与取 token 见同目录 `README.md`）。

---

## 1. S2 放号任务：幂等（集成测试④）

**场景**：`apptReleaseJob` 对「今日+N」重复执行，验证不重复生成。

| 执行 | 目标日期 | 新增排班 | 新增号源 | 跳过号源 | job_log |
|---|---|---|---|---|---|
| `J20261019000001` | 2026-10-26 | 80 | 2820 | 0 | SUCCESS，affected_rows=2900 |
| `J20261019000002` | 2026-10-26 | 0 | 0 | **2820** | SUCCESS，affected_rows=0 |
| `J20261019000003` | 2026-10-26 | 0 | 0 | **2820** | SUCCESS，affected_rows=0 |

**结论**：`UNIQUE(staff_id, visit_date, period)` + `UNIQUE(schedule_id, time_point)` 让重跑零新增；SnailJob 的「成功」只表示这一轮跑完，判据是 `appt_job_log.affected_rows` 与 message。

---

## 2. S3 挂号主链路（防线① 启用）

```bash
APPT_TOKEN='<appt_patient 的 token>' bash backend/script/test/s3_b1_concurrency.sh
```

实测（`PASS=14 FAIL=0 SKIP=0`）：

| 断言 | 期望 | 实测 |
|---|---|---|
| 50 并发抢同一号源 | 恰 1 笔成交 | 成功 1 / `SLOT_GONE` 49 |
| `registration` 有效行 | 1 行 `active_flag=1` | 1 行 |
| `slot` 状态 | `TAKEN` 且回写 `registration_id` | `TAKEN:2112264080722841601` |
| `payment` | 恰 1 笔 `WAIT_PAY` | 1 笔 |
| 防线① 占位键 | 存在（TTL = 支付时限） | `EXISTS=1` |
| 同 `Idempotency-Key` 双击 | 两次 200，第二次 `duplicate=true`，DB 1 单 | 一致 |
| 限购三条 | 分别命中对应业务码 | `LIMIT_DEPT_DAY` / `LIMIT_TIME_CONFLICT` / `LIMIT_HOLD_MAX` |
| 窗口外 | `OUT_OF_WINDOW` | 一致 |

**输出节选**

```text
-- 1. 并发争抢（50 线程同一 slot）--
  目标 slot=2112205873992192001
  PASS 成交恰 1 笔（成功 1 / SLOT_GONE 49）
  PASS registration 该 slot 仅 1 行 active_flag=1
  PASS slot 已置 TAKEN 且回写 registration_id（TAKEN:2112264080722841601）
  PASS payment 恰 1 笔
  PASS 防线① 已写占位键（TTL=支付时限）
-- 2. 同一 Idempotency-Key 连续两次 --
  PASS 两次均返回成功（code 200）
  PASS 第二次标记 duplicate=true
  PASS DB 仅 1 笔挂号单（双击未造两单）
-- 3~5. 限购三条 --
  PASS 返回 LIMIT_DEPT_DAY
  PASS 第二笔返回 LIMIT_TIME_CONFLICT
  PASS 第 4 笔返回 LIMIT_HOLD_MAX
-- 6. 窗口外 --
  PASS 返回 OUT_OF_WINDOW
== 结果：PASS=14 FAIL=0 SKIP=0 ==
```

---

## 3. 对照实验：摘除防线①（等价于 Redis 不可用）

**做法**：服务端加 `--appt.slot-hold.enabled=false` 启动（跳过 Redis 占位），脚本加 `SKIP_HOLD=1`。

```bash
java -jar ruoyi-admin.jar --appt.slot-hold.enabled=false ...
APPT_TOKEN='<token>' SKIP_HOLD=1 bash backend/script/test/s3_b1_concurrency.sh
```

| 断言 | 启用防线① | 摘除防线① |
|---|---|---|
| 成交笔数 | 1 | **1** |
| 失败笔数（`SLOT_GONE`） | 49（Redis 挡掉） | **49（DB CAS 挡住）** |
| 占位键 | `EXISTS=1` | **`EXISTS=0`** |
| `registration` 有效行 | 1 | **1** |
| 其余 10 项（幂等/限购/窗口） | 全 PASS | 全 PASS |

**结论**：Redis 占位只是「过滤器」，不是「判据」；摘掉它，同一号源仍只成交一笔，失败码与前端语义不变——这就是「Redis 挂掉正确性不降」的实测。

**边界声明**：本实验用配置开关模拟 Redis 不可用，未做真实宕机演练；单机 50 并发也不代表生产压测（`docs/技术方案.md` §3.1 的压测对比归 S5）。

---

## 4. 数据不变量抽查（可直接执行）

```sql
-- 有效挂号行与号源状态一致
SELECT r.registration_no, r.status, r.active_flag, s.status AS slot_status, s.registration_id
FROM appt_registration r JOIN appt_slot s ON s.id = r.slot_id
WHERE r.user_id = 1761400000000003101 ORDER BY r.id DESC LIMIT 3;

-- 每次占用都必须留台账
SELECT action, before_status, after_status, COUNT(*)
FROM appt_slot_ledger WHERE action = 'OCCUPY' GROUP BY action, before_status, after_status;

-- 支付单与挂号单一一对应且为待支付
SELECT payment_no, amount, status, expire_time FROM appt_payment ORDER BY id DESC LIMIT 3;
```

**期望**：`active_flag=1` ⇔ slot `TAKEN` 且 `registration_id` 指向该单；台账有 `OCCUPY / AVAILABLE → TAKEN`；`payment.status=WAIT_PAY`、金额等于 `slot.fee` 快照。

---

## 5. S4 支付链路（测试②③ + 竞态 + 并发关单 + 验签）

```bash
APPT_TOKEN='<appt_patient 的 token>' bash backend/script/test/s4_payment.sh
```

实测（`PASS=20 FAIL=0 SKIP=0`）：

| 场景 | 期望 | 实测 |
|---|---|---|
| ③ 回调幂等 | 同一支付单回调 3 次仅入账 1 次 | `payment_callback` 仅 1 条；`payment` 仅 1 次 `PAID`；2 次重复投递 `duplicate=true` |
| ② 关单回补 | 超时关单 → 号源回池 → 可再约 | `payment=CLOSED`、`registration=CLOSED` 且 `active_flag=NULL`、`slot=AVAILABLE` 且清空占用、台账有 `RELEASE`；同一号源再次预约成功 |
| 竞态（钱到了号没了） | 关单后回调 → 自动全额退 | 生成 `refund` 并最终 `REFUNDED`；`payment` 保持 `CLOSED`（无「已关闭+已支付」双态）；`settle_status=REFUNDED` |
| 并发关单 | 5 次并发仅 1 次生效 | 同一轮 `RELEASE` 台账增量为 1；`payment` 只有 1 行 `CLOSED` |
| 验签 | 篡改签名被拒且不入账 | `CALLBACK_SIGN_INVALID`；回调记录 `sign_flag='1'`；`payment` 仍 `WAIT_PAY` |

**边界声明**：本轮用 C2 的 `TIMEOUT`（演示压缩路径）验证关单服务，它与 30 秒巡检**复用同一 `PaymentCloseService`**；
SnailJob 控制台建 `apptPaymentCloseJob`（30 秒）后的实跑属人工验收项，未纳入脚本。

---

## 6. 可直接引用的三句结论

1. 「一个号只能卖一次」是数据库事实，不是应用判断：Redis 占位 → DB 行级 CAS → 联合唯一索引，三道防线任何一道被摘掉，成交数仍然是 1。
2. 幂等的目标是「让用户看到同一张单」，不是「拒绝重复」：同 key 第二次返回 200 + `duplicate=true`，DB 仍只有 1 单。
3. 限购的第三条（同时持有 ≤3）没有索引可兜底，必须靠账号行 `FOR UPDATE` 把同一账号串行化——这是唯一索引解决不了的那一类并发。

---

## 7. S5 查询聚合与余量缓存（测试⑤）

复现入口（两个脚本都不需要 token / 只有一个需要）：

```bash
# 读压测（全匿名）：redis / db 两模式各跑一次
bash script/test/s5_read_bench.sh
# 一致性（集成测试⑤）：需要患者 token
APPT_TOKEN='<token>' bash script/test/s5_remain_consistency.sh
```

前置：后端已启、窗口内（今日+1 ~ 今日+7）有排班与可约号源；`appt.remain.cache` 切换后**必须重启后端**，
且切换前留存的 `appt:remain:*` 键最长 600s 后自然过期（对比压测建议先等 TTL 或清空该命名空间）。

### 7.1 单屏 SQL 次数

`/appt/public/schedule/staffs?deptId=&date=` 的 SQL 由「逐医生逐午别 COUNT（M×2~3）」收敛为：
① 当日正常排班 ② 医生资料批量 ③ 余量一次聚合（缓存命中时为 0 条）。

实测（`s5_read_bench.sh`，`SHOW GLOBAL STATUS 'Questions'` 差值，20 次采样扣脚本自身 2 次 `SHOW`）：

| 指标 | 通过标准 | 实测 |
|---|---|---|
| 单屏 SQL 次数（冷启动首屏） | ≤ 3 | **3**（排班 + 医生资料 + 余量聚合） |
| 单屏 SQL 次数（缓存命中，10 次均值） | ≤ 3 | **2.2**（2 条 + 后台关单巡检噪声） |
| 单屏 SQL 次数（`appt.remain.cache=db`） | ≤ 3 | **3.2**（多一条聚合，无缓存读） |
| 朴素实现（对照） | — | 每格 1 次 COUNT：当前单屏 2 医生 / 2 格 → 2 次；20 医生 × 2~3 午别 → 40~60 次 |

> 关键不变量：次数**与医生数无关**（缓存命中恒 2 条、冷启动恒 3 条），这才是 N+1 被消掉的证据。
> 当前演示数据单屏只有 2 名医生（40 科室 / 60 医务人员摊到 7 天），密度不足；业务数据 seed 归 S7。

### 7.2 延迟分位与两模式对比（100 并发读）

100 并发 × 1000 样本 × 3 轮（单机 curl 进程开销计入，取中位）：

| 模式 | 单屏医生数 | SQL 次数 | p50 | p95 | p99 | 命中率 | QPS |
|---|---|---|---|---|---|---|---|
| redis | 2 | 2.2 | 4.1 ms | 9.3 ms | 12.9 ms | 100.00% | ~1050 |
| db | 2 | 3.2 | 4.0 ms | 10.6 ms | 19.0 ms | —（无缓存读） | ~1160 |

> 通过标准：p95 < 100ms（两模式均达标，余量 10 倍以上）；命中率 ≥ 95%（redis 实测 100%）。
> 两模式 p95 差距 14%，落在三轮波动区间内；默认值裁决理由见 `技术方案.md` §3.2 —— 默认保持 `redis`，`db` 作为可选对照。

### 7.3 一致性（集成测试⑤）

实测 `PASS=11 FAIL=0 SKIP=0`（`CYCLES=1000`，2026-10-20）：

| 场景 | 期望 | 实测 |
|---|---|---|
| 连续 1000 次「挂号 → 超时关单回补」 | 缓存 vs DB 聚合差值 0 | 通过：每 200 次与结束时各比对一次，4 个键差值恒为 0 |
| 键被删除后再挂号/回补 | 不创建键（Lua EXISTS 守卫，无幻数 1） | 通过：删键后完成一轮挂号/回补，键仍不存在 |
| 窗口外日期 `/schedule/staffs` | `code=200` + 空集合 | 通过（今日+30） |
| `/slot/list` 窗口内 | 只含 `AVAILABLE`、字段齐全（slotId/timePoint/fee） | 通过（48 个可约时刻） |
| 参数缺失 / 类型不合法 | `code=400`（**不是 500**） | 通过：`dept/tree` 缺 campusId → `缺少必填参数[campusId]`；`staff/list` 缺 deptId → `缺少必填参数[deptId]`；`slot/list?scheduleId=abc` → `参数类型不合法` |
| `remain=0` 的午别 | 仍然返回（前端置灰），不消失 | 通过：把该午别号源临时置占用后 `AM.remain=0` 且仍在 `periods` 里 |
| 后台排班页余量列 | 与接口同值、0 值置灰、导出无该列 | 通过：下单后接口与页面同为 47，关单后同为 48；导出 xlsx 无「余量」列 |

**本轮验证发现并修复（写路径鲁棒性）**：`releaseToPool` 在 CAS 未命中时**也释放本单占位键**。
触发场景：号源被外部改动（本轮为手工「整午别 UPDATE」）后关单，CAS 未命中提前 return，导致
`appt:slot:hold:{slotId}` 残留，下单持续 `SLOT_GONE` 直到占位 TTL 到期。Lua 比对 value，不会误删后来者的键。

### 7.4 回归（写路径改动的影响面）

`SlotStateService.occupy / releaseToPool` 接入了 afterCommit 余量增减，回归两个既有脚本：

| 脚本 | 结果 |
|---|---|
| `s3_b1_concurrency.sh` | `PASS=11 FAIL=0 SKIP=0`（2026-10-23 复跑，限购改口径后：50 并发仍 1 成交、幂等、同日跨科室 `LIMIT_PATIENT_DAY`、不同就诊日各 1 单成功、窗口外） |
| `s4_payment.sh` | `PASS=21 FAIL=0 SKIP=0`（回调 3 次仅 1 次入账、关单回补可再约、关单后回调自动退款、并发关单 1 次生效、验签） |

> 2026-10-20 二次复跑：`releaseToPool` 占位键释放修复生效（重启后）再跑 `s4_payment.sh`，
> 仍 `PASS=21 FAIL=0 SKIP=0` —— 该修复只影响 CAS 未命中的异常分支，正常关单链路无回归。

**边界声明**：S5 只覆盖「占用（−1）/ 回补（+1）」两条写路径；`AVAILABLE→EXPIRED`（过期扫描）为 **−1**（S6a 已接入）、
`AVAILABLE→SUSPENDED`（停诊）为 **−1**（S6b 待接入）；而 `TAKEN→EXPIRED` 是 **0**（已占的不是可约，过期不改变可约数）。
四种变迁的增量口径见技术方案 §3.2，任何一处写反都会让余量与 DB 长期漂移。
`SlotGenerateService` 批量 insert 可约号源不产生脏值（新排班此前无键），仅「对已存在排班补号」可能滞后 ≤600s，属显示侧可接受。

---

## 8. S6a 状态机与售后链路（集成测试⑥）

复现入口：`backend/script/test/s6a_state_machine.sh`（前置：`script/sql/appt_s6a_seed.sql` 造 triage 角色/账号与两个按钮权限）。

```bash
APPT_TOKEN='<appt_patient token>' \
TRIAGE_TOKEN='<appt_triage token>' \
ADMIN_TOKEN='<超管 token>' \
  bash script/test/s6a_state_machine.sh
```

### 8.1 状态边与副作用

| 场景 | 期望 | 实测（2026-10-20，`PASS=19 FAIL=0 SKIP=0`） |
|---|---|---|
| B5 退号（已支付） | `CANCELED_ACTIVE` + `cancel_type=ACTIVE` + `active_flag=NULL`；号源回池；退款单生成；`CANCEL_SUCCESS` 站内信；余量 −1 再 +1 | ✅ 7 项断言全通过（含余量回到退号前、台账 `RELEASE`） |
| 退号截止 | `visit_date=今天` → `REFUND_DEADLINE_PASSED` | ✅（当日 23:43 跑，今日+1 的号也已被拒——证明截止判断按「前一日 23:00」生效） |
| E1 签到 | `BOOKED→SIGNED` + `sign_type=SCAN`；重复签到 `SIGN_WINDOW_CLOSED` | ✅ 两项均通过 |
| 爽约主批 | `time_point=now-32min` → `NOSHOW` | ✅（任务摘要：爽约=2 号源过期=0） |
| 爽约全量兜底（集成测试⑥） | `time_point=now-3h`（等价「某轮被跳过」）→ `NOSHOW` + `NOSHOW_RECORD` 站内信 | ✅ 兜底批判为 `NOSHOW`，站内信 2 条 |
| 号源过期 | `AVAILABLE→EXPIRED` + 台账 `EXPIRE` | ✅ |
| 置完成 | `SIGNED` + `visit_date < 今天` → `COMPLETED` + `active_flag=NULL` | ✅ |

> 脚本自带清理：结束时删掉造数行与该账号近 30 分钟的站内信，所以跑完后台只留下用例 1 的
> 1 条「已退号(主动)」记录——这是正常现象，不是缺数据。S3/S4 脚本的 `reset_account` 会清空该账号全部挂号单，
> 因此**先跑 S3/S4 再打开后台列表会看到空表**。

### 8.2 边界声明

- 本轮只做**主动**退号；`CANCELED_PASSIVE`（停诊被动退号）与黑名单策略归 S6b（已落地，见 §9），复用同一 `RegistrationStateService`。
- 过期用例由 SQL 直插号源（绕过单柱），缓存与 DB 必然相差 1，因此只断言状态与台账；余量 −1 的口径由 `s5_remain_consistency.sh` 在真实链路上覆盖。
- 任务用例经 `POST /appt/admin/job/{jobName}/run` 触发（白名单 + Redisson 互斥），与 SnailJob 定时触发走同一 Service。

---

## 9. S6b 停诊两段式与黑名单

复现入口：`backend/script/test/s6b_suspend_blacklist.sh`
（前置：`appt_s6a_seed.sql` 的 triage 账号 + `appt_s6b_seed.sql` 的 `appt:suspend:handle`）。

```bash
APPT_TOKEN='<appt_patient>' TRIAGE_TOKEN='<appt_triage>' ADMIN_TOKEN='<超管>' \
  bash script/test/s6b_suspend_blacklist.sh
```

脚本自造一条独立排班（+20 天 NIGHT）+ 3 个号源（1 可约 / 1 已预约已支付 / 1 已签到），
结束时连同黑名单行一起清理，不影响演示数据。

### 9.1 两段式与副作用

| 场景 | 期望 | 实测（2026-10-21，`PASS=25 FAIL=0 SKIP=0`） |
|---|---|---|
| E5 登记（SCHEDULE） | 登记行 `PENDING`、返回 S 批号、**排班未被改动** | ✅ `S20261021000003` + 排班仍 `NORMAL` |
| 同范围重复登记 | `duplicate=true` 且返回原批号，不新建行 | ✅ 返回同 `suspendId` / 同批号 |
| F2 处理 | 排班 `SUSPENDED`；可约号源 → `SUSPENDED`；已预约单 → `CANCELED_PASSIVE` + `cancel_type=PASSIVE` + 批号 + `active_flag=NULL`；已占号源 → `SUSPENDED` 且清占用；已支付 → 退款单；`SUSPEND_CANCEL` 站内信；登记 `HANDLED` | ✅ 摘要「排班 1 / 号源 2 / 被动退号 1 / 退款 1 / 跳过已签到 1」，8 项断言全通过；台账 `SUSPEND` 两条（可约 + 已占） |
| 已签到单 | 仍 `SIGNED`、其号源仍 `TAKEN`（不参与批量退号） | ✅ 两项均通过 |
| 余量口径 | 预置缓存 5 → 停诊 1 个可约号源后 4（−1）；已占号源 0 增量 | ✅ 5 → 4 |
| 重复处理 | `handled=false`，退款单仍 1 条（不重复退款） | ✅ |
| 被动退号不计黑名单 | 停诊前后「近 180 天 `CANCELED_ACTIVE`+`NOSHOW`」计数不变 | ✅ 停诊前后均 1 |

**本轮发现并修复（脚本层，非业务缺陷）**：

1. 断言查错列：`appt_registration` 没有 `registration_id`（那是 `appt_slot` 的列），SQL 报错被 `2>/dev/null` 吞掉后误判「已预约单未被动退号」；改为断言 `status + active_flag`。
2. 黑名单用例下单未带 `Idempotency-Key`，被 B1 前置校验 400 拦下，根本没走到黑名单判定；补上请求头，并加兜底：若意外成交立即 `TIMEOUT` 关单回池。
3. 手工验黑名单页面时，造数 SQL 原先 `JOIN` 依赖 3.4 已删除的临时排班 → 0 行插入；改为 `CROSS JOIN (SELECT ... FROM appt_schedule LIMIT 1)` + `slot_id=0`、`active_flag=NULL`（三条唯一索引均不冲突）。

### 9.2 黑名单

| 场景 | 期望 | 实测 |
|---|---|---|
| 近 180 天主动退号+爽约 ≥6 | 下单返回 `BLACKLISTED`；自动建名单（`status=0`，`end_time=+6 月`）；发 `BLACKLIST_HIT` 站内信 | ✅ 脚本 7 次 → `BLACKLISTED` + 名单行 + 通知；页面「规则治理 → 黑名单」显示 `operator=system`、原因「近 180 天退号与爽约累计 7 次」、失效日 2027-04-21 |
| 生效期内再次下单 | 直接 `BLACKLISTED`，不再重复建名单 | ✅ 页面核对后再下单仍拒绝（`active_flag` 无新增） |
| 到期/人工解除 | 按 `end_time` 自然失效；后台编辑 `status='1'` 人工解除（无新端点） | 人工解除未实测（页面表单可用，逻辑为读侧按 `status=0 AND end_time>=now` 判定） |

> 回归（2026-10-21，S6b 改动后，均带三个 token 全量跑）：
> `s6a_state_machine.sh` `PASS=19 FAIL=0 SKIP=0`（退号 / 截止 / 签到 / 爽约主批+兜底 / 过期 / 置完成，未被停诊与黑名单逻辑影响）、
> `s4_payment.sh` `PASS=21 FAIL=0 SKIP=0`、`s3_b1_concurrency.sh` **`PASS=14 FAIL=0 SKIP=0`**。
>
> **S3 脚本修复（仅脚本，非业务）**：`LIMIT_HOLD_MAX` 长期 SKIP，根因在选号 SQL——「每科室取首个号源」会让候选全挤在同一天 08:00，
> 按 `time_point` 去重后剩 1~2 个；改为「每科室 × 每个就诊日取首个号源」（≈280 个组合）后由 shell 贪心挑出
> 时间点唯一 + 科室唯一的三笔，稳定通过。

### 9.3 边界声明

- 停诊区间以 `scope_value` 编码（`起始~结束`），**一条登记一个批号**；原「按日拆 N 条共用批号」因 `UNIQUE(batch_no)` 不可实现，已废止。
- `SUSPENDED` 号源不参与公开查询（A7 只返回 `AVAILABLE`），已被停诊的排班也不返回（A5/A6 过滤 `status='NORMAL'`）。
- 分诊台模式（uni-app）延后，本轮只做 API 与后台处理按钮。

---

## 10. S7 七查对账与看板

复现入口：

```bash
# 前置：后端为 S7 代码；已执行 appt_s6b_seed.sql / appt_s7_seed.sql / appt_s7_business_seed.sql
ADMIN_TOKEN='<超管 token>' bash script/test/s7_reconcile.sh
```

### 10.1 七查（构造 → 修复 → 二次跑归零）

| # | 构造方式 | 期望 | 实测 |
|---|---|---|---|
| R1 幽灵占号 | 取一个可约号源置 `TAKEN` 且 `registration_id=NULL` | 自动回池（`AVAILABLE` 或 `EXPIRED`）+ 台账 `RELEASE` | ✅ `slot …200111 → 可约` + `RELEASE` 台账 |
| R2 号源未占用 | 把某 `BOOKED` 单的号源改回 `AVAILABLE` | 自动补占用（`TAKEN` + 回写 `registration_id`），余量 −1 | ✅ `slot …201411 → TAKEN/…300245` |
| R3 应退未退 | 把某已支付单改成 `CANCELED_ACTIVE` 并删其退款单 | 自动建退款单 + `settle_status=WAIT_REFUND` + 渠道退款 | ✅ 自动补出退款单（单 `…300263`） |
| R4 给了号没收钱 | 把某 `BOOKED` 单的支付单改成 `WAIT_PAY` | **只告警**（`action=ALERT`），支付单保持 `WAIT_PAY` | ✅ 落 `ALERT` 且支付单仍 `WAIT_PAY`（未被改） |
| R5 退款卡住 | 插入一条 `update_time = now-1h` 的 `WAIT_REFUND` 退款单 | 重新发起渠道退款（状态转 `REFUNDED` 或仍在 `WAIT_REFUND`） | ✅ 重新发起（状态 `WAIT_REFUND`，Mock 回调后仍待入账） |
| R6 停诊漏处理 | 把某 `BOOKED` 单的排班置 `SUSPENDED` | 补被动退号（`CANCELED_PASSIVE`）+ 号源 `SUSPENDED` + 退款/关单 + 站内信 | ✅ 该排班 8 条 `WAIT_PAY/BOOKED` 全部转 `CANCELED_PASSIVE` |
| R7 缓存漂移 | 手写一个 `appt:remain:*` 键 | 命名空间被 `SCAN + UNLINK` 清空；**其它 Redis 键不受影响** | ✅ 余量键归零，占位键等其它键未受影响 |

### 10.2 幂等与耗时

| 指标 | 通过标准 | 实测（2026-10-21，`PASS=22 FAIL=0 SKIP=0`） |
|---|---|---|
| 一轮摘要 | 7 项各给出 found/fixed/alerted/skipped | 批次 `RC20261021000004`：**发现 14 / 修复 12 / 告警 2 / 跳过 0** |
| 二次跑 | R1/R2/R3/R6 的 `found` 合计 = 0；R5 不重复重试 | ✅ 四项合计 0；R5 `found=1`（仍 `WAIT_REFUND`，重试属预期，脚本允许 ≤1） |
| 耗时 | `elapsedMs < 60000`（seed 后 500 排班 / 9000 号源 / 2000 单） | ✅ **1774ms**（约 1.8s，预算 60s） |

> 摘要「发现 14」= 7 项各 1 + **R6 连带清扫同排班的另外 7 条** `WAIT_PAY/BOOKED` 单。
> R6 的判定粒度是**排班级**（停诊必须把该排班所有未就诊单退干净），属设计意图；因此对账脚本的造数
> 必须让 R2/R3/R4/R6 落在**四个不同排班**（脚本已加自检：去重后必须为 4，否则中止提示先跑 seed）。

### 10.3 看板与 seed

| 项 | 期望 | 实测 |
|---|---|---|
| seed 规模 | 500 排班 / 9000 号源 / 2000 挂号单（8 状态齐全）/ 2000 支付单 / 360 退款单 | ✅ 2026-10-21 实跑（~45s）：`500 / 9000 / 2000 / 2000 / 360 / 620` |
| seed 自洽 | `ghost_slots=0 && unoccupied=0`（首轮对账不误报） | ✅ 两项均为 0 |
| 看板 7 指标 | 与 SQL 手算一致；科室 TOP5 按今日挂号数倒序 | ✅ 逐项核对：`todaySlots=9000`（SQL 9000）、`todayBooked=60`（60）、`todaySigned=0`（0）、`noShowRate=0.00`（0/180）、`cancelRate=0.00`、`paySuccessRate=74.00`（1480/2000）；TOP5 五个科室各 10 单 |
| admin 看板页 | 卡片 + 柱图渲染、刷新不轮询、窄屏卡片折行 | ✅ 2026-10-21 页面验收：6 张卡片数值与接口/SQL 三处一致、TOP5 柱图正常渲染 |

> seed 会把有效单补到 620 张，为了满足 `uk_reg_patient_time` 必须把演示就诊人补到 **10 位**（PRD §6.5 单账号上限）；
> 2 位就诊人时该约束决定的上限只有 288 张（实测卡在此处，已记入 ROADMAP S7 踩坑记录）。

---

## 11. S8 患者辅助组（收藏 / 消息 / 分诊签到列表）

复现入口：`backend/script/test/s8_patient_aux.sh`（前置：患者账号 + S6a 的 `triage` 角色，无需新 seed）

```bash
APPT_TOKEN='<appt_patient>' TRIAGE_TOKEN='<appt_triage>' bash script/test/s8_patient_aux.sh
```

### 11.1 实测（2026-10-21，`PASS=29 FAIL=0 SKIP=0`）

| 组 | 用例 | 期望 | 实测 |
|---|---|---|---|
| D1–D3 收藏 | 连续收藏两次 | 两次都成功；首次 `data=true`；库内仅 1 行 | ✅ |
| | 列表 | `total≥1`，行内 `name`/`favoriteTime` 有值 | ✅ |
| | 取消两次 | 都成功（幂等）；库内 0 行 | ✅ |
| D4–D6 消息 | 未读数 | 与新造消息数一致 | ✅ 1 |
| | 未读列表 | 含本人消息、**不含他人消息**（`user_id` 强过滤） | ✅ 两项 |
| | 标记已读 | 成功 + `read_flag=1` + 未读数 −1 | ✅ 1 → 0 |
| | 重复标记 | 幂等成功 | ✅ |
| | 越权标记他人 | **404**（非 403）且他人消息未被改动 | ✅ 两项 |
| E3 签到列表 | triage 读取当日 | 200 + 分页结构 | ✅ `total=180` |
| | 按日过滤 | `2020-01-01` → 0 条 | ✅ |
| | 患者账号调用 | **403**（角色校验） | ✅ |
| 三类通知 | 下单 | 发 `BOOK_SUCCESS` | ✅ 含单号 |
| | 支付成功 | 入账后发 `PAY_SUCCESS` | ✅ |
| | 超时关单 | 关单后发 `PAY_TIMEOUT` | ✅ |
| | 收尾 | 退号不残留有效预约 | ✅ `CANCELED_ACTIVE` |

### 11.2 本轮修复（脚本 4 处 + 种子 2 处）

**脚本**
1. 把 HTTP 200 当业务成功——RuoYi 状态码恒 200，业务码在 `body.code`；收藏/取消/已读四处断言改为看 `body.code`。
2. 收藏幂等校验反了 `status` 语义：RuoYi 是 `'0'=正常`，实体映射 `Boolean` 后「正常」恰好是 `false`，按 `Boolean` 判断会把所有正常医生判成停诊 → 改为只校验存在性。
3. 第二笔下单撞 `LIMIT_DEPT_DAY`：改为「按该账号**真实可约**选号」（`NOT EXISTS` 排除已持有的 `(科室,就诊日)` 与 `time_point`），不再依赖外部排除参数。
4. 残留占位键导致 `SLOT_GONE`：下单前 `DEL appt:slot:hold:<slotId>`（TTL 15 分钟，上一轮测试会留）。

**种子（S7 遗留缺陷）**
5. 2000 张单挂在真实登录账号 → 「同时持有 ≤3」与「同科室同日」把演示账号锁死；改为虚拟数据账号 `…3199`。
6. 但只换 `user_id` 不够：限购按 **`patient_id`** 判定，而种子的 10 位就诊人仍是真实账号的 → 仍 `LIMIT_DEPT_DAY`；最终把**就诊人一并隔离**（`3301–3310` 挂在 `3199` 下）。真实账号现在：0 张单、0 条黑名单计数、2 位就诊人。

### 11.3 边界声明

- E3 本期**不按在岗院区过滤**（`sys_user` 无院区字段，契约 §11 #7 未决）；`appt_registration` 无 `visit_date` 单列索引，当前 2000 行量级可接受，正式环境建议补 `(visit_date, campus_id)`（DDL 不在本期）。
- 消息读侧不做「一键全部已读」（契约未定义），推送/微信订阅消息本期不做。
- **2026-10-23 复跑（限购改口径后）**：`s8_patient_aux.sh` 由 `FAIL=1` 修至 `PASS=29 FAIL=0 SKIP=0`。原因与修法：
  ① **第二笔下单**原假设「可同日再下一单」，新限购（同一就诊人同一就诊日 1 单）会拦 → 改为选**其它就诊日**的号源；
  ② **收尾退号**在深夜跑必失败（退号截止是就诊前一日 23:00，`REFUND_DEADLINE_PASSED`）→ 残留单会在下一轮触发 `LIMIT_PATIENT_DAY` → 改为「前置 + 收尾」都用 SQL 作废并回池号源，不依赖 B5；
  ③ `window_slot` 的排除条件由「同科室同日」改为「**同就诊人同就诊日**」，与后端口径一致。

---

## 12. S9 就诊人管理（B6–B10）

复现入口：`backend/script/test/s9_patient_crud.sh`（前置：患者账号 token，无需新 seed）

```bash
APPT_TOKEN='<appt_patient>' bash script/test/s9_patient_crud.sh
```

### 12.1 实测（2026-10-22，`PASS=23 FAIL=0 SKIP=0`）

| 组 | 用例 | 期望 | 实测 |
|---|---|---|---|
| B6 列表 | 返回体结构 | 只有 `idNoMasked`，无 `idNo` / `idNoHash` | ✅ |
| B7 新增 | 带 `isDefault=true` | 成功；`id_no_hash` 64 位；本人默认仅 1 位 | ✅ 三项 |
| | 响应 | 仅脱敏证件号 | ✅ |
| B7 查重 | 同一证件号再建 | `PATIENT_ID_CONFLICT` | ✅ |
| B8 修改 | `idNo` 留空 | 成功且 hash 不变 | ✅ |
| | 换证件号 | 成功且 hash 重算 | ✅ |
| 越权 | 改/删他人就诊人 | **404**（非 403） | ✅ 两项 |
| B9 删除 | 该就诊人有 `active_flag=1` 单 | `PATIENT_IN_USE` | ✅ |
| B7 上限 | 补到 10 人后再建第 11 位 | `PATIENT_LIMIT_EXCEEDED` | ✅ |
| B10 设默认 | 连续两次 | 均成功（幂等）；默认仅 1 位且指向目标 | ✅ 三项 |
| 清理 | — | 剩余正常就诊人回到基线 2 位 | ✅ |

### 12.2 边界声明

- **演示期证件号明文**（`appt.security.id-no.encrypt=false`）：脚本不断言密文，只断言「hash 为 64 位十六进制」与「响应不含原文」；生产打开加密开关无需改代码。
- **10 人是软上限**：count-then-insert，极端并发可能超出 1~2 人；单账号正常操作不会触发。
- **删除不转移默认**：删掉默认就诊人后账号可暂时没有默认，由前端提示用户重选。
- **`status` 语义（2026-10-22 复核修正）**：原先记录「生成器 `insertByBo` 判反」的说法**不成立**——库列 `char(1)` 中 `'0'`=正常映射 `false`、`'1'`=停用映射 `true`，故 `Boolean.TRUE.equals(status)` 判「停用行」是正确的；`RegistrationBookingService` 亦已校验停用就诊人。结论已写入 `backend/AGENTS.md` §6，而 RuoYi `'0'`（正常）映射为 `false`，语义相反；患者侧实现按正确语义，后台那份建议单开修复项。

---

## 13. S10 患者端主链路（uni-app）

> 记录时间 2026-10-22。门禁 + 接口链路两层；浏览器手工走查由用户在 8084 完成（AI 不代跑浏览器）。

### 13.1 门禁

| 项 | 命令 | 结果 |
|---|---|---|
| 依赖 | `pnpm install --frozen-lockfile` | lockfile 一致 |
| 类型 | `pnpm type-check` | 0 错 |
| 静态检查 | `pnpm lint`（`oxlint src`） | 0 warning / 0 error（47 文件） |
| 构建 | `pnpm build:h5`（`UNI_OUTPUT_DIR` 临时目录，**未删 dist**） | DONE |
| 后端单测 | `mvn -pl ruoyi-modules/appt -am test` | 13 例全绿 |
| 文档门禁 | `python3 script/doc_audit.py` | 5 项全过 |

### 13.2 接口链路（真实加密登录直打，非 mock）

| 步骤 | 端点 | 观测 |
|---|---|---|
| A2 | `GET /appt/public/dept/tree?campusId=…3201` | 一级/二级/三级齐全，叶子才是 A3 入参 |
| A5（科室口径） | `GET /appt/public/schedule/dates?deptId=…3311` | `periods[].scheduleId` 恒 `null`（聚合口径） |
| A6 | `GET /appt/public/schedule/staffs?deptId=…3311&date=2026-10-23` | `periods[].scheduleId="1761500000000100121"`、`remain=8` |
| A7 | `GET /appt/public/slot/list?scheduleId=…&period=PM` | 仅可约号源，`fee="22.00"` |
| B1 | `POST /appt/patient/registration`（带 `Idempotency-Key`） | `R20261022000001` / `P20261022000001` / `amount="22.00"` |
| C3（支付前） | `GET /appt/patient/payment/{no}` | `WAIT_PAY` |
| C2 | `POST …/mock-pay` `{result:SUCCESS}` | `accepted=true`（**仅受理**，不是已支付） |
| C3（2s 后） | 同上 | `PAID` + `tradeNo=MOCK…` |
| B2 | `GET /appt/patient/registration/list?status=BOOKED` | 1 条，字段齐全 |
| B4 | `POST /appt/patient/payment/{no}/cancel`（另一单） | `CLOSED`；**二次调用仍 `CLOSED`**（幂等） |
| 号源回补 | 取消后再查 A7 | 可约数 **8 → 8** |
| B6/B7 | 列表 → 新增 → 再列表 | 空 → `200` 新增 → 立即可见（脱敏串 `1101**********9999`） |

### 13.3 边界与已知问题

- **本片不含**：预约详情（就诊码）、退号（B5 页面）、我的就诊人独立页、我的医生、消息、分诊台 —— 全部归 **S11**。
- **`timePoint` 口径**：B1/B2/B3 三只 VO 此前序列化完整时间戳，与契约 §2.4 冲突；本片加 `@JsonFormat(pattern = "HH:mm")`，前端 `timePointText()` 仍做防御性归一（灰度期两端都显示正常）。
- **`scheduleId` 只回填在能一一对应的地方**：A6 恒有值；A5 仅 staffId 模式有值，deptId 模式恒 `null`（同午别多医生求和，单值无意义）。
- **两处 UI 缺陷（本片已修，留档）**：① `wd-popup` 默认 `z-index:10` 低于底部固定条（20），弹层「保存」被遮挡 → 显式 `:z-index="1000"`；② 从医生主页进排班页却列全科医生 → 改「医生视角 / 科室视角」双口径（A5 staffId / deptId 模式随视角切换）。
- **演示数据前提**：要让演示账号名下从 0 单开始，重跑 `backend/script/sql/appt_s7_business_seed.sql`。

---

## 14. S11 患者端辅助页 + 分诊台

> 记录时间 2026-10-23。门禁 + 接口实测 + 两处口径收口（限购、站内信时间格式）+ 三处 UI 缺陷留档。

### 14.1 门禁

| 项 | 命令 | 结果 |
|---|---|---|
| 类型 | `pnpm type-check` | 0 错（56 文件） |
| 静态检查 | `pnpm lint`（`oxlint src`） | 0 warning / 0 error |
| 构建 | `pnpm build:h5`（`UNI_OUTPUT_DIR` 临时目录，**未删 dist**） | DONE |
| 后端编译 | `mvn -pl ruoyi-modules/appt -am clean compile` | OK |
| 文档门禁 | `python3 script/doc_audit.py` | 5 项全 PASS |

### 14.2 接口实测（真实加密登录直打）

| 步骤 | 端点 | 观测 |
|---|---|---|
| B3 详情 | `GET /appt/patient/registration/{id}` | `visitCode=R20261022000001`、`timePoint=17:20`、`staff` 无 `deptId`（印证「再次预约」只能走医生主页） |
| B5 退号 | `POST /appt/patient/registration/{id}/cancel` | `CANCELED_ACTIVE` + `refundNo=F20261023000001` + `WAIT_REFUND`；详情里 `refund.status=REFUNDED` |
| B5 重复 | 同上 | `REG_STATE_INVALID`（当前预约状态不支持退号） |
| D1→D2→D1→D3 | 收藏四步 | 0 条 → `true` → 1 条（带 `avatarUrl/clinicType/favoriteTime`）→ 删除成功 |
| D5 / D4 | 未读数 / 列表 | `unread=6` → 6 条；`readFlag=false` 与不传分别可用 |
| D6 三态 | `PUT /appt/patient/notice/{id}/read` | 未读→200、已读→200（幂等）、不存在→**404**「消息不存在」；未读数 6→5 |
| E1 扫码签到 | `POST /appt/triage/sign` | `signType=SCAN`；同单再来一次 → `SIGN_WINDOW_CLOSED` |
| E2 手动补签 | `POST /appt/triage/sign/manual`（`registrationId`） | `signType=MANUAL` |
| E3 当日列表 | `GET /appt/triage/sign/list?date=` | 183 条，`campusName/deptName/timePoint` 齐全（`timePoint` 为完整时间戳，前端 `timePointText()` 归一） |
| 限购·同日跨科室 | `POST /appt/patient/registration` | `400` + `bizCode=LIMIT_PATIENT_DAY`「同一就诊人同一天只能有一个预约」 |
| 限购·不同日 | 同上（另一就诊日） | `200`，下单成功（印证「不再限制持有 3 单」） |
| 站内信新文案 | 新下单产生的 `BOOK_SUCCESS` | 「挂号单 R20261023000010 已提交：2026-10-25 08:00 就诊。请于 2026-10-23 03:36 前完成支付…」——**无 `T`、无纳秒** |

### 14.3 限购口径变更（2026-10-23）

| 项 | 变更前 | 变更后 |
|---|---|---|
| 主规则 | 账号级「同时持有 ≤3」+ 同科室同日 1 + 同时间点不可冲突 | **同一就诊人同一就诊日 1 个预约**（跨科室、跨医生都算） |
| 业务码 | `LIMIT_HOLD_MAX` / `LIMIT_DEPT_DAY` / `LIMIT_TIME_CONFLICT` | `LIMIT_PATIENT_DAY`（三条旧码 `@Deprecated`，不再返回） |
| 并发 | 账号行锁内精查 + `uk_*` 兜底 | 同左（`uk_reg_patient_dept_date` / `uk_reg_patient_time` 撞键统一映射 `LIMIT_PATIENT_DAY`） |
| DDL | — | **未改**（`(patient_id, visit_date)` 唯一索引需清存量，留待后续） |
| 脚本 | `s3_b1_concurrency.sh` 断言 3/4/5 围绕旧三条码 | 第 3 项改「同日跨科室 → `LIMIT_PATIENT_DAY`」，第 4 项改「不同就诊日各下 1 单」，旧 `LIMIT_HOLD_MAX`/`LIMIT_TIME_CONFLICT` 断言删除 |

### 14.4 边界与已知问题

- **消息详情无端点**：契约 §6 只有 D4/D5/D6，详情数据由列表页写入 `uni.storage`（`appt_notice_<id>`）后跳转；**直接输 URL 打开会提示「消息不存在或已删除」**（无缓存）。如需深链，要加 `GET /appt/patient/notice/{id}`。
- **E3 `timePoint` 仍是完整时间戳**：S6a 的 `SignListVo` 未加 `@JsonFormat`，前端 `timePointText()` 兜底；如需后端统一，与 B1/B2/B3 一样加注解即可。
- **存量站内信仍含 `T`**：已落库的正文不会自动改写（本次只影响新消息）；如需清洗执行 `test-evidence` 或 ROADMAP 记录的 `REGEXP_REPLACE` 语句。
- **本片未做**：加号登记（E4 后端未实现）。分诊底栏已**隐藏**「加号」入口（底栏 3 项：签到 / 当日 / 停诊），避免演示时点到「暂未开放」。
- **三处 UI 缺陷（已修，留档）**：① `wd-popup` 默认 `z-index:10` 低于底部固定条（20）→「保存」被遮挡，显式 `:z-index="1000"`；② 医生页进排班却列全科 → 「医生视角 / 科室视角」双口径；③ **`@click="goAppointments"` 会把点击事件对象当第一参数传入**，落点意图被存成 `MouseEvent` → `activeTab` 无匹配、列表为空；改为 `@click="goAppointments()"` 并对意图做白名单校验。
- **双角色验收**：分诊账号（`appt_triage`）访问 `/pages/triage/**` 正常，患者 tab 不渲染；患者账号访问分诊页被 guard 拦截。

### 14.5 S11.1 停诊上报（E5，2026-10-23 追加）

页面：`app/src/pages/triage/suspend.vue`（范围三选一 → 院区 / 科室（A2）→ 日期 → 医生（A6）→ 午别 → 原因 → 提交）。**零后端改动**，全部复用 S6b 的 `POST /appt/triage/suspend`。

| 场景 | 请求要点 | 实测结果 |
|---|---|---|
| 院区某日 | `scopeType=CAMPUS_DATE`、`scopeValue=1761400000000003203:2026-10-24` | `S20261023000001` / `PENDING` |
| 同范围重复上报 | 同上再提交一次 | `duplicate=true`，批号复用 `S20261023000001`（幂等） |
| 医生某日 + 区间 | `STAFF_DATE`、`scopeValue=2026-10-25`、`endDate=2026-10-26`、带 `staffId` | `scopeValue` 被规范化成 `2026-10-25~2026-10-26`（`S20261023000002`） |
| 单个午别 | `SCHEDULE`、`scopeValue=<scheduleId>` | `scopeValue` = 排班 id（`S20261023000003`），`staffId` 缺省由排班反查 |
| 边界（后端 `SuspendScopeParser`） | `SCHEDULE` 带 `endDate` / 跨度 >31 天 / 开始日早于今天 / 原因留空 | 分别 400：不支持区间、跨度超限、不能早于今天、原因不能为空 |
| 数据清理 | — | 三条验证登记已删除，`appt_suspend_record` 归零（不污染演示数据） |

> 两段式语义（务必在演示时说明）：本页只**上报**并拿到 `S` 批号；真正「批量被动退号 + 退款 + 站内信 + 排班置停诊」由后台「排班管理 → 停诊处理」（F2）执行。已签到的预约不参与批量退号（PRD §6.10）。

#### 14.5.1 用户实测暴露的两处后端缺陷（2026-10-23，已修）

| # | 缺陷 | 触发 | 根因 | 修法 |
|---|---|---|---|---|
| 1 | 换医生、同一天上报 → 返回「该范围已上报，批号复用」 | 先报「演示医生01 / 2026-10-27」，再选「演示医生31 / 同一天」提交 | `SuspendReportService` 幂等查询只比 `scopeType + scopeValue`；`STAFF_DATE` 的 `scopeValue` 只编码**日期**，医生在独立列 `staff_id` | 判定键补 `staff_id`（仅 `STAFF_DATE` 分支） |
| 2 | 后台「处理」提示成功，但排班未停、预约未退 | 处理 `S20261023000004`（STAFF_DATE / 10-24 / 演示医生01） | `SuspendHandleService.handle` 用 `parse(scopeValue)` 重建范围，而 `parse` **只还原日期/排班 id，不回填 `staffId`** → `loadSchedules` 拼出 `staff_id = null`，命中 0 条 | `handle` 内从记录回填 `scope.setStaffId(record.getStaffId())`；为空则抛 `SUSPEND_SCOPE_INVALID`，不再静默空转 |

**实证**：修复前 `S20261023000004` 的 `status=HANDLED`，但 `appt_schedule` 中该医生 10-24 的排班仍为 `NORMAL`、`status='SUSPENDED'` 的号源计数为 0 —— 说明处理是空操作。**空转意味着数据未被改动，无需回滚**；要让那次停诊真正生效，重启后重新上报同一范围再处理即可（`HANDLED` 记录不参与去重，会生成新批号）。

**修复后验收步骤**（需重启后端）：

1. 分诊台 → 停诊 → 演示医生01 + 2026-10-27 → 上报，记下新批号
2. 改选演示医生31 + 同一天 → 上报，应得到**全新批号**（缺陷 1 验收）
3. admin → 排班管理 → 停诊处理 → 处理第 2 条 → 提示「排班 ≥1 / 被动退号 …」，且该医生当天排班变「已停诊」（缺陷 2 验收）
4. 演示后重跑 `appt_s7_business_seed.sql` 恢复数据

**前端配套**：换科室/医生/午别时清空结果卡（此前旧批号一直挂着，易误读为「当前选择已上报」）；结果卡新增「停诊对象」行（院区 · 科室 · 医生 · 日期 午别）。

#### 14.5.2 回归脚本补齐三种范围（2026-10-23）

`backend/script/test/s6b_suspend_blacklist.sh` 原先只构造 **`SCHEDULE`** 一种范围的登记（第 158 行），而 `SCHEDULE` 的 `scopeValue` 就是排班 id（完整主键），恰好把「`staffId` 从 `scopeValue` 移出到独立列」这一类缺陷全部绕过 —— 这就是上面两个缺陷没被自动化发现的原因。

已补两个用例（+17 条断言），实测 **`PASS=42 FAIL=0 SKIP=0`**（原 25 条）：

| 用例 | 断言 |
|---|---|
| `STAFF_DATE` 幂等 | 同医生同日重复登记 `duplicate=true` 且批号复用；**换医生同日 `duplicate=false` 且批号不同**（缺陷 1 回归） |
| `STAFF_DATE` 处理 | 排班 `NORMAL→SUSPENDED`、该单 `CANCELED_PASSIVE`、号源 `SUSPENDED`+清空占用、生成退款单、**同院区另一医生排班仍 `NORMAL`**（缺陷 2 回归，同时证明按 `staff` 展开不误伤） |
| `CAMPUS_DATE` | `scopeValue` 规范化为 `campusId:日期`；处理后按院区展开，排班停诊 + 被动退号 + 退款 |

造数保护：日期取 **+40 / +41 天**（避开种子窗口 +1~+7），处理前先校验该医生/院区当天除自造排班外无其他排班，否则 `SKIP` 而不是误停演示数据；脚本退出自动清理（实测 `appt_schedule` / `appt_registration` / `appt_blacklist` 归零）。

---

## 15. 小程序端真机验证（2026-10-23）

> 目标：把 H5 已验证的「分诊扫码签到」搬到微信小程序真机。结论：**代码层 bug（不是网络/配置）**，已修。

### 15.1 现象与定位

| 现象 | 判断 |
|---|---|
| 开发者工具模拟器正常渲染；真机（微信 8.0.66 / 基础库 3.17.5）除导航栏与 tabBar 外**全白**，连首页品牌区的静态文字都没有 | 不是接口问题（否则会显示错误态和「重试」），是**页面 JS 没执行** |
| 真机调试 Console | `ReferenceError: TextEncoder is not defined`，栈为 `crypto.js:4 → request.js:4 → pages/triage/sign/index.js`（`pages/triage/list`、`pages/triage/suspend` 同样） |
| 网络侧 | `Test-NetConnection 172.31.124.129 -Port 8082` 与 `192.168.0.108 -Port 8082` 均 `True`，`netstat` 见 `0.0.0.0:8082 LISTENING` —— 与网络无关 |

**根因**：小程序 JS 引擎没有 `TextEncoder/TextDecoder`。`utils/crypto.ts` 在**模块顶层** `new TextEncoder()`，而它被 `utils/request.ts` 顶层 import、`request` 又被几乎所有页面顶层 import → 页面模块在**求值阶段**抛错，组件树不渲染；导航栏与 tabBar 是原生的，所以仍在。

### 15.2 修复与验证

- `crypto.ts` 改为纯 JS UTF-8 编解码（含代理对/emoji），`encoder/decoder` 仍是 `{ encode, decode }` 形状，调用方无感知
- Node 直接跑 `src/utils/crypto.ts`：AES(ECB) 往返 **4/4 PASS**（`hello`、中文、emoji 混排、JSON），base64 往返 PASS
- `build:mp-weixin` 产物中 `TextEncoder/TextDecoder` 引用数 **0**
- 全仓扫描 `btoa/atob/Blob/FileReader/document/window`：除注释外无其他 Web API 依赖

### 15.3 顺带修掉的两处配置（都会造成「看起来是白屏」的假象）

| 项 | 问题 | 修法 |
|---|---|---|
| `manifest.json → mp-weixin.setting` | 生成的 `project.config.json` 只有 `es6:true`，缺 `enhance`（增强编译），产物里的 `??` / `?.`（`pages/` 内 47 处）不会被降级 | 补 `es6 / enhance / postcss / minified`，已验证产物 `project.config.json` 含 `enhance:true` |
| `dev:mp-wsl` 的 baseApi | 默认 `http://localhost:8082`（真机指手机自己）；曾一度被改成本机 IP 时误删成 `http://:8082` → 微信报 `invalid url "http://:8082/..."` | 默认改为本机网卡**转发口** `http://192.168.0.108:18082`（8082 被 QQ 占用，见 §15.4），可用 `APPT_MP_BASE_API` 覆盖 |

### 15.4 WSL2 下让手机访问后端（Win10 无 `networkingMode=mirrored`）

- 手机 → Windows 网卡 → WSL 需要 `netsh interface portproxy`，且 `connectaddress` **必须填 WSL 的 IPv4**（如 `172.31.124.129`）。填 `127.0.0.1` 会失败：Windows 的 `localhost` 优先走 `::1`，WSL 的 localhost 转发落在 IPv6 回环，IPv4 回环上没有监听（实测 `127.0.0.1:8082` 不通、`localhost:8082` 通）
- **转发口不要用 8082**：实测 Windows 上 `QQ.exe`（PID 31612）占着 `0.0.0.0:8082`，`netsh portproxy` 因端口被占**静默绑定失败**（`show v4tov4` 仍显示条目），访问 `192.168.0.108:8082` 实际打到 QQ 的 HTTP 服务 → **空 body 的 404**；前端表现为 `request.ts` 的「响应为空」，且后端日志里**查不到该请求**（这条反证很好用）。改用 `listenport=18082` 后 `curl.exe` 立刻返回 `{"code":200,...}`
- `netsh add` 在端口被占 / 条目已存在时**不报错**，每次都要 `show v4tov4` 复核
- WSL 重启后 IPv4 会变，`portproxy` 需重加；长期方案是 Win11 的 `networkingMode=mirrored`
- 验证顺序：手机浏览器先打开 `http://<局域网IP>:18082/appt/public/campus/list` 看到 JSON，再开小程序

### 15.5 真机扫码签到验收（2026-10-23，通过）

环境：微信 **8.0.66** / 基础库 **3.17.5**，后端经 `portproxy` 18082（→ WSL `172.31.124.129:8082`）访问。

| 步骤 | 操作 | 结果 |
|---|---|---|
| 1 | 造一条今天可签的单：`R20261023000099`（`BOOKED`，就诊 23:59，骨科/演示医生04/东院区，归属 `admin`） | `B3` 详情 `code=200`、`visitCode=R20261023000099` |
| 2 | 电脑 H5（8084）`admin` 登录 → 我的预约 → 该单详情 → 展示二维码 | 二维码正常渲染（内容 = `visitCode`） |
| 3 | 手机分诊端（`appt_triage`）→ 签到 → 扫一扫 → 扫屏幕上的码 | **签到成功**，结果卡显示就诊人/医生/时间/签到方式=扫码 |
| 4 | 同一张码再扫一次 | `SIGN_WINDOW_CLOSED`（预期，状态机正确） |

结论：**小程序端「扫一扫 → E1 → 签到」端到端可用**，与 H5 手动补签（E2）共用同一状态机。

### 15.6 两条遗留已收口（2026-10-23）

| 项 | 处理 | 验证 |
|---|---|---|
| `utils/encrypt.ts` 顶层 import `jsencrypt` | **一度改成 `await import()`，已回滚**（见下方「回滚原因」）；保持静态 import，`rsaEncrypt` 同步 | 静态引用下产物为 `require("../common/vendor.js")` + `new n.JSEncrypt`，真机可登录 |
| ~~回滚原因~~ | 小程序登录报 `"/common/vendor.js" is not a function` | uni-app 的 **mp-weixin 构建把动态 `import()` 编译成 `require(...)` 再 `.then(...)`**，而 `require` 返回模块对象不是 Promise → 登录必崩。H5 的分包收益远小于这个坑，且 `jsencrypt` 内部有 `typeof navigator` 守卫、真机本就不崩 |
| `request.ts` 空 body 吞掉状态码 | 200 → 「响应为空，请稍后重试」；非 200 → 「服务不可达（404），请检查接口地址或网络」，非 silent 时 toast | `type-check` / `lint` / `build:h5` / `build:mp-weixin` 全绿 |

> `jsencrypt` 的 CJS 产物 `typeof module.exports === 'function'`（没有 `.JSEncrypt`、没有 `.default`），原先的 `import { JSEncrypt }` 依赖的是它的 ESM 构建；改成动态 import 后必须按打包器的 interop 形态兜底，否则小程序端会拿到一个函数却取不到构造器。

---

## 16. S12 品牌与首屏（2026-10-24）

> 切片性质：视觉与资产生成，**无后端改动、无端点变更**。验证口径为「资产可复现 + 双端一致 + 门禁全绿 + 人工验收」。

### 16.1 品牌资产（脚本可复现）

| 项 | 结果 |
|---|---|
| 生成命令 | `cd app && pnpm brand:gen`（`scripts/gen-brand-assets.mjs`，devDependency `@resvg/resvg-js@2.6.2`） |
| 母标三档 | `full`（牌 + 十字 7.2 + 三点）/ `compact`（去三点、十字加粗 8.4）/ `crossOnly`（仅十字，紧致画布 + 8% 安全区）；同一套几何常量派生，`fill-rule="evenodd"` 单路径 |
| 主色 PNG | 16 / 32（纯十字）、48 / 64 / 128 / 256 / 512（完整档）+ `logo-compact-48`，另反白 4 档与横版 1 张 |
| `favicon.ico` | PNG-in-ICO 手写拼装（6 字节头 + 3×16 字节目录 + 载荷），内嵌 16 / 32（纯十字）与 48（完整档） |
| 封面 | `cover-144.png`（浅灰底 + 母标）/ `cover-520x280.png`（135° 渐变 + 反白横版 + 「号源」字标，中文取系统字体微软雅黑 600） |
| 跨仓写出 | app 产物 + `admin/src/assets/logo/{logo,logo-white,logo-compact,logo-compact-white}.png` + `admin/public/favicon.ico`；`../admin` 缺失时只写 app 并告警 |

**本轮修掉的母标缺陷**：`logo-preview/final/A3c-母标.svg` 的三点写成独立 `<circle fill="currentColor">`，与牌同色 → 实际渲染完全不可见；改为同一 `evenodd` 路径的 3 段圆形子形状后「十字牌 · 点阵」才成立（DESIGN §12.1 已记录）。

### 16.2 tabBar 与分诊底栏图标（双端一致）

| 端 | 结果 |
|---|---|
| 患者端 | `pages.json` 四项补 `iconPath` / `selectedIconPath`；`build:mp-weixin` 产物 `app.json` 与源一致；`dist/build/mp-weixin/static/tabbar/` 共 14 张 PNG |
| 分诊台 | 自绘底栏（`TriageTabbar.vue`）由 3 个圆点改为同源线性图标 `triage-{sign,list,suspend}`，选中 / 未选中双色 |
| 规格 | 81×81 画布、24 网格、`stroke 2` → 6.75px、圆头圆角、未选中 `#8A94A6` / 选中 `#1F7A8C`（DESIGN §12.5） |

### 16.3 三屏抛光（Stitch 参考 → 差异表 → 落地）

Stitch 项目 `appt-s12` 三屏为 **DESKTOP 画布**（1280×1024 / 2560×2048 / 2560×3248），尺寸不可用，只取版式；逐屏结论写在 `app/DESIGN.md` §9.1 / §9.10 / §9.11 的「Stitch 出图校准（2026-10-24）」。落地时修正三处：

1. **状态与退款块矛盾**：出图「已预约」同时显示退款信息 → 实现只在 `CANCELED_ACTIVE / CANCELED_PASSIVE` 渲染退款块；
2. **证件号并进「证件类型」行** → 拆为「就诊人 / 证件类型 / 证件号」三行，仍只上脱敏串（红线 15）；
3. **我的页三组同屏** → 角色组只在 `isTriage` 渲染；未登录时账户组与退出登录整块不渲染；退出登录独立成卡 + 二次确认。

副产修复：Wot 2.x 按钮底色取 `--wot-primary-6` 色阶而非 `--wot-color-theme`，未覆盖时落框架蓝 → `appt.scss` 补 `--wot-primary-1..10` 与 `--wot-danger-*`，全站 primary 按钮统一 `#1F7A8C`。

### 16.4 门禁与人工验收

```
app   : pnpm type-check / pnpm lint / pnpm build:h5 / pnpm build:mp-weixin    → 全绿
admin : pnpm exec vue-tsc --noEmit / pnpm lint / vite build --outDir dist-s12  → 全绿（dist 未动）
grep  : grep -ri ruoyi admin/src → 仅 @/utils/ruoyi 与 RuoYiAjaxResult（框架内部依赖）
```

人工验收（2026-10-24，用户确认三处通过）：H5 首页品牌区母标与通栏渐变、底部图标 tab、我的页分组与退出确认、详情页信息行分层；分诊台三页底栏图标与按钮主色；后台登录页 / 侧栏 / 顶栏标识、运营看板四卡与科室排行、favicon 与 `<title>`。

### 16.5 边界声明

- **后端零改动**：看板复用 `GET /appt/admin/dashboard` 与 `GET /appt/admin/suspend/list?status=PENDING`（取 `PageResult.total`），未新增接口；
- **未做（归 S12.5）**：后台全局主题变量（`--el-color-primary` 仍为框架默认）、表格密度与空态、8 个业务状态标签配色、表单与弹窗规范、404 / 网络异常页、移动端剩余 7 屏；
- 后台蓝调 `rgba(53,109,255,…)` 仍有 24 处（`_page-shell.scss`、login / register 背景光斑、RightToolbar、system/profile、workflow 等），同归 S12.5；
- `app/src/manifest.json` 的 `mp-weixin.appid` 属本地配置，未纳入提交；
- Stitch 提示词已补移动视口声明（`390x844 mobile viewport`），重出时按新提示词执行。

---

## 17. S12.5 全站视觉统一（2026-10-24）

> 切片性质：样式层与常量层改动，**后端零改动、无端点变更、无新增依赖**。
> 四屏 Stitch 出图（`appt-s12-5` = project `1165857668159132014`）先写差异表，再按差异表落地。

### 17.1 四屏差异表落地（§13.2 四类逐项过）

| 屏 | 画布 | 可 1:1 落地 | 判定为「需回调」并已落地 |
|---|---|---|---|
| 404（`screens/12da2218…`） | 2560×2048 DESKTOP | 居中结构、淡十字水印、标题 + 一句说明 + 主按钮 + 文字链 | 十字放大到 `96rpx` 且主色 20%（出图 `#D6E4E7` 偏灰绿）；主按钮回 `88rpx` / 圆角 `12rpx` |
| 网络异常（`screens/87b60835…`） | 390×844 MOBILE | 结构、文案、按钮层级全对 | 十字同上统一；文字链与按钮间距回 `24rpx` |
| 消息详情（`screens/102252fc…`） | 1280×502 DESKTOP | 白卡「标题 + 时间」基线对齐、类型标签、正文分段、原生导航标题 | 返回入口 plain 小按钮 → **纯文字链**；类型标签维持 `22rpx` + `#EEF2F6` 底；正文加 `white-space: pre-wrap` 保留纯文本换行 |
| 后台登录页（`screens/7e27602e…`） | 2880×618 DESKTOP | 左平面深潭青面板 + 右白卡表单，控件全部可映射 Element Plus | 第三方 5 个圆钮沿用既有 `svg-icon`；角色卡底 `rgba(255,255,255,.10)`；验证码保留后端 `codeUrl`；版权行改「号源演示系统 · 数据全部虚构」 |

### 17.2 移动端兜底页（新增）

- `pages/fallback/index.vue` 单页两模式：`notfound`（页面不存在 / 返回首页 / 返回上一页）、`offline`（网络不可用 / 重新加载 / 返回首页）；共用母标纯十字档水印（`logo-cross-128.png`，20% 透明度）。
- 接线两处、**不做全局自动跳转**：① `router/h5-fallback.ts` 在 H5 启动时校验 hash 路由，未注册页面换到 `notfound`（条件编译，小程序为空实现）；② 首页首屏 `listCampus` 失败且无数据时 `goFallback('offline')`。
- `utils/fallback.ts` 做 1.5s 防抖；兜底页加入 `WHITE_LIST`（未登录也能看，否则弱网会把用户踢去登录页）。
- 后台 404 同口径重写：母标水印 + 「页面不存在」+ 一句说明 + 返回首页，去掉卡通云图与 `#1482f0`。

### 17.3 后台主题收口（三处同源）

| 层 | 文件 | 改动 |
|---|---|---|
| 编译期 SCSS | `tokens/_sass-vars.scss` | `$color-primary #1f7a8c` / `success #2e9e6b` / `warning #d98e04` / `danger #d14343` / `info #3b82c4` |
| 运行前默认值 | `src/settings.ts` | `theme: '#1F7A8C'`（否则首屏闪一下框架蓝） |
| 运行时 CSS 变量 | `tokens/_theme.scss` | 新增 `--el-color-{success,warning,danger,info}` + `light-3/5/7/8/9` + `dark-2` 共 28 个变量 |

框架蓝收口：`rgba(53,109,255,…)` 与 `rgba(64,158,255,…)` 共 **20 个文件**统一改主色 RGB，`#409EFF` / `#60a5fa` 同步替换；`views/appt/dashboard` 的 ECharts 柱色一并改。
圆角归一：卡片 `--app-radius-base: 16px`、`--el-border-radius-base: 8px`（输入/按钮）、`--el-border-radius-small: 4px`（标签）。
验证残留：`grep -rn "#409EFF\|53, 109, 255" admin/src` → **0 命中**。

### 17.4 状态标签（8 态映射统一）

`views/appt/options.ts` 的 `ApptOption` 增 `type`（`primary/success/info/warning/danger`），六组状态补齐：

| 业务 | 映射 |
|---|---|
| 挂号 8 态 | `WAIT_PAY` warning · `BOOKED` primary · `SIGNED`/`COMPLETED` success · `CLOSED`/`CANCELED_ACTIVE`/`CANCELED_PASSIVE` info · `NOSHOW` danger |
| 支付 4 态 | `WAIT_PAY` warning · `PAID` success · `CLOSED`/`REFUNDED` info |
| 退款 3 态 | `WAIT_REFUND` warning · `REFUNDED` success · `FAILED` danger |
| 结算 3 态 | `NONE` info · `WAIT_REFUND` warning · `REFUNDED` success |
| 停诊 2 态 | `PENDING` warning · `HANDLED` success |
| 回调 4 态 | `PENDING` warning · `SUCCESS` success · `IGNORED` info · `FAILED` danger |

新增 `components/ApptStatusTag.vue`（未知线值兜底 `info`，不猜危险色），替换 registration / payment / refund / suspend / paymentCallback 五个列表页的状态列——原先都是纯文本 `formatter`，与移动端彩色标签是两套观感。

### 17.5 门禁与人工验收

```
app   : pnpm type-check / pnpm lint / pnpm build:h5 / pnpm build:mp-weixin  → 全绿
admin : vue-tsc --noEmit 0 错 / oxlint 0 错 / vite build（outDir=/tmp，未动仓库 dist）→ 通过
grep  : admin/src 内 #409EFF、rgba(53,109,255,…) → 0 命中
docs  : python3 script/doc_audit.py → 五项全过
```

人工验收（2026-10-24）：后台登录页青白两栏、运营看板、挂号单状态标签着色、停诊登记空态、404 页；移动端 H5 走 `#/pages/nope` 落兜底页、首页断网落 offline 页、消息详情文字链与类型标签。

### 17.6 边界声明

- **后端零改动**；无新增依赖，后台构建体积基本不变。
- 表单与弹窗本轮**只落规范**（`admin/AGENTS.md` §13.4）并抽查两页，未逐页重排 20 张表单位置——如后续发现对不齐，按规范单点修。
- 暗色主题只做了色值替换（`_theme-dark.scss`），未做对比度专项校验；`i18n` / 移动端暗色不在本片范围。
- 后台 404 需部署侧把未命中路径 rewrite 到应用入口才完整生效（归 S16）。
- **未登录体验补正（2026-10-24，app `4c50e67`）**：原先点任一 tab 会被守卫 `reLaunch` 到登录页，底栏消失且页面栈被清空（登录完只能回首页）。现改为：预约 / 消息 / 我的三页未登录也放行并在页内渲染未登录态（tabBar 全程可见），点「去登录」`navigateTo` 叠层、登录成功 `navigateBack` 回来源 tab；其余受保护页同样改用 `navigateTo` 不再 `reLaunch`。**第二处修正（同日晚，app `9e7e554`）**：首版仍会被 401 弹走——①「我的预约」未登录时仍调用 B2 做默认落点探测 → 401；② 请求层 `handleUnauthorized()` 是 `reLaunch` 且延迟到达的401 会在切 tab 后再弹一次（所以「点预约」和「切首页」都会跳登录页）。现改为：未登录不探测、401 走 `navigateTo` 叠登录页（已在登录页不重复跳）。**第三处修正（app `5b87c60`）**：未登录态下任何 401 一律不再跳转（「本来就没 token」不是「登录过期」，只清登录态、由页面渲染未登录态）；退出登录改为回首页保留底栏，而不是落到登录页。**第四处修正（app `68a04a2`）**：实测「未登录 → 消息 → 点首页」仍跳登录页且 Network 无任何 401，定位为守卫 `pathOf()` 只 `split('?')`、tabBar 传入的 url 可能缺前导斜杠 → 白名单判不中；现归一化路径 + tab 页一律放行 + dev 下打印拦截原因。**第五处（app `0d64569`）**：dev 日志显示被拦路径是 `/` —— H5 tabBar 点首页时 uni 传的是根路径，白名单只有 `/pages/index/index`；`pathOf()` 现将 `/` 折算为首页。口径见 DESIGN §8.3。
- `app/src/manifest.json`（本地 AppID）与 `docs/appt.code-workspace` 按约定未提交。

---

## 18. S13 门面与物料（2026-10-24，部分完成）

> 目标：陌生人 30 分钟跑通、5 分钟讲明白。本节只记**可复现证据**，不复制 README 正文。

### 18.1 截图（脚本产出，禁止手工）

| 项 | 结果 |
|---|---|
| 脚本 | `qd-appt-showcase/tools/screenshots`（Playwright ^1.56，`node run.mjs --shots`） |
| 产物 | 10 张 PNG：患者端 5（首页 / 选院区 / 科室 / 我的预约 / 消息）、分诊 2（签到 / 当日）、后台 3（运营看板 / 挂号单 / 停诊登记） |
| 体积 | 合计 1.2 MB，单张 11–95 KB（阈值 ≤300 KB/张） |
| 视口 | H5 `390×844 @2x`、后台 `1440×900 @1x`；`locale=zh-CN`、`tz=Asia/Shanghai` |
| 等待 | `waitForSelector` / `getByText(...).waitFor()`；仅 `waitForTimeout(260)` 做过渡收尾（有注释） |
| 可重复 | 同一命令连续两次结果一致（类名无关，文案/结构选择器） |

**环境解法（免 root，均未改动系统）**

- `chromium` 缺 `libnspr4 / libnss3 / libasound2` → `apt-get download` + `dpkg -x` 到 `.libs/`，
  启动前挂 `LD_LIBRARY_PATH`（`ldd` 缺失库归零后启动成功）；
- 中文渲染成方块 → `fonts-wqy-zenhei` 同样解包到 `.libs/fonts`，`FONTCONFIG_FILE` 指过去；
- 浏览器二进制复用 `~/.cache/ms-playwright/chromium-*`，安装依赖时 `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`，未重复下载。

### 18.2 过程中修掉的两个真实缺陷

1. **首页冷启动误跳兜底页**（app `43036c1`）：`loadCampuses()` 只要首帧请求失败就 `goFallback('offline')`，
   而冷启动时请求可能先于登录态恢复/路由就绪 → 「同一 URL 有时首页、有时网络异常页」。
   现改为仅 `navigator.onLine === false` 才跳兜底，其余失败走页内错误态 + 重试。
2. **后台整页刷新丢登录态，导致截图脚本无法按 URL 导航**：改为点侧栏菜单（DOM click），
   并发现 Element 折叠子菜单在 Playwright 里被判定不可见——DOM click 两层都绕开。
   这条对将来任何后台自动化都适用，已写进 `tools/screenshots/README.md`。

### 18.3 后台「去模板化」清理（本轮）

| 项 | 处理 |
|---|---|
| 注册页页脚 | 「Copyright © 2018-… 疯狂的狮子Li All Rights Reserved.」→「号源演示系统 · 数据全部虚构」 |
| 登录页第三方登录 | 整块移除（分割线 + 5 个圆形按钮 + `doSocialLogin` + `authRouterUrl`/`HttpStatus` import + 样式）；后端无任何 social 客户端 |
| 侧栏顶级菜单 | `appt_s13_menu_showcase.sql` 隐藏「系统监控 / 系统工具 / PLUS官网」（含 AI 残留叶子），保留「系统管理」；「挂号业务」置顶；只改 `visible`/`order_num`，附回滚 |
| 演示账号昵称 | `sys_user.nick_name` 由框架种子带入「疯狂的狮子Li」，会显示在患者端首页「<昵称> · 我的预约 ›」与后台顶栏 → 改为「演示管理员 / 测试账号A / 测试账号B」 |
| 侧栏配色 | `sideTheme: 'theme-light'`，去掉框架默认深蓝侧栏，与「深潭青 + 白卡」统一（admin `30d46f4`） |
| 示例页 | `views/demo`、`views/ai`、`views/workflow` 保留文件但不挂菜单（`admin/AGENTS.md` §13 已记） |

### 18.4 SpringDoc 实测

```
GET /v3/api-docs/1.门诊预约业务 → paths: 110
GET /v3/api-docs/2.系统与权限   → paths: 109
GET /v3/api-docs/3.通用能力     → paths: 10
GET /v3/api-docs/4.代码生成     → paths: 12
```

- 分组与 `contact` 已改项目口径，框架示例模块分组（`org.dromara.demo`）不再暴露；
- **本仓未引 `springdoc-openapi-starter-webmvc-ui`，`/doc.html` 与 `/swagger-ui/*` 不存在**
  （返回业务码 404，HTTP 200），README 与 DEMO 如实写「用 OpenAPI JSON 导入 Apifox/Insomnia」；
- 截图实例 `18082` 以 `dev,screenshot` 启动：`captchaEnabled:false`（主实例 8082 仍为 true），
  并关掉 `snail-job`（其端口公式 `2${server.port}` 在 18082 下溢出为 218082，启动即失败）。

### 18.5 文档物料

- `docs/DEMO.md`：5 分钟剧本（患者 7 步 / 分诊 4 步 / 管理端 5 步），每步含「看到什么」与「卡点怎么办」；
  附小程序真机截图清单（8 屏、750×1334、命名 `mp-<页面>-<状态>.png`）。
- `docs/adr/`：六篇 + 索引，每篇固定「背景 / 决策 / 后果 / 证据」，证据指向 `test-evidence` 章节或契约条款。
- `showcase/README.md`：门面，含四张内嵌截图、架构图、启动、账号、ADR 索引、已知边界。

### 18.6 15 秒 GIF（`assets/demo.gif`）

| 项 | 结果 |
|---|---|
| 命令 | `cd tools/screenshots && node gif.mjs` |
| 参数 | 视口 540×1170、12 fps、14 秒、**168 帧**、**5.0 MB**（上限 10 MB，超限自动降到 10/8 fps 与 480 宽） |
| 路径 | 首页 → 选院区 → 科室 → 医生 → 排班（选午别）→ 选时间，末尾停在「下一步」前 |
| 不提交订单 | 刻意不点提交：限购是「同一就诊人同一就诊日 1 单」，录一次就占额度，重复录会失败 |
| 登录不出现在画面里 | 先建**无录像**上下文登录，取 `storageState` 后开录像上下文，开场即首页 |
| 开头白屏 | 录像随上下文建立就开始，页面未渲染完是纯白 → 编码前按「非白像素占比 > 2%」自动裁掉前若干帧 |

**转码链路的两个硬约束（Playwright 自带 ffmpeg 是精简构建）**

1. `-muxers` 里**没有 gif**，`-filters` 里**没有 palettegen/paletteuse** → 不能一步出 GIF；
2. `fps` 滤镜初始化会失败（报 output file invalid）→ 用 `-r <帧率>` 代替。

因此实现为：`ffmpeg -r 12 -vf scale=540:-2 frames/%04d.png`（image2 导出）→ `fast-png` 解码 →
`gifenc` 逐帧 256 色量化编码。逐帧处理，不把 168 帧（每帧 2.5 MB RGBA）全读进内存。

### 18.7 未完成与边界

- `run.mjs --all` 目前等同 `--shots`（流程关键帧未单独出图，GIF 已覆盖主链路）。
- 小程序真机截图仍需手工（Playwright 无法驱动微信开发者工具），只交付清单。
- 小程序真机截图仍需手工（Playwright 无法驱动微信开发者工具），只交付清单。
- 门面 README 的本地路径按「四仓平级」书写，实际放置不同需自行调整。

---

## 19. S14 一键演示（2026-10-25）

> 目标：只有 Docker 的机器上「一条命令起全栈」，并按 tag 产出三个可独立 `docker run` 的镜像。本节只记实测数字与复现命令。

### 19.1 环境

| 项 | 值 |
|---|---|
| 宿主 | Linux（WSL2），Docker 29.7.2 / Compose v5.5.0（include 需 ≥2.20） |
| 端口说明 | 验收机同时跑着开发环境（8082/8083/8084/6380 被占用）。`./demo.sh` **无参**运行即自动避让为 **18082/18083/18084 + 16380**（MySQL 3307 / MinIO 9010-9011 本身空闲，保持默认），并把实际端口打印出来；若端口是显式指定的（`.env` 或 shell），脚本不擅自更换，直接报错给两种解法 |

### 19.2 构建与运行耗时

| 步骤 | 命令 | 结果 |
|---|---|---|
| 构建 admin | `cd admin && docker build -t ghcr.io/xcqj/appt-admin:latest .` | **29s**（依赖层命中缓存） |
| 构建 H5 | `cd app && docker build -t ghcr.io/xcqj/appt-h5:latest .` | **2m32s**（首次 pnpm 依赖 2m00s + `build:h5` 8.5s） |
| 构建 api | `cd backend && docker build -t ghcr.io/xcqj/appt-api:latest .` | **1m23s**（Maven 全量构建，含依赖下载） |
| 构建 snailjob | `cd backend && docker build -f Dockerfile.snailjob -t ghcr.io/xcqj/appt-snailjob:latest .` | **55s**（同 reactor，依赖已缓存） |
| 一键起全栈（首次） | `cd showcase && ./demo.sh` | **1m44s**，七步全绿 |
| 一键起全栈（复跑，无参） | `./demo.sh`（端口自动避让） | **1m24s**，七步全绿 |
| 一键起全栈（热态复跑） | `./demo.sh` | **58s**（镜像/数据/依赖已就绪，`--full` 幂等） |

### 19.3 镜像体积

| 镜像 | 体积 | 构成 |
|---|---|---|
| `ghcr.io/xcqj/appt-api` | **793 MB** | `eclipse-temurin:21-jre-jammy`（407 MB）+ 205 MB fat jar + fontconfig / DejaVu / curl |
| `ghcr.io/xcqj/appt-admin` | **109 MB** | `nginx:1.31-alpine` + `dist` |
| `ghcr.io/xcqj/appt-h5` | **95.1 MB** | 同上（H5 产物在 `dist/build/h5`） |
| `ghcr.io/xcqj/appt-snailjob` | **638 MB** | `eclipse-temurin:21-jre-jammy` + `ruoyi-snailjob-server` jar（控制台 8800 / gRPC 17888） |

### 19.4 健康检查结果

| 端点 | 检查 | 结果 |
|---|---|---|
| api | `GET /appt/public/campus/list` | 200，返回 3 个院区 |
| api | `GET /auth/code`（图形验证码） | 200，返回 `uuid` + `img`（base64 PNG，约 3.6 KB） |
| api 容器 | compose healthcheck（`curl` 打匿名接口） | `healthy` |
| admin | `GET /` 与 `GET /prod-api/appt/public/campus/list` | 200 / 200（nginx 运行时反代） |
| h5 | `GET /` 与 `GET /dev-api/appt/public/campus/list` | 200 / 200 |
| SnailJob 控制台 | `GET /snail-job/`（宿主 18800） | 200，控制台登录 `admin/admin` 可用 |
| admin 反代 | `GET http://<admin>/snail-job/` | 200（iframe 直连 compose 内 snailjob:8800） |
| 依赖 | `docker ps` | MySQL / Redis / MinIO / SnailJob 均 `healthy` |
| 建库自检 | `init-db.sh --full` 末尾 SQL | 排班 **500** / 号源 **9000** / 挂号单 **2000** / 支付单 **2000** / 账号 **5** |

### 19.5 独立 `docker run` 与参数外置

```bash
docker run -d --network qd-appt-demo_default -p 18092:8082 \
  -e APPT_DB_URL='jdbc:mysql://mysql:3306/appt?useSSL=false&allowPublicKeyRetrieval=true' \
  -e APPT_REDIS_HOST=redis ghcr.io/xcqj/appt-api:latest
```

- 该容器**只用环境变量**连库与 Redis，第 7 次探活即绪（约 14s）；
- 账号验证分两种口径（镜像默认「验证码开 + 接口加密开」，下面两种都不改仓库配置）：

| 口径 | 方法 | 结果 |
|---|---|---|
| 独立 `docker run` 连通性 | 临时 `CAPTCHA_ENABLE=false` + `API_DECRYPT_ENABLED=false` | `admin` 200 / `appt_triage` 200，均有 `access_token` |
| **真实链路**（compose 实例） | 取 `/auth/code` 的 `uuid` → 从 Redis `global:captcha_codes:<uuid>` 读答案 → 按前端算法加密（`encrypt-key` = RSA(base64(aesKey))，body = AES-256-ECB+Base64）提交 | `admin` 200（token 444）/ `appt_triage` 200（token 355） |

- **地址确由运行时注入**：admin 容器 `APPT_API_UPSTREAM=http://127.0.0.1:1` → `/prod-api/...` 返回 **502**；改为 compose 默认的 `http://api:8082` → **200**。

### 19.6 复现（默认端口）

```bash
cd qd-appt/showcase
./demo.sh            # 首次拉/构建三镜像；之后复跑约 1 分钟；端口被占用会自动换并打印
./demo.sh down       # 停止，保留数据
./demo.sh reset      # 二次确认后删数据卷（bind mount 目录会提示手工清理）
```

端口想固定下来时（例如截图脚本要指向稳定地址），在 `showcase/deploy/.env` 写 `APPT_API_PORT=18082` 等键即可；
一旦显式写了，脚本就不再自动更换。

### 19.7 边界与已知问题

- 实测机端口被开发环境占用，故用备用端口验证；脚本默认 8082/8083/8084，全部可在 `showcase/deploy/.env` 覆盖。
- `ghcr` 推送无法在本地替代远端打 tag：三仓 `image.yml` 已就绪（tag 推 `v*` + `latest` + `sha-*`，手动触发默认只 build），本轮只验证 `docker build` 与 `docker run`。
- **验证码保持开启**：UI 登录仍需人工输入算术题；自动化验证见 §19.5（真实链路那行从 Redis 取答案，不改配置）。
- **musl/Alpine 基底踩坑（2026-10-25 修复）**：首版用 `bellsoft/liberica-openjre-alpine`，镜像内 fontconfig 与 DejaVu 齐全、`fc-match sans` 正常，但 JVM 仍抛
  `java.lang.RuntimeException: Fontconfig head is null, check your fonts or fonts configuration` → `GET /auth/code` **500**、登录页验证码裂图（`/appt/public/**` 等不碰 AWT 的接口不受影响，所以只有登录暴露）。
  改 glibc 基底 `eclipse-temurin:21-jre-jammy` + `fontconfig` + `fonts-dejavu-core`（并在 Dockerfile 注释里写明原因）后恢复；这是放弃 musl 小体积的唯一原因。
- `docker build` 会遍历 `backend/deploy/data`；容器写出的 root 属主目录不可读时 BuildKit 报 `permission denied` → `demo.sh` 用一次性 alpine 容器 `chmod -R o+rX` 兜底（`ensure_build_context_readable`）。
- 首次构建 api / H5 需联网下载 Maven 与 npm 依赖；完全离线只能使用已推送的镜像。
- **SnailJob 服务端已随 demo 发布**（S14 追加，见 §19.9）：`ghcr.io/xcqj/appt-snailjob` + compose 服务，客户端默认 `APPT_SNAILJOB_ENABLED=true`、连 `snailjob:17888`、namespace `dev`；只想跑三端时可置 `APPT_SNAILJOB_ENABLED=false` 并停掉该服务（定时任务仍可在后台「任务日志 → 手动执行」触发）。
- 小程序包不在镜像内：需真实 AppID 与微信开发者工具，归本地手验。

### 19.8 验收中发现并修掉的六处缺陷（2026-10-25）

| # | 现象 | 根因 | 修复 | 验证 |
|---|---|---|---|---|
| 1 | 登录页验证码裂图；`GET /auth/code` 500（`错误编号 xxx`） | musl（Alpine）JRE 的 fontconfig 不可用：库与 DejaVu 齐全、`fc-match` 正常，JVM 仍抛 `Fontconfig head is null`（详见 §19.7） | 运行时基底改 glibc `eclipse-temurin:21-jre-jammy` + `fontconfig` + `fonts-dejavu-core`，headless 显式开启 | `/prod-api/auth/code` 200（base64 PNG）；真实验证码 + RSA/AES 登录两账号 200 |
| 2 | 镜像后台侧栏只有二级（基础数据/排班管理…），点「基础数据」空白页 | `appt_s1_menus.sql` 只建到二级；**三级页面菜单与按钮是代码生成器在开发库里点出来的，没有任何脚本**，`--full` 后整棵子树缺失 | 新增 `appt_s14_menu_pages.sql`（从开发库固化 82 行：19 C + 63 F，按 id 区间先删后插，幂等）+ `appt_s2_menu_generate.sql`（补「生成排班」按钮），插入点在 `appt_s1_menus` 之后、`appt_s6a_seed` 之前 | 删库重跑 `--full` 后，与开发库逐 `parent_id` 对比 **diff 为空**（46 组一致）；Playwright 展开「挂号业务 → 基础数据」可见院区管理 / 收费标准 / 时段模板 / 医务人员 / 科室树 / 门诊类型 |
| 3 | `http://<api>/` 与登录通知出现上游框架名 | `IndexController` 用 `spring.application.name` 拼提示；`AuthController` 欢迎语硬编码 | 两处改为项目口径（「号源演示后端已启动…」「欢迎登录号源预约挂号管理后台」），不动逻辑 | `curl /` 返回新文案；Playwright 登录后通知文本为「凌晨好，欢迎登录号源预约挂号管理后台」 |
| 4 | 登录页输入框异常高（.el-form-item 152px；dev 46px） | **生产构建的 CSS 顺序**：Element Plus `.el-input .el-input__icon { height: inherit }`（0,2,0）排在 `SvgIcon` 组件样式之后，把 `.svg-icon { height: 1em }` 覆盖掉 → `<svg>` 退回替换元素默认 **300×150**，撑高整个输入框。dev 下组件样式后注入所以正常 | `SvgIcon/index.vue` 增加 `.svg-icon.el-input__icon` / `.svg-icon.input-icon`（含 scoped 属性，权重 0,3,0），尺寸不再依赖加载顺序 | 同视口 1440×900 下 `itemH` 由 152 → **46**，`.login-shell` 由 802 → **595**，与 dev 完全一致 |
| 5 | 侧栏缺「SnailJob 控制台」入口 | `appt_s13_menu_showcase.sql` 隐藏了「系统监控」顶级菜单，其下的「任务调度中心」（menu_id `1761400000000000120`，component `monitor/snailjob/index`）随之不可见 | `appt_s13_menu_showcase.sql` 第 5 段把它移到「运维对账」末尾并保持可见；admin 镜像 nginx 增加 `/snail-job/` 反代（`APPT_SNAILJOB_UPSTREAM`，默认 `http://host.docker.internal:8800`），compose 加 `host-gateway` | `getRouters` 返回 `运维对账 → 任务调度中心 [snailjob]`；`GET /snail-job/` 200 且返回 SnailJob 控制台 HTML（本机 8800 有服务端）；`/snail-job` 302 保留端口跳转 |
| 6 | 镜像后台侧栏为白色，dev 是深蓝，强刷也不变 | `admin/src/settings.ts` 在 S13 把 `sideTheme` 改为 `theme-light`；**布局设置按 origin 存 localStorage**，8083 里存着更早的 `theme-dark`，而 18083 里存着上一次访问留下的 `theme-light` —— 两边都在用缓存值，代码默认值根本没生效 | ① 默认改回 `theme-dark`；② `store/modules/settings.ts` 加一次性迁移（`layout-setting-version=2`）：只把旧缓存的 `sideTheme` 对齐到新默认，其余偏好保留，之后用户手切仍会记住 | 全新上下文：背景 **`rgb(17, 24, 39)`**；再模拟「旧缓存 = theme-light 且无版本标记」→ 刷新后 `stored=theme-dark`、`version=2`、背景 `rgb(17,24,39)` |

**关于「镜像样式与原样式不一致」的实测结论**：同一视口（1440×900、DPR 1、locale zh-CN）下分别打开 `localhost:8083`（dev）与 `127.0.0.1:18083`（镜像）的登录页，量得
`cardWidth=437`、`inputWidth=385`、`inputHeight=44`、`inputFontSize=14px`、`bodyFontSize=16px`、`bodyFontFamily=MiSans,…` **全部一致**；
后台侧栏默认深蓝（S14 按项目既有观感改回，浅色仍可切换）。截图尺寸差异来自浏览器缩放/截图缩放，非镜像构建差异。

### 19.9 SnailJob 服务端镜像与任务种子（2026-10-25 追加）

> 起因：`application-dev.yml` 里 `snail-job.enabled: true`，定时任务（放号/关单/爽约/置完成/对账）靠开发机上单独起的 SnailJob 2.0.2；镜像只有客户端，换机器就没人调度。本轮把服务端也容器化，并把开发期手工建的任务固化成 seed。

**镜像与端口**

| 项 | 容器内 | 宿主机默认 | 说明 |
|---|---|---|---|
| 控制台（Web） | 8800 | **18800** | context-path `/snail-job`，登录 `admin/admin` |
| 客户端 gRPC | 17888 | **27888** | 避开开发机常驻的 17888 |
| 构建 | `docker build -f Dockerfile.snailjob -t ghcr.io/xcqj/appt-snailjob:latest backend` | 55s / 638 MB | 与 api 同 reactor，多阶段 |

**任务种子（`appt_s14_snailjob_seed.sql`）**

| 任务 | 执行器 | 触发 | 说明 |
|---|---|---|---|
| 每日放号 | `apptReleaseJob` | cron `0 0 8 * * ?` | S2 滚动放号 |
| apptPaymentCloseJob | `apptPaymentCloseJob` | cron `*/30 * * * * ?` | S4 支付超时关单 + 号源回补 |

- 字段与开发库一致；`next_trigger_at` 在插入时重置为「次日同时刻」，**避免容器一起来就触发一次**改动演示数据；
- 顺手删掉 `ry_job.sql` 自带的 `demo-job`（本应用没有 `testJobExecutor`，留着只刷日志）；
- **登录页三个外链图标已隐藏**（官方邮箱 / Gitee / GitHub）：前端打在 `BOOT-INF/lib/snail-job-server-ui-*.jar` 里改不了源码，构建时解出 `admin/` 静态目录、向 `index.html` 注入 `.pt-24px .pt-12px.text-center{display:none}` 并以 `SPRING_WEB_RESOURCES_STATIC_LOCATIONS=file:/app/admin-override/,classpath:admin/` 让补丁目录优先 —— 直连 18800 与后台 iframe 都生效，登录与控制台功能不受影响。

**实测**

- `sj_job` = 2 条；`sj_job_executor` 注册到 **5 个业务执行器**：`apptCompleteJob` / `apptNoShowJob` / `apptPaymentCloseJob` / `apptReleaseJob` / `apptReconcileJob`；
- 控制台 `GET /snail-job/` 200，登录后首页显示命名空间 Development、组 `ruoyi_group`「总任务数 2」、在线机器 客户端 1 + 服务端 1；
- admin 的 `/snail-job/` 反代 200，后台「运维对账 → 任务调度中心」iframe 直接可用；
- **启动顺序有硬要求**：必须 `init-db.sh --full`（建 `sj_*` 表）之后再起 snailjob，否则服务端会持续报 `Table 'appt.sj_group_config' doesn't exist`（本轮实测先起会刷 172 条错误日志，表建好后自愈）。`demo.sh` 已把 SnailJob 放在第 ⑥ 步（建库之后）。

**未覆盖**：在控制台点「执行一次」的端到端触发（需要人工在 UI 里点，或后续补控制台 API 登录 + 触发脚本）；「任务日志 → 手动执行」这条不依赖 SnailJob 的路径在 S2/S4 已验收。

---

## 20. S15 医院感细节（2026-10-26）

> 目标：让患者端读起来像医院的患者服务入口，而不是一张演示表单。本节记三条质量门槛的实跑输出、四入口与八状态流程条的核对结果，以及本切片的边界。
> 本切片**不改后端接口与表结构**，全部内容落在 `app` 仓；本节不涉及 SQL 脚本与接口回归。

### 20.1 环境

| 项 | 值 |
|---|---|
| 包管理器 / 构建链 | pnpm；uni-app Compiler 5.24（vue3），`uni build -p h5` |
| 基线 | `app` @ `0d1298d`（S14 之后首次改动）；`docs` @ `fe7d90a` |
| 数据来源 | 仅复用 A1 `GET /appt/public/campus/list`（匿名、定长 3 项）；**零新增接口、零表结构改动** |

### 20.2 三条质量门槛（顺序不可换）

| # | 命令 | 实跑结果 |
|---|---|---|
| 1 | `pnpm type-check` | `vue-tsc --noEmit` 无输出，退出码 0 |
| 2 | `pnpm lint` | `Found 0 warnings and 0 errors.`（67 files / 96 rules / 16 threads） |
| 3 | `pnpm build:h5` | `DONE  Build complete.`（Compiler version: 5.24（vue3）） |

> `pnpm build` 不做类型检查，不能替代前两步（`app/AGENTS.md` §3）。

### 20.3 文档门禁

```text
== 文档一致性门禁 ==
  PASS [stale] 无过期表述
  PASS [status] §2 与 §3 状态一致（16 个切片）
  PASS [evidence] 章节编号连续（§1–§20）
  PASS [p1] P1 清单未残留已完成端点
  PASS [enum] 字典一致（全部一致 ✓）

结果：全部通过（0 项警告）
```

> 上表是 S15 当轮的输出快照；S15.1 补种后切片数变为 17、章节到 §21，属后续增量，不是本文数字漂移。

### 20.4 四入口核对

| # | 路径 | 预期 |
|---|---|---|
| 1 | 首页院区卡 → 「院区信息」 | 进院区详情；**不触发**选院区（不写 `store/booking`、不进科室）—— 靠 `@click.stop`（mp-weixin 编译成 `catchtap`） |
| 2 | 首页院区卡 → 卡主体 | 行为不变：写入 `store/booking` 后进选科室 |
| 3 | 我的 → 「院区与就诊指南」 | 未登录也渲染、可进；落就诊指南（院区 3 行 + 规则入口 + 急诊提示 + 页脚） |
| 4 | 就诊指南 → 院区行 / 规则卡 | 分别进院区详情（`?campusId=`，字符串传参）/ 须知与规则 |
| 5 | 首页「查看预约须知 ›」 | 直接进须知与规则（不经就诊指南） |

> 浏览器与小程序肉眼验收由用户在演示环境执行（`app` dev 8084 → 后端 8082）；本节记录的是代码路径与门禁结果。

### 20.5 预约详情八种状态 × 流程条

| 状态 | 流程条渲染 |
|---|---|
| `WAIT_PAY` | 预约已完成、支付为当前、其后未开始 |
| `BOOKED` | 预约 / 支付已完成、签到为当前 |
| `SIGNED` | 前 3 步已完成、候诊为当前 |
| `COMPLETED` | 五步全部已完成 |
| `CANCELED_ACTIVE` | 不点亮任何节点，只显示「本次预约已退号，就诊流程已终止」 |
| `CANCELED_PASSIVE` | 只显示「因医生停诊已退号，就诊流程已终止」 |
| `CLOSED` | 只显示「本次预约已关闭，就诊流程已终止」 |
| `NOSHOW` | 只显示「本次预约已爽约，就诊流程已终止」 |
| 未知状态 | 整条不渲染（宁可不显示，也不误报阶段） |

> 映射是纯函数 `utils/appt.ts::regStepProgress()`，节点名唯一出处是 `REG_STEPS`；首页流程条走静态模式（不传 `states`），不发请求、未登录可见。

### 20.6 页脚与急诊提示的作用域

| 组件 | 出现页面 | 明确不出现 |
|---|---|---|
| `AppFooter`「演示系统 · 数据虚构 · 不提供医疗服务」 | 首页 / 我的 / 就诊指南 / 院区详情 / 须知与规则（5 页） | 选时间、确认预约、支付（有 `.appt-bottom-bar` 固定条）、列表页 |
| `EmergencyTip`「急诊指引」 | 首页 / 预约详情 / 就诊指南（3 页） | 院区详情、须知与规则、挂号链路页 |

### 20.7 边界与已知取舍

- **不改后端**：三页只用 A1。院区联系电话 / 门诊时间 / 交通指引在契约与 `appt_campus` 中都不存在，落 `utils/campusProfile.ts` 的虚构常量，**按院区名称匹配**（雪花 id 换库或重置 seed 会变）；未命中走「请致电门诊服务台咨询」通用兜底，不编造具体线路。
- **静态页四态口径**：须知与规则为纯静态内容、无接口请求，按 `DESIGN §9.11` 先例不设骨架；就诊指南与院区详情走 `PageState` 四态（加载 / 正常 / 空 / 异常）。
- **首页流程条不发请求**：不为静态说明新增 B2 调用（未登录会 401 触发登录跳转，且首屏多一次网络等待）；三态只在详情页按 `status` 出。
- **未做**：Stitch 出图（结构简单，按 `DESIGN §13.1` 直接落 blueprint）；流程条的装饰性动效（红线 10 明令禁止）；`admin` / `backend` 任何改动；S16 部署相关内容。

### 20.8 验收发现（2026-10-26）

| # | 现象 | 判定 | 处置 |
|---|---|---|---|
| 1 | 预约详情「就诊医生」显示成 `演示医生36 PHYSICIAN` | **缺陷**：职称线值直接进 UI，违反 `DESIGN §8.1` 与红线 3（不出现英文代号与内部状态名） | 已修：改走 `titleLabel()` 中文映射（其余页面本来就都走它，只有这一处漏了） |
| 2 | 已完成的预约仍显示就诊码 | **不是缺陷**：契约 §4.3 规定 `visitCode` 在 `BOOKED / SIGNED / COMPLETED` 返回，`DESIGN §9.10` 的四态同口径 | 不改；验收说明里「已完成隐藏二维码」是我写错了 |
| 3 | 「我的预约」四个 tab 找不到已签到的预约 | **既有缺口**（S10 收窄留下）：tab 只有 待支付 / 已预约 / 已完成 / 退号·爽约，B2 一次只能查一个状态 | 登记为 **S15.2（未开始）**，含两个候选方案与验收样本 `RS70000003376` |

---

## 21. S15.1 SnailJob 任务补种（2026-10-26）

> 起因：开发库出现「就诊日已过仍显示已预约」。排查结论是**任务没注册**而不是数据算错——`sj_job` 只有 3 条，爽约扫描从未跑过。本节记排查证据、补种内容与自动触发的实测。

### 21.1 现象与证据（补种前）

```text
db_now = 2026-10-26 00:34
appt_registration：BOOKED 301 条，其中 time_point < now 的 299 条
                    最早 2026-10-21 11:20 / 最晚 2026-10-24 16:20
                    归属：造数虚拟账号 294 / admin 4 / appt_triage 1
NOSHOW 120 条，最后 update_time = 2026-10-21 22:04
sj_job 3 条：demo-job / 每日放号（0 0 8 * * ?）/ apptPaymentCloseJob（*/30 * * * * ?）
             → 无 apptNoShowJob / apptCompleteJob / apptReconcileJob
```

- 客户端 `snail-job.enabled=true` 连 `127.0.0.1:17888`，五个执行器在线，但**没有任何任务绑定 `apptNoShowJob`**；
- 详情页照常给就诊码是 `canShowVisitCode(BOOKED)=true` 的正常表现，不是前端缺陷（状态权威在服务端）。

### 21.2 补种内容

| id | job_name | cron | 首触发策略 |
|---|---|---|---|
| 2 | 每日放号 | `0 0 8 * * ?` | 次日（S14 既有） |
| 3 | `apptPaymentCloseJob` | `*/30 * * * * ?` | **30 秒后**（本片修正；原为「次日」，新环境会 24 小时不关单） |
| 4 | `apptNoShowJob` | `0 */5 * * * ?` | **下一个 5 分钟整点** |
| 5 | `apptCompleteJob` | `0 30 23 * * ?` | 次日 |
| 6 | `apptReconcileJob` | `0 0 3 * * ?` | 次日 |

首触发策略不同是有原因的：**爽约扫描与支付关单是「必须持续跑」的巡检**——前者延到次日的后果是演示当天过期单一直显示「已预约」（2026-10-26 实际踩到），后者延到次日会让新环境整整 24 小时不关单、不回补号源；**放号 / 置完成 / 对账**延到次日，因为它们会改动演示数据，容器一起来就触发不合适。

### 21.3 实测

| 项 | 结果 |
|---|---|
| 自动触发 | `apptNoShowJob` 于 **2026-10-26 01:00:00** 自动执行，批号 `J20261026000125`、`affected=0` |
| 自动重排 | 执行后 `next_trigger_at` 推进到 **01:05:00**（服务端按 cron 续排） |
| 任务日志序列 | `00:46:20 爽约=299/过期=2000` → `00:52:06 过期=2000` → `00:52:30 过期=1135` → `00:52:36 0` → `01:00:00 自动 0` |
| 单轮上限印证 | 每次最多 2000 条（`SCAN_BATCH_SIZE=100 × MAX_ROUNDS=20`），不足一批即收尾 → 3135 条过期号源需两轮 |
| 数据结果 | `BOOKED` 301 → **2**（均为未来单），过期残留 **0**；`NOSHOW` 120 → **419**；`appt_slot` 的 `EXPIRED` **5255**、「AVAILABLE 且时刻已过」**0**；`NOSHOW_RECORD` 站内信 **299** 封 |
| 主账号保护 | admin 名下 6 条测试单改归属虚拟账号 `1761400000000003199`（该账号无 `sys_user` 行）后，违约计数回到 `0+0`、未生成黑名单，admin 只剩 2 张未来单 + 1 张已关闭单 |
| 置完成（手动执行） | 批号 `J20261026000234`、`affected=206`，`SIGNED` 206 → **0**、`COMPLETED` 498 → **704** |
| 对账（后台「立即对账」） | 批次 `RC20261026000001`、耗时 **14950ms**、七查「发现 507 / 修复 507 / 告警 0 / 跳过 0」（R1 幽灵占号 505 + R3 补退 2，成因见 §21.5） |
| seed 幂等复验 | 改完后整份 seed 用「不提交事务」试跑：事务内正好 5 条、关单任务 `next_trigger_at` = 当时 +26~30s；断连回滚，dev 库一行未动 |

### 21.4 边界

- **只补任务定义**，任务代码与 cron 语义一行未改（仅补了 `ApptJobRunService` 的 javadoc 白名单注释）；
- `apptCompleteJob` / `apptReconcileJob` 的**手动执行**已验证（见 §21.3），**自动首触发**落在次日 `00:56:29`，之后才回到 23:30 / 03:00；本片「按 cron 自动跑」的直接证据只有爽约扫描那一条；
- 放号 / 置完成 / 对账仍是「次日同一时刻」首触发而非 cron 时刻首触发（S14 既有口径，本片不改）；
- seed 与 `ry_job.sql` 有顺序依赖：必须后执行（`init-db.sh --full` 第 80 行），否则 `sj_group_config` 不存在会插入失败；
- 数据侧的三处人工处置（跑扫描、改测试单归属）是**一次性运维动作**，不进 seed：任何环境重灌 `appt_s7_business_seed.sql` 后，过期 `BOOKED` 会由补种后的 `apptNoShowJob` 在 5 分钟内自愈。



### 21.5 观察：505 条幽灵占号来自「终态不释放号源」（本片未改）

对账批次 `RC20261026000001` 报 R1 幽灵占号 **505** 条，数字正好等于本轮两次终态流转的条数：

```text
299（BOOKED → NOSHOW）+ 206（SIGNED → COMPLETED）= 505
```

**成因**：`RegistrationStateService` 的终态边（`markNoShow` / `markCompleted`）只改挂号单状态与 `active_flag`，**不迁移号源**；`SlotStateService` 里 `TAKEN → EXPIRED` 的唯一调用点是 `reclaimGhost()`（对账 R1）。于是每次爽约 / 置完成都会留下「Slot 仍 `TAKEN`、但已无有效单」的行，等 03:00 对账才被扫掉。

**影响**：

- 患者侧无感（A7 只返回 `AVAILABLE`，余量只统计可约）；
- 对账噪音：R1 每天报几百条「发现 / 修复」，真正的脏数据会被淹没；
- 台账时间失真：`RELEASE` 记录落在**对账时刻**，不是状态流转时刻；
- 本轮 R1 修复后复查：`TAKEN` 507 → **2**、`EXPIRED` 5255 → **5760**、`AVAILABLE` 保持 **14500**（过期保护生效：已过时刻直接置 `EXPIRED`，不回池）。

**处置（2026-10-26，S15.3 已修）**：按本小节给过的候选修法落地 —— 新增 `SlotStateService.expireTaken()`（`TAKEN → EXPIRED`、余量 0、写台账），`markNoShow` / `markCompleted` 在同事务内调用；实测见 §23。本小节保留作问题溯源。

---

## 22. S15.2 已签到入口（2026-10-26）

> 来源：S15 验收时发现「已签到的预约在『我的预约』里没有入口」。本节记查询映射、行为核对与门禁输出；浏览器肉眼走查由用户在演示环境完成（需要一个 `SIGNED` 样本单，见 §22.5）。

### 22.1 环境与基线

| 项 | 值 |
|---|---|
| 基线 | `app` @ `0e44641`；`docs` @ `43b5e88` |
| 改动面 | 仅 `app/src/pages/registration/index.vue` + `app/DESIGN.md §9.9`；**零后端、零接口、零表结构** |
| 数据来源 | B2 `GET /appt/patient/registration/list?status=`（一次一个状态，契约 §4.2） |

### 22.2 查询映射（改后的四个 tab × 子状态）

| tab | 子筛选 | 传给 B2 的 `status` | 默认 |
|---|---|---|---|
| 待支付 | 无 | `WAIT_PAY` | — |
| 已预约 | **已预约 / 已签到** | `BOOKED` / `SIGNED` | 已预约 |
| 已完成 | 无 | `COMPLETED` | — |
| 退号·爽约 | 主动退号 / 停诊退号 / 已爽约 / 已关闭 | `CANCELED_ACTIVE` / `CANCELED_PASSIVE` / `NOSHOW` / `CLOSED` | 主动退号 |

- 子筛选行只在「当前 tab 有子项」时渲染（`v-if="currentSubs.length"`），两个 tab 共用同一套结构与样式；
- `queryStatus = currentSub || activeTab`，B2 **永远只收到一个状态**，没有并发合并查询；
- 子状态按 tab **记忆**上次所选（离开「已预约→已签到」去「已完成」再回来，仍是已签到）。

### 22.3 行为核对

| 项 | 改前 | 改后 |
|---|---|---|
| `SIGNED` 卡片动作 | 落进 `else` 分支 → 「再次预约」（错误） | 与 `BOOKED` 共用「查看就诊码」 |
| 已签到空态 | 「暂无预约记录 / 请选择科室与医生完成预约」（答非所问） | 「暂无已签到预约 / 到院签到后，预约会显示在这里」 |
| 外部落点进入 | — | 复位到该 tab 的默认子状态（支付成功「查看预约」不会被上次停留的「已签到」挡住） |
| 未登录 | 页内空态、不发请求 | 不变（`load()` 与 `resolveDefaultTab()` 都先判登录态） |

### 22.4 三条质量门槛（顺序不可换）

| # | 命令 | 实跑结果 |
|---|---|---|
| 1 | `pnpm type-check` | `vue-tsc --noEmit` 无输出，退出码 0 |
| 2 | `pnpm lint` | `Found 0 warnings and 0 errors.`（67 files / 96 rules） |
| 3 | `pnpm build:h5` | `DONE  Build complete.`（Compiler 5.24 vue3） |

### 22.5 手工走查清单（用户在演示环境执行）

1. 登录 admin → 底部「预约」→ 点「已预约」：出现两枚子筛选，默认选中「已预约」，列表仍显示 2 条未来单（`R20261023000008` / `R20261026000001`）。
2. 切「已签到」：显示 `RS70000003376`（绿色「已签到」标签），按钮为「查看就诊码」，点开能进详情并看到二维码。
3. 切「已完成」→ 再回「已预约」：仍停在「已签到」（记忆生效）；退出页面重进：回到「已预约」。
4. 走一遍「退号·爽约」四个子筛选与「待支付」tab，确认原口径未变。
5. 退出登录后进入该 tab 页：显示页内未登录态，**不发 B2 请求**（Network 里不应出现 `registration/list`）。

> 样本单 `RS70000003376` 现挂在造数虚拟账号 `1761400000000003199` 名下。验证前临时改归属、验完改回：
> `UPDATE appt.appt_registration SET user_id=1761100000000000001 WHERE registration_no='RS70000003376';`
> 改回：`UPDATE appt.appt_registration SET user_id=1761400000000003199 WHERE registration_no='RS70000003376';`

**实测（2026-10-26，用户走查）**：「已预约」tab 默认显示 2 条未来单；切「已签到」显示样本单（绿色「已签到」标签 + 「查看就诊码」按钮），点开能进详情；无数据时空态为「暂无已签到预约 / 到院签到后，预约会显示在这里」。通过。

> **为什么样本单要临时改状态**：01:49 手动跑「置完成」把全部 **206** 条 `SIGNED` 转成了 `COMPLETED`（`SIGNED` 归 0），而可预约窗口是「今日+1 ~ 今日+7」（PRD D1）、签到只在就诊当日 00:00 起 —— 当天既约不到今日号，也签不了未来单。因此只能把一条终态单临时改成 `SIGNED`（`active_flag=1`，与 `chk_reg_active` 一致）验证列表与详情，验完已复原为 `COMPLETED` / `active_flag=NULL` 并归还虚拟账号。明天 `R20261023000008` 到就诊日，可走真实链路（`appt_triage` 分诊台补签）复验。

### 22.6 边界

- 不改 B2 接口（仍一次一个状态）、不动详情页与其他 tab 的动作；
- 列表仍**不提供退号**入口（退号在详情页，受「就诊前一日 23:00」时限与二次确认约束）；
- 状态色沿用 `DESIGN §2.3`（`SIGNED` = `#2E9E6B`），本片未新增色值、字号或圆角；
- `DESIGN §9.9` 的「状态 → 动作」段原文与实现长期不符（写「其余只展示状态标签」），本片按实现订正，属文档纠偏而非行为变更。

---

## 23. S15.3 终态号源释放（2026-10-26）

> 起因：§21.5 观察到「爽约 / 置完成不迁号源，一天积出 505 条幽灵占号」。本节记修法、夹具与实测数字。

### 23.1 改动（3 个文件）

| 文件 | 改动 |
|---|---|
| `schedule/SlotStateService` | 新增 `expireTaken(slotId, registrationId)`：`TAKEN → EXPIRED`、清 `registration_id`、写 `EXPIRE` 台账、**余量 0**（不发缓存增量） |
| `registration/RegistrationStateService` | `markNoShow` / `markCompleted` 签名加 `slotId`，**CAS 命中（affected>0）后同一事务**调用 `expireTaken` |
| `job/ApptNoShowJobService`、`job/ApptCompleteJobService` | 查询多取 `ApptRegistration::getSlotId` 并传入，不额外查库 |

四条状态边互斥：退号走 `releaseToPool`（未到时刻回池 / 已过置过期，余量 +1 或 0）、停诊走 `suspendTaken`（`TAKEN → SUSPENDED`），都**没有**改成调用 `expireTaken`，因此不会重复写台账。

`expireTaken` 的 CAS 带 `registration_id`：重复调用、或号源已被对账 R1 回收时影响 0 行、不写台账。

### 23.2 夹具（回滚式，跑完任务自动回到原状态）

| 夹具 | 退回成 | 涉及行 |
|---|---|---|
| F1 爽约路径 | `BOOKED` + `active_flag=1`，slot `TAKEN` | 单 `R20261023000016`（id `2113351434572869633`）/ slot `1761500000000218114` |
| F2 置完成路径 | `SIGNED` + `active_flag=1`，slot `TAKEN` | 单 `RS70000003876`（id `1761500000000303876`）/ slot `1761500000000221606` |

两条都是造数虚拟账号 `1761400000000003199` 的历史单，`visit_date` / `time_point` 均在 10-24（已过），因此会被两条任务直接命中。

### 23.3 实测

| 步骤 | 结果 |
|---|---|
| 跑「爽约+号源过期扫描」 | `affected=1` → F1 单 `NOSHOW`、slot `EXPIRED`、`registration_id` 清空 |
| 跑「置完成」 | `affected=1` → F2 单 `COMPLETED`、slot `EXPIRED`、`registration_id` 清空 |
| 台账 | 两条 `EXPIRE`：`TAKEN → EXPIRED`，`create_time` = **02:47:13 / 02:47:59**（状态流转时刻，不再是 03:00 对账时刻） |
| 「立即对账」 | 批次 `RC20261026000002`：**907ms、七查全 0（发现/修复/告警/跳过 均 0）、新批次结果 0 行**；旧批次 `RC20261026000001` 的 507 行保留作历史 |
| 幽灵占号复核 | **0**（基线同为 0 —— 本轮证明「不再产生新的」，505 那批已由上一轮对账修掉） |
| 编译 | `mvn -pl ruoyi-modules/appt -am clean compile` → 退出码 0 |

### 23.4 边界

- 只处理 `NOSHOW` / `COMPLETED` 两条终态；退号、停诊、关单的释放路径一行未改；
- 不改对账口径（R1 仍保留兜底，真脏数据照样能修）；
- 余量语义不变：`TAKEN → EXPIRED` 恒 0，`AVAILABLE → EXPIRED` 才是 −1；
- 不改 A7 / B2 的查询条件与展示；
- 夹具是**一次性数据操作**（回滚到流转前状态），不进 seed；正常环境里这条边由真实流转触发。

---

## 24. 部署方案与 wsl 公网联调（S16.1 预研，2026-10-29）

> 定位：**不是切片验收**。S16.1 当时在 ROADMAP §2 仍是「未开始」；本节记录的是"部署形态的可行性已被证明"以及为此付出的调试成本。当时的镜像仍为本地构建、**GHCR 零推送**、没有任何部署流水线。**后续（2026-10-30）**：S16.1 已完成，四枚镜像改由 GHCR 提供，实测见 §25。

### 24.1 环境与基线

| 项 | 值 |
|---|---|
| 主机 | Windows 10 + WSL2 Ubuntu；主机内存 32G，WSL 分配 16G |
| Docker / Compose | 29.7.2 / v5.5.0 |
| 隧道客户端 | cloudflared 2026.10.5，systemd 服务 `enabled` |
| 部署栈 | `showcase/deploy` 的 `qd-appt-demo` 项目，7 个容器（mysql / redis / minio / snailjob / api / admin / h5） |
| 宿主端口 | api **18082** / admin **18083** / h5 **18084**（8082–8084 被开发态 `pnpm dev` 占用，`demo.sh` 按 +10000 避让） |
| 域名 | `qdappt.us.ci`（DNSHE 免费二级域名，到期 2027-10-29），NS 已托管到 Cloudflare 且 Active |

### 24.2 实测结果

| 环节 | 结果 | 复现命令 |
|---|---|---|
| DNS 委派 | 只返回两台 Cloudflare NS | `dig +short NS qdappt.us.ci @1.1.1.1` |
| 隧道连接 | 4 条 `Registered tunnel connection`（lax01 / lax05） | `sudo journalctl -u cloudflared -n 40 \| grep Registered` |
| 站点可达 | 两域名均 200，证书由 Cloudflare 边缘签发 | `curl -sI https://admin.qdappt.us.ci/` |
| 反代到 api | 匿名院区接口 `code:200` | `curl -s https://demo.qdappt.us.ci/dev-api/appt/public/campus/list` |
| 登录链路 | 算术验证码 + RSA/AES 加密登录成功（`admin/admin123`） | 浏览器人工 |
| 业务链路 | 下单 → Mock 支付成功 → 站内信 2 条（`BOOK_SUCCESS` / `PAY_SUCCESS`）→ 详情可打开 | `/dev-api/appt/patient/notice/list` 返回 `code:200` |
| SSE 通道 | `text/event-stream` 原样透传、`Cf-Cache-Status: DYNAMIC`、`:connected` 抵达 | DevTools → Network → `resource/message` |
| 开机自启 | `docker` / `cloudflared` 均 enabled | `systemctl is-enabled docker cloudflared` |

### 24.3 观察到的现象（已决定不改代码）

- **SSE 连接寿命约 55 s**：服务端心跳 `heartbeatInterval = 60 s`（`MessageProperties`），连接在首次心跳之前就被中间层按空闲回收；前端 `autoReconnect.delay = 5000`，表现为每 ~60 s 一轮重连。判定依据是重连时**重新做了 TCP+TLS 握手**（`Initial connection` + `SSL` 各 1.42 s），说明是对端断连而非前端主动 `closePush()`。
- 影响面：仅管理后台「实时提醒」；站内信落库（`appt_notice`）是兜底，业务功能不受影响。
- **2026-10-29 决定**：先记录不修。若将来要修，把 `message.heartbeat-interval` 调到 20 s 并重建 api 镜像——属后端仓改动，不放进工程化切片。

### 24.4 调试成本（供后续排期参考）

| 卡点 | 根因 | 频次 |
|---|---|---|
| Cloudflare 一直 Pending | DNSHE 侧只加 CF 的 NS、**没删**自己那两台（混合委派） | 一次 |
| Zero Trust 侧栏找不到 Tunnels | 2026 UI 已挪到账号级 `Networking > Tunnels` | 一次 |
| `cloudflared service install` 报已存在 | 旧 unit 残留，需先 uninstall | 一次 |
| `demo` 打不开 / `admin` 显示患者端 | **两条同名 `admin` Public Hostname**，`demo` 实际无路由 | 一次 |
| admin 域名报 Vite `Blocked request … allowedHosts` | 隧道指向 8083 的 `pnpm dev`，容器在 18083 | 一次 |
| PowerShell `curl -I` 报「驱动器 https 不存在」 | PowerShell 把 `curl` 别名成 `Invoke-WebRequest` | 一次 |
| 改完路由仍 404 | 浏览器缓存了 4xx 页面 | 每次改路由 |

> 结论：**"能不能公网演示"已经有答案（能）**；剩下的是工程化——镜像可复现、可回滚、可一键重来，不在本节范围。

---

## 25. S16.1 部署形态与 wsl 发布链（2026-10-30）

> 定位：**切片验收证据**。承接 §24 的手工联调，本节记录"拉同一镜像部署 + 可回滚 + 可重来"这条链真正跑通的数字。

### 25.1 交付物

| 仓 | 内容 |
|---|---|
| showcase | `deploy/compose.yml`（四应用，纯 image）、`compose.deps.yml`（MySQL/Redis/MinIO 快照）、`compose.wsl.yml`（18082/18083/18084，依赖仅回环）、`compose.cloud.yml`（依赖不发布 + mem_limit）、`compose.build.yml`（仅本地）；删除旧的 `docker-compose.yml`（含跨仓 `include`） |
| showcase | `deploy/deploy.sh`（up / adopt / down / rollback / backup / restore / status）、`.github/workflows/release.yml`、`demo.sh` 改多 `-f`、`.env.example` 扩充 |
| backend | `deploy/init-db.sh` 支持冒号分隔多份编排（单路径兼容） |

### 25.2 实测数字（wsl 目标，全部实跑）

| 场景 | 命令 | 结果 | 耗时 |
|---|---|---|---|
| 首次发布 | `./deploy.sh wsl up --tag v0.1.0` | 7 容器全 healthy + 5 条业务探针全绿；`.state/current` 写入 4 个镜像 digest | **39s** |
| 回滚 | `./deploy.sh wsl rollback` | 探针全绿，`current`/`previous` 正确互换 | **42s** |
| 前滚 | `./deploy.sh wsl up --tag v0.1.0` | 探针全绿 | **46s** |
| 备份 | `./deploy.sh wsl backup` | MySQL 761K + MinIO 7.4K | **1s** |
| 恢复 | `./deploy.sh wsl restore <dump>` | 停应用→灌库→起栈→探活全绿；行数前后一致 | **62s** |
| 公网 | `curl https://admin.qdappt.us.ci/prod-api/appt/public/campus/list` | `code:200`，发布/回滚期间两域名全程可访问 | — |
| CI 发布 | `release.yml` run #4（`deploy_target=wsl`, `tag=v0.1.0`） | preflight 37s + deploy 24s，**1m09s 全绿**；容器同 tag 幂等未重建 | **1m09s** |

恢复前后行数（同一 dump 灌回）：注册单 **2001** / 号源 **20040** / 支付 **2001** / 站内信 **122**，四项完全一致。

### 25.3 三个真问题（都是实跑才暴露的）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| 1 | `up` 在重建 redis 时崩：`Bind for 0.0.0.0:6380 failed: port is already allocated` | 开发态 `qd-appt-redis` 长期占 6380；演示栈此前靠 `demo.sh` 的 `+10000` 避让落在 16380，改成 compose 默认值后把既有栈顶掉了 | `compose.wsl.yml` redis 默认改 **16380**，并在 `deploy/.env` 钉死全部端口 |
| 2 | CI 部署后 api `Restarting`、admin/h5 卡在 `Created` | 从 `~/qd-appt-deploy` 起栈时 `${APPT_DATA_DIR:-../data}` 解析成 `~/data`（空目录），MySQL 在空库里初始化出"有库无表" | `deploy.sh` 加**数据目录守卫**（有 `.state/current` 但无 `$DATA_DIR/mysql` → 拒绝启动）；数据目录统一为绝对路径 `/home/user01/qd-appt-data` |
| 3 | run #1/#2 preflight 全红：`manifest inspect` 四枚全 401；修完后 `docker login` 报 `password is empty` | ① preflight 跑在托管 runner，读不到**别的仓**发布的私有包（本仓 `GITHUB_TOKEN` 无权限）② 只判 `vars.GHCR_PRIVATE` 没判 secret 存在 | preflight 改 `runs-on: [self-hosted, ...]`（用机器上的 `~/.docker/config.json`），并删除那个单开关登录步骤 |

### 25.4 边界

- `cloud` 目标只落了结构（`compose.cloud.yml` + `deploy.sh` 的 target 分支），**未在任何云主机上跑过**，归 S16.2；
- 同一 tag 重复发布是**幂等 no-op**（compose 判定无变化即不重建），所以"发布耗时"不含容器重启；
- SSE 连接约 55s 被中间层回收（§24.3）仍未修，与本次发布链无关；
- 镜像冷拉验证针对本机已缓存的四枚 `v0.1.0`：`docker manifest inspect` 四枚均命中，`pull` 成功后再 `up`。

### 25.5 冷启动演练（验证「只装 Docker 就能跑」仍成立）

> 动机：`demo.sh` 这条路最后一次验证是 S14，之后 compose 换成五件套、`init-db.sh` 也改过。面试最可能的一句是「现场跑一下」，所以必须证明它没坏。

| 步骤 | 做法 | 结果 | 耗时 |
|---|---|---|---|
| 双保险备份 | `./deploy.sh wsl backup` + 数据目录整体改名留档 | 逻辑 dump 784K + MinIO 8K；物理快照 253M | — |
| 停栈 | `./demo.sh down` | 7 容器与网络移除，数据目录改名后路径不存在 | — |
| **冷启动** | `./demo.sh`（无容器、无数据） | 八步全过：拉镜像 → 起依赖 → **`init-db --full` 建库建表灌 seed** → bucket → SnailJob → 三端 → 探活 | **122s** |
| 冷启动后数据 | SQL 计数 | 注册单 **2000** / 号源 **9000** / 支付 **2000** / 站内信 **0**；`R20261029%` 命中 **0**（确认是干净 seed，不含历史订单） | — |
| 回切原数据 | `down` → 删冷启动目录 → 移回快照 → `up --no-pull` | 五条探针全绿 | **39s** |
| 回切后数据 | SQL 计数 | 注册单 **2001** / 号源 **20040** / 支付 **2001** / 站内信 **122**；`R20261029%` 命中 **1** | — |

- 公网 `admin` / `demo` 两域名在冷启动期间与回切后均返回 **200**。
- 结论：「只装 Docker 即可起全栈」在五件套改造后**仍然成立**，`demo.sh` 未因 S16.1 的编排拆分而退化。
- 顺带修掉一处误导：`demo.sh down` 曾固定打印 `showcase/data`，而真实目录由 `APPT_DATA_DIR` 决定（提交 `f67f16a`）。

---

## 26. 整机重启后的自启复验（2026-10-30）

> 定位：**运维观察，不是切片验收**。S16.1 已在 §25 验收；本节只回答「Windows 重启后这套栈还在不在、算不算好、怎么最快确认」。
> 触发：OS 重启后第一次自检（`docker ps` 22 个容器，其中本项目 8 个）。

### 26.1 实测

| 环节 | 命令 | 结果 |
|---|---|---|
| 容器自启 | `docker ps --format '{{.Names}}' \| sort` | 22 个 running；qd-appt 相关 8 个 = 演示栈 7 + 开发态 `qd-appt-redis` |
| 容器状态 | `./deploy.sh wsl status` | 7 个全 `Up 3 minutes`（`CREATED 17 hours ago`，**容器未重建**，只是被 Docker 拉起）；admin/api/h5/mysql/redis/snailjob 均 `(healthy)`，minio 无 healthcheck 属正常 |
| 业务探活 | 同上 | 五项全绿：api 直连 / admin 首页 / api 经 admin 反代 / h5 首页 / api 经 h5 反代 |
| 数据目录 | 同上 | `/home/user01/qd-appt-data`，**266M**（`APPT_DATA_DIR` 绝对路径生效，未起空库） |
| 部署记录 | 同上 | **「当前版本 / 上一版本」均为空**（见 26.2 第 1 条） |

### 26.2 两个真问题（本轮暴露）

| # | 现象 | 根因 | 处置 |
|---|---|---|---|
| 1 | 栈在 §25.2 走过 `up` 并写入 `.state/current`，但从 `showcase/deploy` 跑 `status` 显示版本为空，`rollback` 会报「没有 .state/previous」 | `STATE_DIR="$DEPLOY_DIR/.state"`、`BACKUP_DIR="$ROOT_DIR/backup"` 都相对脚本自身位置：发布发生在 `~/qd-appt-deploy`（`release.yml` 第 114 行），查询发生在 `showcase/deploy`，**两处各一份记忆** | `deployment-cicd-plan.md` §7.6 第 4 条补「执行入口唯一」：固定用 `~/qd-appt-deploy`，`showcase/deploy` 只当源码与首次同步来源 |
| 2 | `curl -sI https://admin.qdappt.us.ci/ \| head -1` 输出 `HTTP/1.1 200 Connection established`，看着像站点 200 | 本机走 HTTP 代理，这一行是 curl 的 CONNECT 握手响应，真实状态行被 `head -1` 挤掉；**该行只证明代理通，不证明站点通** | `deployment-cicd-plan.md` §9.6 ⑦ 与 §10.5 A 段改为 `curl -sS --noproxy '*' -o /dev/null -w '%{http_code}'`；§9.6 故障对照表补该现象 |

### 26.3 结论与边界

- **自启链路成立**：`docker.service` + 各服务 `restart: unless-stopped` 使 7 个容器在重启后自动恢复，业务探活五项全绿，无需人工干预。
- **"容器在跑"不等于"部署记录在"**：`.state` 是发布记帐，不参与容器启动；缺它时栈可用，但 `rollback` 无落点——所以自检要看两样（容器 + `.state`）。
- 本轮只复验「容器 + 业务探活」，**公网与隧道未在本轮复测**，日常按 `deployment-cicd-plan.md` §9.6「日常运维五项」执行（属 S16.2 之前的运维动作）。
- 开发态（8082 后端 / 8083 admin / 8084 H5）是宿主机进程，**不在自启范围**，需手工起；演示栈占用 18xxx，两者互不冲突。
- `restart: unless-stopped` 对被**手动 `stop`** 过的容器不生效（Docker 语义）；本轮 22 个全部自启，说明此前无遗留 stop 状态。

---

## 27. 菜单入口归属修正与 seed 幂等审计（2026-10-30）

> 定位：**缺陷修复**，不是切片。承接 §22 问题 5（当时把「任务调度中心」移到「运维对账」下，属三级）。
> 触发：线上（18083）侧栏「运维对账」下只剩 5 项，缺「任务调度中心」；开发库（8083）却有。

### 27.1 根因（三层各错一点）

| 层 | 事实 |
|---|---|
| 数据 | 线上库 `sys_menu` 里 `menu_id=1761400000000000120` **整行不存在**（开发库存在，parent=2007） |
| 脚本 | `appt_s13_menu_showcase.sql` 第 5 段当时只写 `UPDATE ... WHERE menu_id=120` → 影响 0 行**静默通过**，脚本不报错 |
| 部署 | `--full` 新建库有该行（`ry_vue.sql` 插入 → s13 迁移），所以「新库正常」；线上那份是 §25.5 回切的历史库，该行被人工清理过 |

结论：不是页面或反代坏了，是 seed 用 `UPDATE` 兜底、默认目标行必然存在。

### 27.2 改动（1 个 SQL + 1 个部署脚本 + 两个库）

| 对象 | 改动 |
|---|---|
| `backend/script/sql/appt_s13_menu_showcase.sql` | 第 5 段改「`INSERT ... WHERE NOT EXISTS` + `UPDATE`」；归属由 `运维对账(2007) order 9`（三级）提到 **`挂号业务(2001) order 8`**（二级），并纠正 `path`/`component`/`perms` 漂移 |
| `backend/deploy/init-db.sh` | `BASE_FILES` 补 `appt_s14_menu_pages` / `appt_s2_menu_generate` / `appt_s13_menu_showcase`——`s1_menus` 清理时会删掉二级目录下的页面与按钮，缺这三份时开发机重跑一次默认模式就丢「19 个三级页面 + 任务调度中心」 |
| `backend/script/sql/appt_s1_menus.sql` | 清理段改**递归删整棵子树**（原版只删 2001–2008 的**直接**子节点：三级页面被删、F 型按钮留下变孤儿，其授权也一起变脏） |
| `backend/script/sql/appt_s0_cleanup.sql` | 补「清全局孤儿授权」：上游 `ry_vue.sql` 的 `sys_role_menu` 种子引用了不存在的菜单（`1761400000000011616` 段共 15 行），属框架自带脏数据 |
| 两个库 | 开发库（`blog-mysql/appt`）、线上库（`qd-appt-demo-mysql/appt`）各执行一次 |

### 27.3 实测

| 场景 | 做法 | 结果 |
|---|---|---|
| 开发库改归属 | `UPDATE ... parent_id=2001, order_num=8` | 回读 8 项：7 个 M 目录 + 1 个 C 页面 |
| 「行已存在」幂等 | 开发库整份重跑 s13 | 无重复插入，120 仍 `parent=2001 order=8` |
| 「行缺失」自愈 | 线上库整份执行 s13 | 补插成功，回读 `parent=2001 order=8` |
| 干净机全量 | `DB_NAME=appt_fullcheck` + `init-db.sh --full` | 排班 500 / 号源 9000 / 挂号 2000 / 支付 2000 / 账号 5；2001 下恰 8 项，120 无 2007 残留 |
| 开发机重跑 | 同一临时库再跑默认模式（`init-db.sh`） | 三级页面 **82 行**（19 C + 63 F）保留、`appt:schedule:add` 按钮 1 行、120 仍在二级 |
| 其余受检项 | `sys_oss_config` / `sys_client` | minio `status=Y`；app 客户端 `access_path` 四段齐全 |
| 孤儿数据 | 临时库连跑 `--full` + 默认模式两轮后查 | 孤儿菜单 **0**、孤儿授权 **0**（修前：`s1_menus` 留下一层 F 按钮孤儿；上游种子另有 15 行孤儿授权） |

临时库 `appt_fullcheck` 验完即删，未触碰 `appt` 库。

### 27.4 其余 seed 的审计结论

| 脚本 / 语句 | 风险 | 结论 |
|---|---|---|
| `appt_s13_menu_showcase.sql` 第 1–4 段 | `UPDATE` 依赖行存在 | 依赖 `ry_vue.sql` 固定的顶级菜单与 3 个演示账号，两库实测均命中；本轮未改 |
| `appt_s2_oss_config.sql` 的 `gen_table_column` UPDATE | 依赖 `gen_table` 有数据 | `appt_s1_gen_config.sql` 不在 `--full` 链路 → 干净机上必然 0 行空转；只影响代码生成器页（「系统工具」已被 s13 隐藏），**无业务影响**。附：该文件同一段 UPDATE+SELECT 重复两遍（可清） |
| `appt_e5_client_access.sql` | `UPDATE` 依赖 `client_key='app'` | `ry_vue.sql` 固定插入；两库实测都是 `/appt/**,/auth/**,/system/**,/resource/**` |
| `appt_s1_menus.sql` | 删除只覆盖一层，且不清子树授权 | **已修**：改递归 CTE 删整棵子树，并在删菜单前先清子树内的 `sys_role_menu`（实测连跑两轮后孤儿菜单、孤儿授权均为 0） |
| `ry_vue.sql` 的 `sys_role_menu` 种子 | 引用不存在的菜单（`1761400000000011616` 段 15 行） | 上游自带脏数据，功能上不影响（超管旁路），但角色授权树会出现幽灵勾选 → 由 `appt_s0_cleanup.sql` 新增的「清全局孤儿授权」处理 |
| `appt_s2_menu_cleanup` / `s2_menu_order` / `s2_gen_column_fix` / `s1_gen_config` / `s3_patient_seed` | 不在任何清单 | 开发期一次性脚本，按需手工执行，不属两条链路 |

### 27.5 边界

- 未改前端、未改 nginx 反代，`/snail-job/` 链路不变；
- 线上生效需**退出重登**（`getRouters` 在登录/路由守卫时拉取）；
- 该页仍是 iframe，SnailJob 服务端未起时 502 属预期；
- 层级变更只影响侧栏观感与面包屑，`monitor:snailjob:list` 权限位数不变。
