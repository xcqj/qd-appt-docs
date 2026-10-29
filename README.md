# 号源 QueueDepth · 项目文档（qd-appt-docs）

> 本目录 = 远端 `qd-appt-docs` 仓的检出内容（建仓后），是项目级文档的唯一权威源。
> 命名：中文名「号源」/ 英文代号 QueueDepth / 代码缩写 `appt`（PRD D10，使用规则见 PRD §14.1.1）。

## 这个项目是什么

单医院 + 多院区门诊预约挂号系统（求职演示项目）：患者端 uni-app 一套代码双角色（患者 / 分诊台，PRD D3）+ plus-ui 管理后台 + RuoYi-Vue-Plus 后端（业务模块 `appt`，包 `org.dromara.appt`，表前缀 `appt_`）。与项目一（sd-blog / StackDepth）完全独立，命名与之形成 Stack / Queue 对偶。

**合规声明**：全部数据虚构，不使用真实医院/科室/医务人员名称；不问诊不诊断不开放；支付仅 Mock 渠道。各仓 README 必须带「技术演示 / 虚构数据 / 不提供医疗服务」声明。

## 仓库地图

父目录 `qd-appt/` 不是 Git 仓库；**五个仓**同级 clone 于其下（S13 起新增门面仓）：

| 本地目录 | 远端仓库 | 角色 | 状态 |
|---|---|---|---|
| `backend` | `qd-appt-backend` | 后端（RuoYi-Vue-Plus + 模块 `appt`） | 已建（框架基线 + 工程基线 + S1 表结构） |
| `admin` | `qd-appt-admin` | 管理后台（plus-ui / Vue3） | 已建（框架基线 + dev 代理 8082） |
| `app` | `qd-appt-app` | 移动端（uni-app，患者 + 分诊台双角色） | **功能完成（S10/S11 于 2026-10-22/23 收口）**：患者 9 屏 + 辅助 4 屏 + 分诊台 3 项（签到/当日/停诊），小程序真机扫码已验收；视觉打磨归 **S12/S12.5** |
| `docs` | `qd-appt-docs` | 本目录：项目级文档 | 已建 |
| `showcase` | `qd-appt-showcase` | **门面与物料仓**（S13 起）：README、脚本产出的截图与 GIF、`tools/screenshots`、一键演示 `demo.sh` + `deploy/` | 已建（S13；S14 增一键演示，2026-10-25） |

一次会话围绕**一个切片或一个明确目标**：切片必须由用户显式开启（规则见 `AGENTS.md` §1）；跨仓改动按仓**分别提交**。构建只在各仓库目录内执行，**不在父目录跑 `mvn` / `npm`**（父目录不受 .gitignore 保护，游离产物长期残留）。

## 文档地图

| 文档 | 权威范围 | 状态 |
|---|---|---|
| `PRD.md` | 业务规则 / 状态机 / 接口清单 / 非功能 / 决策记录（产品视角唯一权威，v0.5） | 已建 |
| `技术方案.md` | 六难点实现方案 / 核心不变量 / 对账 / 配置 / 索引（实现视角唯一权威，v0.3 + S2–S8 增补） | 已建 |
| `redlines.md` | 红线全集（建仓时拆分复制进各仓 `AGENTS.md`） | 已建 |
| `AGENTS.md` | **跨仓协作协议**：切片闸门 / 开场卡与阅读回执 / 最小必读集 / 收尾与判定标准 / 环境事实 | 已建 |
| `api-contract.md` | API 契约：四层边界、端点条目、16 个业务错误码、权限标识、状态边界矩阵（实现视角，v0.1 已定稿；P0 端点全部落地，仅剩 B8–B10 / C4 / E4 / F8–F30 待补） | 已建 |
| `database-design.md`（本仓）+ `appt_schema.sql`（backend 仓 `script/sql/`） | 库表设计（字段级唯一权威）+ 建表 SQL（20 表已在 `appt` 库验证） | 已建 v0.1（S1） |
| `ROADMAP.md` | **切片排期单一权威**：切片顺序 / 验收口径 / 进度与时间戳 / 待决项（PRD §13.1-13.2 只管范围与边界，不管排期） | 已建 **v0.7.9**（S1–**S16.1** 完成；S16.2 云目标与公网 HTTPS 未开始，阻塞于服务器） |
| `DEMO.md` | **5 分钟演示剧本**：患者下单 → 支付 → 就诊码 → 分诊签到 → 停诊两段式 → 看板与对账，逐步写「点哪里 / 看到什么 / 卡点怎么办」；附录小程序真机截图清单 | 已建（S13） |
| `adr/` | **架构决策记录**六篇（限购口径 / 停诊两段式与批号幂等 / `active_flag` 与唯一索引 / `scopeValue` 复合键 / `timePoint` 口径 / 三层防线）+ 索引 | 已建（S13） |
| `test-evidence.md` | **测试证据**：各切片实测数字与复现命令（交付验收材料，随切片追加） | 已建（§1–**§25**，S2–S16.1） |
| `deployment-cicd-plan.md` | **部署与 CI/CD 方案**：现状核查 / 工具选型 / `wsl`↔`cloud` 目标切换 / 工作流草案 / 风险与分阶段清单（**只写「怎么做」，进度以 `ROADMAP.md` 为准**） | 已建（2026-10-29） |
| `script/doc_audit.py` | **文档一致性门禁**：过期表述 / §2–§3 状态传播 / 证据章节编号 / P1 清单 / 字典审计（收尾必跑，见 AGENTS §5） | 已建 |
| `architecture.md` | 模块图、请求链路、部署拓扑、拆分预案 | 待建 |

