#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 生成模块
===========
通用 LLM 调用封装，支持学习资料生成和思维导图生成。
基于 OpenAI SDK（兼容 DeepSeek 及其他 OpenAI 格式 API）。

前置条件：pip install openai python-dotenv
"""

import re
import time
from pathlib import Path
from typing import Optional, Callable

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config_manager import AppConfig, WATERMARK_PATTERNS, clean_line
from .prompt_manager import build_study_guide_prompt, build_mindmap_prompt


def _ensure_deps():
    if OpenAI is None:
        raise ImportError("请安装 openai: pip install openai")


# ============================================================
# 素材读取
# ============================================================

def clean_md_text(raw: str) -> str:
    """清洗 Markdown 文本"""
    cleaned = []
    for line in raw.split("\n"):
        result = clean_line(line)
        if result is not None:
            cleaned.append(result)
    return "\n".join(cleaned)


def read_chapter_material(
    input_dir: Path,
    chapter_name: str,
) -> Optional[str]:
    """读取单个章节素材并清洗"""
    fp = input_dir / f"{chapter_name}.md"
    if not fp.exists():
        return None
    raw = fp.read_text(encoding="utf-8")
    cleaned = clean_md_text(raw)
    return cleaned if len(cleaned.strip()) >= 50 else None


def read_selected_materials(
    input_dir: Path,
    selected_chapters: list[str],
) -> list[dict]:
    """读取选中的章节素材列表"""
    chapters = []
    for name in selected_chapters:
        content = read_chapter_material(input_dir, name)
        if content:
            chapters.append({"name": name, "content": content, "size": len(content)})
    return chapters


# ============================================================
# LLM 调用核心
# ============================================================

def call_llm(
    messages: list[dict],
    config: AppConfig,
    stream: bool = True,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    调用 LLM API。

    Args:
        messages: OpenAI 格式的消息列表
        config: API 配置
        stream: 是否流式输出
        stream_callback: 流式输出的回调函数，每收到一个 chunk 调用一次

    Returns:
        完整的生成文本
    """
    _ensure_deps()
    client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    last_error = None
    for attempt in range(1, config.retry_times + 1):
        try:
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                max_tokens=config.max_tokens,
                stream=stream,
            )

            collected = []
            if stream:
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        collected.append(content)
                        if stream_callback:
                            stream_callback(content)
            else:
                collected.append(response.choices[0].message.content)

            return "".join(collected)

        except Exception as e:
            last_error = e
            if attempt < config.retry_times:
                time.sleep(config.retry_delay)

    raise RuntimeError(f"API 调用失败（已重试 {config.retry_times} 次）: {last_error}")


# ============================================================
# 学习资料生成
# ============================================================

def generate_study_guide(
    input_dir: Path,
    selected_chapters: list[str],
    config: AppConfig,
    focus_areas: str = "全部章节",
    detail_level: str = "标准",
    include_mnemonics: bool = True,
    include_exercises: bool = True,
    prompt_template: Optional[Path] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    生成综合学习资料（AI 模式）。

    Returns:
        生成的完整 Markdown 文本
    """
    chapters = read_selected_materials(input_dir, selected_chapters)
    if not chapters:
        raise ValueError("未读取到任何有效章节素材")

    # 组装素材
    parts = ["以下是全部章节的复习笔记素材，请根据要求生成综合学习资料：\n"]
    for ch in chapters:
        parts.append(f"\n{'='*60}")
        parts.append(f"章节：{ch['name']}")
        parts.append(f"{'='*60}\n")
        parts.append(ch["content"])
    material = "\n".join(parts)

    # 构建提示词
    system_prompt, user_prompt = build_study_guide_prompt(
        material=material,
        focus_areas=focus_areas,
        detail_level=detail_level,
        include_mnemonics=include_mnemonics,
        include_exercises=include_exercises,
        template_path=prompt_template,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return call_llm(messages, config, stream=True, stream_callback=stream_callback)


def generate_study_guide_batch(
    input_dir: Path,
    selected_chapters: list[str],
    config: AppConfig,
    focus_areas: str = "全部章节",
    detail_level: str = "标准",
    include_mnemonics: bool = True,
    include_exercises: bool = True,
    prompt_template: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """
    逐章生成学习资料，最后合并。
    适合素材量大、完整模式可能超时的情况。

    Returns:
        合并后的完整 Markdown 文本
    """
    chapters = read_selected_materials(input_dir, selected_chapters)
    if not chapters:
        raise ValueError("未读取到任何有效章节素材")

    all_output = []
    total = len(chapters)

    for i, ch in enumerate(chapters, 1):
        if progress_callback:
            progress_callback(i, total, f"正在生成: {ch['name']}")

        system_prompt, user_prompt = build_study_guide_prompt(
            material=ch["content"],
            focus_areas=focus_areas,
            detail_level=detail_level,
            include_mnemonics=include_mnemonics,
            include_exercises=include_exercises,
            template_path=prompt_template,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = call_llm(messages, config, stream=False)
        all_output.append(f"\n\n{'#'*60}\n# {i}. {ch['name']}\n{'#'*60}\n\n")
        all_output.append(result)

        if i < total:
            time.sleep(1)

    return "".join(all_output)


# ============================================================
# 思维导图生成
# ============================================================

def generate_mindmap(
    input_dir: Path,
    selected_chapters: list[str],
    config: AppConfig,
    format_pref: str = "both",
    prompt_template: Optional[Path] = None,
    stream_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    生成思维导图 Markdown。

    Returns:
        包含 Markmap + Mermaid 的 Markdown 文本
    """
    chapters = read_selected_materials(input_dir, selected_chapters)
    if not chapters:
        raise ValueError("未读取到任何有效章节素材")

    parts = []
    for ch in chapters:
        parts.append(f"\n=== {ch['name']} ===\n{ch['content']}\n")
    material = "\n".join(parts)

    system_prompt, user_prompt = build_mindmap_prompt(
        material=material,
        format_pref=format_pref,
        template_path=prompt_template,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return call_llm(messages, config, stream=True, stream_callback=stream_callback)


def extract_mermaid_blocks(text: str) -> list[str]:
    """从生成结果中提取 Mermaid mindmap 代码块"""
    blocks = re.findall(r"```mermaid\n(mindmap.*?)```", text, re.DOTALL)
    return blocks
