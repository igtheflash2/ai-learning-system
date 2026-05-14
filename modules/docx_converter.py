#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown 转 Word 模块
=====================
将 Markdown 文本转为格式精美的 .docx。
基于 python-docx。

前置条件：pip install python-docx
"""

import re
from pathlib import Path
from typing import Optional, Union

try:
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    Document = None


def _ensure_deps():
    if Document is None:
        raise ImportError("请安装 python-docx: pip install python-docx")


def _set_cell_shading(cell, color: str):
    """设置单元格背景色"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    shading.set(qn('w:val'), 'clear')
    tcPr.append(shading)


def _set_cell_text(cell, text: str, bold: bool = False, size: int = 10, color: Optional[tuple] = None):
    """设置单元格文本格式"""
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if bold:
        run.bold = True
    if color:
        run.font.color.rgb = RGBColor(*color)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)


def _add_formatted_paragraph(
    doc, text: str, style: str = 'Normal', size: int = 11,
    bold: bool = False, color: Optional[tuple] = None,
    alignment=None, space_before: int = 0, space_after: int = 6
):
    """添加格式化的段落"""
    p = doc.add_paragraph(style=style)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if bold:
        run.bold = True
    if color:
        run.font.color.rgb = RGBColor(*color)
    if alignment:
        p.alignment = alignment
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def _add_horizontal_rule(doc):
    """添加分隔线段落"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '4')
    bottom.set(qn('w:color'), 'CCCCCC')
    pBdr.append(bottom)
    pPr.append(pBdr)


def _parse_inline_formatting(p, remaining: str):
    """解析行内粗体/斜体格式并添加到段落"""
    parts = re.split(r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)', remaining)
    for part in parts:
        if part.startswith('***') and part.endswith('***'):
            text = part[3:-3]
            run = p.add_run(text)
            run.bold = True
            run.italic = True
        elif part.startswith('**') and part.endswith('**'):
            text = part[2:-2]
            run = p.add_run(text)
            run.bold = True
        elif part.startswith('*') and part.endswith('*') and len(part) > 2:
            text = part[1:-1]
            run = p.add_run(text)
            run.italic = True
        else:
            run = p.add_run(part)
        run.font.size = Pt(11)
        run.font.name = '微软雅黑'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')


def add_image_to_docx(
    doc: Document,
    image_path: Union[str, Path],
    width_cm: float = 14.0,
    caption: Optional[str] = None,
):
    """
    向 Word 文档中插入一张图片（居中、带可选图注）。

    Args:
        doc: python-docx Document 对象
        image_path: 图片文件路径
        width_cm: 图片宽度（厘米）
        caption: 可选图注文本
    """
    img_path = Path(image_path)
    if not img_path.exists():
        return

    # 居中段落
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(img_path), width=Cm(width_cm))

    # 图注
    if caption:
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_p.paragraph_format.space_before = Pt(2)
        cap_p.paragraph_format.space_after = Pt(10)
        cap_run = cap_p.add_run(f"图：{caption}")
        cap_run.font.size = Pt(9)
        cap_run.font.color.rgb = RGBColor(100, 100, 100)
        cap_run.font.name = '微软雅黑'
        cap_run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # 图片后空行
    doc.add_paragraph()


def embed_images_to_docx(
    docx_path: Union[str, Path],
    images: list[dict],
    output_path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    向已有的 .docx 文件末尾嵌入统计图表图片。

    Args:
        docx_path: 原始 .docx 文件路径
        images: 图表信息列表，每个元素为 dict，必须含 'path' 和 'title' 键
                格式: [{"path": "chart.png", "title": "图表标题"}, ...]
        output_path: 输出 .docx 路径，若为 None 则在原文件名上加 _with_charts

    Returns:
        输出文件路径
    """
    doc = Document(str(docx_path))
    doc_path = Path(docx_path)

    # 添加分页
    doc.add_page_break()

    # 添加"附录：统计图表"标题
    h = doc.add_heading('附录：统计数据可视化', level=2)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for img_info in images:
        img_path = img_info.get('path', '')
        title = img_info.get('title', '统计图表')
        add_image_to_docx(doc, img_path, width_cm=14.0, caption=title)

    if output_path is None:
        output_path = doc_path.parent / f"{doc_path.stem}_with_charts.docx"
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def convert_markdown_to_docx(
    md_content: str,
    output_path: Path,
    title: Optional[str] = None,
) -> Path:
    """
    将 Markdown 文本转换为 Word 文档。

    Args:
        md_content: Markdown 文本内容
        output_path: 输出的 .docx 文件路径
        title: 可选的文档标题，若未提供则自动检测一级标题

    Returns:
        生成的文件路径
    """
    _ensure_deps()
    doc = Document()

    # 设置默认字体
    style = doc.styles['Normal']
    font = style.font
    font.name = '微软雅黑'
    font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # 配置标题样式
    for level, (size, color_hex) in {
        1: (22, '1a3c6e'),
        2: (16, '2c5f8a'),
        3: (13, '3a7bbf'),
    }.items():
        style_name = f'Heading {level}'
        if style_name in doc.styles:
            hs = doc.styles[style_name]
            hs.font.name = '微软雅黑'
            hs.font.size = Pt(size)
            hs.font.bold = True
            hs.font.color.rgb = RGBColor(
                int(color_hex[0:2], 16),
                int(color_hex[2:4], 16),
                int(color_hex[4:6], 16),
            )
            hs.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            hs.paragraph_format.space_before = Pt(12 if level == 1 else 8)
            hs.paragraph_format.space_after = Pt(6)

    lines = md_content.split('\n')
    i = 0
    in_toc = False
    doc_title_added = False

    while i < len(lines):
        line = lines[i]

        # 跳过目录区块
        if line.strip().startswith('## 目录'):
            in_toc = True
            i += 1
            continue
        if in_toc:
            if line.strip().startswith('## ') and '目录' not in line:
                in_toc = False
            else:
                i += 1
                continue

        # Front matter / 引用块
        if line.strip().startswith('> '):
            text = line.strip()[2:]
            _add_formatted_paragraph(
                doc, text, size=10, color=(100, 100, 100),
                space_before=2, space_after=2
            )
            i += 1
            continue

        # 分隔线
        if line.strip().startswith('---') and len(line.strip()) >= 3:
            _add_horizontal_rule(doc)
            i += 1
            continue

        # 一级标题（文档标题）
        if line.strip().startswith('# ') and not line.strip().startswith('##'):
            text = line.strip()[2:].strip()
            if not doc_title_added:
                title_p = doc.add_paragraph()
                title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = title_p.add_run(title or text)
                run.font.size = Pt(28)
                run.bold = True
                run.font.color.rgb = RGBColor(26, 60, 110)
                run.font.name = '微软雅黑'
                run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                title_p.paragraph_format.space_after = Pt(2)
                doc_title_added = True
            else:
                doc.add_heading(text, level=1)
            i += 1
            continue

        # 二级标题
        if line.strip().startswith('## '):
            text = line.strip()[3:].strip()
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
            doc.add_heading(text, level=2)
            i += 1
            continue

        # 三级标题
        if line.strip().startswith('### '):
            text = line.strip()[4:].strip()
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
            doc.add_heading(text, level=3)
            i += 1
            continue

        # 表格解析
        if line.strip().startswith('|') and line.strip().endswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip())
                i += 1

            if len(table_lines) >= 2:
                header_cells = [c.strip() for c in table_lines[0].split('|')[1:-1]]
                data_rows = table_lines[2:] if len(table_lines) > 2 else []

                if data_rows:
                    num_cols = len(header_cells) if header_cells else len(
                        [c.strip() for c in data_rows[0].split('|')[1:-1]]
                    )
                    num_rows = len(data_rows)
                    if header_cells and any(h.strip() for h in header_cells):
                        num_rows += 1

                    table = doc.add_table(rows=num_rows, cols=num_cols)
                    table.alignment = WD_TABLE_ALIGNMENT.CENTER
                    table.style = 'Table Grid'

                    row_idx = 0
                    if header_cells and any(h.strip() for h in header_cells):
                        for j, h_cell in enumerate(header_cells):
                            clean_h = h_cell.replace('**', '')
                            cell = table.cell(0, j)
                            _set_cell_text(cell, clean_h, bold=True, size=9, color=(255, 255, 255))
                            _set_cell_shading(cell, '2c5f8a')
                        row_idx = 1

                    for dr in data_rows:
                        cells = [c.strip() for c in dr.split('|')[1:-1]]
                        while len(cells) < num_cols:
                            cells.append('')
                        for j, cell_text in enumerate(cells):
                            clean = cell_text.replace('**', '')
                            cell = table.cell(row_idx, j)
                            _set_cell_text(cell, clean, size=9)
                            if row_idx % 2 == 0 and (not header_cells or row_idx > 0):
                                _set_cell_shading(cell, 'f0f4f8')
                        row_idx += 1

                    doc.add_paragraph()
            continue

        # 特殊标记 ***背景***
        stripped = line.strip()
        if stripped.startswith('***') and stripped.endswith('***') and len(stripped) > 6:
            text = stripped.strip('*')
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(f'▎{text}')
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(44, 95, 138)
            run.font.name = '微软雅黑'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            i += 1
            continue

        # 普通段落（带行内格式）
        if line.strip():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.35
            _parse_inline_formatting(p, line)
            i += 1
        else:
            i += 1

    # 页面边距
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    return output_path
