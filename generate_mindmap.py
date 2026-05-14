#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 DeepSeek AI 生成系统架构设计师思维导图
========================================
功能：
1. 读取 思维导图生成.prompt.md 作为系统提示词
2. 读取 output_md/ 下所有 Markdown 文件作为素材
3. 调用 DeepSeek API 生成 Markmap 格式思维导图
4. 输出可直接用 Markmap 扩展渲染的 .md 文件，同时包含 Mermaid mindmap 代码块

用法：
  python generate_mindmap.py                     # 完整模式（全部章节汇总一张全局导图）
  python generate_mindmap.py --chapter 1          # 单章模式（只生成第 1 章思维导图）
  python generate_mindmap.py --batch              # 逐章模式（每章独立生成 + 汇总）
  python generate_mindmap.py --format mermaid     # 指定输出格式偏好

前置条件：
  - 在 .env 文件中设置 DEEPSEEK_API_KEY
  - 安装依赖：pip install openai python-dotenv

输出文件：
  - 完整模式：思维导图_完整版.md
  - 单章模式：思维导图_第X章_章节名.md
  - 逐章模式：思维导图_逐章/ 目录下每章一个文件 + 思维导图_汇总.md
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv


# ============================================================
# 配置区
# ============================================================

# API 配置
load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY") or "sk-4901944a76474bb7b08415aa91df54ed"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"          # DeepSeek V3，128K 上下文

# 路径配置
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "output_md"
PROMPT_FILE = BASE_DIR / "思维导图生成.prompt.md"
OUTPUT_DIR = BASE_DIR / "output_mindmap"
LOG_FILE = BASE_DIR / "generate_mindmap.log"

# API 调用参数
MAX_TOKENS = 64000
RETRY_TIMES = 3
RETRY_DELAY = 5

# 水印过滤规则
WATERMARK_PATTERNS = [
    r"手资源独家更新.*",
    r"如在其他店购买务必差评.*",
    r"文老师软考教育",
    r"文老师系统架构设计师",
    r"淘宝搜", r"淘宝搜索:", r"淘宝搜索：",
    r"构设计", r"师系", r"均设计", r"勺设计师",
    r"设计师$", r"计师$",
]

# 内容阈值
CONTENT_WARN_THRESHOLD = 80000
CONTENT_MAX_THRESHOLD = 280000

