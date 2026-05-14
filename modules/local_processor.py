#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地清洗重组模块
================
不调用任何外部 API，仅对 output_md/ 中的 Markdown 做本地清洗、
结构化、排序、汇总，生成综合学习资料。

复用自 generate_study_guide.py 的核心逻辑。
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config_manager import WATERMARK_PATTERNS, CHAPTER_ORDER, clean_line


# ============================================================
# 核心清洗函数
# ============================================================

def clean_md_text(raw: str) -> str:
    """清洗整个 Markdown 文本，返回干净文本"""
    cleaned = []
    for line in raw.split("\n"):
        result = clean_line(line)
        if result is not None:
            cleaned.append(result)
    return "\n".join(cleaned)


# ============================================================
# 结构化提取
# ============================================================

def extract_sections(text: str) -> dict:
    """
    从清洗后的文本中提取结构化信息。
    返回: {"title": str, "exam_trend": str, "sections": [(heading, content), ...]}
    """
    lines = text.split("\n")
    title = ""
    exam_trend = ""
    current_heading = ""
    current_content: list[str] = []
    sections: list[tuple[str, str]] = []

    for line in lines:
        if line is None:
            continue

        # 一级标题
        if line.startswith("# ") and not line.startswith("##"):
            title = line.lstrip("# ").strip()
            continue

        # 二级及以上标题
        if line.startswith("##") or line.startswith("###") or line.startswith("####"):
            if current_heading and current_content:
                sections.append((current_heading, "".join(current_content).strip()))
            current_heading = line.strip()
            current_content = []
            continue

        # 考情检测
        if "历年真题考情" in line or "真题考情" in line:
            exam_trend += line + "\n"
            continue

        # 跳过分隔线
        if line.strip() == "---":
            continue
        current_content.append(line + "\n")

    if current_heading and current_content:
        sections.append((current_heading, "".join(current_content).strip()))

    return {
        "title": title,
        "exam_trend": exam_trend.strip(),
        "sections": sections,
    }


def extract_exam_questions(text: str) -> list[dict]:
    """提取考试真题部分的题目"""
    questions = []
    q_blocks = re.split(r"(?=考试真题|真题演练|真题)", text)
    for block in q_blocks:
        if "【答案】" in block or "答案：" in block:
            questions.append({
                "raw": block.strip(),
                "answer": _extract_answer(block),
            })
    return questions


def _extract_answer(block: str) -> str:
    """从文本块中提取答案"""
    m = re.search(r"[【\[]答案[】\]]\s*([A-Za-z]+)", block)
    if m:
        return m.group(1)
    m = re.search(r"答案[：:]\s*([A-Za-z]+)", block)
    if m:
        return m.group(1)
    return ""


# ============================================================
# 文件读取与排序
# ============================================================

def sort_chapters(files: list[Path]) -> list[Path]:
    """按 CHAPTER_ORDER 排序文件列表"""
    def sort_key(fp: Path):
        name = fp.stem
        try:
            return CHAPTER_ORDER.index(name)
        except ValueError:
            return 999
    return sorted(files, key=sort_key)


def read_md_file(filepath: Path) -> Optional[dict]:
    """读取并解析单个 MD 文件"""
    try:
        raw = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [错误] 读取失败 {filepath.name}: {e}")
        return None

    cleaned_lines = []
    for line in raw.split("\n"):
        result = clean_line(line)
        if result is not None:
            cleaned_lines.append(result)
    cleaned_text = "\n".join(cleaned_lines)

    info = extract_sections(cleaned_text)
    if not info["title"]:
        info["title"] = filepath.stem

    info["questions"] = extract_exam_questions(cleaned_text)
    info["raw_text"] = cleaned_text
    return info


# ============================================================
# 输出组装
# ============================================================

def generate_chapter_section(info: dict) -> str:
    """为单个章节生成格式化输出"""
    lines = []
    title = info.get("title", "未命名章节")
    lines.append(f"## {title}\n")

    trend = info.get("exam_trend", "")
    if trend:
        lines.append("### 📊 考情分析\n")
        lines.append(trend + "\n")

    for heading, content in info.get("sections", []):
        if any(w in heading for w in ["淘宝", "文老师", "构设计"]):
            continue
        lines.append(f"### {heading}\n")
        lines.append(content + "\n")

    questions = info.get("questions", [])
    if questions:
        lines.append("### ✅ 真题演练\n")
        for q in questions:
            lines.append(q["raw"] + "\n")
            if q["answer"]:
                lines.append(f"> **答案：{q['answer']}**\n")

    return "\n".join(lines)


def generate_front_matter(chapter_infos: list[dict]) -> str:
    """生成总体统计信息"""
    total_questions = sum(len(c.get("questions", [])) for c in chapter_infos)
    lines = [
        "# 系统架构设计师 综合学习资料（本地自动生成）\n",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"> 涵盖章节：**{len(chapter_infos)}** 个\n",
        f"> 收录真题：**{total_questions}** 道\n",
        "---\n",
    ]
    return "\n".join(lines)


def process_local_study_guide(
    input_dir: Path,
    selected_chapters: Optional[list[str]] = None,
) -> str:
    """
    主流程：读取 → 清洗 → 结构化 → 输出为 Markdown 字符串。

    Args:
        input_dir: 输入 Markdown 目录
        selected_chapters: 若指定，只处理这些章节；否则处理全部

    Returns:
        完整的 Markdown 文本
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"目录不存在: {input_dir}")

    md_files = list(input_dir.glob("*.md"))
    md_files = sort_chapters(md_files)

    if selected_chapters:
        md_files = [fp for fp in md_files if fp.stem in selected_chapters]

    all_chapters: list[dict] = []
    for fp in md_files:
        info = read_md_file(fp)
        if info:
            all_chapters.append(info)

    output_parts = []
    output_parts.append(generate_front_matter(all_chapters))

    # 目录概览
    output_parts.append("## 📑 目录\n")
    for i, ch in enumerate(all_chapters, 1):
        title = ch.get("title", "")
        q_count = len(ch.get("questions", []))
        output_parts.append(f"{i}. **{title}**（真题 {q_count} 道）\n")
    output_parts.append("\n---\n")

    # 各章节详细内容
    output_parts.append("## 一、各章精讲\n")
    for ch in all_chapters:
        output_parts.append(generate_chapter_section(ch))
        output_parts.append("\n---\n")

    # 冲刺速记汇总
    output_parts.append("## 二、冲刺速记汇总\n")
    output_parts.append(
        "> ⏳ 此部分在本地模式下为占位符，使用 AI 模式可生成高频考点 TOP20、易错题集、公式速查\n"
    )

    # 案例专题
    case_chapter = [c for c in all_chapters if "案例" in c.get("title", "")]
    if case_chapter:
        output_parts.append("## 三、案例专题\n")
        for c in case_chapter:
            output_parts.append(generate_chapter_section(c))

    # 论文专题
    essay_chapter = [c for c in all_chapters if "论文" in c.get("title", "")]
    if essay_chapter:
        output_parts.append("## 四、论文专题\n")
        for c in essay_chapter:
            output_parts.append(generate_chapter_section(c))

    return "\n".join(output_parts)
