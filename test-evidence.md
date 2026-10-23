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
| `s3_b1_concurrency.sh` | `PASS=14 FAIL=0 SKIP=0`（50 并发仍 1 成交、幂等、限购三条、窗口外） |
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
| `dev:mp-wsl` 的 baseApi | 默认 `http://localhost:8082`（真机指手机自己）；曾一度被改成本机 IP 时误删成 `http://:8082` → 微信报 `invalid url "http://:8082/..."` | 默认改为本机网卡 `http://192.168.0.108:8082`，可用 `APPT_MP_BASE_API` 覆盖 |

### 15.4 WSL2 下让手机访问后端（Win10 无 `networkingMode=mirrored`）

- 手机 → Windows 网卡 → WSL 需要 `netsh interface portproxy`，且 `connectaddress` **必须填 WSL 的 IPv4**（如 `172.31.124.129`）。填 `127.0.0.1` 会失败：Windows 的 `localhost` 优先走 `::1`，WSL 的 localhost 转发落在 IPv6 回环，IPv4 回环上没有监听（实测 `127.0.0.1:8082` 不通、`localhost:8082` 通）
- WSL 重启后 IPv4 会变，`portproxy` 需重加；长期方案是 Win11 的 `networkingMode=mirrored`
- 验证顺序：手机浏览器先打开 `http://<局域网IP>:8082/appt/public/campus/list` 看到 JSON，再开小程序

### 15.5 遗留

- `utils/encrypt.ts` 顶层 import `jsencrypt`（依赖 `window/navigator`）。真机未复现（该库内部有 `typeof navigator` 守卫），但只在登录时用，后续应改 `await import('jsencrypt')` 动态加载，避免进启动链路
- 扫码签到本机已验证到「登录 + 页面可渲染」，**扫码动作本身待真机复测**（需真实 AppID + 后端可达；`manifest` 里的 AppID 属个人配置，不入库）