## 阅读顺序（新会话 / 新人）

- **排期与进度**看 `ROADMAP.md`；做什么 / 不做什么看 `PRD.md` §13.1-13.2
1. 本 README（地图）→ `redlines.md`（红线）
2. `PRD.md` §14 决策记录 → §4 数据模型 → §6 业务规则
3. `技术方案.md` §1 总体架构 / §2 核心不变量 → 按任务读 §3 对应难点
4. 动手前读目标仓自己的 `AGENTS.md`（建仓后存在；红线已在其内，勿只依赖本目录）
5. **新会话开场**：先按本目录 `AGENTS.md` §2 输出「开场卡」，模板见 §4；切片闸门见 §1（一片做完即停，不自动进入下一片）

## 多根工作区

`appt.code-workspace`（本目录根）：`code ~/projects/qd-appt/docs/appt.code-workspace`。
四个 folder：`../backend`、`../admin`、`../app`、`.`（本目录）。仓未建时缺失的 folder 由 IDE 容忍，不影响打开。

## 纪律

- **改任何红线**：同步 `redlines.md` + 所有仓的 `AGENTS.md`（建仓后）——这是多仓文档结构唯一的真实成本，用纪律换。
- **文档冲突时**：业务规则以 PRD 为准、实现手段以技术方案为准、字段以 database-design 为准、
  **排期与验收以 ROADMAP 为准**；冲突先报告，由最新明确决定裁决。
- 本目录文件**不被 AI 工具自动加载**（项目一已验证）——关键约束必须落在各仓 `AGENTS.md`，这是红线要在建仓时落进各仓的原因。

---

## 启动与演示（2026-10-21 S7 交付；2026-10-24 S13 补门面入口）

> **只想看效果**：先读门面仓 `../showcase/README.md`（含架构图、10 张脚本截图、14 秒 GIF），
> 再按 `DEMO.md` 走 5 分钟剧本；只想跑起来照着下面做，账号 `admin / admin123`（患者与后台）、`appt_triage / admin123`（分诊）。
>
> 依赖容器编排（`docker-compose`）已由工程基线 **E2** 交付，见 `backend/deploy`（端口 3307 / 6380 / 9010-9011）；下面第 1 步为等价的手工操作，供不用容器时参照。
> 演示数据全部虚构，仅 Mock 支付渠道，不提供任何医疗服务。
>
> **一条命令（S14，推荐）**：机器上只有 Docker 也行——五个仓同级 clone 后执行 `cd showcase && ./demo.sh`。
> 脚本负责拉/构建三镜像、起依赖、`init-db.sh --full` 建库导数据、起三端并逐端探活，就绪后打印地址与账号；
> **端口无需手填**：默认 `8082/8083/8084`，被占用时按 `+10000` 自动换到空闲端口并打印实际地址。
> `./demo.sh down` 停止、`reset` 清数据。下面的 0–5 步是**手工等价操作**，供不用容器或逐步排查时参照。

### 0. 前置（容器）

| 组件 | 用途 | 本地约定 |
|---|---|---|
| MySQL 8 | 业务库 `appt` | 容器 `blog-mysql`，账号 `root/root` |
| Redis 7 | 占位键 / 余量缓存 / Sa-Token / 幂等键 | 容器 `qd-appt-redis`（`backend/deploy`，宿主机 `6380`），db `1`，密码 `ruoyi123` |
| MinIO | 图片对象存储（院区封面 / 医生头像 `ossId`） | `127.0.0.1:9000` |
| SnailJob 2.0.2 | 定时任务调度台（放号 / 关单 / 爽约 / 置完成 / 对账） | **demo compose 自带**：控制台宿主 `18800`，账号 `admin/admin`；手工跑时按官方发行包单独部署（`8800`），组 `ruoyi_group` |

### 1. 建库并导入脚本

**一键（推荐，E2）**：`backend/deploy` 里已备好 compose 与导入脚本（端口 3307 / 6380 / 9010-9011，刻意错开宿主机上其它项目的 3306 / 6379 / 9000）：

```bash
cd backend/deploy
docker compose up -d     # MySQL 8.4 / Redis 8 / MinIO（SnailJob 需按官方发行包单独部署）
./init-db.sh             # 等健康检查 → 按序导入 8 个 SQL → 打印规模自检
```

