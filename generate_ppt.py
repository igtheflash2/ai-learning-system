#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教学用 PPT 生成脚本
生成项目总结与教学演示幻灯片
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

# ============================================================
# 配色方案 — 学术蓝灰系
# ============================================================
COLOR_PRIMARY = RGBColor(26, 60, 110)      # #1a3c6e 深蓝
COLOR_SECONDARY = RGBColor(44, 95, 138)    # #2c5f8a 中蓝
COLOR_ACCENT = RGBColor(70, 130, 180)      # 亮蓝点缀
COLOR_TEXT = RGBColor(51, 51, 51)          # 深灰正文
COLOR_TEXT_LIGHT = RGBColor(102, 102, 102) # 浅灰副文
COLOR_WHITE = RGBColor(255, 255, 255)
COLOR_BG_LIGHT = RGBColor(245, 248, 252)   # 极浅蓝背景

# ============================================================
# 工具函数
# ============================================================
def add_title_slide(prs, title, subtitle=""):
    """封面页"""
    slide_layout = prs.slide_layouts[6]  # 空白布局
    slide = prs.slides.add_slide(slide_layout)
    
    # 背景色块
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_PRIMARY
    shape.line.fill.background()
    
    # 标题
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.5), Inches(8.4), Inches(1.5))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE
    p.font.name = "微软雅黑"
    p.alignment = PP_ALIGN.CENTER
    
    # 副标题
    if subtitle:
        sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(4.2), Inches(8.4), Inches(1))
        tf2 = sub_box.text_frame
        p2 = tf2.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(20)
        p2.font.color.rgb = RGBColor(180, 200, 220)
        p2.font.name = "微软雅黑"
        p2.alignment = PP_ALIGN.CENTER
    
    # 底部信息
    info_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.8), Inches(8.4), Inches(0.5))
    tf3 = info_box.text_frame
    p3 = tf3.paragraphs[0]
    p3.text = "技术文档与教学演示  |  2026.05"
    p3.font.size = Pt(14)
    p3.font.color.rgb = RGBColor(150, 170, 190)
    p3.font.name = "微软雅黑"
    p3.alignment = PP_ALIGN.CENTER
    
    return slide

def add_section_slide(prs, title, subtitle=""):
    """章节分隔页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_SECONDARY
    shape.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(3), Inches(8.4), Inches(1.2))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE
    p.font.name = "微软雅黑"
    p.alignment = PP_ALIGN.CENTER
    
    if subtitle:
        sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(4.3), Inches(8.4), Inches(0.8))
        tf2 = sub_box.text_frame
        p2 = tf2.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(18)
        p2.font.color.rgb = RGBColor(200, 215, 230)
        p2.font.name = "微软雅黑"
        p2.alignment = PP_ALIGN.CENTER
    
    return slide

def add_content_slide(prs, title, bullets, note=""):
    """标准内容页（左侧标题 + 右侧要点）或上下布局"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    
    # 顶部装饰条
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.15))
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_PRIMARY
    bar.line.fill.background()
    
    # 标题
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.font.name = "微软雅黑"
    
    # 内容区
    content_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(9), Inches(5.5))
    tf2 = content_box.text_frame
    tf2.word_wrap = True
    
    for i, bullet in enumerate(bullets):
        if i == 0:
            p = tf2.paragraphs[0]
        else:
            p = tf2.add_paragraph()
        p.text = f"●  {bullet}"
        p.font.size = Pt(18)
        p.font.color.rgb = COLOR_TEXT
        p.font.name = "微软雅黑"
        p.space_before = Pt(12)
        p.line_spacing = 1.4
    
    # 备注
    if note:
        note_box = slide.shapes.add_textbox(Inches(0.5), Inches(6.8), Inches(9), Inches(0.5))
        tf3 = note_box.text_frame
        p3 = tf3.paragraphs[0]
        p3.text = note
        p3.font.size = Pt(12)
        p3.font.color.rgb = COLOR_TEXT_LIGHT
        p3.font.name = "微软雅黑"
        p3.font.italic = True
    
    return slide

