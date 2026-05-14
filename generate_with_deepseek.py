#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 DeepSeek AI 生成系统架构设计师综合学习资料
==============================================
功能：
1. 读取 prompt_agent_学习资料生成.md 作为系统提示词
2. 读取 output_md/ 下所有 Markdown 文件作为素材
3. 调用 DeepSeek API 根据提示词+素材自动生成完整的学习资料
4. 输出为单个完整的 Markdown 文件

用法：
  python generate_with_deepseek.py              # 完整模式（全部素材一次性发送）
  python generate_with_deepseek.py --chapter 3   # 单章模式（只处理第3章）
  python generate_with_deepseek.py --batch       # 逐章模式（每章分别生成后合并）

首次使用：
  1. 在 .env 文件中设置 DEEPSEEK_API_KEY，或直接修改脚本中的 API_KEY 变量
  2. 运行脚本即可
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv


# ============================================================
# 配置区
# ============================================================

# API 配置（优先读 .env 文件，其次读环境变量，最后用下方默认值）
load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY") or "sk-4901944a76474bb7b08415aa91df54ed"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"          # DeepSeek V3，128K 上下文

# 路径配置
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "output_md"
PROMPT_FILE = BASE_DIR / "prompt_agent_学习资料生成.md"
OUTPUT_FILE = BASE_DIR / "综合学习资料_AI生成.md"
LOG_FILE = BASE_DIR / "generate_deepseek.log"

# API 调用参数
MAX_TOKENS = 64000               # 每次调用最大输出 token
RETRY_TIMES = 3                  # 失败重试次数
RETRY_DELAY = 5                  # 重试间隔（秒）

# 水印过滤规则（复用现有规则）
WATERMARK_PATTERNS = [
    r"手资源独家更新.*",
    r"如在其他店购买务必差评.*",
    r"文老师软考教育",
    r"文老师系统架构设计师",
    r"淘宝搜", r"淘宝搜索:", r"淘宝搜索：",
    r"构设计", r"师系", r"均设计", r"勺设计师",
    r"设计师$", r"计师$",
]

# 内容大小告警阈值（字符数）
CONTENT_WARN_THRESHOLD = 80000
CONTENT_MAX_THRESHOLD = 280000


# ============================================================
# 日志
# ============================================================

def log(msg: str):
    """同时输出到终端和日志文件"""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ============================================================
# 文件清洗（复用现有逻辑）
# ============================================================

def clean_line(line: str) -> Optional[str]:
    """清洗单行：去除水印；返回 None 表示该行应删除"""
    stripped = line.strip()
    if not stripped:
        return ""
    for pat in WATERMARK_PATTERNS:
        if re.match(pat, stripped):
            return None
    return line


def clean_md_text(raw: str) -> str:
    """清洗整个 Markdown 文本，返回干净文本"""
    cleaned = []
    for line in raw.split("\n"):
        result = clean_line(line)
        if result is not None:
            cleaned.append(result)
    return "\n".join(cleaned)


def read_all_chapters() -> list[dict]:
    """读取所有章节 MD 文件，按顺序返回 [{name, content, size}, ...]"""
    if not INPUT_DIR.exists():
        log(f"[错误] 目录不存在: {INPUT_DIR}")
        sys.exit(1)

    # 章节顺序
    chapter_order = [
        "0.第二版教材对比解读", "1.计算机硬件", "2.操作系统知识",
        "3.数据库系统", "4.嵌入式技术", "5.计算机网络",
        "6.其他计算机系统基础知识", "7.系统配置与性能评价",
        "8.信息系统基础知识", "9.系统安全", "10.软件工程",
        "11.面向对象技术", "12.项目管理", "13.系统架构设计",
        "14.软件可靠性基础", "15.软件架构的演化和维护",
        "16.未来信息综合技术", "补充-数学与经济管理",
        "补充-知识产权与标准化",
        "架构案例专题1-历年考点分类精讲及真题详解", "论文写作专题",
    ]

    chapters = []
    for name in chapter_order:
        fp = INPUT_DIR / f"{name}.md"
        if not fp.exists():
            log(f"  [跳过] {name}.md 不存在")
            continue
        raw = fp.read_text(encoding="utf-8")
        cleaned = clean_md_text(raw)
        if len(cleaned.strip()) < 50:
            log(f"  [跳过] {name} 内容过短")
            continue
        chapters.append({
            "name": name,
            "content": cleaned,
            "size": len(cleaned),
        })
        log(f"  [读取] {name} ({len(cleaned):,} 字符)")

    return chapters


