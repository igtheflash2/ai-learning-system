#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统架构设计师 学习资料自动生成工具
=====================================
功能：读取 output_md/ 下所有 Markdown 文件，
      清洗广告水印，提取结构化信息，
      生成综合学习指南 Markdown 文件。
"""

import re
import os
from pathlib import Path
from typing import Optional


# ============================================================
# 配置区
# ============================================================
INPUT_DIR = Path(__file__).parent / "output_md"
OUTPUT_FILE = Path(__file__).parent / "综合学习资料_自动生成.md"

# 需要过滤的广告/水印关键词（按行匹配）
WATERMARK_PATTERNS = [
    r"手资源独家更新.*",
    r"如在其他店购买务必差评.*",
    r"文老师软考教育",
    r"文老师系统架构设计师",
    r"淘宝搜",
    r"淘宝搜索:",
    r"淘宝搜索：",
    r"构设计",  # 页眉干扰词
    r"师系",    # 同上
    r"均设计",  # 同上
    r"勺设计师",
    r"设计师$",
    r"计师$",
]

# 章节排序（用于控制最终输出的章节顺序）
CHAPTER_ORDER = [
    "0.第二版教材对比解读",
    "1.计算机硬件",
    "2.操作系统知识",
    "3.数据库系统",
    "4.嵌入式技术",
    "5.计算机网络",
    "6.其他计算机系统基础知识",
    "7.系统配置与性能评价",
    "8.信息系统基础知识",
    "9.系统安全",
    "10.软件工程",
    "11.面向对象技术",
    "12.项目管理",
    "13.系统架构设计",
    "14.软件可靠性基础",
    "15.软件架构的演化和维护",
    "16.未来信息综合技术",
    "补充-数学与经济管理",
    "补充-知识产权与标准化",
    "架构案例专题1-历年考点分类精讲及真题详解",
    "论文写作专题",
]


# ============================================================
# 核心函数
# ============================================================

def clean_line(line: str) -> Optional[str]:
    """清洗单行：去除水印、空行规范化；返回 None 表示该行应删除"""
    stripped = line.strip()
    # 空行保留（作为段落分隔）
    if not stripped:
        return ""

    # 广告/水印过滤
    for pat in WATERMARK_PATTERNS:
        if re.match(pat, stripped):
            return None  # 删除该行
    return line


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
        # 跳过完全空的行列表
        if line is None:
            continue

        # 标题行 —— 一级标题
        if line.startswith("# ") and not line.startswith("##"):
            title = line.lstrip("# ").strip()
            continue

        # 二级或三级标题
        if line.startswith("##") or line.startswith("###") or line.startswith("####"):
            if current_heading and current_content:
                sections.append((current_heading, "".join(current_content).strip()))
            current_heading = line.strip()
            current_content = []
            continue

        # 检测 "历年真题考情" 块
        if "历年真题考情" in line or "真题考情" in line:
            exam_trend += line + "\n"
            continue

        # 收集正文
        # 跳过纯分隔线
        if line.strip() == "---":
            continue
        current_content.append(line + "\n")

    # 最后一次
    if current_heading and current_content:
        sections.append((current_heading, "".join(current_content).strip()))

    return {
        "title": title,
        "exam_trend": exam_trend.strip(),
        "sections": sections,
    }


def read_md_file(filepath: Path) -> Optional[dict]:
    """读取并解析单个 MD 文件"""
    try:
        raw = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [错误] 读取失败 {filepath.name}: {e}")
        return None

    # 逐行清洗
    cleaned_lines: list[str] = []
    for line in raw.split("\n"):
        result = clean_line(line)
        if result is not None:
            cleaned_lines.append(result)

    cleaned_text = "\n".join(cleaned_lines)

    # 提取结构化内容
    info = extract_sections(cleaned_text)
    if not info["title"]:
        info["title"] = filepath.stem  # 用文件名当后备标题

    # 提取真题
    questions = extract_exam_questions(cleaned_text)
    info["questions"] = questions

    return info


def extract_exam_questions(text: str) -> list[dict]:
    """提取 考试真题 部分的题目"""
    questions = []
    # 常见的题目模式：题干 + 选项 + 答案
    # 用 "【答案】" 或 "答案：" 作为锚点
    q_blocks = re.split(r"(?=考试真题|真题演练|真题)", text)
    for block in q_blocks:
        if "【答案】" in block or "答案：" in block:
            questions.append({
                "raw": block.strip(),
                "answer": extract_answer(block),
            })
    return questions


def extract_answer(block: str) -> str:
    """从文本块中提取答案"""
    m = re.search(r"[【\[]答案[】\]]\s*([A-Za-z]+)", block)
    if m:
        return m.group(1)
    m = re.search(r"答案[：:]\s*([A-Za-z]+)", block)
    if m:
        return m.group(1)
    return ""


def sort_chapters(files: list[Path]) -> list[Path]:
    """按 CHAPTER_ORDER 排序文件列表"""
    def sort_key(fp: Path):
        name = fp.stem
        try:
            return CHAPTER_ORDER.index(name)
        except ValueError:
            return 999  # 不在列表中的排最后
    return sorted(files, key=sort_key)


def generate_chapter_section(info: dict) -> str:
    """为单个章节生成格式化输出"""
    lines = []
    title = info.get("title", "未命名章节")
    lines.append(f"## {title}\n")

    # 考情分析
    trend = info.get("exam_trend", "")
    if trend:
        lines.append("### 📊 考情分析\n")
        lines.append(trend + "\n")

    # 各小节
    for heading, content in info.get("sections", []):
        # 跳过纯广告性质的标题
        if any(w in heading for w in ["淘宝", "文老师", "构设计"]):
            continue
        lines.append(f"### {heading}\n")
        lines.append(content + "\n")

    # 真题
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
    total_chars = sum(len(c.get("raw_text", "")) for c in chapter_infos)
    lines = [
        "# 系统架构设计师 综合学习资料（自动生成）\n",
        f"> 生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"> 涵盖章节：**{len(chapter_infos)}** 个\n",
        f"> 收录真题：**{total_questions}** 道\n",
        "---\n",
    ]
    return "\n".join(lines)


def generate_study_guide():
    """主流程：读取→清洗→结构化→输出"""
    print(f"=" * 60)
    print(f"  系统架构设计师 学习资料生成工具")
    print(f"=" * 60)

    # 1. 收集输入文件
    if not INPUT_DIR.exists():
        print(f"[错误] 目录不存在: {INPUT_DIR}")
        return

    md_files = list(INPUT_DIR.glob("*.md"))
    md_files = sort_chapters(md_files)
    print(f"\n发现 {len(md_files)} 个 Markdown 文件\n")

    # 2. 逐一处理
    all_chapters: list[dict] = []
    for fp in md_files:
        print(f"  📖 正在处理: {fp.name} ...", end=" ")
        info = read_md_file(fp)
        if info:
            # 保存原始清洗后文本（用于统计）
            raw_text = fp.read_text(encoding="utf-8")
            cleaned_lines = [l for l in raw_text.split("\n") if clean_line(l) is not None]
            info["raw_text"] = "\n".join(cleaned_lines)
            all_chapters.append(info)
            q_count = len(info.get("questions", []))
            print(f"完成（提取 {q_count} 道真题）")
        else:
            print("跳过")

    # 3. 组装输出
    print(f"\n正在生成综合学习资料 ...")
    output_parts = []

    # 封面信息
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
    output_parts.append("> ⏳ 此部分需结合 AI 分析各章节高频考点后生成\n")

    # 案例专题汇总
    case_chapter = [c for c in all_chapters if "案例" in c.get("title", "")]
    if case_chapter:
        output_parts.append("## 三、案例专题\n")
        for c in case_chapter:
            output_parts.append(generate_chapter_section(c))

    # 论文专题汇总
    essay_chapter = [c for c in all_chapters if "论文" in c.get("title", "")]
    if essay_chapter:
        output_parts.append("## 四、论文专题\n")
        for c in essay_chapter:
            output_parts.append(generate_chapter_section(c))

    # 4. 写出文件
    final_text = "\n".join(output_parts)
    OUTPUT_FILE.write_text(final_text, encoding="utf-8")

    total_chars = len(final_text)
    print(f"\n✅ 完成！输出文件: {OUTPUT_FILE}")
    print(f"   总字数: {total_chars:,}")
    print(f"   覆盖章节: {len(all_chapters)}")
    total_q = sum(len(c.get("questions", [])) for c in all_chapters)
    print(f"   真题数量: {total_q}")


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    generate_study_guide()