def add_two_column_slide(prs, title, left_title, left_items, right_title, right_items):
    """双栏对比页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.15))
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_PRIMARY
    bar.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.font.name = "微软雅黑"
    
    # 左栏
    left_title_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(4.3), Inches(0.6))
    ltf = left_title_box.text_frame
    lp = ltf.paragraphs[0]
    lp.text = left_title
    lp.font.size = Pt(20)
    lp.font.bold = True
    lp.font.color.rgb = COLOR_SECONDARY
    lp.font.name = "微软雅黑"
    
    left_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.9), Inches(4.3), Inches(5))
    ltf2 = left_box.text_frame
    ltf2.word_wrap = True
    for i, item in enumerate(left_items):
        p = ltf2.paragraphs[0] if i == 0 else ltf2.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(16)
        p.font.color.rgb = COLOR_TEXT
        p.font.name = "微软雅黑"
        p.space_before = Pt(8)
    
    # 分隔线
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(4.95), Inches(1.3), Inches(0.02), Inches(5.2))
    line.fill.solid()
    line.fill.fore_color.rgb = RGBColor(220, 220, 220)
    line.line.fill.background()
    
    # 右栏
    right_title_box = slide.shapes.add_textbox(Inches(5.2), Inches(1.3), Inches(4.3), Inches(0.6))
    rtf = right_title_box.text_frame
    rp = rtf.paragraphs[0]
    rp.text = right_title
    rp.font.size = Pt(20)
    rp.font.bold = True
    rp.font.color.rgb = COLOR_SECONDARY
    rp.font.name = "微软雅黑"
    
    right_box = slide.shapes.add_textbox(Inches(5.2), Inches(1.9), Inches(4.3), Inches(5))
    rtf2 = right_box.text_frame
    rtf2.word_wrap = True
    for i, item in enumerate(right_items):
        p = rtf2.paragraphs[0] if i == 0 else rtf2.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(16)
        p.font.color.rgb = COLOR_TEXT
        p.font.name = "微软雅黑"
        p.space_before = Pt(8)
    
    return slide

def add_table_slide(prs, title, headers, rows):
    """表格页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.15))
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_PRIMARY
    bar.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.font.name = "微软雅黑"
    
    rows_count = len(rows) + 1
    cols_count = len(headers)
    table = slide.shapes.add_table(rows_count, cols_count, Inches(0.5), Inches(1.4), Inches(9), Inches(0.6 + len(rows)*0.45)).table
    
    # 表头
    for i, header in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_PRIMARY
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = COLOR_WHITE
        p.font.name = "微软雅黑"
        p.alignment = PP_ALIGN.CENTER
    
    # 数据行
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx+1, c_idx)
            cell.text = str(val)
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(13)
            p.font.color.rgb = COLOR_TEXT
            p.font.name = "微软雅黑"
            if c_idx == 0:
                p.alignment = PP_ALIGN.LEFT
            else:
                p.alignment = PP_ALIGN.CENTER
            if r_idx % 2 == 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(240, 245, 250)
    
    return slide