# ============================================================
# API 调用
# ============================================================

def call_deepseek(messages: list[dict], stream: bool = True) -> str:
    """
    调用 DeepSeek API。
    messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    stream: 是否流式输出（实时显示生成过程）
    返回: API 响应的完整文本
    """
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    last_error = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS,
                stream=stream,
            )

            collected = []
            if stream:
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        collected.append(content)
                        print(content, end="", flush=True)
                print()  # 换行
            else:
                collected.append(response.choices[0].message.content)

            return "".join(collected)

        except Exception as e:
            last_error = e
            log(f"  [重试 {attempt}/{RETRY_TIMES}] API 错误: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"API 调用失败（已重试 {RETRY_TIMES} 次）: {last_error}")


def compute_prompt_stats(chapters: list[dict]) -> dict:
    """计算提示词统计信息"""
    total_chars = sum(c["size"] for c in chapters)
    # 粗略估算 token（中文约 1.5 字符/token，英文约 4 字符/token）
    estimated_tokens = int(total_chars / 1.8)
    return {
        "total_chars": total_chars,
        "estimated_tokens": estimated_tokens,
        "chapter_count": len(chapters),
    }


# ============================================================
# 生成模式
# ============================================================

def build_system_prompt() -> str:
    """读取 agent 提示词作为 system prompt"""
    if not PROMPT_FILE.exists():
        log(f"[错误] 提示词文件不存在: {PROMPT_FILE}")
        sys.exit(1)
    return PROMPT_FILE.read_text(encoding="utf-8")


def build_user_message(chapters: list[dict]) -> str:
    """将所有章节内容组装为一条 user message"""
    parts = ['以下是全部章节的复习笔记素材，请根据"输出要求"中的结构生成综合学习资料：\n']
    for ch in chapters:
        parts.append(f"\n{'='*60}")
        parts.append(f"章节：{ch['name']}")
        parts.append(f"{'='*60}\n")
        parts.append(ch["content"])
    return "\n".join(parts)


def mode_full(chapters: list[dict]):
    """完整模式：所有素材一次发送给 AI"""
    stats = compute_prompt_stats(chapters)
    log(f"\n{'='*50}")
    log(f"  完整模式启动")
    log(f"  章节数: {stats['chapter_count']}")
    log(f"  总字符: {stats['total_chars']:,}")
    log(f"  预估 token: {stats['estimated_tokens']:,}")
    log(f"{'='*50}\n")

    if stats["total_chars"] > CONTENT_MAX_THRESHOLD:
        log(f"[警告] 内容过大（{stats['total_chars']:,} 字符），建议使用 --batch 模式")
        proceed = input("  是否继续？(y/n): ").strip().lower()
        if proceed != "y":
            log("  用户取消")
            return

    system_prompt = build_system_prompt()
    user_message = build_user_message(chapters)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    log("开始生成，等待 DeepSeek 响应...\n")
    log("=" * 30 + " 生成中 " + "=" * 30)
    result = call_deepseek(messages, stream=True)
    log("\n" + "=" * 30 + " 生成完毕 " + "=" * 30)

    OUTPUT_FILE.write_text(result, encoding="utf-8")
    log(f"\n✅ 输出已保存: {OUTPUT_FILE}")
    log(f"   生成字数: {len(result):,}")


def build_single_chapter_message(system_prompt: str, chapter: dict, index: int, total: int) -> list[dict]:
    """构建单章的 API 消息"""
    user_msg = (
        f"以下是第 {index}/{total} 章「{chapter['name']}」的复习笔记素材。\n"
        f"请严格按照 Agent 提示词中的「综合学习指南」格式输出该章节内容"
        f"（包括考情分析、知识点体系、考点精讲、新教材变化、记忆口诀、真题演练）。\n\n"
        f"素材内容：\n{chapter['content']}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


def mode_batch(chapters: list[dict]):
    """逐章模式：每章单独生成，最后合并"""
    system_prompt = build_system_prompt()
    all_output = []
    total = len(chapters)

    log(f"\n{'='*50}")
    log(f"  逐章模式启动（共 {total} 章）")
    log(f"{'='*50}\n")

    for i, ch in enumerate(chapters, 1):
        log(f"\n[{i}/{total}] 正在生成: {ch['name']} ({ch['size']:,} 字符)")
        log("-" * 40)

        messages = build_single_chapter_message(system_prompt, ch, i, total)
        result = call_deepseek(messages, stream=True)

        # 保存到单独文件
        chapter_file = BASE_DIR / f"output_chapter/{ch['name']}.md"
        chapter_file.parent.mkdir(exist_ok=True)
        chapter_file.write_text(result, encoding="utf-8")
        log(f"  -> 已保存: {chapter_file}")

        all_output.append(f"\n\n{'#'*60}\n# {i}. {ch['name']}\n{'#'*60}\n\n")
        all_output.append(result)

        # 章节间停顿，避免 API 限流
        if i < total:
            log("  等待 3 秒后处理下一章...")
            time.sleep(3)

    # 合并输出
    combined = "".join(all_output)
    OUTPUT_FILE.write_text(combined, encoding="utf-8")
    log(f"\n{'='*50}")
    log(f"✅ 全部完成！")
    log(f"   合并输出: {OUTPUT_FILE}")
    log(f"   总字数: {len(combined):,}")
    log(f"   各章节单独保存在: {BASE_DIR / 'output_chapter'}")


def mode_single_chapter(chapters: list[dict], chapter_num: int):
    """单章模式：只处理指定章节"""
    if chapter_num < 1 or chapter_num > len(chapters):
        log(f"[错误] 章节序号无效（1-{len(chapters)}）")
        return

    ch = chapters[chapter_num - 1]
    system_prompt = build_system_prompt()

    log(f"\n{'='*50}")
    log(f"  单章模式: {ch['name']}")
    log(f"{'='*50}\n")

    messages = build_single_chapter_message(system_prompt, ch, chapter_num, len(chapters))
    result = call_deepseek(messages, stream=True)

    chapter_file = BASE_DIR / f"综合学习资料_第{chapter_num}章_{ch['name']}.md"
    chapter_file.write_text(result, encoding="utf-8")
    log(f"\n✅ 已保存: {chapter_file}（{len(result):,} 字符）")


# ============================================================
# 入口
# ============================================================

def print_banner():
    banner = r"""
╔══════════════════════════════════════════════════╗
║    系统架构设计师  AI 学习资料生成器              ║
║    引擎: DeepSeek V3                             ║
╠══════════════════════════════════════════════════╣
║  模式:                                           ║
║    python generate_with_deepseek.py     完整模式  ║
║    python generate_with_deepseek.py --batch 逐章  ║
║    python generate_with_deepseek.py --chapter N   ║
╚══════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    # 解析参数
    args = sys.argv[1:]
    mode_single = False
    chapter_num = 0
    batch_mode = False

    if "--chapter" in args:
        idx = args.index("--chapter")
        if idx + 1 < len(args):
            chapter_num = int(args[idx + 1])
            mode_single = True

    if "--batch" in args:
        batch_mode = True

    # 清空日志
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    print_banner()

    # 验证 API Key
    if not API_KEY or API_KEY == "your-deepseek-api-key-here":
        log("[错误] 请先设置 DEEPSEEK_API_KEY")
        log("   方式1: 在本脚本同级目录创建 .env 文件，写入:")
        log('          DEEPSEEK_API_KEY=sk-xxx')
        log("   方式2: 直接修改脚本 API_KEY 变量")
        sys.exit(1)

    # 读取素材
    log("正在读取章节文件...")
    chapters = read_all_chapters()
    log(f"共读取 {len(chapters)} 个章节\n")

    if not chapters:
        log("[错误] 没有读取到任何章节内容")
        sys.exit(1)

    # 选择模式执行
    if mode_single:
        mode_single_chapter(chapters, chapter_num)
    elif batch_mode:
        mode_batch(chapters)
    else:
        mode_full(chapters)


if __name__ == "__main__":
    main()