若端口或密码与本机不符，改 `docker-compose.yml` 的 `ports` 并同步 `application.yml`（`spring.datasource.url` / `spring.data.redis.port`）。
不想起容器时，也可对已有实例执行 `MYSQL_PORT=3306 ./init-db.sh`。

**手工（等价，按顺序）**：

```bash
cd backend/script/sql
mysql -uroot -proot appt < appt_schema.sql          # 表结构
mysql -uroot -proot appt < appt_s1_seed.sql         # 基础数据（院区/科室/人员/收费标准/模板）
mysql -uroot -proot appt < appt_s1_menus.sql        # 菜单与权限
mysql -uroot -proot appt < appt_s3_patient_seed.sql # 联调账号 appt_patient + 就诊人
mysql -uroot -proot appt < appt_s6a_seed.sql        # triage 角色/账号 + 签到权限
mysql -uroot -proot appt < appt_s6b_seed.sql        # 停诊处理权限
mysql -uroot -proot appt < appt_s7_seed.sql         # 看板菜单 + 对账/看板权限
mysql -uroot -proot appt < appt_s7_business_seed.sql # 演示业务数据（500 排班 / 9000 号源 / 2000 单，约 45s）
```

> `appt_s7_business_seed.sql` 会**清空业务表**（挂号/支付/退款/台账/任务日志/对账结果/站内信/停诊登记/排班号源），
> 保留基础数据、账号与就诊人；可重复执行。演示顺序：**先灌 seed，再跑对账/看板**（否则对账记录会被清掉）。

### 2. 起后端

```bash
cd backend
mvn -pl ruoyi-admin -am package -DskipTests
java -jar ruoyi-admin/target/ruoyi-admin.jar          # 8082
```

自检：`curl -s http://127.0.0.1:8082/appt/public/campus/list` 应返回 3 个院区。

### 3. 起管理后台

```bash
cd admin
pnpm install
pnpm dev                                              # 8083，dev 代理已指向 8082
```

超管登录 `admin`（密码见框架初始化脚本）。

移动端（`app` 仓，可选）：

```bash
cd app
pnpm install
pnpm dev:h5        # H5：http://localhost:8084（/dev-api 代理到 8082）
pnpm dev:mp-wsl    # 小程序：产物输出到 D:\programming\project\appt-app，开发者工具导入该目录
```

- `dev:mp-wsl` 供「源码在 WSL、开发者工具在 Windows」使用；小程序端不走 vite 代理，脚本把 `VITE_APP_BASE_API` 默认为 **`http://<本机网卡>:18082`**（经 `netsh portproxy` 转到 WSL 的 8082；**别用 8082，会被 Windows 上的 QQ 占用**，详见 `app/README` §2.1 与 `test-evidence` §15.4），路径与地址可分别用 `APPT_MP_OUT_DIR` / `APPT_MP_BASE_API` 覆盖；
- 开发者工具导入后勾「不校验合法域名、web-view、TLS」。

### 4. 演示入口

| 角色 | 入口 | 能演示什么 |
|---|---|---|
| 匿名患者 | `GET /appt/public/**`（A1–A7） | 院区 / 科室树 / 医生 / 日期栏 / 当日出诊+余量 / 可约时间点 |
| 患者 | `/appt/patient/**`（B1/B2/B3/B5） | 挂号（三道防线 + 限购 + 黑名单）→ 支付（Mock）→ 我的预约 → 退号（退款） |
| 分诊 | `/appt/triage/**`（E1/E2/E5） | 扫码签到 / 手动补签 / 停诊上报 |
| 后台 | 排班管理 / 停诊登记 / 挂号单 / 退款单 / 黑名单 / 任务日志 / **对账结果** / **数据看板** | 排班生成与余量、停诊两段式、手动退号、退款、黑名单解除、任务手动重跑、**七查对账**、**7 指标看板** |

### 5. 验收脚本（`backend/script/test/`）

| 脚本 | 覆盖 |
|---|---|
| `s3_b1_concurrency.sh` | 集成测试① 并发争抢 / 幂等 / **限购「同一就诊人同一就诊日 1 单」**（2026-10-23 改口径） |
| `s4_payment.sh` | 集成测试②③ 关单回补 / 回调幂等 / 钱到了号没了 |
| `s5_read_bench.sh`、`s5_remain_consistency.sh` | 单屏 SQL 次数与分位 / 集成测试⑤ 缓存一致性 |
| `s6a_state_machine.sh` | 集成测试⑥ 退号 / 签到 / 爽约兜底 / 置完成 |
| `s6b_suspend_blacklist.sh` | 停诊两段式与幂等 / 黑名单拦截 |
| `s7_reconcile.sh` | 七查构造与修复 / 二次跑归零 / 耗时 |
| `s8_patient_aux.sh` | 收藏 D1–D3 / 消息 D4–D6 / E3 签到列表 / 三类站内信 |
| `s9_patient_crud.sh` | 就诊人 B6–B10（含 10 人上限、越权 404、设默认幂等） |

留档数字见 `test-evidence.md`（§3–§10）。