# 章节顺序
CHAPTER_ORDER = [
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

# 输出格式偏好（可被 --format 覆盖）
OUTPUT_FORMAT = "markmap"  # 可选: markmap, mermaid, both


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
# 文件清洗
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


def read_chapter(chapter_name: str) -> Optional[dict]:
    """读取单个章节文件，返回 {name, content, size}"""
    fp = INPUT_DIR / f"{chapter_name}.md"
    if not fp.exists():
        log(f"  [跳过] {chapter_name}.md 不存在")
        return None
    raw = fp.read_text(encoding="utf-8")
    cleaned = clean_md_text(raw)
    if len(cleaned.strip()) < 50:
        log(f"  [跳过] {chapter_name} 内容过短")
        return None
    result = {
        "name": chapter_name,
        "content": cleaned,
        "size": len(cleaned),
    }
    log(f"  [读取] {chapter_name} ({len(cleaned):,} 字符)")
    return result


def read_all_chapters() -> list[dict]:
    """读取所有章节 MD 文件，按顺序返回"""
    if not INPUT_DIR.exists():
        log(f"[错误] 目录不存在: {INPUT_DIR}")
        sys.exit(1)

    chapters = []
    for name in CHAPTER_ORDER:
        ch = read_chapter(name)
        if ch:
            chapters.append(ch)
    return chapters


# ============================================================
# API 调用
# ============================================================

def call_deepseek(messages: list[dict], stream: bool = True) -> str:
    """调用 DeepSeek API"""
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
                print()
            else:
                collected.append(response.choices[0].message.content)

            return "".join(collected)

        except Exception as e:
            last_error = e
            log(f"  [重试 {attempt}/{RETRY_TIMES}] API 错误: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"API 调用失败（已重试 {RETRY_TIMES} 次）: {last_error}")


def build_batch_prompts(
    chapters: list[dict],
    format_pref: str,
    max_chars: int = CONTENT_MAX_THRESHOLD,
) -> list[list[dict]]:
    """
    将所有章节分批（每批素材不超过 max_chars 字符），
    返回多个 messages 列表，每个对应一次 API 调用。
    """
    prompt_content = PROMPT_FILE.read_text(encoding="utf-8")

    batches = []
    current_batch = []
    current_size = 0

    # 对于上大篇幅的单独成批
    for ch in chapters:
        if current_size + ch["size"] > max_chars and current_batch:
            # 归档当前批次
            batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append(ch)
        current_size += ch["size"]

    if current_batch:
        batches.append(current_batch)

    result = []
    for batch in batches:
        # 构建 user 消息内容
        user_content = f"""请为以下章节生成思维导图。
输出格式偏好：{format_pref}

章节素材内容如下：

"""
        for ch in batch:
            user_content += f"\n=== {ch['name']} ===\n{ch['content']}\n"

        messages = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": user_content},
        ]
        result.append(messages)

    return result


def build_full_prompt(chapters: list[dict], format_pref: str) -> list[dict]:
    """构建完整模式（所有素材一次发送）的 messages"""
    prompt_content = PROMPT_FILE.read_text(encoding="utf-8")

    user_content = f"""请为以下全部章节生成一张全局思维导图（宏观知识地图），同时每章再分别输出独立的子导图。
输出格式偏好：{format_pref}

全部章节素材内容如下：

"""
    for ch in chapters:
        user_content += f"\n=== {ch['name']} ===\n{ch['content']}\n"

    # 检查总大小
    total = len(user_content)
    log(f"  素材总字符数: {total:,}")
    if total > CONTENT_MAX_THRESHOLD:
        log(f"  [警告] 超过最大阈值 {CONTENT_MAX_THRESHOLD:,}，建议改用 --batch 模式")
    elif total > CONTENT_WARN_THRESHOLD:
        log(f"  [提示] 素材较大 ({total:,})，API 可能超时")

    return [
        {"role": "system", "content": prompt_content},
        {"role": "user", "content": user_content},
    ]


def build_chapter_prompt(chapter: dict, format_pref: str) -> list[dict]:
    """构建单章模式的 messages"""
    prompt_content = PROMPT_FILE.read_text(encoding="utf-8")

    user_content = f"""请为以下章节生成思维导图。
输出格式偏好：{format_pref}

章节素材内容：

=== {chapter['name']} ===
{chapter['content']}
"""

    return [
        {"role": "system", "content": prompt_content},
        {"role": "user", "content": user_content},
    ]


# ============================================================
# 输出处理
# ============================================================

def extract_mermaid_blocks(text: str) -> list[str]:
    """从生成结果中提取 Mermaid mindmap 代码块"""
    blocks = re.findall(r"```mermaid\n(mindmap.*?)```", text, re.DOTALL)
    return blocks


def extract_markmap_sections(text: str) -> str:
    """提取 Markmap 可用内容（# 标题层级结构）"""
    # 过滤掉代码块，保留标题和列表结构
    lines = text.split("\n")
    cleaned = []
    in_code_block = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def save_output(content: str, output_path: Path):
    """保存输出文件"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    log(f"  [保存] {output_path} ({len(content):,} 字符)")


def add_footer(content: str, chapters_used: list[str]) -> str:
    """添加元信息页脚"""
    footer = f"""

---
*生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*素材来源：{"、".join(chapters_used)}*
*提示词：思维导图生成.prompt.md*
*模型：{MODEL}*
"""
    return content + footer


# ============================================================
# 模式分发
# ============================================================

def run_full_mode(format_pref: str):
    """完整模式：全部章节一次生成全局思维导图"""
    log("=" * 50)
    log("完整模式：生成全局思维导图")
    log("=" * 50)

    chapters = read_all_chapters()
    if not chapters:
        log("[错误] 没有可用的章节内容")
        return

    chapter_names = [c["name"] for c in chapters]
    log(f"共 {len(chapters)} 个章节")

    messages = build_full_prompt(chapters, format_pref)
    log("正在调用 API（全量生成，可能需要较长时间）...")
    result = call_deepseek(messages)

    output_path = OUTPUT_DIR / "思维导图_完整版.md"
    content = add_footer(result, chapter_names)
    save_output(content, output_path)
    log("完整模式完成！")


def run_chapter_mode(chapter_id: str, format_pref: str):
    """单章模式：只生成指定章节的思维导图"""
    log("=" * 50)
    log(f"单章模式：生成第 {chapter_id} 章思维导图")
    log("=" * 50)

    # 匹配章节
    target = None
    for name in CHAPTER_ORDER:
        if name.startswith(f"{chapter_id}."):
            target = name
            break
    if not target:
        log(f"[错误] 未找到第 {chapter_id} 章")
        log(f"可用章节编号：{[n.split('.')[0] for n in CHAPTER_ORDER if '.' in n]}")
        return

    chapter = read_chapter(target)
    if not chapter:
        return

    messages = build_chapter_prompt(chapter, format_pref)
    log(f"正在为「{target}」生成思维导图...")
    result = call_deepseek(messages)

    safe_name = target.replace(".", "_").replace("/", "_")
    output_path = OUTPUT_DIR / f"思维导图_第{chapter_id}章_{safe_name}.md"
    content = add_footer(result, [target])
    save_output(content, output_path)
    log("单章模式完成！")


def run_batch_mode(format_pref: str):
    """逐章模式：每章独立生成 + 汇总合并"""
    log("=" * 50)
    log("逐章模式：每章独立生成 + 合并汇总")
    log("=" * 50)

    chapters = read_all_chapters()
    if not chapters:
        log("[错误] 没有可用的章节内容")
        return

    chapter_names = [c["name"] for c in chapters]
    per_chapter_dir = OUTPUT_DIR / "思维导图_逐章"
    per_chapter_dir.mkdir(parents=True, exist_ok=True)

    all_results = []

    for i, ch in enumerate(chapters, 1):
        log(f"\n[{i}/{len(chapters)}] 正在处理 {ch['name']} ({ch['size']:,} 字符)...")
        messages = build_chapter_prompt(ch, format_pref)
        try:
            result = call_deepseek(messages)
            all_results.append({"name": ch["name"], "content": result})
            safe_name = ch["name"].replace(".", "_").replace("/", "_")
            fp = per_chapter_dir / f"思维导图_{ch['name']}.md"
            content = add_footer(result, [ch["name"]])
            save_output(content, fp)
        except Exception as e:
            log(f"  [错误] {ch['name']} 生成失败: {e}")
            all_results.append({"name": ch["name"], "content": f"# {ch['name']}\n\n*生成失败: {e}*"})
        # API 限速保护
        if i < len(chapters):
            time.sleep(1)

    # 合并汇总
    log("\n正在合并汇总...")
    merged = f"# 系统架构设计师 思维导图汇总\n\n"
    merged += f"*生成日期：{datetime.now().strftime('%Y-%m-%d')}*\n"
    merged += f"*共 {len(all_results)} 章*\n\n"
    merged += "---\n\n"

    for result in all_results:
        merged += f"{result['content']}\n\n---\n\n"

    summary_path = OUTPUT_DIR / "思维导图_逐章汇总.md"
    merged = add_footer(merged, chapter_names)
    save_output(merged, summary_path)
    log("逐章模式完成！")


# ============================================================
# 入口
# ============================================================

def parse_args():
    """解析命令行参数"""
    args = {
        "mode": "full",
        "chapter": None,
        "format": OUTPUT_FORMAT,
    }

    for arg in sys.argv[1:]:
        if arg == "--batch":
            args["mode"] = "batch"
        elif arg.startswith("--chapter"):
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
                args["chapter"] = sys.argv[idx + 1]
                args["mode"] = "chapter"
        elif arg == "--full":
            args["mode"] = "full"
        elif arg == "--format":
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
                pref = sys.argv[idx + 1].lower()
                if pref in ("markmap", "mermaid", "both"):
                    args["format"] = pref

    return args


def main():
    """主入口"""
    log("=" * 50)
    log("DeepSeek 思维导图生成器 启动")
    log(f"模型: {MODEL}")
    log(f"素材目录: {INPUT_DIR}")
    log(f"提示词: {PROMPT_FILE}")
    log("=" * 50)

    args = parse_args()
    format_pref = args["format"]

    if not PROMPT_FILE.exists():
        log(f"[错误] 提示词文件不存在: {PROMPT_FILE}")
        log("请确保 思维导图生成.prompt.md 在当前目录")
        sys.exit(1)

    try:
        if args["mode"] == "full":
            run_full_mode(format_pref)
        elif args["mode"] == "chapter":
            run_chapter_mode(args["chapter"], format_pref)
        elif args["mode"] == "batch":
            run_batch_mode(format_pref)
    except KeyboardInterrupt:
        log("\n用户中断")
        sys.exit(1)
    except Exception as e:
        log(f"[错误] 运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    log("\n全部完成！")


if __name__ == "__main__":
    main()
