#!/usr/bin/env python3
"""Convert 考前复习材料完整版.md to a well-formatted Word document."""

import re
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def set_cell_shading(cell, color):
    """Set cell background shading."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    shading.set(qn('w:val'), 'clear')
    tcPr.append(shading)

def add_table_with_style(doc, rows, cols, header_data=None):
    """Add a formatted table with optional header."""
    table = doc.add_table(rows=rows, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    return table

def set_cell_text(cell, text, bold=False, size=10, color=None):
    """Set cell text with formatting."""
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
    # Reduce cell margins
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)

def add_formatted_paragraph(doc, text, style='Normal', size=11, bold=False, color=None, alignment=None, space_before=0, space_after=6):
    """Add a paragraph with formatting."""
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

def convert_markdown_to_docx(md_path, docx_path):
    """Convert the markdown review file to a formatted Word document."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = '微软雅黑'
    font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # Configure heading styles
    for level, (size, color_hex) in {1: (22, '1a3c6e'), 2: (16, '2c5f8a'), 3: (13, '3a7bbf')}.items():
        style_name = f'Heading {level}'
        if style_name in doc.styles:
            hs = doc.styles[style_name]
            hs.font.name = '微软雅黑'
            hs.font.size = Pt(size)
            hs.font.bold = True
            hs.font.color.rgb = RGBColor(
                int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            )
            hs.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            hs.paragraph_format.space_before = Pt(12 if level == 1 else 8)
            hs.paragraph_format.space_after = Pt(6)

    # Process lines
    lines = content.split('\n')
    i = 0
    
    # Skip the TOC section — we'll regenerate it
    in_toc = False
    
    while i < len(lines):
        line = lines[i]
        
        # Skip TOC lines (between "## 目录" and next "## ")
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
        
        # Front matter blockquote
        if line.strip().startswith('> '):
            text = line.strip()[2:]
            p = add_formatted_paragraph(doc, text, size=10, color=(100, 100, 100), space_before=2, space_after=2)
            i += 1
            continue
        
        # Horizontal rule (chapter separator)
        if line.strip().startswith('---') and len(line.strip()) >= 3:
            # Add a subtle separator paragraph
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
            i += 1
            continue
        
        # Heading level 1 (main title) - skip, we'll make our own
        if line.strip().startswith('# ') and '考前复习材料' in line:
            # Add document title
            title_p = doc.add_paragraph()
            title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title_p.add_run('软考系统架构设计师')
            run.font.size = Pt(28)
            run.bold = True
            run.font.color.rgb = RGBColor(26, 60, 110)
            run.font.name = '微软雅黑'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            title_p.paragraph_format.space_after = Pt(2)
            
            sub_p = doc.add_paragraph()
            sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = sub_p.add_run('考前复习材料完整版')
            run.font.size = Pt(20)
            run.font.color.rgb = RGBColor(44, 95, 138)
            run.font.name = '微软雅黑'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            sub_p.paragraph_format.space_after = Pt(6)
            
            i += 1
            continue
        
        # Heading level 2: ## Chapter
        if line.strip().startswith('## '):
            text = line.strip()[3:].strip()
            # Remove markdown links [text](#ref)
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
            doc.add_heading(text, level=2)
            i += 1
            continue
        
        # Heading level 3: ### Section
        if line.strip().startswith('### '):
            text = line.strip()[4:].strip()
            doc.add_heading(text, level=3)
            i += 1
            continue
        
        # Table parsing
        if line.strip().startswith('|') and line.strip().endswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip())
                i += 1
            
            if len(table_lines) >= 2:
                # Parse header row
                header_cells = [c.strip() for c in table_lines[0].split('|')[1:-1]]
                # Skip alignment row (index 1)
                data_rows = table_lines[2:] if len(table_lines) > 2 else []
                
                if len(data_rows) > 0:
                    num_cols = len(header_cells) if header_cells else len(
                        [c.strip() for c in data_rows[0].split('|')[1:-1]]
                    )
                    num_rows = len(data_rows)
                    if header_cells and any(h.strip() for h in header_cells):
                        num_rows += 1
                    
                    table = add_table_with_style(doc, num_rows, num_cols)
                    
                    row_idx = 0
                    # Header row
                    if header_cells and any(h.strip() for h in header_cells):
                        for j, h_cell in enumerate(header_cells):
                            clean_h = h_cell.replace('**', '')
                            cell = table.cell(0, j)
                            set_cell_text(cell, clean_h, bold=True, size=9, color=(255, 255, 255))
                            set_cell_shading(cell, '2c5f8a')
                        row_idx = 1
                    
                    # Data rows
                    for dr in data_rows:
                        cells = [c.strip() for c in dr.split('|')[1:-1]]
                        # Pad if needed
                        while len(cells) < num_cols:
                            cells.append('')
                        for j, cell_text in enumerate(cells):
                            clean = cell_text.replace('**', '')
                            cell = table.cell(row_idx, j)
                            set_cell_text(cell, clean, size=9)
                            # Alternate row shading
                            if row_idx % 2 == 0 and (not header_cells or row_idx > 0):
                                set_cell_shading(cell, 'f0f4f8')
                        row_idx += 1
                    
                    doc.add_paragraph()  # spacing after table
                else:
                    # If only header row + alignment row, skip
                    pass
            continue
        
        # Handle regular paragraphs with inline formatting
        if line.strip():
            # Check for special marker patterns
            stripped = line.strip()
            
            # Section markers like ***背景***
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
            
            # Empty after stripping markers
            # Process inline bold/italic
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.35
            
            # Parse inline formatting
            remaining = line
            # Handle **bold** and *italic* patterns
            parts = re.split(r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)', remaining)
            
            for part in parts:
                if part.startswith('***') and part.endswith('***'):
                    # Bold + italic
                    text = part[3:-3]
                    run = p.add_run(text)
                    run.bold = True
                    run.italic = True
                    run.font.size = Pt(11)
                    run.font.name = '微软雅黑'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                elif part.startswith('**') and part.endswith('**'):
                    text = part[2:-2]
                    run = p.add_run(text)
                    run.bold = True
                    run.font.size = Pt(11)
                    run.font.name = '微软雅黑'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                elif part.startswith('*') and part.endswith('*') and len(part) > 2:
                    text = part[1:-1]
                    run = p.add_run(text)
                    run.italic = True
                    run.font.size = Pt(11)
                    run.font.name = '微软雅黑'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
                else:
                    run = p.add_run(part)
                    run.font.size = Pt(11)
                    run.font.name = '微软雅黑'
                    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            
            i += 1
        else:
            # Empty line — skip
            i += 1

    # Set page margins
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Save
    doc.save(docx_path)
    print(f'Word document saved to: {docx_path}')
    print(f'File size: {__import__("os").path.getsize(docx_path)} bytes')


if __name__ == '__main__':
    import os
    md_file = r'd:\杂件\机器人\readpdf\综合学习资料_AI生成.md'
    docx_file = r'd:\杂件\机器人\readpdf\综合学习资料_AI生成.docx'
    
    if not os.path.exists(md_file):
        print(f'ERROR: Markdown file not found: {md_file}')
    else:
        convert_markdown_to_docx(md_file, docx_file)
