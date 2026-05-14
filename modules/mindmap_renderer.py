#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
思维导图渲染模块
================
将 Mermaid 代码块渲染为 PNG 图片。

支持两种方案：
1. mermaid-cli（需 Node.js + @mermaid-js/mermaid-cli）
2. Playwright（纯 Python，自动下载浏览器）

前置条件（二选一）：
  npm install -g @mermaid-js/mermaid-cli
  或
  pip install playwright && playwright install chromium
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def extract_mermaid_blocks(text: str) -> list[str]:
    """从 Markdown 文本中提取 mermaid 代码块内容"""
    # 匹配 ```mermaid ... ``` 格式的代码块
    pattern = r"```mermaid\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]


def _check_mmdc() -> Optional[str]:
    """检查 mermaid-cli (mmdc) 是否可用"""
    return shutil.which("mmdc")


def _check_playwright() -> bool:
    """检查 playwright 是否可用"""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


def render_with_mmdc(mermaid_code: str, output_path: Path, width: int = 1600, height: int = 1200) -> bool:
    """使用 mermaid-cli 渲染"""
    mmdc = _check_mmdc()
    if not mmdc:
        return False

    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', encoding='utf-8', delete=False) as f:
        f.write(mermaid_code)
        temp_mmd = Path(f.name)

    try:
        cmd = [
            mmdc,
            "-i", str(temp_mmd),
            "-o", str(output_path),
            "-b", "white",
            "-w", str(width),
            "-H", str(height),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0 and output_path.exists()
    finally:
        temp_mmd.unlink(missing_ok=True)


def render_with_playwright(mermaid_code: str, output_path: Path, width: int = 1600, height: int = 1200) -> bool:
    """使用 Playwright 渲染"""
    if not _check_playwright():
        return False

    from playwright.sync_api import sync_playwright

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body {{ margin: 0; background: white; }}
  #container {{ padding: 20px; }}
</style>
</head>
<body>
<div id="container">
<pre class="mermaid">
{mermaid_code}
</pre>
</div>
<script>
mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
</script>
</body>
</html>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', encoding='utf-8', delete=False) as f:
        f.write(html_content)
        temp_html = Path(f.name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file://{temp_html}")
            page.wait_for_selector(".mermaid svg", timeout=30000)
            # 等待渲染完成
            page.wait_for_timeout(2000)
            # 截图 SVG 区域
            svg = page.query_selector(".mermaid svg")
            if svg:
                svg.screenshot(path=str(output_path))
                browser.close()
                return output_path.exists()
            browser.close()
            return False
    except Exception:
        return False
    finally:
        temp_html.unlink(missing_ok=True)


def render_mindmap_to_png(
    md_content: str,
    output_path: Path,
    width: int = 1600,
    height: int = 1200,
) -> Optional[Path]:
    """
    从 Markdown 内容中提取第一个 mermaid 思维导图并渲染为 PNG。

    Args:
        md_content: 包含 mermaid 代码块的 Markdown 文本
        output_path: 输出 PNG 路径
        width: 图片宽度
        height: 图片高度

    Returns:
        成功时返回输出路径，失败返回 None
    """
    blocks = extract_mermaid_blocks(md_content)
    if not blocks:
        return None

    mermaid_code = blocks[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 优先尝试 mmdc，其次 playwright
    if render_with_mmdc(mermaid_code, output_path, width, height):
        return output_path
    if render_with_playwright(mermaid_code, output_path, width, height):
        return output_path
    return None


def render_mindmap_to_svg(
    md_content: str,
    output_path: Path,
) -> Optional[Path]:
    """
    将 Mermaid 渲染为 SVG（若 mmdc 可用）。
    """
    blocks = extract_mermaid_blocks(md_content)
    if not blocks:
        return None

    mmdc = _check_mmdc()
    if not mmdc:
        return None

    mermaid_code = blocks[0]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', encoding='utf-8', delete=False) as f:
        f.write(mermaid_code)
        temp_mmd = Path(f.name)

    try:
        cmd = [
            mmdc,
            "-i", str(temp_mmd),
            "-o", str(output_path),
            "-b", "white",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            return output_path
    finally:
        temp_mmd.unlink(missing_ok=True)
    return None

