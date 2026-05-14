#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大模型多文件综合分析 — 学习资料生成工作台
==========================================
Streamlit 主应用，整合 OCR、本地清洗、AI 生成、思维导图、Word 导出全流程。

启动方式：
    streamlit run app.py

前置条件：
    pip install streamlit python-docx openai python-dotenv jinja2
    # 可选（思维导图转图片）
    npm install -g @mermaid-js/mermaid-cli
    # 或
    pip install playwright && playwright install chromium
"""

import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# Streamlit 版本兼容
try:
    from streamlit import rerun as st_rerun
except ImportError:
    try:
        from streamlit import experimental_rerun as st_rerun
    except ImportError:
        def st_rerun():
            st.warning("请升级 Streamlit 以支持页面刷新")


def safe_rerun():
    """安全地刷新页面"""
    try:
        st_rerun()
    except Exception:
        pass

# ============================================================
# 模块导入
# ============================================================
from modules.config_manager import AppConfig, get_available_chapters, CHAPTER_ORDER, WATERMARK_PATTERNS, clean_line
from modules.ocr_engine import process_pdf_to_md, batch_process_pdfs
from modules.local_processor import process_local_study_guide
from modules.ai_generator import generate_study_guide, generate_study_guide_batch, generate_mindmap, read_chapter_material
from modules.docx_converter import convert_markdown_to_docx, embed_images_to_docx
from modules.mindmap_renderer import render_mindmap_to_png
from modules.excel_charter import generate_charts_from_excel, generate_charts_from_md, generate_charts_from_md_with_llm

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="软考架构设计师 · 学习资料生成工作台",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Session State 初始化
# ============================================================

def init_session_state():
    defaults = {
        "config": AppConfig.from_env(),
        "selected_chapters": [],
        "local_md": "",
        "ai_md": "",
        "mindmap_md": "",
        "docx_path": "",
        "mindmap_png_path": "",
        "current_step": "idle",  # idle, ocr, local, ai_guide, ai_mindmap, docx, render_png
        "logs": [],
        "run_mode": "api",  # api / local
        "generation_mode": "完整模式",  # 完整模式 / 逐章模式
        "uploaded_new": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()

# ============================================================
# 工具函数
# ============================================================

def add_log(msg: str):
    """添加日志并显示"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    st.session_state["logs"].append(line)
    # 只保留最近 200 条
    st.session_state["logs"] = st.session_state["logs"][-200:]


def save_temp_md(content: str, suffix: str = "temp") -> Path:
    """保存临时 Markdown 文件"""
    temp_dir = Path("temp_output")
    temp_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%m%d_%H%M%S")
    path = temp_dir / f"generated_{suffix}_{ts}.md"
    path.write_text(content, encoding="utf-8")
    return path


# 学习资料持久化路径（所有按钮生成的 md 统一保存至此）
STUDY_GUIDE_PATH = Path("综合学习资料_AI生成.md")


# ============================================================
# Word / Excel → Markdown 包装函数
# ============================================================

