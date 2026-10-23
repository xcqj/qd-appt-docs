#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档一致性门禁（docs/script/doc_audit.py）

为什么需要它：本项目每片都要同步 6 个文档位置（ROADMAP §2/§3/§3.9/§5/§8 + 契约 + test-evidence），
靠"记得改"必然漏。本脚本把「容易忘、忘了不报错」的四类问题变成可执行检查：

  1. 未来时残留     —— 已完成切片里还写着「待实测 / 待填 / 待点检 / 仍留 E2 / 本期结束」
  2. 状态传播       —— ROADMAP §2 状态列与 §3 的 [x]/[ ] 不一致
  3. 章节编号       —— test-evidence 的 ## N. 重复或断号
  4. P1 清单过期    —— 契约 §10 的 P1 列表里仍列着已转正的端点

外加复用 backend 的字典审计（枚举线值/注解/文档语料）。

用法：
  python3 script/doc_audit.py            # 全量检查，失败退出码 1
  python3 script/doc_audit.py --verbose  # 打印每条命中的原文行
"""

import os
import re
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
VERBOSE = "--verbose" in sys.argv

RED, GREEN, YELLOW, DIM, RESET = "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[0m"

failures = []
warnings = []


def fail(check, msg, lines=None):
    failures.append((check, msg))
    print(f"  {RED}FAIL{RESET} [{check}] {msg}")
    if VERBOSE and lines:
        for n, text in lines[:8]:
            print(f"        {DIM}{n}: {text.strip()[:120]}{RESET}")


def warn(check, msg):
    warnings.append((check, msg))
    print(f"  {YELLOW}WARN{RESET} [{check}] {msg}")


def ok(check, msg):
    print(f"  {GREEN}PASS{RESET} [{check}] {msg}")


def read(name):
    p = DOCS / name
    if not p.exists():
        fail("files", f"缺少文档 {name}")
        return ""
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 1. 未来时残留
# 只收「明确已经过期就一定是假话」的短语，避免误伤「待支付 / 待退款 / 待处理」等业务词。
STALE_TOKENS = [
    "待实测",
    "待填",
    "待点检",
    "仍留 E2",
    "仍属工程基线",
    "本期结束",
]


def check_stale():
    hits = []
    for name in ["ROADMAP.md", "PRD.md", "api-contract.md", "技术方案.md", "database-design.md",
                 "test-evidence.md", "README.md"]:
        text = read(name)
        lines = text.splitlines()
        # §8 是变更记录（历史快照），里面出现「待实测」是在描述当时的决定，不算过期
        skip_from = len(lines)
        for idx, l in enumerate(lines):
            if l.startswith("## 8. 变更记录"):
                skip_from = idx
                break
        for i, line in enumerate(lines, 1):
            if i > skip_from:
                break
            for token in STALE_TOKENS:
                if token in line:
                    hits.append((name, i, token, line))
    if hits:
        fail("stale", f"{len(hits)} 处过期表述（已完成的事仍写成将来时）",
             [(f"{n}:{i}", l) for n, i, _, l in hits])
        for n, i, t, _ in hits:
            print(f"        {DIM}{n}:{i} 含「{t}」{RESET}")
    else:
        ok("stale", "无过期表述")


# ---------------------------------------------------------------- 2. 状态传播
SLICE_ROW = re.compile(r"^\|\s*\*\*(S\d+(?:\.\d+)?)\*\*\s*\|")
SECTION = re.compile(r"^###\s+(S\d+(?:\.\d+)?)\b")


def parse_roadmap():
    text = read("ROADMAP.md")
    lines = text.splitlines()

    # §2 状态列（表的最后一格）
    table_status = {}
    for line in lines:
        m = SLICE_ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        status = cells[-1]
        if "已完成" in status:
            table_status[m.group(1)] = "done"
        elif "未开始" in status:
            table_status[m.group(1)] = "todo"
        else:
            table_status[m.group(1)] = "wip"

    # §3 各切片的 checkbox 统计
    section_state = {}
    current = None
    for line in lines:
        m = SECTION.match(line)
        if line.startswith("### ") and not m:
            current = None
            continue
        if m:
            current = m.group(1)
            section_state[current] = {"done": 0, "todo": 0, "deferred": 0, "line": 0}
            continue
        if current and line.lstrip().startswith("- [x]"):
            section_state[current]["done"] += 1
        elif current and line.lstrip().startswith("- [ ]"):
            # 「已移交其它切片」不算本片欠账：待 S9 / 移至 S6b / 归 S10 / 见 S11
            if re.search(r"(待|移至|移至|归|见)\s*\**S\d+", line):
                section_state[current]["deferred"] += 1
            else:
                section_state[current]["todo"] += 1
    return table_status, section_state


def check_status_propagation():
    table_status, section_state = parse_roadmap()

    missing = sorted(set(table_status) - set(section_state))
    if missing:
        fail("status", f"§2 有、§3 无对应小节：{', '.join(missing)}")

    bad = []
    for sid, state in table_status.items():
        sec = section_state.get(sid)
        if sec is None:
            continue
        if state == "done" and sec["todo"] > 0:
            bad.append(f"{sid}（§2 已完成，但 §3 还有 {sec['todo']} 项未勾且未标注移交切片）")
        if state == "todo" and sec["done"] > 0:
            bad.append(f"{sid}（§2 未开始，但 §3 已有 {sec['done']} 项勾选）")
    if bad:
        fail("status", "状态传播不一致：" + "；".join(bad))
    else:
        ok("status", f"§2 与 §3 状态一致（{len(table_status)} 个切片）")

    done_todo = [s for s, v in table_status.items() if v == "wip"]
    if done_todo:
        warn("status", f"进行中的切片（状态列既非已完成亦非未开始）：{', '.join(done_todo)}")


# ---------------------------------------------------------------- 3. 章节编号
NUM_HEADING = re.compile(r"^##\s+(\d+)\.\s")


def check_evidence_numbering():
    text = read("test-evidence.md")
    nums = [int(m.group(1)) for m in (NUM_HEADING.match(l) for l in text.splitlines()) if m]
    if not nums:
        fail("evidence", "test-evidence.md 未找到 ## N. 章节")
        return
    dup = {n for n in nums if nums.count(n) > 1}
    gaps = [n for n in range(1, max(nums) + 1) if n not in nums]
    if dup:
        fail("evidence", f"章节重复：{sorted(dup)}")
    elif gaps:
        warn("evidence", f"章节断号：{gaps}（不连续但可能是有意留空）")
    else:
        ok("evidence", f"章节编号连续（§1–§{max(nums)}）")


# ---------------------------------------------------------------- 4. P1 清单
P1_DONE_MARKERS = ["D1–D6", "E3 当日", "F3 对账", "F4 看板"]


def check_p1_list():
    text = read("api-contract.md")
    line = next((l for l in text.splitlines() if l.startswith("**P1 端点")), None)
    if line is None:
        warn("p1", "契约未找到 P1 端点清单行（可能已全部转正）")
        return
    stale = [m for m in P1_DONE_MARKERS if m in line]
    # 允许出现在紧随其后的「已转正」注记里
    if stale:
        idx = text.splitlines().index(line)
        tail = "\n".join(text.splitlines()[idx:idx + 3])
        if "已转正" not in tail:
            fail("p1", f"P1 清单仍列已完成端点：{stale}")
            return
    ok("p1", "P1 清单未残留已完成端点")


# ---------------------------------------------------------------- 5. 字典审计
def check_enum_audit():
    script = DOCS.parent / "backend" / "script" / "enum_sync_audit.py"
    if not script.exists():
        warn("enum", f"未找到 {script}，跳字典审计")
        return
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip().splitlines()
    tail = out[-1] if out else ""
    if proc.returncode == 0 and "全部一致" in (proc.stdout + proc.stderr):
        ok("enum", f"字典一致（{tail}）")
    else:
        fail("enum", "enum_sync_audit 不一致", [(f"line{i+1}", l) for i, l in enumerate(out[-6:])])


def main():
    print("== 文档一致性门禁 ==")
    check_stale()
    check_status_propagation()
    check_evidence_numbering()
    check_p1_list()
    check_enum_audit()

    print()
    if failures:
        print(f"{RED}结果：{len(failures)} 项失败{RESET}，{len(warnings)} 项警告")
        print("提示：收尾协议见 docs/AGENTS.md §5（Definition of Done），逐项对照后再提交。")
        return 1
    print(f"{GREEN}结果：全部通过{RESET}（{len(warnings)} 项警告）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:      # 被 `| head` 之类提前关闭管道时优雅退出
        try:
            sys.stdout.close()
        finally:
            os._exit(0)
