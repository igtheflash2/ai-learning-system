#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
============
统一管理 API 配置、路径配置、工作流状态。
支持从 .env 文件、环境变量、Streamlit session_state 读取配置。
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class AppConfig:
    """应用全局配置"""

    # API 配置
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_tokens: int = 64000

    # 路径配置
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    input_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "input")
    output_md_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "output_md")
    output_mindmap_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "output_mindmap")
    prompts_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "prompts")

    # 内容阈值
    content_warn_threshold: int = 80000
    content_max_threshold: int = 280000

    # 重试配置
    retry_times: int = 3
    retry_delay: int = 5

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量和 .env 创建配置"""
        base = cls()

        # 尝试多种 API Key 环境变量
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY") or ""
        base.api_key = api_key

        # 可被通用变量覆盖
        base.base_url = os.getenv("LLM_BASE_URL", base.base_url)
        base.model = os.getenv("LLM_MODEL", base.model)

        # 如果 base_url 未被手动覆盖，根据 API Key 类型自动推断
        if not os.getenv("LLM_BASE_URL"):
            if os.getenv("MOONSHOT_API_KEY"):
                base.base_url = "https://api.moonshot.cn/v1"
        # 如果 model 未被手动覆盖，根据 base_url 自动推断
        if not os.getenv("LLM_MODEL"):
            base._auto_detect_model()

        return base

    def _auto_detect_model(self):
        """根据 base_url 自动推断默认模型名"""
        url = self.base_url.rstrip("/")
        if "moonshot" in url:
            self.model = "kimi-k2.6"
        elif "deepseek" in url:
            self.model = "deepseek-chat"
        elif "openai" in url or "openai.azure" in url:
            self.model = "gpt-4o"
        # 其他未知提供商保持原有默认值

    def is_api_ready(self) -> bool:
        """检查 API 配置是否可用"""
        return bool(self.api_key) and self.api_key not in (
            "your-deepseek-api-key-here",
            "sk-your-api-key",
        )


# ============================================================
# 水印过滤规则（全局复用）
# ============================================================

import re
from typing import Optional

def clean_line(line: str) -> Optional[str]:
    """清洗单行：去除水印、空行规范化；返回 None 表示该行应删除"""
    stripped = line.strip()
    if not stripped:
        return ""
    for pat in WATERMARK_PATTERNS:
        if re.match(pat, stripped):
            return None
    return line


# 注意：WATERMARK_PATTERNS 定义在 clean_line 之后，
# 但 Python 函数在调用时才会解析全局变量，所以没有问题。
# 为避免循环导入问题，请从本模块导入 clean_line 和 WATERMARK_PATTERNS。

WATERMARK_PATTERNS = [
    r"手资源独家更新.*",
    r"如在其他店购买务必差评.*",
    r"文老师软考教育",
    r"文老师系统架构设计师",
    r"淘宝搜",
    r"淘宝搜索:",
    r"淘宝搜索：",
    r"构设计",
    r"师系",
    r"均设计",
    r"勺设计师",
    r"设计师$",
    r"计师$",
]


# ============================================================
# 章节顺序（全局复用）
# ============================================================

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


def get_available_chapters(output_dir: Path) -> list[str]:
    """获取 output_dir 下按章节顺序排列的可用章节名"""
    available = set()
    if output_dir.exists():
        available = {fp.stem for fp in output_dir.glob("*.md")}

    result = []
    for name in CHAPTER_ORDER:
        if name in available:
            result.append(name)
    # 追加未在顺序表中的文件
    for fp in sorted(output_dir.glob("*.md")):
        if fp.stem not in CHAPTER_ORDER:
            result.append(fp.stem)
    return result