def process_word_to_md(word_path: Path, output_dir: Path) -> Path:
    """将 Word 文件（.docx / .doc）转为 Markdown 并保存到 output_dir"""
    import readword as rw
    output_dir.mkdir(parents=True, exist_ok=True)
    is_doc = word_path.suffix.lower() == ".doc"
    temp_path = None
    try:
        if is_doc:
            temp_path = rw.convert_doc_to_docx(word_path)
            docx_path = temp_path
        else:
            docx_path = word_path
        text = rw.extract_docx_text(docx_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if not text.strip():
        text = "[No extractable text content.]"

    md_name = rw.sanitize_filename(word_path.stem) + ".md"
    md_path = output_dir / md_name
    md_path.write_text(f"# {word_path.stem}\n\n{text}\n", encoding="utf-8")
    return md_path


def process_excel_to_md(excel_path: Path, output_dir: Path) -> Path:
    """将 Excel 文件（.xlsx / .xls）转为 Markdown 并保存到 output_dir"""
    import readexcel as rex
    output_dir.mkdir(parents=True, exist_ok=True)
    is_xls = excel_path.suffix.lower() == ".xls"
    if is_xls:
        if rex.xlrd is None:
            raise ImportError("请安装 xlrd: pip install xlrd")
        text = rex.extract_xls_text(excel_path)
    else:
        if rex.openpyxl is None:
            raise ImportError("请安装 openpyxl: pip install openpyxl")
        text = rex.extract_xlsx_text(excel_path)

    if not text.strip():
        text = "[No extractable text content.]"

    md_name = rex.sanitize_filename(excel_path.stem) + ".md"
    md_path = output_dir / md_name
    md_path.write_text(f"# {excel_path.stem}\n\n{text}\n", encoding="utf-8")
    return md_path


# ============================================================
# 自定义 CSS
# ============================================================

def inject_custom_css():
    """注入全局自定义 CSS 样式"""
    st.markdown("""
    <style>
    /* 全局字体与间距 */
    .main .block-container {
        max-width: 1200px;
        padding-top: 1.5rem;
    }

    /* 卡片容器 */
    div[data-testid="stVerticalBlockBorderer"] > div,
    .st-card {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: box-shadow 0.2s ease;
    }
    .st-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }

    /* 步骤标题 */
    h2, h3 {
        border-bottom: 2px solid #f0f2f6;
        padding-bottom: 0.4rem;
        margin-top: 1rem;
    }

    /* 按钮圆角 */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: transform 0.1s ease;
    }
    .stButton button:active {
        transform: scale(0.97);
    }

    /* 标签美化 */
    .stTabs [role="tab"] {
        border-radius: 6px 6px 0 0;
        font-weight: 500;
    }
    .stTabs [role="tab"][aria-selected="true"] {
        background: #e8f0fe;
        border-bottom: 2px solid #1a73e8;
    }

    /* 代码块文字大小 */
    .stCodeBlock {
        font-size: 0.85rem;
    }

    /* Sidebar 美化 */
    section[data-testid="stSidebar"] {
        min-width: 320px;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* 进度条颜色 */
    .stProgress > div > div {
        background: linear-gradient(90deg, #1a73e8, #4285f4);
    }

    /* 展开器小调整 */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #1a3c6e;
    }

    /* 多选框美化 */
    .stMultiSelect div[data-baseweb="select"] {
        border-radius: 8px;
    }

    /* 文件上传区域 */
    div[data-testid="stFileUploader"] {
        border: 2px dashed #ccc;
        border-radius: 12px;
        padding: 0.75rem;
    }
    div[data-testid="stFileUploader"]:hover {
        border-color: #1a73e8;
        background: #f0f6ff;
    }

    /* 流式输出打字区域 */
    .stream-output-area {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        max-height: 500px;
        overflow-y: auto;
        font-size: 0.95rem;
        line-height: 1.65;
    }
    .stream-output-area p {
        margin-bottom: 0.5rem;
    }

    /* 暗黑模式适配 — 跟随系统 */
    @media (prefers-color-scheme: dark) {
        div[data-testid="stVerticalBlockBorderer"] > div,
        .st-card { background: #1e1e1e; border-color: #333; }
        .stTabs [role="tab"][aria-selected="true"] { background: #1e2a4a; }
        .stream-output-area { background: #1e1e1e; border-color: #333; }
        .streamlit-expanderHeader { color: #8ab4f8; }
    }
    /* 暗黑模式 — 手动切换（通过 data-dark-mode 属性） */
    html[data-dark-mode="true"] .main,
    html[data-dark-mode="true"] div[data-testid="stVerticalBlockBorderer"] > div,
    html[data-dark-mode="true"] .st-card { background: #1e1e1e !important; border-color: #333 !important; }
    html[data-dark-mode="true"] .stTabs [role="tab"][aria-selected="true"] { background: #1e2a4a !important; }
    html[data-dark-mode="true"] .stream-output-area { background: #1e1e1e !important; border-color: #333 !important; }
    html[data-dark-mode="true"] .streamlit-expanderHeader { color: #8ab4f8 !important; }
    html[data-dark-mode="true"] .stMarkdown, html[data-dark-mode="true"] p,
    html[data-dark-mode="true"] li, html[data-dark-mode="true"] span:not(.st-emotion-css) { color: #e0e0e0 !important; }
    </style>

    <!-- 暗黑模式 JS toggle -->
    <script>
    (function() {
        try { var d = sessionStorage.getItem('darkMode');
        if (d === 'true') document.documentElement.setAttribute('data-dark-mode', 'true');
        } catch(e) {}
    })();
    function toggleDarkMode(e) {
        try {
            if (e) { document.documentElement.setAttribute('data-dark-mode', 'true');
            sessionStorage.setItem('darkMode', 'true');
            } else { document.documentElement.removeAttribute('data-dark-mode');
            sessionStorage.setItem('darkMode', 'false'); }
        } catch(e2) {}
    }
    </script>
    """, unsafe_allow_html=True)


# ============================================================
# 提示词工作台（Section 2.1）
# ============================================================

DEFAULT_PROMPTS = {
    "study_guide.j2": """# Agent Prompt：软考系统架构设计师学习资料生成器

## 角色定义
你是**软考系统架构设计师考前辅导专家**，拥有深厚的架构设计知识体系。

## 素材内容

{{ material }}

## 输出要求
1. 按章节输出考情分析、知识点体系、考点精讲
2. 输出冲刺速记手册
3. 用 Markdown 格式输出
""",
    "mindmap.j2": """# 思维导图生成器

## 角色定义
你是一名知识结构化专家和软考系统架构设计师考前辅导专家。

## 素材内容

{{ material }}

## 输出要求
1. 输出 Markmap 格式
2. 同时输出 Mermaid mindmap 代码块
""",
}


def render_prompt_workbench():
    """提示词工作台：浏览、编辑、重置、预览提示词模板"""
    cfg = st.session_state["config"]

    with st.expander("🔧 提示词工作台（Prompt Workbench）", expanded=False):
        st.markdown("浏览、编辑、预览提示词模板，修改后实时生效。")

        # 列出提示词模板文件
        prompt_files = list(cfg.prompts_dir.glob("*.j2")) + list(cfg.prompts_dir.glob("*.md"))
        prompt_options = [p.name for p in prompt_files]
        if not prompt_options:
            prompt_options = ["（默认模板）"]

        # 选择模板
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            selected_prompt = st.selectbox(
                "选择提示词模板",
                options=prompt_options,
                key="prompt_selector",
            )
        with col_p2:
            st.caption(" ")
            if st.button("🔄 重置为默认", use_container_width=True, key="reset_prompt_btn"):
                _reset_prompt_template(selected_prompt)
                st.success(f"已重置 {selected_prompt}")
                safe_rerun()

        # 读取并编辑模板内容
        if selected_prompt and selected_prompt != "（默认模板）":
            template_path = cfg.prompts_dir / selected_prompt
            current_content = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
        else:
            current_content = DEFAULT_PROMPTS.get("study_guide.j2", "")

        edited_content = st.text_area(
            "编辑提示词（支持 Jinja2 模板语法）",
            value=current_content,
            height=400,
            key="prompt_editor",
            help="修改后点击「保存修改」生效",
        )

        col_save, col_preview = st.columns([1, 2])
        with col_save:
            if selected_prompt and selected_prompt != "（默认模板）" and edited_content != current_content:
                if st.button("💾 保存修改", use_container_width=True, type="primary"):
                    template_path = cfg.prompts_dir / selected_prompt
                    template_path.write_text(edited_content, encoding="utf-8")
                    st.success(f"✅ 已保存至 {selected_prompt}")
                    add_log(f"提示词模板已更新: {selected_prompt}")

        # 预览渲染效果
        with col_preview:
            if st.checkbox("👁️ 预览渲染效果", value=False, key="preview_toggle"):
                with st.spinner("渲染中..."):
                    try:
                        from modules.prompt_manager import render_prompt
                        sample_vars = {
                            "material": "## 计算机硬件\n\n### 考情分析\n本章历年考查分值约4-6分...",
                            "focus_areas": "全部章节",
                            "detail_level": "标准",
                            "include_mnemonics": True,
                            "include_exercises": True,
                            "format_pref": "both",
                        }
                        if selected_prompt and selected_prompt != "（默认模板）":
                            rendered = render_prompt(cfg.prompts_dir / selected_prompt, sample_vars)
                        else:
                            rendered = edited_content.replace("{{ material }}", sample_vars["material"])
                        st.info("渲染结果（示例素材）")
                        st.code(rendered[:2000] + ("\n\n...（截断）" if len(rendered) > 2000 else ""), language="text")
                    except Exception as e:
                        st.error(f"渲染失败: {e}")

        # --- AI 辅助修改提示词 ---
        st.markdown("---")
        st.markdown("**🤖 AI 辅助修改**")
        st.caption("用自然语言描述你想如何修改提示词，AI 根据当前编辑框内容生成修改建议。")

        modification_request = st.text_area(
            "修改要求",
            placeholder="例如：让语气更专业严谨 / 增加考情分析字段 / 强调历年真题权重 / 改为英文输出...",
            height=80,
            key="prompt_mod_request",
            label_visibility="collapsed",
        )

        col_ai_btn, col_ai_hint = st.columns([1, 3])
        with col_ai_btn:
            can_modify = bool(modification_request.strip()) and cfg.is_api_ready()
            if st.button("🤖 生成 AI 修改建议", use_container_width=True, type="secondary",
                         disabled=not can_modify):
                with st.spinner("AI 正在分析并修改提示词..."):
                    try:
                        import openai
                        client = openai.OpenAI(
                            api_key=cfg.api_key,
                            base_url=cfg.base_url,
                        )
                        sys_prompt = (
                            "你是一名提示词工程专家。根据用户的修改要求，修改下面的提示词模板。"
                            "只返回修改后的完整提示词模板，不要加额外解释。"
                        )
                        user_prompt = (
                            f"当前提示词模板：\n---\n{edited_content}\n---\n\n"
                            f"用户修改要求：\n{modification_request}"
                        )
                        resp = client.chat.completions.create(
                            model=cfg.model,
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            max_tokens=cfg.max_tokens,
                        )
                        suggestion = resp.choices[0].message.content.strip()
                        st.session_state["_ai_suggested_prompt"] = suggestion
                        st.session_state["_ai_suggested_active"] = True
                        safe_rerun()
                    except Exception as e:
                        st.error(f"AI 修改失败: {e}")
                        add_log(f"AI 修改提示词失败: {e}")
        with col_ai_hint:
            if cfg.is_api_ready():
                st.caption("基于当前编辑框内容生成")
            else:
                st.caption("⚠️ 请先在侧边栏配置 API Key")

        # 显示 AI 修改建议
        if st.session_state.get("_ai_suggested_active") and st.session_state.get("_ai_suggested_prompt"):
            suggestion = st.session_state["_ai_suggested_prompt"]
            st.markdown("---")
            st.markdown("**📝 AI 修改建议**")

            tab_diff, tab_full = st.tabs(["并排对比", "完整结果"])
            with tab_diff:
                col_o, col_n = st.columns(2)
                with col_o:
                    st.markdown("**修改前**")
                    st.code(edited_content[:4000], language="text")
                with col_n:
                    st.markdown("**修改后**")
                    st.code(suggestion[:4000], language="text")
            with tab_full:
                st.code(suggestion, language="text")

            col_apply, col_discard = st.columns(2)
            with col_apply:
                if st.button("✅ 应用修改到模板", use_container_width=True, type="primary"):
                    target = selected_prompt if (selected_prompt and selected_prompt != "（默认模板）") else None
                    if target:
                        (cfg.prompts_dir / target).write_text(suggestion, encoding="utf-8")
                        add_log(f"AI 修改已应用至模板: {target}")
                        st.success(f"✅ 已保存至 {target}")
                    else:
                        # 默认模板 → 写入 study_guide.j2 供后续使用
                        fallback = cfg.prompts_dir / "study_guide.j2"
                        fallback.write_text(suggestion, encoding="utf-8")
                        add_log(f"AI 修改已保存为 {fallback.name}")
                        st.success(f"✅ 已保存至 {fallback.name} （默认模板）")
                    st.session_state["_ai_suggested_active"] = False
                    safe_rerun()
            with col_discard:
                if st.button("🗑️ 丢弃建议", use_container_width=True):
                    st.session_state["_ai_suggested_active"] = False
                    safe_rerun()

        # --- AI 基于全部知识库生成提示词模板 ---
        st.markdown("---")
        st.markdown("**📚 AI 基于全部知识库生成模板**")
        st.caption(
            "读取 output_md/ 下所有章节素材，调用 AI 综合分析后生成完整的提示词模板，并替换当前选中的模板。"
        )

        col_gen_btn, col_gen_status = st.columns([1, 3])
        with col_gen_btn:
            can_gen = cfg.is_api_ready()
            # 预先检查文件是否存在
            md_files = sorted(cfg.output_md_dir.glob("*.md"))
            has_material = len(md_files) > 0
            if st.button(
                "🤖 基于全部知识库生成模板",
                use_container_width=True,
                type="secondary",
                disabled=not (can_gen and has_material),
            ):
                with st.spinner("正在读取知识库文件并调用 AI 生成提示词模板..."):
                    try:
                        # 1. 读取所有 output_md 文件
                        add_log(f"开始基于 {len(md_files)} 个知识库文件生成提示词模板...")

                        # 2. 拼接素材内容（超出则截断）
                        combined_material = ""
                        total_size = 0
                        max_material_chars = 80000  # 约 80K 字符，避免超出 token 限制
                        file_list = []
                        for fp in md_files:
                            content = fp.read_text(encoding="utf-8")
                            file_list.append(f"## 文件: {fp.name}\n\n{content}")
                            total_size += len(content)

                        # 如果内容超过上限，仅取前 N 个文件
                        chunk = ""
                        for item in file_list:
                            if len(chunk) + len(item) > max_material_chars:
                                remaining = max_material_chars - len(chunk)
                                if remaining > 2000:
                                    chunk += item[:remaining] + "\n\n...（截断）"
                                break
                            chunk += item + "\n\n"

                        combined_material = chunk
                        file_count = len(md_files)
                        total_kb = total_size / 1024
                        used_kb = len(combined_material) / 1024

                        add_log(
                            f"已读取 {file_count} 个文件 ({total_kb:.0f} KB)，"
                            f"送入模型 {used_kb:.0f} KB"
                        )

                        # 3. 调用 AI 生成提示词模板
                        import openai
                        client = openai.OpenAI(
                            api_key=cfg.api_key,
                            base_url=cfg.base_url,
                        )
                        sys_prompt = (
                            "你是一名提示词工程专家和软考系统架构设计师辅导专家。\n\n"
                            "任务：根据下面提供的全部知识库素材（output_md/ 目录下的所有章节），"
                            "生成一个完整的、高质量的提示词模板（Jinja2 格式），用于 AI 后续基于素材生成学习资料。\n\n"
                            "要求：\n"
                            "1. 角色定义明确（软考系统架构设计师考前辅导专家）\n"
                            "2. 包含素材内容占位符 {{ material }}\n"
                            "3. 输出要求清晰：按章节输出考情分析、知识点体系、考点精讲、冲刺速记\n"
                            "4. 加入记忆口诀和真题演练的占位控制（例如 {% if include_mnemonics %} / {% if include_exercises %}）\n"
                            "5. 用 Markdown 格式输出\n"
                            "6. 语言：中文\n"
                            "7. 只返回提示词模板本身，不要额外解释"
                        )
                        user_prompt = (
                            f"以下是 output_md/ 目录下共 {file_count} 个知识库文件的完整内容"
                            f"（共 {total_kb:.0f} KB，实际送入 {used_kb:.0f} KB）：\n\n"
                            f"{combined_material}"
                        )
                        resp = client.chat.completions.create(
                            model=cfg.model,
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            max_tokens=cfg.max_tokens,
                        )
                        generated = resp.choices[0].message.content.strip()

                        # 4. 替换当前选中的模板
                        target = (
                            selected_prompt
                            if selected_prompt and selected_prompt != "（默认模板）"
                            else None
                        )
                        if target:
                            (cfg.prompts_dir / target).write_text(generated, encoding="utf-8")
                            add_log(f"AI 基于知识库生成的模板已保存至: {target}")
                            st.success(f"✅ 已基于 {file_count} 个知识库文件生成并保存至 {target}")
                        else:
                            fallback = cfg.prompts_dir / "study_guide.j2"
                            fallback.write_text(generated, encoding="utf-8")
                            add_log(f"AI 基于知识库生成的模板已保存为 {fallback.name}")
                            st.success(f"✅ 已基于 {file_count} 个知识库文件生成并保存至 {fallback.name}（默认模板）")

                        # 5. 预览生成的模板
                        st.markdown("**📝 生成的提示词模板预览（前 2000 字符）**")
                        st.code(generated[:2000] + ("\n\n...（截断）" if len(generated) > 2000 else ""), language="text")

                    except Exception as e:
                        st.error(f"生成失败: {e}")
                        add_log(f"AI 基于知识库生成模板失败: {e}")

        with col_gen_status:
            if not can_gen:
                st.caption("⚠️ 请先在侧边栏配置 API Key")
            elif not has_material:
                st.caption("⚠️ output_md/ 目录为空，请先上传素材")
            else:
                st.caption(f"将读取 output_md/ 全部 {len(md_files)} 个素材文件，调用 AI 综合分析后生成提示词模板")


def _reset_prompt_template(name: str):
    """重置提示词模板为默认内容"""
    if name in DEFAULT_PROMPTS:
        cfg = st.session_state["config"]
        path = cfg.prompts_dir / name
        path.write_text(DEFAULT_PROMPTS[name], encoding="utf-8")
        add_log(f"提示词模板已重置: {name}")


# ============================================================
# 知识库浏览器（Section 2.2）
# ============================================================

def render_knowledge_browser():
    """知识库浏览器：预览、编辑知识库文件"""
    cfg = st.session_state["config"]

    with st.expander("📂 知识库浏览器（Knowledge Base Browser）", expanded=False):
        col_b1, col_b2 = st.columns([1, 2])

        # 左侧：文件列表
        with col_b1:
            st.markdown("**文件列表**")
            all_files = sorted(cfg.output_md_dir.glob("*.md"))
            if not all_files:
                st.caption("output_md/ 目录为空")
                return

            file_options = [f.name for f in all_files]
            selected_file = st.selectbox(
                "选择文件",
                options=file_options,
                key="kb_file_selector",
                label_visibility="collapsed",
            )

            # 文件信息
            if selected_file:
                fp = cfg.output_md_dir / selected_file
                size_kb = fp.stat().st_size / 1024
                st.caption(f"大小：{size_kb:.1f} KB")
                st.caption(f"修改时间：{datetime.fromtimestamp(fp.stat().st_mtime).strftime('%m-%d %H:%M')}")

                if st.button("🗑️ 删除临时文件", use_container_width=True, key="kb_delete"):
                    try:
                        fp.unlink()
                        st.success(f"已删除 {selected_file}")
                        add_log(f"知识库文件已删除: {selected_file}")
                        safe_rerun()
                    except Exception as e:
                        st.error(f"删除失败: {e}")

        # 右侧：内容预览与编辑
        with col_b2:
            if selected_file:
                fp = cfg.output_md_dir / selected_file
                content = fp.read_text(encoding="utf-8")

                tab_raw, tab_preview = st.tabs(["📝 编辑", "👁️ 渲染预览"])

                with tab_raw:
                    edited = st.text_area(
                        "编辑内容",
                        value=content,
                        height=500,
                        key="kb_editor",
                    )
                    if edited != content:
                        if st.button("💾 保存更改", type="primary", use_container_width=True):
                            fp.write_text(edited, encoding="utf-8")
                            st.success("✅ 已保存")
                            add_log(f"知识库文件已编辑: {selected_file}")
                            safe_rerun()

                with tab_preview:
                    preview_content = edited if 'edited' in locals() else content
                    with st.container(height=500):
                        st.markdown(preview_content)
            else:
                st.caption("请选择一个文件")


# ============================================================
# 卡片式章节选择器（Section 3.2）
# ============================================================

def render_chapter_card_selector(available: list[str]) -> list[str]:
    """卡片风格的章节多选器，代替原生 multiselect"""
    st.markdown("**📖 选择章节（点击卡片切换）**")
    st.caption(f"共 {len(available)} 个章节可用")

    # 用 columns 分行显示卡片
    selected = st.session_state.get("_card_selected", [])
    cols_per_row = 3
    for i in range(0, len(available), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, ch in enumerate(available[i:i + cols_per_row]):
            with cols[j]:
                is_selected = ch in selected
                btn_type = "primary" if is_selected else "secondary"
                icon = "✅ " if is_selected else "📄 "
                if st.button(
                    f"{icon}{ch}",
                    key=f"card_{ch}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    if is_selected:
                        selected.remove(ch)
                    else:
                        selected.append(ch)
                    st.session_state["_card_selected"] = selected
                    safe_rerun()

    # 快捷操作
    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    with col_q1:
        if st.button("全选", use_container_width=True):
            st.session_state["_card_selected"] = list(available)
            safe_rerun()
    with col_q2:
        if st.button("全不选", use_container_width=True):
            st.session_state["_card_selected"] = []
            safe_rerun()
    with col_q3:
        if st.button("选前5章", use_container_width=True):
            st.session_state["_card_selected"] = list(available[:5])
            safe_rerun()
    with col_q4:
        if st.button("反选", use_container_width=True):
            selected_set = set(st.session_state.get("_card_selected", []))
            st.session_state["_card_selected"] = [ch for ch in available if ch not in selected_set]
            safe_rerun()

    st.caption(f"已选 **{len(selected)}** 个章节")
    return selected


# ============================================================
# 侧边栏
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.title("⚙️ 配置面板")

        # 运行模式
        st.subheader("运行模式")
        mode = st.radio(
            "选择运行模式",
            options=["API 模式（AI 深度加工）", "本地模式（零 API 成本）"],
            index=0 if st.session_state["run_mode"] == "api" else 1,
            help="API 模式调用大模型生成高质量内容；本地模式仅做清洗重组，不消耗 API 额度",
        )
        st.session_state["run_mode"] = "api" if "API" in mode else "local"

        # API 配置
        if st.session_state["run_mode"] == "api":
            st.subheader("API 配置")
            cfg = st.session_state["config"]

            api_key = st.text_input(
                "API Key",
                value=cfg.api_key,
                type="password",
                placeholder="sk-...",
                help="支持 DeepSeek / Moonshot(Kimi) / OpenAI 等兼容格式的 API",
            )
            base_url = st.text_input(
                "Base URL",
                value=cfg.base_url,
                placeholder="https://api.deepseek.com  /  https://api.moonshot.cn/v1",
                help="DeepSeek: https://api.deepseek.com | Kimi: https://api.moonshot.cn/v1 | OpenAI: https://api.openai.com/v1",
            )
            model = st.text_input(
                "模型名称",
                value=cfg.model,
                placeholder="deepseek-chat / kimi-k2.6 / gpt-4o ...",
                help="根据 base_url 对应的 API 提供商填写正确的模型名。"
                     "DeepSeek → deepseek-chat；Kimi(Moonshot) → kimi-k2.6；OpenAI → gpt-4o",
            )
            max_tokens = st.number_input(
                "Max Tokens", 1000, 128000, cfg.max_tokens, 1000,
                help="单次生成最大 token 数",
            )

            # 更新配置
            cfg.api_key = api_key.strip()
            cfg.base_url = base_url.strip()
            cfg.model = model.strip()
            cfg.max_tokens = max_tokens
            st.session_state["config"] = cfg

            if not cfg.is_api_ready():
                st.warning("⚠️ API Key 未配置，AI 功能将不可用")
            else:
                st.success("✅ API 已配置")

            # 生成模式
            st.subheader("生成策略")
            gen_mode = st.selectbox(
                "生成模式",
                ["完整模式", "逐章模式"],
                index=0 if st.session_state["generation_mode"] == "完整模式" else 1,
                help="完整模式一次性发送全部素材；逐章模式每章分别调用 API 后合并，适合超长素材",
            )
            st.session_state["generation_mode"] = gen_mode

        # 生成偏好（两种模式共用）
        st.subheader("生成偏好")
        st.session_state["focus_areas"] = st.text_input(
            "重点范围",
            value=st.session_state.get("focus_areas", "全部章节"),
            help="例如：全部章节 / 计算机硬件、操作系统、数据库",
        )
        st.session_state["detail_level"] = st.select_slider(
            "详细程度",
            options=["精简", "标准", "详细"],
            value=st.session_state.get("detail_level", "标准"),
        )
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.session_state["include_mnemonics"] = st.checkbox(
                "记忆口诀", value=st.session_state.get("include_mnemonics", True)
            )
        with col_m2:
            st.session_state["include_exercises"] = st.checkbox(
                "真题演练", value=st.session_state.get("include_exercises", True)
            )

        # 主题切换
        st.divider()
        st.caption("🎨 显示")
        dark_mode = st.checkbox("暗黑模式", value=st.session_state.get("_dark_mode", False),
                                help="切换亮色/暗色主题")
        if dark_mode != st.session_state.get("_dark_mode", False):
            st.session_state["_dark_mode"] = dark_mode
            safe_rerun()

        # 关于
        st.divider()
        st.caption(
            "📚 AI大模型多文件综合分析学习资料生成工具\n\n"
            "工作流：素材 → 清洗 → AI生成 → 思维导图 → Word导出\n\n"
            f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )


# ============================================================
# Step 1: 素材管理
# ============================================================

def render_step1_material():
    st.header("Step 1: 素材管理")

    cfg = st.session_state["config"]
    available = get_available_chapters(cfg.output_md_dir)

    col_left, col_right = st.columns([2, 1])

    if available:
        with col_left:
            st.subheader("📁 选择已有素材")

            # 初始化卡片选中状态
            if "_card_selected" not in st.session_state:
                preselected = available[:5] if len(available) >= 5 else available
                st.session_state["_card_selected"] = list(preselected)

            # 切换开关：卡片模式 vs 下拉模式
            use_card_mode = st.toggle(
                "卡片模式（点选）",
                value=st.session_state.get("_use_card_mode", True),
                help="卡片模式更直观，下拉模式更紧凑",
            )
            st.session_state["_use_card_mode"] = use_card_mode

            if use_card_mode:
                selected = render_chapter_card_selector(available)
            else:
                selected = st.multiselect(
                    "选择要处理的章节（复选）",
                    options=available,
                    default=st.session_state.get("_card_selected", available[:5]),
                    help="留空表示选择全部",
                )

            st.session_state["selected_chapters"] = selected if selected else available
            st.caption(f"已选择 **{len(st.session_state['selected_chapters'])}** 个章节")
    else:
        with col_left:
            st.info("output_md/ 目录下暂无素材，请上传 PDF 或运行 OCR")
        st.session_state["selected_chapters"] = []

    with col_right:
        st.subheader("📤 上传新资料")
        uploaded_files = st.file_uploader(
            "上传素材文件（多选：PDF / Word / Excel）",
            type=["pdf", "docx", "doc", "xlsx", "xls"],
            accept_multiple_files=True,
            help="上传 PDF → 自动 OCR；上传 Word/Excel → 自动提取文本并加入素材库",
        )

        if uploaded_files:
            progress_bar = st.progress(0)
            total = len(uploaded_files)
            results, errors = [], []
            for idx, uploaded_file in enumerate(uploaded_files):
                save_path = cfg.input_dir / uploaded_file.name
                save_path.write_bytes(uploaded_file.getvalue())
                ext = save_path.suffix.lower()

                if ext == ".pdf":
                    with st.spinner(f"OCR 中: {uploaded_file.name}..."):
                        try:
                            md_path = process_pdf_to_md(
                                save_path, cfg.output_md_dir,
                                progress_callback=lambda cur, tot, txt: None,
                            )
                            results.append(md_path)
                            add_log(f"OCR 完成: {uploaded_file.name} -> {md_path.name}")
                        except Exception as e:
                            st.error(f"OCR 失败: {uploaded_file.name} - {e}")
                            add_log(f"OCR 失败: {uploaded_file.name} - {e}")
                            errors.append(uploaded_file.name)
                elif ext in (".docx", ".doc"):
                    with st.spinner(f"提取 Word: {uploaded_file.name}..."):
                        try:
                            md_path = process_word_to_md(save_path, cfg.output_md_dir)
                            results.append(md_path)
                            add_log(f"Word 提取完成: {uploaded_file.name} -> {md_path.name}")
                        except Exception as e:
                            st.error(f"Word 提取失败: {uploaded_file.name} - {e}")
                            add_log(f"Word 提取失败: {uploaded_file.name} - {e}")
                            errors.append(uploaded_file.name)
                elif ext in (".xlsx", ".xls"):
                    with st.spinner(f"提取 Excel: {uploaded_file.name}..."):
                        try:
                            md_path = process_excel_to_md(save_path, cfg.output_md_dir)
                            results.append(md_path)
                            add_log(f"Excel 提取完成: {uploaded_file.name} -> {md_path.name}")
                        except Exception as e:
                            st.error(f"Excel 提取失败: {uploaded_file.name} - {e}")
                            add_log(f"Excel 提取失败: {uploaded_file.name} - {e}")
                            errors.append(uploaded_file.name)
                else:
                    st.warning(f"不支持的文件类型: {uploaded_file.name}")
                    errors.append(uploaded_file.name)

                progress_bar.progress((idx + 1) / total)

            if results and not errors:
                st.success(f"✅ 所有 {len(results)} 个文件已处理完成并加入知识库！")
            elif results and errors:
                st.warning(f"⚠️ {len(results)} 个成功，{len(errors)} 个失败")
            else:
                st.error("❌ 全部处理失败")
            st.session_state["uploaded_new"] = True
            safe_rerun()

        st.divider()
        if st.button("📥 批量转换: input/ → output_md", use_container_width=True,
                     help="扫描 input/ 目录下所有 PDF/Word/Excel，批量转换输出到 output_md/",
                     type="secondary"):
            # 收集所有支持的文件
            file_map: dict[str, list[Path]] = {}
            for pattern in ("*.pdf", "*.docx", "*.doc", "*.xlsx", "*.xls"):
                for p in sorted(cfg.input_dir.glob(pattern)):
                    file_map.setdefault(p.suffix.lower(), []).append(p)

            if not file_map:
                st.warning("input/ 目录下没有支持的源文件（PDF / Word / Excel）")
            else:
                all_files = []
                for _ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
                    all_files.extend(file_map.get(_ext, []))
                total_files = len(all_files)

                batch_bar = st.progress(0.0, text=f"正在转换共 {total_files} 个文件...")
                batch_status = st.empty()
                results, errors = [], []
                type_labels = {".pdf": "OCR", ".docx": "Word", ".doc": "Word",
                               ".xlsx": "Excel", ".xls": "Excel"}

                for idx, src_path in enumerate(all_files):
                    ext = src_path.suffix.lower()
                    label = type_labels.get(ext, "转换")
                    batch_status.caption(f"处理中: [{idx+1}/{total_files}] {label} - {src_path.name}")
                    try:
                        if ext == ".pdf":
                            md_path = process_pdf_to_md(src_path, cfg.output_md_dir)
                        elif ext in (".docx", ".doc"):
                            md_path = process_word_to_md(src_path, cfg.output_md_dir)
                        elif ext in (".xlsx", ".xls"):
                            md_path = process_excel_to_md(src_path, cfg.output_md_dir)
                        else:
                            continue
                        results.append(md_path)
                        add_log(f"{label} 完成: {src_path.name} -> {md_path.name}")
                    except Exception as e:
                        st.error(f"{label} 失败: {src_path.name} - {e}")
                        add_log(f"{label} 失败: {src_path.name} - {e}")
                        errors.append(src_path.name)
                    batch_bar.progress((idx + 1) / total_files)

                batch_status.empty()
                if results:
                    done_text = f"✅ 完成 {len(results)} 个文件"
                    if errors:
                        done_text += f"，{len(errors)} 个失败"
                    batch_bar.progress(1.0, text=done_text)
                    add_log(f"批量转换完成: {len(results)} 个文件 -> {cfg.output_md_dir}")
                    st.success(done_text)
                    st.session_state["uploaded_new"] = True
                    safe_rerun()

    # 显示素材统计
    if available:
        with st.expander("📊 素材统计"):
            stats = []
            for name in available:
                fp = cfg.output_md_dir / f"{name}.md"
                size = fp.stat().st_size if fp.exists() else 0
                stats.append({"章节": name, "大小(字节)": size})
            st.dataframe(stats, use_container_width=True, hide_index=True)


# ============================================================
# Step 2: 执行工作流
# ============================================================

def render_step2_workflow():
    st.header("Step 2: 执行生成")

    selected = st.session_state.get("selected_chapters", [])
    if not selected:
        st.warning("⚠️ 请先选择素材（Step 1）")
        return

    cfg = st.session_state["config"]
    run_mode = st.session_state["run_mode"]

    # Pipeline 进度仪表盘（Section 3.3）
    pipeline_stages = [
        ("🧹 本地清洗", bool(st.session_state.get("local_md"))),
        ("📝 AI 资料", bool(st.session_state.get("ai_md"))),
        ("🧠 思维导图", bool(st.session_state.get("mindmap_md"))),
        ("📝 Word", bool(st.session_state.get("docx_path"))),
        ("🖼️ PNG", bool(st.session_state.get("mindmap_png_path"))),
    ]
    total_done = sum(1 for _, done in pipeline_stages if done)
    with st.expander("📊 Pipeline 进度", expanded=False):
        for label, done in pipeline_stages:
            status = "✅" if done else "⏳"
            st.markdown(f"{status} **{label}**{' — 已完成' if done else ' — 未执行'}")
        st.progress(total_done / len(pipeline_stages),
                    text=f"总进度：{total_done}/{len(pipeline_stages)} 阶段")

    # 生成统计
    with st.expander("📈 内容统计", expanded=False):
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            local_len = len(st.session_state.get("local_md", ""))
            st.metric("本地清洗", f"{local_len:,} 字" if local_len else "未生成")
        with col_s2:
            ai_len = len(st.session_state.get("ai_md", ""))
            st.metric("AI 生成", f"{ai_len:,} 字" if ai_len else "未生成")
        with col_s3:
            mind_len = len(st.session_state.get("mindmap_md", ""))
            st.metric("思维导图", f"{mind_len:,} 字" if mind_len else "未生成")

    # 显示操作按钮
    cols = st.columns(6)

    with cols[0]:
        if st.button("🧹 本地清洗重组", use_container_width=True, help="不调用 API，仅本地清洗排序"):
            _run_local_cleaning(cfg, selected)

    with cols[1]:
        if st.button("📝 AI 学习资料", use_container_width=True, help="调用 AI 生成综合学习资料"):
            if run_mode == "api" and not cfg.is_api_ready():
                st.error("请先配置 API Key（侧边栏）")
                return
            _run_ai_study_guide(cfg, selected)

    with cols[2]:
        if st.button("🧠 AI 思维导图", use_container_width=True, help="调用 AI 生成思维导图"):
            if run_mode == "api" and not cfg.is_api_ready():
                st.error("请先配置 API Key（侧边栏）")
                return
            _run_ai_mindmap(cfg, selected)

    with cols[3]:
        if st.button("🚀 一键全链路", use_container_width=True, help="顺序执行：清洗 → AI资料 → 思维导图 → Word → PNG"):
            if run_mode == "api" and not cfg.is_api_ready():
                st.error("请先配置 API Key（侧边栏）")
                return
            _run_full_pipeline(cfg, selected)

    with cols[4]:
        mindmap_md = st.session_state.get("mindmap_md", "")
        if st.button("🖼️ 导出 PNG", use_container_width=True, disabled=not mindmap_md,
                     help="将思维导图 MD 渲染为 PNG 图片"):
            try:
                output_path = cfg.output_md_dir.parent / "思维导图_AI生成.png"
                result = render_mindmap_to_png(mindmap_md, output_path)
                if result:
                    st.session_state["mindmap_png_path"] = str(result)
                    st.success(f"PNG 导出成功: {result}")
                    add_log(f"PNG 导出完成: {result}")
                else:
                    st.error("PNG 导出失败（请检查 mermaid-cli 或 playwright 是否安装）")
            except Exception as e:
                st.error(f"PNG 导出异常: {e}")
                add_log(f"PNG 导出异常: {e}")

    with cols[5]:
        ai_md_btn = st.session_state.get("ai_md", "") or st.session_state.get("local_md", "")
        if st.button("📊 生成图表 Word", use_container_width=True, disabled=not ai_md_btn,
                     help="从学习资料中提取统计图表并嵌入 Word 文档"):
            try:
                chart_dir = cfg.output_md_dir.parent / "charts"
                docx_path = cfg.output_md_dir.parent / "综合学习资料_AI生成.docx"
                # 如果 docx 不存在先生成
                if not docx_path.exists():
                    source_md = STUDY_GUIDE_PATH.read_text(encoding="utf-8") if STUDY_GUIDE_PATH.exists() else ai_md_btn
                    convert_markdown_to_docx(source_md, docx_path)
                    st.session_state["docx_path"] = str(docx_path)
                    add_log(f"Word 文档已生成: {docx_path}")
                # 生成图表
                charts = generate_charts_from_md_with_llm(ai_md_btn, chart_dir, sheet_name="AI学习资料",
                                                            cfg=cfg, add_log=add_log)
                st.session_state["chart_images"] = charts
                if charts:
                    out_path = embed_images_to_docx(docx_path, charts)
                    st.session_state["docx_with_charts_path"] = str(out_path)
                    st.success(f"图表 Word 生成完成，已嵌入 {len(charts)} 张图表")
                    add_log(f"图表 Word 完成: {out_path} ({len(charts)} charts)")
                else:
                    st.warning("未找到可统计的图表数据")
            except Exception as e:
                st.error(f"图表 Word 生成失败: {e}")
                add_log(f"图表 Word 异常: {e}")

    # 流式输出显示区域
    with st.expander("📋 执行日志 / 流式输出", expanded=True):
        if st.session_state["logs"]:
            log_placeholder = st.empty()
            log_lines = st.session_state["logs"][-50:]
            log_text = "\n".join(log_lines)
            log_placeholder.markdown(
                f'<div class="stream-output-area">{"<br>".join(log_lines)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("暂无日志")


def _run_local_cleaning(cfg: AppConfig, selected: list[str]):
    """执行本地清洗"""
    st.session_state["current_step"] = "local"
    add_log("开始本地清洗重组...")

    try:
        with st.spinner("正在本地清洗重组..."):
            result = process_local_study_guide(cfg.output_md_dir, selected)
            st.session_state["local_md"] = result
            STUDY_GUIDE_PATH.write_text(result, encoding="utf-8")
            add_log(f"本地清洗完成，共 {len(result):,} 字符，已保存至 {STUDY_GUIDE_PATH}")
        st.success("✅ 本地清洗重组完成！")
    except Exception as e:
        st.error(f"本地清洗失败: {e}")
        add_log(f"本地清洗失败: {e}")


def _run_ai_study_guide(cfg: AppConfig, selected: list[str]):
    """执行 AI 学习资料生成"""
    st.session_state["current_step"] = "ai_guide"
    add_log("开始 AI 学习资料生成...")

    placeholder = st.empty()
    stream_buffer = []

    def on_chunk(chunk: str):
        stream_buffer.append(chunk)
        # 每收到一定内容更新一次显示
        if len(stream_buffer) % 20 == 0:
            with placeholder.container():
                st.markdown("".join(stream_buffer) + "▌")

    try:
        with st.spinner("AI 正在生成，请稍候..."):
            if st.session_state.get("generation_mode") == "逐章模式":
                result = generate_study_guide_batch(
                    cfg.output_md_dir,
                    selected,
                    cfg,
                    focus_areas=st.session_state.get("focus_areas", "全部章节"),
                    detail_level=st.session_state.get("detail_level", "标准"),
                    include_mnemonics=st.session_state.get("include_mnemonics", True),
                    include_exercises=st.session_state.get("include_exercises", True),
                    prompt_template=cfg.prompts_dir / "study_guide.j2",
                    progress_callback=lambda cur, tot, msg: add_log(f"[{cur}/{tot}] {msg}"),
                )
            else:
                result = generate_study_guide(
                    cfg.output_md_dir,
                    selected,
                    cfg,
                    focus_areas=st.session_state.get("focus_areas", "全部章节"),
                    detail_level=st.session_state.get("detail_level", "标准"),
                    include_mnemonics=st.session_state.get("include_mnemonics", True),
                    include_exercises=st.session_state.get("include_exercises", True),
                    prompt_template=cfg.prompts_dir / "study_guide.j2",
                    stream_callback=on_chunk,
                )

            st.session_state["ai_md"] = result
            STUDY_GUIDE_PATH.write_text(result, encoding="utf-8")
            add_log(f"AI 学习资料生成完成，共 {len(result):,} 字符，已保存至 {STUDY_GUIDE_PATH}")
        placeholder.empty()
        st.success("✅ AI 学习资料生成完成！")
    except Exception as e:
        placeholder.empty()
        st.error(f"AI 生成失败: {e}")
        add_log(f"AI 生成失败: {e}")


def _run_ai_mindmap(cfg: AppConfig, selected: list[str]):
    """执行 AI 思维导图生成"""
    st.session_state["current_step"] = "ai_mindmap"
    add_log("开始 AI 思维导图生成...")

    placeholder = st.empty()
    stream_buffer = []

    def on_chunk(chunk: str):
        stream_buffer.append(chunk)
        if len(stream_buffer) % 20 == 0:
            with placeholder.container():
                st.markdown("".join(stream_buffer) + "▌")

    try:
        with st.spinner("AI 正在生成思维导图..."):
            result = generate_mindmap(
                cfg.output_md_dir,
                selected,
                cfg,
                format_pref="both",
                prompt_template=cfg.prompts_dir / "mindmap.j2",
                stream_callback=on_chunk,
            )
            st.session_state["mindmap_md"] = result
            path = save_temp_md(result, "mindmap")
            add_log(f"思维导图生成完成，共 {len(result):,} 字符，保存至 {path.name}")
        placeholder.empty()
        st.success("✅ 思维导图生成完成！")
    except Exception as e:
        placeholder.empty()
        st.error(f"思维导图生成失败: {e}")
        add_log(f"思维导图生成失败: {e}")


def _run_full_pipeline(cfg: AppConfig, selected: list[str]):
    """一键执行完整工作流"""
    progress = st.progress(0.0)
    status = st.empty()

    def set_status(step_name: str, pct: float):
        status.info(f"🔄 当前步骤：{step_name}")
        progress.progress(min(pct, 1.0))

    # Step 1: 本地清洗（可选，作为预处理）
    set_status("本地清洗重组", 0.1)
    try:
        local_result = process_local_study_guide(cfg.output_md_dir, selected)
        st.session_state["local_md"] = local_result
        add_log("本地清洗完成")
    except Exception as e:
        add_log(f"本地清洗跳过: {e}")

    # Step 2: AI 学习资料
    set_status("AI 生成学习资料", 0.3)
    try:
        if st.session_state.get("generation_mode") == "逐章模式":
            ai_result = generate_study_guide_batch(
                cfg.output_md_dir, selected, cfg,
                focus_areas=st.session_state.get("focus_areas", "全部章节"),
                detail_level=st.session_state.get("detail_level", "标准"),
                include_mnemonics=st.session_state.get("include_mnemonics", True),
                include_exercises=st.session_state.get("include_exercises", True),
                prompt_template=cfg.prompts_dir / "study_guide.j2",
            )
        else:
            ai_result = generate_study_guide(
                cfg.output_md_dir, selected, cfg,
                focus_areas=st.session_state.get("focus_areas", "全部章节"),
                detail_level=st.session_state.get("detail_level", "标准"),
                include_mnemonics=st.session_state.get("include_mnemonics", True),
                include_exercises=st.session_state.get("include_exercises", True),
                prompt_template=cfg.prompts_dir / "study_guide.j2",
            )
        st.session_state["ai_md"] = ai_result
        STUDY_GUIDE_PATH.write_text(ai_result, encoding="utf-8")
        add_log("AI 学习资料生成完成")
    except Exception as e:
        st.error(f"AI 学习资料生成失败: {e}")
        add_log(f"AI 学习资料生成失败: {e}")
        progress.empty()
        status.empty()
        return

    # Step 2.5: 生成统计图表（基于 AI 学习资料中的表格）
    set_status("生成统计图表", 0.4)
    try:
        ai_md_for_charts = st.session_state.get("ai_md", "")
        if ai_md_for_charts:
            chart_dir = cfg.output_md_dir.parent / "charts"
            charts = generate_charts_from_md_with_llm(ai_md_for_charts, chart_dir, sheet_name="AI学习资料",
                                                        cfg=cfg, add_log=add_log)
            st.session_state["chart_images"] = charts
            add_log(f"统计图表生成完成：共 {len(charts)} 张")
    except Exception as e:
        add_log(f"统计图表生成跳过: {e}")

    # Step 3: AI 思维导图
    set_status("AI 生成思维导图", 0.5)
    try:
        mm_result = generate_mindmap(
            cfg.output_md_dir, selected, cfg,
            format_pref="both",
            prompt_template=cfg.prompts_dir / "mindmap.j2",
        )
        st.session_state["mindmap_md"] = mm_result
        save_temp_md(mm_result, "mindmap")
        add_log("思维导图生成完成")
    except Exception as e:
        st.error(f"思维导图生成失败: {e}")
        add_log(f"思维导图生成失败: {e}")

    # Step 4: Word 转换（以 ./综合学习资料_AI生成.md 为准）
    set_status("转换为 Word", 0.75)
    try:
        md_content = STUDY_GUIDE_PATH.read_text(encoding="utf-8") if STUDY_GUIDE_PATH.exists() else ""
        if md_content:
            docx_path = cfg.output_md_dir.parent / "综合学习资料_AI生成.docx"
            convert_markdown_to_docx(md_content, docx_path)
            st.session_state["docx_path"] = str(docx_path)
            add_log(f"Word 转换完成: {docx_path}")
    except Exception as e:
        add_log(f"Word 转换失败: {e}")

    # Step 4.5: 嵌入统计图表到 Word 文档
    set_status("嵌入图表到 Word", 0.82)
    try:
        charts = st.session_state.get("chart_images", [])
        docx_path = st.session_state.get("docx_path", "")
        if charts and docx_path and Path(docx_path).exists():
            out_path = embed_images_to_docx(docx_path, charts)
            st.session_state["docx_with_charts_path"] = str(out_path)
            add_log(f"图表嵌入完成: {out_path}")
        else:
            add_log("无图表或 Word 文档，跳过嵌入步骤")
    except Exception as e:
        add_log(f"图表嵌入失败: {e}")

    # Step 5: 思维导图渲染为 PNG
    set_status("渲染思维导图为图片", 0.9)
    try:
        mm_md = st.session_state.get("mindmap_md", "")
        if mm_md:
            png_path = cfg.output_md_dir.parent / "思维导图_AI生成.png"
            result = render_mindmap_to_png(mm_md, png_path)
            if result:
                st.session_state["mindmap_png_path"] = str(result)
                add_log(f"思维导图图片渲染完成: {result}")
            else:
                add_log("思维导图图片渲染失败（请检查 mermaid-cli 或 playwright 是否安装）")
    except Exception as e:
        add_log(f"思维导图渲染失败: {e}")

    set_status("全部完成", 1.0)
    progress.empty()
    status.empty()
    st.balloons()
    st.success("🎉 全链路执行完成！请前往 Step 3 下载结果。")


# ============================================================
# Step 3: 结果下载
# ============================================================

def render_step3_download():
    st.header("Step 3: 结果下载与预览")

    has_any = any([
        st.session_state.get("local_md"),
        st.session_state.get("ai_md"),
        st.session_state.get("mindmap_md"),
        st.session_state.get("docx_path"),
        st.session_state.get("mindmap_png_path"),
    ])

    if not has_any:
        st.info("请在 Step 2 执行生成后，在此处查看和下载结果")
        return

    # 对比视图（Section 3.3）
    ai_md = st.session_state.get("ai_md", "")
    local_md = st.session_state.get("local_md", "")
    if ai_md and local_md:
        with st.expander("📊 AI vs 本地结果对比", expanded=False):
            col_a, col_l = st.columns(2)
            with col_a:
                st.markdown("**🤖 AI 生成**")
                chars = len(ai_md)
                sections = ai_md.count("#")
                st.metric("总字符", f"{chars:,}", delta_color="normal")
                st.metric("章节数", sections)
            with col_l:
                st.markdown("**🧹 本地重组**")
                chars = len(local_md)
                sections = local_md.count("#")
                st.metric("总字符", f"{chars:,}", delta_color="normal")
                st.metric("章节数", sections)

            tab_ai_inner, tab_local_inner = st.tabs(["AI 内容", "本地内容"])
            with tab_ai_inner:
                with st.container(height=400):
                    st.markdown(ai_md[:5000] + ("\n\n...（截断）" if len(ai_md) > 5000 else ""))
            with tab_local_inner:
                with st.container(height=400):
                    st.markdown(local_md[:5000] + ("\n\n...（截断）" if len(local_md) > 5000 else ""))

    tabs = st.tabs(["📄 学习资料 MD", "🧠 思维导图 MD", "📝 Word 文档", "🖼️ 思维导图图片"])

    # Tab 1: 学习资料 MD
    with tabs[0]:
        ai_md = st.session_state.get("ai_md", "")
        local_md = st.session_state.get("local_md", "")
        md_content = ai_md or local_md

        if md_content:
            with st.container(height=500):
                st.markdown(md_content[:8000] + ("\n\n...（内容过长，已截断）" if len(md_content) > 8000 else ""))

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "⬇️ 下载学习资料 .md",
                    data=md_content.encode("utf-8"),
                    file_name="综合学习资料_AI生成.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_dl2:
                if st.button("📝 转为 Word", use_container_width=True):
                    try:
                        cfg = st.session_state["config"]
                        docx_path = cfg.output_md_dir.parent / "综合学习资料_AI生成.docx"
                        source_md = STUDY_GUIDE_PATH.read_text(encoding="utf-8") if STUDY_GUIDE_PATH.exists() else md_content
                        convert_markdown_to_docx(source_md, docx_path)
                        st.session_state["docx_path"] = str(docx_path)
                        # 同时生成图表并嵌入
                        try:
                            chart_dir = cfg.output_md_dir.parent / "charts"
                            charts = generate_charts_from_md_with_llm(source_md, chart_dir, sheet_name="AI学习资料",
                                                                        cfg=cfg, add_log=add_log)
                            st.session_state["chart_images"] = charts
                            if charts:
                                out_path = embed_images_to_docx(docx_path, charts)
                                st.session_state["docx_with_charts_path"] = str(out_path)
                                add_log(f"图表嵌入完成: {len(charts)} 张图表")
                        except Exception as chart_e:
                            add_log(f"图表生成/嵌入跳过: {chart_e}")
                        st.success(f"Word 已生成: {docx_path}")
                        safe_rerun()
                    except Exception as e:
                        st.error(f"转换失败: {e}")
        else:
            st.caption("暂无学习资料内容")

    # Tab 2: 思维导图 MD
    with tabs[1]:
        mm_md = st.session_state.get("mindmap_md", "")
        if mm_md:
            with st.container(height=500):
                st.markdown(mm_md[:8000] + ("\n\n...（内容过长，已截断）" if len(mm_md) > 8000 else ""))
            col_mm1, col_mm2 = st.columns(2)
            with col_mm1:
                st.download_button(
                    "⬇️ 下载 .md",
                    data=mm_md.encode("utf-8"),
                    file_name="思维导图_AI生成.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_mm2:
                png_path = st.session_state.get("mindmap_png_path", "")
                if png_path and Path(png_path).exists():
                    with open(png_path, "rb") as f:
                        st.download_button(
                            "🖼️ 下载 .png",
                            data=f,
                            file_name="思维导图_AI生成.png",
                            mime="image/png",
                            use_container_width=True,
                        )
                else:
                    st.caption("未生成 PNG（执行全链路或点击「导出 PNG」生成）")
        else:
            st.caption("暂无思维导图内容")

    # Tab 3: Word
    with tabs[2]:
        docx_path = st.session_state.get("docx_path", "")
        if docx_path and Path(docx_path).exists():
            st.success(f"Word 文档已生成")
            col_doc1, col_doc2 = st.columns(2)
            with col_doc1:
                with open(docx_path, "rb") as f:
                    st.download_button(
                        "⬇️ 下载 .docx",
                        data=f,
                        file_name="综合学习资料_AI生成.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
            with col_doc2:
                charts_path = st.session_state.get("docx_with_charts_path", "")
                if charts_path and Path(charts_path).exists():
                    with open(charts_path, "rb") as f:
                        st.download_button(
                            "📊 下载含图表 .docx",
                            data=f,
                            file_name="综合学习资料_AI生成_with_charts.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                else:
                    st.caption("含图表版本请在执行全链路后生成")

    # Tab 4: 思维导图 PNG
    with tabs[3]:
        png_path = st.session_state.get("mindmap_png_path", "")
        if png_path and Path(png_path).exists():
            st.image(str(png_path), use_container_width=True)
            with open(png_path, "rb") as f:
                st.download_button(
                    "⬇️ 下载 .png",
                    data=f,
                    file_name="思维导图_AI生成.png",
                    mime="image/png",
                    use_container_width=True,
                )
        else:
            st.caption("暂无思维导图图片，需要安装 mermaid-cli 或 playwright 才能渲染")
            st.code("npm install -g @mermaid-js/mermaid-cli", language="bash")
            st.code("pip install playwright && playwright install chromium", language="bash")


# ============================================================
# 主入口
# ============================================================

def main():
    st.title("📚 AI大模型多文件综合分析 · 学习资料生成工作台")
    st.caption("整合 OCR → 清洗 → AI生成 → 思维导图 → Word 导出的全流程工作流")

    inject_custom_css()

    # 暗黑模式 JS 注入
    dark_mode = st.session_state.get("_dark_mode", False)
    if dark_mode:
        st.markdown(
            "<script>toggleDarkMode(true);</script>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<script>toggleDarkMode(false);</script>",
            unsafe_allow_html=True,
        )

    render_sidebar()

    # 知识库浏览器 & 提示词工作台（在 Step1 前后插入）
    render_knowledge_browser()

    st.divider()
    render_step1_material()

    st.divider()
    render_prompt_workbench()

    st.divider()
    render_step2_workflow()

    st.divider()
    render_step3_download()


if __name__ == "__main__":
    main()
