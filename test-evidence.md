# 测试证据（S2 / S3）

> 目的：把「设计承诺」变成「可复核的数字」。每条 = 场景 → 复现命令 → 实测输出 → 结论。
> 环境：backend `084fbe0`+（2026-10-20 本地），MySQL `appt`、Redis db1、患者账号 `appt_patient`、单机 50 并发。
> 复现入口：`backend/script/test/s3_b1_concurrency.sh`（前置与取 token 见 `backend/script/test/README.md`）。

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
