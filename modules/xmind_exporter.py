#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XMind 思维导图导出模块
======================
将 Mermaid mindmap 代码解析为树结构，导出为 .xmind 格式（XML inside ZIP）。

前置条件：无需额外依赖（Python 标准库 zipfile + xml.etree）
"""

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


# ============================================================
# Mermaid mindmap 语法解析
# ============================================================

def parse_mermaid_mindmap(mermaid_code: str) -> dict:
    """
    解析 Mermaid mindmap 语法为嵌套字典树。

    Mermaid mindmap 格式示例：
        mindmap
          root((中心主题))
            分支1
              子分支1-1
            分支2
              子分支2-1
                子分支2-1-1

    Returns:
        {"name": "root", "children": [...]}
    """
    lines = mermaid_code.strip().split('\n')

    # 跳过前导空行和 mindmap 声明行
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('mindmap'):
            start = i
            break

    tree_lines = lines[start:]
    if not tree_lines:
        return {"name": "empty", "children": []}

    # 确定缩进单位：取第一个非空行的前导空格数
    indent_sizes = [len(ln) - len(ln.lstrip()) for ln in tree_lines if ln.strip()]
    if not indent_sizes:
        return {"name": "empty", "children": []}

    base_indent = min(indent_sizes)
    if base_indent == 0 and len(indent_sizes) > 1:
        # 根节点可能没有缩进，取第二个缩进值
        second_indents = [s for s in indent_sizes if s > 0]
        if second_indents:
            base_indent = min(second_indents)

    # 默认缩进单位 = base_indent（当 base_indent == 0 时自动调整为 2）
    indent_unit = base_indent if base_indent > 0 else 2

    def _clean_name(text: str) -> str:
        """清理节点名称：去掉 ((  ))、[ ] 等 Mermaid 装饰符"""
        text = text.strip()
        # 剥离前导的 Mermaid 语法修饰符
        text = re.sub(r'^[\(\[*#]+\s*', '', text)
        text = re.sub(r'\s*[\)\]*]+$', '', text)
        # 特殊处理 ((text))
        text = re.sub(r'^\(+\(?', '', text)
        text = re.sub(r'\)+\)?$', '', text)
        text = text.strip('[]').strip()
        return text

    root = None
    # stack 中每个元素为 (depth, node)
    stack: list[tuple[int, dict]] = []

    for line in tree_lines:
        if not line.strip():
            continue

        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        depth = (indent - base_indent) // indent_unit if indent >= base_indent else 0
        if depth < 0:
            depth = 0

        name = _clean_name(stripped)
        if not name:
            continue

        node = {"name": name, "children": []}

        if root is None:
            root = node
            stack = [(depth, node)]
        else:
            # 回溯到正确的父深度
            while stack and stack[-1][0] >= depth:
                stack.pop()
            if stack:
                stack[-1][1]["children"].append(node)
            stack.append((depth, node))

    return root or {"name": "empty", "children": []}


# ============================================================
# XMind XML 构建
# ============================================================

NS = 'urn:xmind:xmap:xmlns:content:2.0'


def _make_topic(parent_elem: ET.Element, topic_id: str, title: str) -> ET.Element:
    """创建一个 XMind topic 元素"""
    topic = ET.SubElement(parent_elem, f'{{{NS}}}topic')
    topic.set('id', topic_id)
    title_elem = ET.SubElement(topic, f'{{{NS}}}title')
    title_elem.text = title
    return topic


def _add_children(parent_topic: ET.Element, children: list[dict], parent_id: str):
    """递归添加子主题"""
    if not children:
        return

    children_elem = ET.SubElement(parent_topic, f'{{{NS}}}children')
    topics_elem = ET.SubElement(children_elem, f'{{{NS}}}topics')

    for idx, child in enumerate(children):
        child_id = f'{parent_id}-{idx}'
        child_topic = _make_topic(topics_elem, child_id, child['name'])
        if child.get('children'):
            _add_children(child_topic, child['children'], child_id)


def _build_xmind_xml(topic_tree: dict) -> bytes:
    """构建 XMind content.xml 的 XML 字节"""
    root = ET.Element(f'{{{NS}}}xmap-content')
    root.set('xmlns', NS)

    sheet = ET.SubElement(root, f'{{{NS}}}sheet')
    sheet.set('id', 'default-sheet')
    sheet_title = ET.SubElement(sheet, f'{{{NS}}}title')
    sheet_title.text = '思维导图'

    # 根主题
    root_topic = _make_topic(sheet, 'root-topic', topic_tree['name'])
    if topic_tree.get('children'):
        _add_children(root_topic, topic_tree['children'], 'root-topic')

    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def _build_manifest_xml() -> bytes:
    """构建 manifest.xml"""
    root = ET.Element('manifest')
    for item in ['content.xml', 'meta.xml', 'styles.xml']:
        entry = ET.SubElement(root, 'file-entry')
        entry.set('full-path', item)
        entry.set('media-type', 'text/xml')
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def _build_meta_xml() -> bytes:
    """构建 meta.xml"""
    root = ET.Element('meta')
    creator = ET.SubElement(root, 'creator')
    creator.text = '软考学习资料生成器'
    version = ET.SubElement(root, 'version')
    version.text = '1.0'
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def _build_styles_xml() -> bytes:
    """构建 styles.xml（空骨架）"""
    root = ET.Element('styles')
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


# ============================================================
# 公开 API
# ============================================================

def export_mermaid_to_xmind(
    mermaid_code: str,
    output_path: Path,
    title: str = '思维导图',
) -> Optional[Path]:
    """
    将 Mermaid mindmap 代码导出为 .xmind 文件。

    Args:
        mermaid_code: Mermaid mindmap 代码文本
        output_path: 输出 .xmind 文件路径
        title: 思维导图标题（作为根节点）

    Returns:
        成功时返回输出路径，失败返回 None
    """
    try:
        topic_tree = parse_mermaid_mindmap(mermaid_code)
        if topic_tree['name'] == 'empty':
            return None

        # 用标题覆盖根节点名称
        topic_tree['name'] = title

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 构建各 XML
        content_xml = _build_xmind_xml(topic_tree)
        manifest_xml = _build_manifest_xml()
        meta_xml = _build_meta_xml()
        styles_xml = _build_styles_xml()

        # 打包为 .xmind (ZIP)
        with zipfile.ZipFile(str(output_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('content.xml', content_xml)
            zf.writestr('meta.xml', meta_xml)
            zf.writestr('manifest.xml', manifest_xml)
            zf.writestr('styles.xml', styles_xml)

        return output_path if output_path.exists() else None

    except Exception:
        return None


def export_mindmap_md_to_xmind(
    md_content: str,
    output_path: Path,
    title: str = '思维导图',
) -> Optional[Path]:
    """
    从 Markdown 文本中提取第一个 mermaid mindmap 代码块并导出为 .xmind。

    Args:
        md_content: 包含 ```mermaid ... ``` 代码块的 Markdown 文本
        output_path: 输出 .xmind 文件路径
        title: 思维导图标题

    Returns:
        成功时返回输出路径，失败返回 None
    """
    # 匹配 mermaid 代码块
    pattern = r"```mermaid\n(.*?)```"
    matches = re.findall(pattern, md_content, re.DOTALL)
    if not matches:
        return None

    mermaid_code = matches[0].strip()
    if not mermaid_code:
        return None

    return export_mermaid_to_xmind(mermaid_code, output_path, title)
