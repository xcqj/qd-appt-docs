# 号源 QueueDepth · 项目文档（qd-appt-docs）

> 本目录 = 远端 `qd-appt-docs` 仓的检出内容（建仓后），是项目级文档的唯一权威源。
> 命名：中文名「号源」/ 英文代号 QueueDepth / 代码缩写 `appt`（PRD D10，使用规则见 PRD §14.1.1）。

## 这个项目是什么

单医院 + 多院区门诊预约挂号系统（求职演示项目）：患者端 uni-app 一套代码双角色（患者 / 分诊台，PRD D3）+ plus-ui 管理后台 + RuoYi-Vue-Plus 后端（业务模块 `appt`，包 `org.dromara.appt`，表前缀 `appt_`）。与项目一（sd-blog / StackDepth）完全独立，命名与之形成 Stack / Queue 对偶。

**合规声明**：全部数据虚构，不使用真实医院/科室/医务人员名称；不问诊不诊断不开放；支付仅 Mock 渠道。各仓 README 必须带「技术演示 / 虚构数据 / 不提供医疗服务」声明。

## 仓库地图

父目录 `qd-appt/` 不是 Git 仓库；四个仓同级 clone 于其下：

| 本地目录 | 远端仓库 | 角色 | 状态 |
|---|---|---|---|
| `backend` | `qd-appt-backend` | 后端（RuoYi-Vue-Plus + 模块 `appt`） | 待建仓 |
| `admin` | `qd-appt-admin` | 管理后台（plus-ui / Vue3） | 待建仓 |
| `app` | `qd-appt-app` | 移动端（uni-app，患者 + 分诊台双角色） | 待建仓 |
| `docs` | `qd-appt-docs` | 本目录：项目级文档 | 待建仓 |

一次 Agent 会话原则上只动一个仓库；构建只在各仓库目录内执行，**不在父目录跑 `mvn` / `npm`**（父目录不受 .gitignore 保护，游离产物长期残留）。

## 文档地图

| 文档 | 权威范围 | 状态 |
|---|---|---|
| `PRD.md` | 业务规则 / 状态机 / 接口清单 / 非功能 / 决策记录（产品视角唯一权威，v0.5） | 已建 |
| `技术方案.md` | 六难点实现方案 / 核心不变量 / 对账 / 配置 / 索引（实现视角唯一权威，v0.3） | 已建 |
| `redlines.md` | 红线全集（建仓时拆分复制进各仓 `AGENTS.md`） | 已建 |
| `api-contract.md` | API 契约：四层边界、请求响应、错误码、权限标识 | **待建（契约先行：实现前先立）** |
| `database-design.md` + `appt_schema.sql` | 库表设计 + 建表 SQL | 待建（S1） |
| `architecture.md` | 模块图、请求链路、部署拓扑、拆分预案 | 待建 |
| `ROADMAP.md` | 切片排期 + 决策记录 | 待建 |

## 阅读顺序（新会话 / 新人）

1. 本 README（地图）→ `redlines.md`（红线）
2. `PRD.md` §14 决策记录 → §4 数据模型 → §6 业务规则
3. `技术方案.md` §1 总体架构 / §2 核心不变量 → 按任务读 §3 对应难点
4. 动手前读目标仓自己的 `AGENTS.md`（建仓后存在；红线已在其内，勿只依赖本目录）

## 多根工作区

`appt.code-workspace`（本目录根）：`code ~/projects/qd-appt/docs/appt.code-workspace`。
四个 folder：`../backend`、`../admin`、`../app`、`.`（本目录）。仓未建时缺失的 folder 由 IDE 容忍，不影响打开。

## 纪律

- **改任何红线**：同步 `redlines.md` + 所有仓的 `AGENTS.md`（建仓后）——这是多仓文档结构唯一的真实成本，用纪律换。
- **文档冲突时**：业务规则以 PRD 为准、实现手段以技术方案为准；冲突先报告，由最新明确决定裁决。
- 本目录文件**不被 AI 工具自动加载**（项目一已验证）——关键约束必须落在各仓 `AGENTS.md`，这是红线要在建仓时落进各仓的原因。
