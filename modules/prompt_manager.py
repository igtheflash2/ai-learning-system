#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词模板管理模块
==================
基于 Jinja2 实现提示词的动态渲染和版本管理。
"""

import re
from pathlib import Path
from typing import Optional

try:
    from jinja2 import Template, Environment, BaseLoader
except ImportError:
    Template = None
    Environment = None
    BaseLoader = None


def _fallback_render(template_text: str, variables: dict) -> str:
    """无 Jinja2 时的简单模板渲染（支持 {{ var }}）"""
    result = template_text
    for key, value in variables.items():
        result = result.replace(f"{{{{ {key} }}}}", str(value))
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def render_prompt(template_path: Path, variables: Optional[dict] = None) -> str:
    """从文件加载模板并渲染"""
    if not template_path.exists():
        raise FileNotFoundError(f"提示词模板不存在: {template_path}")

    text = template_path.read_text(encoding="utf-8")
    variables = variables or {}

    if Template is not None:
        env = Environment(loader=BaseLoader())
        template = env.from_string(text)
        return template.render(**variables)
    else:
        return _fallback_render(text, variables)


def build_study_guide_prompt(
    material: str,
    focus_areas: str = "全部章节",
    detail_level: str = "标准",
    include_mnemonics: bool = True,
    include_exercises: bool = True,
    template_path: Optional[Path] = None,
) -> tuple[str, str]:
    """构建学习资料生成的完整提示词，返回 (system_prompt, user_prompt)"""
    if template_path and template_path.exists():
        system_prompt = render_prompt(template_path, {
            "material": material,
            "focus_areas": focus_areas,
            "detail_level": detail_level,
            "include_mnemonics": include_mnemonics,
            "include_exercises": include_exercises,
        })
        user_prompt = "请根据以上角色定义和输出要求，基于提供的素材生成综合学习资料。"
        return system_prompt, user_prompt

    # 默认系统提示词（精简版，建议用模板文件覆盖）
    system_prompt = (
        "你是软考系统架构设计师考前辅导专家，拥有深厚的架构设计知识体系，"
        "熟悉第二版新教材的考点变化，擅长将零散的复习笔记转化为结构化、系统化的学习资料。"
    )

    user_prompt = f"""请根据以下复习笔记素材，生成系统架构设计师综合学习资料。

## 用户偏好
- 重点范围：{focus_areas}
- 详细程度：{detail_level}
- {'需要' if include_mnemonics else '不需要'}包含记忆口诀
- {'需要' if include_exercises else '不需要'}包含真题演练

## 素材内容

{material}

## 输出要求
1. 按章节输出考情分析、知识点体系、考点精讲、新教材变化、记忆口诀、真题演练
2. 输出冲刺速记手册（高频考点TOP20、易错题集、公式速查）
3. 输出案例专题总结
4. 输出论文专题指导
5. 用 Markdown 格式，适当使用表格、列表
"""
    return system_prompt, user_prompt


def build_mindmap_prompt(
    material: str,
    format_pref: str = "both",
    template_path: Optional[Path] = None,
) -> tuple[str, str]:
    """构建思维导图生成的完整提示词，返回 (system_prompt, user_prompt)"""
    if template_path and template_path.exists():
        system_prompt = render_prompt(template_path, {
            "material": material,
            "format_pref": format_pref,
        })
        user_prompt = "请根据以上角色定义和输出要求，基于提供的素材生成思维导图。"
        return system_prompt, user_prompt

    system_prompt = (
        "你是一名知识结构化专家和软考系统架构设计师考前辅导专家。"
        "你的任务是将复习笔记自动生成可呈现为思维导图的结构化大纲。"
    )

    user_prompt = f"""请为以下章节生成思维导图。
输出格式偏好：{format_pref}

章节素材内容如下：

{material}

## 输出要求
1. 输出 Markmap 格式（基于 Markdown 标题层级的思维导图）
2. 同时输出 Mermaid mindmap 代码块
3. 包含考情分支、知识主干、新教材变化、助记分支、真题索引
4. 层级合理，每层分支4-7个为宜
5. 去除广告信息，压缩冗余，保留核心名词、分值、分类
"""
    return system_prompt, user_prompt