def add_process_slide(prs, title, steps):
    """流程步骤页（横向时间线风格）"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.15))
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_PRIMARY
    bar.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.font.name = "微软雅黑"
    
    # 步骤纵向排列，带编号圆圈
    y_start = Inches(1.4)
    for i, step in enumerate(steps):
        y = y_start + i * Inches(0.85)
        
        # 编号圆圈
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.5), y, Inches(0.4), Inches(0.4))
        circle.fill.solid()
        circle.fill.fore_color.rgb = COLOR_SECONDARY
        circle.line.fill.background()
        
        num_box = slide.shapes.add_textbox(Inches(0.5), y, Inches(0.4), Inches(0.4))
        ntf = num_box.text_frame
        ntf.paragraphs[0].text = str(i+1)
        ntf.paragraphs[0].font.size = Pt(16)
        ntf.paragraphs[0].font.bold = True
        ntf.paragraphs[0].font.color.rgb = COLOR_WHITE
        ntf.paragraphs[0].alignment = PP_ALIGN.CENTER
        ntf.paragraphs[0].font.name = "微软雅黑"
        
        # 文字
        text_box = slide.shapes.add_textbox(Inches(1.1), y, Inches(8.4), Inches(0.5))
        ttf = text_box.text_frame
        ttf.word_wrap = True
        ttf.paragraphs[0].text = step
        ttf.paragraphs[0].font.size = Pt(18)
        ttf.paragraphs[0].font.color.rgb = COLOR_TEXT
        ttf.paragraphs[0].font.name = "微软雅黑"
    
    return slide

# ============================================================
# 主程序：构建 PPT
# ============================================================
def main():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    
    # --------------------------------------------------------
    # 1. 封面
    # --------------------------------------------------------
    add_title_slide(prs, 
        "软考系统架构设计师\nAI 学习资料生成工作台",
        "项目框架 · 技术架构 · 实现流程  教学演示")
    
    # --------------------------------------------------------
    # 2. 目录
    # --------------------------------------------------------
    add_content_slide(prs, "演示大纲", [
        "项目背景与痛点分析 —— 为什么要做这个项目",
        "系统定位与核心价值 —— 解决什么问题、为谁服务",
        "整体架构与技术栈 —— 分层设计与关键技术选型",
        "核心处理流程 —— 从原始素材到多模态输出的全链路",
        "双前端策略与界面 —— Streamlit 快速原型 + Flask 生产级",
        "关键设计决策 —— 5 个影响深远的架构选择",
        "教学成果与输出样例 —— 5 种格式的学习资料",
        "演进路线与展望 —— 从工具到平台的演进规划"
    ], note="本演示面向技术培训场景，帮助学员理解项目全貌")
    
    # --------------------------------------------------------
    # 3. 章节分隔：项目背景
    # --------------------------------------------------------
    add_section_slide(prs, "01  项目背景与痛点", "为什么要做这个项目？")
    
    # --------------------------------------------------------
    # 4. 备考痛点
    # --------------------------------------------------------
    add_content_slide(prs, "软考备考的四大痛点", [
        "素材分散：教材、讲义、真题分布在 PDF / Word / Excel 多种格式中，人工整理耗时巨大",
        "格式混乱：大量培训资料带有水印、页眉页脚广告，严重干扰阅读和知识提取",
        "缺乏结构化：知识点之间关联性弱，考生难以形成体系化记忆和知识网络",
        "输出单一：传统方式只能产出静态文档，无法自动生成思维导图、统计图表等多模态资料"
    ], note="数据来源：软考培训市场调研与考生反馈")
    
    # --------------------------------------------------------
    # 5. 项目定位
    # --------------------------------------------------------
    add_content_slide(prs, "项目定位与目标用户", [
        "核心定位：面向「软考系统架构设计师」的 AI 辅助学习资料自动生成工作台",
        "目标用户① 备考考生 —— 快速将教材转化为结构化资料、思维导图、速记卡片",
        "目标用户② 培训讲师 —— 批量生成标准化讲义，针对不同班级调整深度和案例",
        "目标用户③ 知识整理者 —— 将零散技术文档沉淀为可复用的知识体系",
        "核心价值：OCR → 清洗 → AI 深度加工 → 多格式导出，一站式资料生产"
    ])
    
    # --------------------------------------------------------
    # 6. 章节分隔：架构
    # --------------------------------------------------------
    add_section_slide(prs, "02  系统架构与技术栈", "如何构建这个系统？")
    
    # --------------------------------------------------------
    # 7. 分层架构
    # --------------------------------------------------------
    add_content_slide(prs, "四层架构设计", [
        "前端层（二选一）：Streamlit 快速原型版 + Flask/HTML 生产级版，共用同一套业务逻辑",
        "API / 业务逻辑层：ai_generator（LLM 封装）、prompt_manager（提示词）、local_processor（本地清洗）、config_manager（配置中心）",
        "数据处理层：ocr_engine（PDF OCR）、readword/readexcel（文档提取）、excel_charter（智能图表）",
        "输出渲染层：docx_converter（Markdown→Word）、mindmap_renderer（Mermaid→PNG）、xmind_exporter（零依赖生成 .xmind）"
    ], note="关键设计：模块间单向依赖，底层不感知上层存在")
    
    # --------------------------------------------------------
    # 8. 技术栈表格
    # --------------------------------------------------------
    add_table_slide(prs, "关键技术选型", 
        ["层级", "技术/框架", "核心用途"],
        [
            ["AI 调用", "OpenAI SDK", "兼容 DeepSeek / Moonshot / OpenAI 等 OpenAI-Compatible API"],
            ["PDF OCR", "rapidocr + PyMuPDF + OpenCV", "扫描版/图片版 PDF 文字识别，DPI 可调"],
            ["Word 处理", "python-docx + win32com", "Markdown→精美排版 Word，支持表格与图片嵌入"],
            ["图表生成", "matplotlib + pandas", "自动从表格数据生成柱状/饼图/雷达/散点图"],
            ["思维导图", "mermaid-cli / Playwright", "Mermaid 代码→PNG/SVG 可视化"],
            ["XMind 导出", "zipfile + xml.etree", "零第三方依赖生成标准 .xmind 文件"],
            ["模板引擎", "Jinja2", "提示词模板动态渲染，支持用户自定义"],
            ["配置管理", "python-dotenv", ".env 文件加载 API Key 与环境变量"]
        ]
    )
    
    # --------------------------------------------------------
    # 9. 章节分隔：流程
    # --------------------------------------------------------
    add_section_slide(prs, "03  核心处理流程", "素材如何变成学习资料？")
    
    # --------------------------------------------------------
    # 10. 完整工作流
    # --------------------------------------------------------
    add_process_slide(prs, "一键全链路工作流", [
        "输入层：将 PDF课件 / Word讲义 / Excel数据表 放入 input/ 目录",
        "提取层：OCR 引擎与文档提取器将原始素材转换为 output_md/ 下的 Markdown 知识库",
        "加工层（双模式可选）：本地模式零成本清洗重组  /  API 模式调用 LLM 深度加工生成6大模块",
        "增值层：excel_charter 解析表格数据 → 自动统计图表；AI 生成 Markmap + Mermaid 思维导图",
        "输出层：docx_converter 生成精美 Word；mindmap_renderer 生成 PNG；xmind_exporter 生成 .xmind"
    ])
    
    # --------------------------------------------------------
    # 11. 双模式对比
    # --------------------------------------------------------
    add_two_column_slide(prs, "本地模式 vs API 模式",
        "本地模式（零成本）",
        [
            "零 API 费用，无需联网",
            "秒级完成，极速响应",
            "清洗重组，去水印、结构化",
            "自动排序、生成目录",
            "适合：快速去杂质、无网络环境"
        ],
        "API 模式（高质量）",
        [
            "按 Token 计费，需联网",
            "1~10 分钟，流式展示进度",
            "AI 润色，语言精炼专业",
            "考情分析 + 口诀 + 真题演练",
            "适合：最终版资料、思维导图"
        ]
    )
    
    # --------------------------------------------------------
    # 12. 章节分隔：前端
    # --------------------------------------------------------
    add_section_slide(prs, "04  双前端策略", "如何满足不同用户群体？")
    
    # --------------------------------------------------------
    # 13. Streamlit 版
    # --------------------------------------------------------
    add_content_slide(prs, "Streamlit 版 —— 快速原型与个人工具", [
        "宽屏布局 + 自定义 CSS（300+ 行样式注入），实现卡片容器、暗黑模式、按钮动效",
        "卡片式章节选择器：3 列网格，点击切换选中状态，直观高效",
        "提示词工作台：编辑 / 预览 / 重置 / AI 辅助修改 / 基于知识库生成模板",
        "知识库浏览器：左侧文件列表 + 右侧编辑/渲染预览双栏，实时查看效果",
        "流式输出打字机效果 + Pipeline 进度仪表盘，让等待过程可视化"
    ], note="启动命令：streamlit run app.py  |  地址：http://localhost:8501")
    
    # --------------------------------------------------------
    # 14. Flask HTML 版
    # --------------------------------------------------------
    add_content_slide(prs, "Flask/HTML 版 —— 生产级 Web 应用", [
        "完整单页应用（464 行 HTML + 958 行 CSS + 1148 行 JS），6 大功能标签页全覆盖",
        "设计系统：CSS 变量主题、玻璃态导航栏、卡片阴影、渐变点缀、完整暗黑模式",
        "响应式侧边栏：桌面端固定左侧，移动端滑出遮罩层，适配多种设备",
        "SSE 流式输出：Server-Sent Events 实时推送 AI 生成内容到日志区域",
        "Toast 通知系统 + 实时状态指示器（就绪/运行中/完成三色标识）"
    ], note="启动命令：python backend/app.py  |  地址：http://localhost:5001")
    
    # --------------------------------------------------------
    # 15. 章节分隔：设计决策
    # --------------------------------------------------------
    add_section_slide(prs, "05  关键设计决策", "5 个影响深远的架构选择")
    
    # --------------------------------------------------------
    # 16. 设计决策详情
    # --------------------------------------------------------
    add_content_slide(prs, "关键设计决策（1/2）", [
        "双前端策略：Streamlit 快速迭代 + Flask/HTML 精致体验，满足不同场景，共用同一套 modules/ 业务逻辑",
        "延迟导入依赖：rapidocr、PyMuPDF、OpenCV 等重型库均在函数内部导入，避免启动崩溃，降低环境配置门槛",
        "模板兜底机制：Jinja2 模板缺失时自动降级为内置默认提示词，确保系统在任何情况下都能运行"
    ])
    
    add_content_slide(prs, "关键设计决策（2/2）", [
        "流式与非流式统一封装：call_llm() 单函数通过 stream_callback 解耦两种模式，前端无论是否实时展示都调用同一接口",
        "LLM 驱动图表决策：excel_charter.py 不仅用规则判断图表类型，还能调用 LLM 分析数据语义，选择更合适的 chart type",
        "零依赖 XMind 导出：仅用 Python 标准库 zipfile + xml.etree 生成标准 .xmind，避免引入重型第三方库"
    ])
    
    # --------------------------------------------------------
    # 17. 章节分隔：成果
    # --------------------------------------------------------
    add_section_slide(prs, "06  教学成果与输出样例", "系统能产出什么？")
    
    # --------------------------------------------------------
    # 18. 输出格式
    # --------------------------------------------------------
    add_content_slide(prs, "五种输出格式全覆盖", [
        "结构化 Markdown 学习资料：6 大固定模块（考情分析 / 知识体系 / 考点精讲 / 新教材变化 / 记忆口诀 / 真题演练）",
        "精美排版 Word 文档：蓝灰学术色系、微软雅黑字体、表格带表头背景与斑马纹、页面边距规范",
        "思维导图（4 种格式）：Markmap（VS Code 交互式）、Mermaid（GitHub 原生渲染）、PNG 图片、XMind 文件",
        "自动统计图表：matplotlib 生成柱状图 / 饼图 / 雷达图 / 散点图 / 折线图，自动嵌入 Word 附录",
        "冲刺速记版：从完整版自动提炼核心考点，生成便携速记卡片"
    ])
    
    # --------------------------------------------------------
    # 19. 章节分隔：演进
    # --------------------------------------------------------
    add_section_slide(prs, "07  演进路线与展望", "从工具到平台")
    
    # --------------------------------------------------------
    # 20. 演进路线
    # --------------------------------------------------------
    add_table_slide(prs, "四阶段演进规划", 
        ["阶段", "主题", "关键特性"],
        [
            ["P0 体验优化", "已落地", "可插拔模块系统、提示词工作台、知识库浏览器、UI 美化"],
            ["P1 质量保障", "进行中", "QualityGate 质量门禁、自动重试机制、检查点恢复（断点续跑）"],
            ["P2 平台化", "规划中", "@tool 注册机制、Pipeline YAML 声明式编排、模板市场分享下载"],
            ["P3 企业级", "规划中", "多项目工作区、生成质量评估报告、多用户权限管理（讲师/学员/管理员）"]
        ]
    )
    
    # --------------------------------------------------------
    # 21. 总结
    # --------------------------------------------------------
    add_content_slide(prs, "项目总结", [
        "不是一个简单的 'PDF→AI→Markdown' 演示玩具，而是在每个环节都做了扎实工程化设计的生产力工具",
        "输入层支持 PDF（OCR）、Word（含 .doc 兼容）、Excel 三种格式，覆盖培训资料全场景",
        "处理层提供本地清洗与 AI 深度加工双模式，灵活应对有网/无网、有预算/零预算场景",
        "输出层覆盖 Markdown / Word / 思维导图（4种格式）/ 统计图表 / XMind，一站式满足学习需求",
        "具备良好的长期维护价值和商业转化潜力，演进路线清晰：从个人工具 → 可配置平台 → 企业级 SaaS"
    ])
    
    # --------------------------------------------------------
    # 22. 结束页
    # --------------------------------------------------------
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_PRIMARY
    shape.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.8), Inches(8.4), Inches(1.2))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = "感谢聆听"
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE
    p.font.name = "微软雅黑"
    p.alignment = PP_ALIGN.CENTER
    
    sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(4.2), Inches(8.4), Inches(1))
    tf2 = sub_box.text_frame
    p2 = tf2.paragraphs[0]
    p2.text = "欢迎交流讨论与二次开发"
    p2.font.size = Pt(20)
    p2.font.color.rgb = RGBColor(180, 200, 220)
    p2.font.name = "微软雅黑"
    p2.alignment = PP_ALIGN.CENTER
    
    # 保存
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "教学演示.pptx")
    prs.save(output_path)
    print(f"[OK] PPT 已生成：{output_path}")
    print(f"[INFO] 共 {len(prs.slides)} 页幻灯片")

if __name__ == "__main__":
    main()
