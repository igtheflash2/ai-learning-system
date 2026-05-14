#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 后端服务器
===============
替代 Streamlit 前端，提供 REST API + HTML 交互界面。

启动方式：
    python backend/app.py

然后访问 http://localhost:5001
"""

import json
import uuid
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from io import BytesIO

# 添加项目根目录到 path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(str(_project_root))

import threading
from flask import (
    Flask, request, jsonify, Response, send_file,
    send_from_directory, stream_with_context,
)
from flask_cors import CORS

# ============================================================
# 导入现有模块
# ============================================================
from modules.config_manager import AppConfig, get_available_chapters, CHAPTER_ORDER, clean_line
from modules.local_processor import process_local_study_guide
from modules.ai_generator import (
    generate_study_guide, generate_study_guide_batch,
    generate_mindmap, call_llm,
)
from modules.docx_converter import convert_markdown_to_docx
from modules.mindmap_renderer import render_mindmap_to_png
from modules.prompt_manager import render_prompt

# Word / Excel 处理模块
from readword import extract_docx_text, convert_doc_to_docx, sanitize_filename as sf_readword
from readexcel import extract_xlsx_text, extract_xls_text

def _sanitize_filename(name: str) -> str:
    """Remove or replace characters unsafe for filenames."""
    return sf_readword(name)

# ============================================================
# 全局状态
# ============================================================
class AppState:
    """应用全局状态（替代 Streamlit session_state）"""
    def __init__(self):
        self.config = AppConfig.from_env()
        self.selected_chapters = []
        self.local_md = ""
        self.ai_md = ""
        self.mindmap_md = ""
        self.docx_path = ""
        self.mindmap_png_path = ""
        self.run_mode = "api"
        self.generation_mode = "完整模式"
        self.focus_areas = "全部章节"
        self.detail_level = "标准"
        self.include_mnemonics = True
        self.include_exercises = True
        self.logs = []
        self._lock = threading.Lock()

    def add_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        with self._lock:
            self.logs.append(line)
            self.logs = self.logs[-200:]

    def get_logs(self, n: int = 50):
        with self._lock:
            return self.logs[-n:]


state = AppState()

# ============================================================
# Flask 应用
# ============================================================
app = Flask(__name__)
CORS(app)

PROJECT_ROOT = Path(_project_root)
STUDY_GUIDE_PATH = PROJECT_ROOT / "综合学习资料_AI生成.md"
TEMP_OUTPUT = PROJECT_ROOT / "temp_output"

TEMP_OUTPUT.mkdir(exist_ok=True)

# ============================================================
# 工具函数
# ============================================================

import threading as _threading
import queue as _queue


def _run_with_heartbeat(
    worker_fn,
    *,
    heartbeat_interval: float = 3.0,
    stream_callback=None,
) -> _queue.Queue:
    """
    在后台线程执行 worker_fn，返回一个 Queue。
    外部生成器必须持续读取该 Queue：
      - ('heartbeat',)  → 可丢弃或 yield 心跳
      - ('chunk', text) → stream_callback 收集到的文本片段
      - ('result', val) → 函数成功返回
      - ('error', exc)  → 函数抛出异常
    """
    q = _queue.Queue()

    def _streaming_callback(chunk: str):
        q.put(('chunk', chunk))

    def _wrapper():
        try:
            kwargs = {}
            if stream_callback:
                kwargs["stream_callback"] = _streaming_callback
            result = worker_fn(**kwargs)
            q.put(('result', result))
        except Exception as e:
            q.put(('error', e))

    t = _threading.Thread(target=_wrapper, daemon=True)
    t.start()
    return q


def _heartbeat_generator(q: _queue.Queue, heartbeat_interval: float = 3.0):
    """
    消费 _run_with_heartbeat 返回的队列，定期 yield 心跳。
    Yields:
      - ('yield_sse', sse_string)
      - ('result', value)
      - ('error', exception)
    """
    while True:
        try:
            item = q.get(timeout=heartbeat_interval)
        except _queue.Empty:
            yield ('heartbeat', None)
            continue

        kind = item[0]
        if kind == 'chunk':
            # 可以将 chunk 转发给 SSE
            yield ('chunk', item[1])
        elif kind == 'result':
            yield ('result', item[1])
            return
        elif kind == 'error':
            yield ('error', item[1])
            return

def save_temp_md(content: str, suffix: str = "temp") -> Path:
    ts = datetime.now().strftime("%m%d_%H%M%S")
    path = TEMP_OUTPUT / f"generated_{suffix}_{ts}.md"
    path.write_text(content, encoding="utf-8")
    return path


def json_response(data, status=200):
    return jsonify(data), status


def error_response(message, status=400):
    return jsonify({"error": message}), status


# ============================================================
# 全链路流水线后台任务管理
# ============================================================

_pipeline_runners: dict[str, _queue.Queue] = {}

def _pipeline_worker(task_id: str, chapters: list):
    """Run the full pipeline in a background thread, pushing status events to the queue."""
    q = _pipeline_runners[task_id]
    cfg = state.config

    def _emit(event_type: str, text: str):
        q.put((event_type, text))

    try:
        # Step 1: 本地清洗
        _emit('status', '🔄 Step 1/5: 本地清洗重组...')
        try:
            local_result = process_local_study_guide(cfg.output_md_dir, chapters)
            state.local_md = local_result
            _emit('status', '✅ 本地清洗完成')
        except Exception as e:
            _emit('status', f'⚠️ 本地清洗跳过: {e}')

        # Step 2: AI 学习资料
        _emit('status', '🔄 Step 2/5: AI 生成学习资料...')
        try:
            if state.generation_mode == "逐章模式":
                ai_result = generate_study_guide_batch(
                    cfg.output_md_dir, chapters, cfg,
                    focus_areas=state.focus_areas,
                    detail_level=state.detail_level,
                    include_mnemonics=state.include_mnemonics,
                    include_exercises=state.include_exercises,
                    prompt_template=cfg.prompts_dir / "study_guide.j2",
                )
            else:
                q_guide = _run_with_heartbeat(
                    lambda stream_callback=None: generate_study_guide(
                        cfg.output_md_dir, chapters, cfg,
                        focus_areas=state.focus_areas,
                        detail_level=state.detail_level,
                        include_mnemonics=state.include_mnemonics,
                        include_exercises=state.include_exercises,
                        prompt_template=cfg.prompts_dir / "study_guide.j2",
                        stream_callback=stream_callback,
                    ),
                    stream_callback=True,
                )
                ai_result = None
                for evt in _heartbeat_generator(q_guide):
                    if evt[0] == 'result':
                        ai_result = evt[1]
                    elif evt[0] == 'error':
                        raise evt[1]
            state.ai_md = ai_result
            STUDY_GUIDE_PATH.write_text(ai_result, encoding="utf-8")
            _emit('status', '✅ AI 学习资料生成完成')
        except Exception as e:
            _emit('error', f'AI 学习资料生成失败: {e}')
            return

        # Step 3: AI 思维导图
        _emit('status', '🔄 Step 3/5: AI 生成思维导图...')
        try:
            q_mindmap = _run_with_heartbeat(
                lambda stream_callback=None: generate_mindmap(
                    cfg.output_md_dir, chapters, cfg,
                    format_pref="both",
                    prompt_template=cfg.prompts_dir / "mindmap.j2",
                    stream_callback=stream_callback,
                ),
                stream_callback=True,
            )
            mm_result = None
            for evt in _heartbeat_generator(q_mindmap):
                if evt[0] == 'result':
                    mm_result = evt[1]
                elif evt[0] == 'error':
                    raise evt[1]
            state.mindmap_md = mm_result
            save_temp_md(mm_result, "mindmap")
            _emit('status', '✅ 思维导图生成完成')
        except Exception as e:
            _emit('status', f'⚠️ 思维导图生成失败: {e}')

        # Step 4: Word 转换
        _emit('status', '🔄 Step 4/5: 转换为 Word...')
        try:
            md_content = STUDY_GUIDE_PATH.read_text(encoding="utf-8") if STUDY_GUIDE_PATH.exists() else ""
            if md_content:
                docx_path = PROJECT_ROOT / "综合学习资料_AI生成.docx"
                convert_markdown_to_docx(md_content, docx_path)
                state.docx_path = str(docx_path)
                _emit('status', '✅ Word 转换完成')
        except Exception as e:
            _emit('status', f'⚠️ Word 转换失败: {e}')

        # Step 5: PNG 渲染
        _emit('status', '🔄 Step 5/5: 渲染思维导图图片...')
        try:
            mm_md = state.mindmap_md
            if mm_md:
                png_path = PROJECT_ROOT / "思维导图_AI生成.png"
                result = render_mindmap_to_png(mm_md, png_path)
                if result:
                    state.mindmap_png_path = str(result)
                    _emit('status', '✅ 思维导图图片渲染完成')
                else:
                    _emit('status', '⚠️ 图片渲染失败（需安装 mermaid-cli 或 playwright）')
        except Exception as e:
            _emit('status', f'⚠️ 渲染失败: {e}')

        _emit('status', '🎉 全链路执行完成！')
        q.put(('done', None))
    except Exception as e:
        q.put(('error', str(e)))
        q.put(('done', None))


# ============================================================
# SSE 事件流辅助
# ============================================================

def sse_event(data: str, event: str = "message") -> str:
    if event == "message":
        return f"data: {json.dumps({'text': data})}\n\n"
    return f"event: {event}\ndata: {json.dumps({'text': data})}\n\n"


def sse_done() -> str:
    return "event: done\ndata: {}\n\n"


def sse_error(msg: str) -> str:
    return f"event: error\ndata: {json.dumps({'error': msg})}\n\n"


# ============================================================
# 静态文件服务
# ============================================================

@app.route("/")
def index():
    return send_from_directory(
        str(PROJECT_ROOT / "backend" / "static"), "index.html"
    )


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(
        str(PROJECT_ROOT / "backend" / "static"), filename
    )


# ============================================================
# API: 配置
# ============================================================

@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = state.config
    return json_response({
        "api_key": cfg.api_key[:6] + "..." + cfg.api_key[-4:] if len(cfg.api_key) > 10 else "",
        "api_key_masked": bool(cfg.api_key),
        "base_url": cfg.base_url,
        "model": cfg.model,
        "max_tokens": cfg.max_tokens,
        "is_api_ready": cfg.is_api_ready(),
        "run_mode": state.run_mode,
        "generation_mode": state.generation_mode,
        "focus_areas": state.focus_areas,
        "detail_level": state.detail_level,
        "include_mnemonics": state.include_mnemonics,
        "include_exercises": state.include_exercises,
    })


@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.json or {}
    cfg = state.config

    if "api_key" in data:
        cfg.api_key = data["api_key"]
    if "base_url" in data:
        cfg.base_url = data["base_url"]
    if "model" in data:
        cfg.model = data["model"]
    if "max_tokens" in data:
        cfg.max_tokens = int(data["max_tokens"])
    if "run_mode" in data:
        state.run_mode = data["run_mode"]
    if "generation_mode" in data:
        state.generation_mode = data["generation_mode"]
    if "focus_areas" in data:
        state.focus_areas = data["focus_areas"]
    if "detail_level" in data:
        state.detail_level = data["detail_level"]
    if "include_mnemonics" in data:
        state.include_mnemonics = bool(data["include_mnemonics"])
    if "include_exercises" in data:
        state.include_exercises = bool(data["include_exercises"])

    return json_response({"success": True})


@app.route("/api/config/verify", methods=["POST"])
def verify_api():
    """验证 API 连通性 — 发送一条简单测试消息"""
    cfg = state.config
    if not cfg.api_key:
        return json_response({"success": False, "error": "API Key 未配置"}), 400
    try:
        from openai import OpenAI
    except ImportError:
        return json_response({"success": False, "error": "请安装 openai: pip install openai"}), 500
    try:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
            stream=False,
        )
        reply = resp.choices[0].message.content or ""
        state.add_log(f"API 验证成功: 模型 {cfg.model} 返回正常")
        return json_response({"success": True, "reply": reply.strip()})
    except Exception as e:
        msg = str(e)
        state.add_log(f"API 验证失败: {msg}")
        return json_response({"success": False, "error": msg}), 502


# ============================================================
# API: 章节
# ============================================================

@app.route("/api/chapters", methods=["GET"])
def list_chapters():
    available = get_available_chapters(state.config.output_md_dir)
    return json_response({"chapters": available})


@app.route("/api/chapters/select", methods=["POST"])
def select_chapters():
    data = request.json or {}
    chapters = data.get("chapters", [])
    state.selected_chapters = chapters
    return json_response({"success": True, "count": len(chapters)})


# ============================================================
# API: 知识库文件
# ============================================================

@app.route("/api/files", methods=["GET"])
def list_files():
    output_dir = state.config.output_md_dir
    files = []
    if output_dir.exists():
        for fp in sorted(output_dir.glob("*.md")):
            stat = fp.stat()
            files.append({
                "name": fp.name,
                "stem": fp.stem,
                "size_kb": round(stat.st_size / 1024, 1),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%m-%d %H:%M"),
            })
    return json_response({"files": files})


@app.route("/api/files/<path:filename>", methods=["GET"])
def get_file(filename):
    filepath = state.config.output_md_dir / filename
    if not filepath.exists() or not filepath.is_file():
        return error_response("文件不存在", 404)
    content = filepath.read_text(encoding="utf-8")
    return json_response({"name": filename, "content": content})


@app.route("/api/files/<path:filename>", methods=["POST"])
def save_file(filename):
    filepath = state.config.output_md_dir / filename
    data = request.json or {}
    content = data.get("content", "")
    filepath.write_text(content, encoding="utf-8")
    state.add_log(f"知识库文件已编辑: {filename}")
    return json_response({"success": True})


@app.route("/api/files/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    filepath = state.config.output_md_dir / filename
    if filepath.exists() and filepath.is_file():
        filepath.unlink()
        state.add_log(f"知识库文件已删除: {filename}")
        return json_response({"success": True})
    return error_response("文件不存在", 404)


# ============================================================
# API: 提示词模板
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


@app.route("/api/prompts", methods=["GET"])
def list_prompts():
    prompts_dir = state.config.prompts_dir
    files = []
    for fp in sorted(prompts_dir.glob("*.j2")) + sorted(prompts_dir.glob("*.md")):
        files.append(fp.name)
    return json_response({"prompts": files})


@app.route("/api/prompts/<name>", methods=["GET"])
def get_prompt(name):
    path = state.config.prompts_dir / name
    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = DEFAULT_PROMPTS.get(name, "")
    return json_response({"name": name, "content": content})


@app.route("/api/prompts/<name>", methods=["POST"])
def save_prompt(name):
    data = request.json or {}
    content = data.get("content", "")
    path = state.config.prompts_dir / name
    path.write_text(content, encoding="utf-8")
    state.add_log(f"提示词模板已更新: {name}")
    return json_response({"success": True})


@app.route("/api/prompts/<name>/reset", methods=["POST"])
def reset_prompt(name):
    if name in DEFAULT_PROMPTS:
        path = state.config.prompts_dir / name
        path.write_text(DEFAULT_PROMPTS[name], encoding="utf-8")
        state.add_log(f"提示词模板已重置: {name}")
        return json_response({"success": True})
    return error_response("无默认模板可重置")


@app.route("/api/prompts/ai-edit", methods=["POST"])
def ai_edit_prompt():
    data = request.json or {}
    current_content = data.get("current_content", "")
    modification = data.get("modification", "")
    cfg = state.config

    if not cfg.is_api_ready():
        return error_response("API 未配置")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        sys_prompt = (
            "你是一名提示词工程专家。根据用户的修改要求，修改下面的提示词模板。"
            "只返回修改后的完整提示词模板，不要加额外解释。"
        )
        user_prompt = (
            f"当前提示词模板：\n---\n{current_content}\n---\n\n"
            f"用户修改要求：\n{modification}"
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
        return json_response({"suggestion": suggestion})
    except Exception as e:
        return error_response(str(e))


@app.route("/api/prompts/preview", methods=["POST"])
def preview_prompt():
    data = request.json or {}
    content = data.get("content", "")
    name = data.get("name", "study_guide.j2")
    cfg = state.config

    sample_vars = {
        "material": "## 计算机硬件\n\n### 考情分析\n本章历年考查分值约4-6分...",
        "focus_areas": "全部章节",
        "detail_level": "标准",
        "include_mnemonics": True,
        "include_exercises": True,
        "format_pref": "both",
    }
    try:
        if name in ("study_guide.j2", "mindmap.j2"):
            rendered = render_prompt(cfg.prompts_dir / name, sample_vars)
        else:
            rendered = content.replace("{{ material }}", sample_vars["material"])
        return json_response({"rendered": rendered[:2000]})
    except Exception as e:
        return error_response(str(e))


@app.route("/api/prompts/generate-from-kb", methods=["POST"])
def generate_prompt_from_kb():
    """基于全部知识库文件生成提示词模板"""
    cfg = state.config
    if not cfg.is_api_ready():
        return error_response("API 未配置")

    data = request.json or {}
    target_name = data.get("target_name", "study_guide.j2")

    # 1. 扫描知识库文件
    md_dir = cfg.output_md_dir
    md_files = sorted(md_dir.glob("*.md"))
    if not md_files:
        return error_response("知识库目录为空，请先上传并处理 PDF")

    # 2. 拼接内容（上限 ~80K 字符）
    parts = []
    total_len = 0
    MAX_CHARS = 80000
    for fp in md_files:
        content = fp.read_text(encoding="utf-8")
        chunk = f"===== 文件: {fp.name} =====\n\n{content}\n\n"
        if total_len + len(chunk) > MAX_CHARS:
            remaining = MAX_CHARS - total_len
            if remaining > 200:
                parts.append(chunk[:remaining])
            break
        parts.append(chunk)
        total_len += len(chunk)

    combined = "".join(parts)
    file_count = len(md_files)
    state.add_log(f"开始基于 {file_count} 个知识库文件生成模板")

    # 3. 调用 AI 生成
    sys_prompt = (
        "你是一名提示词工程专家。你的任务是基于提供的教材素材，"
        "编写一份高质量的 Jinja2 提示词模板，用于 AI 生成软考系统架构设计师学习资料。\n\n"
        "模板要求：\n"
        "1. 使用 Jinja2 变量占位，主要变量：{{ material }}（素材内容）\n"
        "2. 包含完整角色定义、输出要求、格式规范\n"
        "3. 结构清晰，层次分明\n"
        "4. 开头必须是 '# Agent Prompt：软考系统架构设计师学习资料生成器'\n"
        "5. 直接输出模板内容，不要额外解释"
    )
    user_prompt = (
        f"以下是从 {file_count} 个教材素材文件中提取的内容，"
        f"请基于这些素材的结构和知识点，生成一份完整的提示词模板：\n\n{combined}"
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=cfg.max_tokens,
        )
        generated = resp.choices[0].message.content.strip()
    except Exception as e:
        state.add_log(f"AI 基于知识库生成模板失败: {e}")
        return error_response(str(e))

    # 4. 保存到目标模板文件
    target_path = cfg.prompts_dir / target_name
    target_path.write_text(generated, encoding="utf-8")
    state.add_log(f"AI 基于知识库生成的模板已保存为 {target_name}")

    return json_response({
        "success": True,
        "name": target_name,
        "content": generated,
        "preview": generated[:2000] + ("\n\n...（截断）" if len(generated) > 2000 else ""),
        "file_count": file_count,
    })


# ============================================================
# API: 上传 / OCR
# ============================================================

@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return error_response("请选择文件上传")
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return error_response("仅支持 PDF 文件")

    save_path = state.config.input_dir / file.filename
    save_path.write_bytes(file.read())
    state.add_log(f"文件已上传: {file.filename}")

    # 上传后自动触发 OCR 转换
    try:
        from modules.ocr_engine import process_pdf_to_md
        md_path = process_pdf_to_md(save_path, state.config.output_md_dir)
        state.add_log(f"OCR 完成: {file.filename} -> {md_path.name}")
        return json_response({
            "success": True,
            "filename": file.filename,
            "md_file": md_path.name,
        })
    except Exception as e:
        state.add_log(f"OCR 失败: {file.filename} - {e}")
        return json_response({
            "success": True,
            "filename": file.filename,
            "ocr_error": str(e),
        })


@app.route("/api/ocr", methods=["POST"])
def ocr_single():
    data = request.json or {}
    filename = data.get("filename", "")
    if not filename:
        return error_response("请提供文件名")
    pdf_path = state.config.input_dir / filename
    if not pdf_path.exists():
        return error_response("文件不存在", 404)

    try:
        from modules.ocr_engine import process_pdf_to_md
        md_path = process_pdf_to_md(pdf_path, state.config.output_md_dir)
        state.add_log(f"OCR 完成: {filename} -> {md_path.name}")
        return json_response({"success": True, "md_file": md_path.name})
    except Exception as e:
        state.add_log(f"OCR 失败: {filename} - {e}")
        return error_response(str(e))


@app.route("/api/ocr/batch", methods=["POST"])
def ocr_batch():
    input_dir = state.config.input_dir
    pdf_list = sorted(input_dir.glob("*.pdf"))
    if not pdf_list:
        return error_response("input/ 目录下没有 PDF 文件")

    def generate():
        from modules.ocr_engine import process_pdf_to_md
        total = len(pdf_list)
        yield sse_event(f"开始批量 OCR，共 {total} 个 PDF...", "status")
        for idx, pdf_path in enumerate(pdf_list):
            yield sse_event(f"处理中: [{idx+1}/{total}] {pdf_path.name}", "status")
            try:
                md_path = process_pdf_to_md(pdf_path, state.config.output_md_dir)
                state.add_log(f"OCR 完成: {pdf_path.name} -> {md_path.name}")
                yield sse_event(f"✅ [{idx+1}/{total}] {pdf_path.name} 完成", "progress")
            except Exception as e:
                state.add_log(f"OCR 失败: {pdf_path.name} - {e}")
                yield sse_event(f"❌ [{idx+1}/{total}] {pdf_path.name} 失败: {e}", "progress")
        yield sse_event(f"批量 OCR 完成，共处理 {total} 个 PDF", "status")
        yield sse_done()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: Word / Excel 转换
# ============================================================

@app.route("/api/convert/word", methods=["POST"])
def convert_word():
    """Upload .doc/.docx → Markdown."""
    if "file" not in request.files:
        return error_response("请选择 Word 文件上传")
    file = request.files["file"]
    filename = file.filename or "untitled"
    ext = Path(filename).suffix.lower()
    if ext not in (".doc", ".docx"):
        return error_response("仅支持 .doc / .docx 文件")

    input_dir = state.config.input_dir
    input_dir.mkdir(parents=True, exist_ok=True)
    src_path = input_dir / _sanitize_filename(filename)
    file.save(str(src_path))

    docx_path = src_path
    try:
        if ext == ".doc":
            docx_path = convert_doc_to_docx(src_path)

        text = extract_docx_text(docx_path)
        output_dir = state.config.output_md_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        md_name = _sanitize_filename(Path(filename).stem + ".md")
        md_path = output_dir / md_name
        md_content = f"# {Path(filename).stem}\n\n{text}\n"
        md_path.write_text(md_content, encoding="utf-8")

        state.add_log(f"Word转换完成: {filename} -> {md_name}")
        return jsonify({"success": True, "md_file": md_name, "message": f"转换完成: {md_name}"})
    except Exception as e:
        state.add_log(f"Word转换失败: {filename} - {e}")
        return error_response(f"Word转换失败: {e}")
    finally:
        if ext == ".doc" and docx_path and docx_path != src_path:
            try:
                docx_path.unlink(missing_ok=True)
            except Exception:
                pass


@app.route("/api/convert/excel", methods=["POST"])
def convert_excel():
    """Upload .xls/.xlsx → Markdown."""
    if "file" not in request.files:
        return error_response("请选择 Excel 文件上传")
    file = request.files["file"]
    filename = file.filename or "untitled"
    ext = Path(filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return error_response("仅支持 .xls / .xlsx 文件")

    input_dir = state.config.input_dir
    input_dir.mkdir(parents=True, exist_ok=True)
    src_path = input_dir / _sanitize_filename(filename)
    file.save(str(src_path))

    try:
        if ext == ".xlsx":
            text = extract_xlsx_text(src_path)
        else:
            text = extract_xls_text(src_path)

        output_dir = state.config.output_md_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        md_name = _sanitize_filename(Path(filename).stem + ".md")
        md_path = output_dir / md_name
        md_content = f"# {Path(filename).stem}\n\n{text}\n"
        md_path.write_text(md_content, encoding="utf-8")

        state.add_log(f"Excel转换完成: {filename} -> {md_name}")
        return jsonify({"success": True, "md_file": md_name, "message": f"转换完成: {md_name}"})
    except Exception as e:
        state.add_log(f"Excel转换失败: {filename} - {e}")
        return error_response(f"Excel转换失败: {e}")


# ============================================================
# API: 本地处理
# ============================================================

@app.route("/api/process/local", methods=["POST"])
def process_local():
    data = request.json or {}
    chapters = data.get("chapters", state.selected_chapters)
    if not chapters:
        return error_response("请先选择章节")

    try:
        result = process_local_study_guide(state.config.output_md_dir, chapters)
        state.local_md = result
        STUDY_GUIDE_PATH.write_text(result, encoding="utf-8")
        state.add_log(f"本地清洗完成，共 {len(result):,} 字符")
        return json_response({
            "success": True,
            "content": result[:500],
            "length": len(result),
            "preview": result[:2000],
        })
    except Exception as e:
        state.add_log(f"本地清洗失败: {e}")
        return error_response(str(e))


# ============================================================
# API: AI 学习资料（SSE 流式）
# ============================================================

@app.route("/api/process/ai-guide", methods=["POST"])
def process_ai_guide():
    data = request.json or {}
    chapters = data.get("chapters", state.selected_chapters)
    if not chapters:
        return error_response("请先选择章节")
    cfg = state.config
    if not cfg.is_api_ready():
        return error_response("API 未配置")

    def generate():
        stream_buffer = []
        full_text = []

        def on_chunk(chunk: str):
            stream_buffer.append(chunk)
            full_text.append(chunk)
            # 不再使用 yield（不能从回调中 yield 到外层生成器）
            # 分块数据已累积到 stream_buffer / full_text 中

        try:
            if state.generation_mode == "逐章模式":
                result = generate_study_guide_batch(
                    cfg.output_md_dir, chapters, cfg,
                    focus_areas=state.focus_areas,
                    detail_level=state.detail_level,
                    include_mnemonics=state.include_mnemonics,
                    include_exercises=state.include_exercises,
                    prompt_template=cfg.prompts_dir / "study_guide.j2",
                    progress_callback=lambda cur, tot, msg: state.add_log(f"[{cur}/{tot}] {msg}"),
                )
            else:
                result = generate_study_guide(
                    cfg.output_md_dir, chapters, cfg,
                    focus_areas=state.focus_areas,
                    detail_level=state.detail_level,
                    include_mnemonics=state.include_mnemonics,
                    include_exercises=state.include_exercises,
                    prompt_template=cfg.prompts_dir / "study_guide.j2",
                    stream_callback=on_chunk,
                )
        except Exception as e:
            yield sse_error(str(e))
            state.add_log(f"AI 学习资料生成失败: {e}")
            return

        state.ai_md = result
        STUDY_GUIDE_PATH.write_text(result, encoding="utf-8")
        state.add_log(f"AI 学习资料生成完成，共 {len(result):,} 字符")
        yield sse_event(result[-500:] if len(result) > 500 else result)
        yield sse_done()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: AI 思维导图（SSE 流式）
# ============================================================

@app.route("/api/process/ai-mindmap", methods=["POST"])
def process_ai_mindmap():
    data = request.json or {}
    chapters = data.get("chapters", state.selected_chapters)
    if not chapters:
        return error_response("请先选择章节")
    cfg = state.config
    if not cfg.is_api_ready():
        return error_response("API 未配置")

    def generate():
        stream_buffer = []
        full_text = []

        def on_chunk(chunk: str):
            stream_buffer.append(chunk)
            full_text.append(chunk)

        try:
            result = generate_mindmap(
                cfg.output_md_dir, chapters, cfg,
                format_pref="both",
                prompt_template=cfg.prompts_dir / "mindmap.j2",
                stream_callback=on_chunk,
            )
        except Exception as e:
            yield sse_error(str(e))
            state.add_log(f"思维导图生成失败: {e}")
            return

        state.mindmap_md = result
        save_temp_md(result, "mindmap")
        state.add_log(f"思维导图生成完成，共 {len(result):,} 字符")
        yield sse_event(result[-500:] if len(result) > 500 else result)
        yield sse_done()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: 全链路流水线（SSE 流式）
# ============================================================

@app.route("/api/process/pipeline", methods=["POST"])
def process_pipeline_start():
    """Start the full pipeline as a background task and return a task_id for streaming."""
    data = request.json or {}
    chapters = data.get("chapters", state.selected_chapters)
    if not chapters:
        return error_response("请先选择章节")
    cfg = state.config
    if not cfg.is_api_ready():
        return error_response("API 未配置")

    task_id = uuid.uuid4().hex
    _pipeline_runners[task_id] = _queue.Queue()
    t = _threading.Thread(
        target=_pipeline_worker,
        args=(task_id, chapters),
        daemon=True,
    )
    t.start()
    return jsonify({"task_id": task_id})


@app.route("/api/process/pipeline/stream/<task_id>", methods=["GET"])
def process_pipeline_stream(task_id: str):
    """SSE endpoint that streams pipeline events for a given task_id."""
    q = _pipeline_runners.get(task_id)
    if q is None:
        return error_response("无效的 task_id 或任务已结束", 404)

    def generate():
        while True:
            try:
                evt = q.get(timeout=15.0)
            except _queue.Empty:
                # send heartbeat to keep connection alive
                yield ": heartbeat\n\n"
                continue

            kind, data = evt
            if kind == 'done':
                yield sse_done()
                return
            elif kind == 'error':
                yield sse_error(data)
                yield sse_done()
                return
            elif kind == 'status':
                yield sse_event(data, "status")
            else:
                yield sse_event(str(data))

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# API: 文档转换
# ============================================================

@app.route("/api/convert/docx", methods=["POST"])
def convert_docx():
    md_content = state.ai_md or state.local_md
    if not md_content:
        return error_response("无内容可转换")

    try:
        docx_path = PROJECT_ROOT / "综合学习资料_AI生成.docx"
        convert_markdown_to_docx(md_content, docx_path)
        state.docx_path = str(docx_path)
        state.add_log(f"Word 文档已生成: {docx_path.name}")
        return json_response({"success": True, "path": str(docx_path)})
    except Exception as e:
        return error_response(str(e))


@app.route("/api/convert/png", methods=["POST"])
def convert_png():
    mm_md = state.mindmap_md
    if not mm_md:
        return error_response("无思维导图内容")

    try:
        png_path = PROJECT_ROOT / "思维导图_AI生成.png"
        result = render_mindmap_to_png(mm_md, png_path)
        if result:
            state.mindmap_png_path = str(result)
            state.add_log(f"思维导图图片已生成: {result.name}")
            return json_response({"success": True, "path": str(result)})
        else:
            return error_response("渲染失败，请安装 mermaid-cli 或 playwright")
    except Exception as e:
        return error_response(str(e))


# ============================================================
# API: 内容 / 状态
# ============================================================

@app.route("/api/content/study-guide", methods=["GET"])
def get_study_guide():
    content = state.ai_md or state.local_md or ""
    return json_response({"content": content[:50000], "length": len(content)})


@app.route("/api/content/mindmap", methods=["GET"])
def get_mindmap():
    content = state.mindmap_md or ""
    return json_response({"content": content[:50000], "length": len(content)})


@app.route("/api/content/comparison", methods=["GET"])
def get_comparison():
    return json_response({
        "ai": {
            "length": len(state.ai_md),
            "sections": state.ai_md.count("#"),
        },
        "local": {
            "length": len(state.local_md),
            "sections": state.local_md.count("#"),
        },
        "mindmap": {
            "length": len(state.mindmap_md),
            "sections": state.mindmap_md.count("#"),
        },
    })


@app.route("/api/logs", methods=["GET"])
def get_logs():
    n = request.args.get("n", 50, type=int)
    return json_response({"logs": state.get_logs(n)})


@app.route("/api/status", methods=["GET"])
def get_status():
    def exists(p):
        return bool(p and Path(p).exists())
    return json_response({
        "current_step": "idle",
        "has_local": bool(state.local_md),
        "has_ai": bool(state.ai_md),
        "has_mindmap": bool(state.mindmap_md),
        "has_docx": exists(state.docx_path),
        "has_png": exists(state.mindmap_png_path),
    })


# ============================================================
# API: 下载
# ============================================================

@app.route("/api/download/md")
def download_md():
    content = state.ai_md or state.local_md or ""
    if not content:
        return error_response("无内容可下载")
    return Response(
        content.encode("utf-8"),
        mimetype="text/markdown",
        headers={
            "Content-Disposition": "attachment; filename=综合学习资料_AI生成.md",
            "Content-Type": "text/markdown; charset=utf-8",
        },
    )


@app.route("/api/download/mindmap-md")
def download_mindmap_md():
    content = state.mindmap_md or ""
    if not content:
        return error_response("无内容可下载")
    return Response(
        content.encode("utf-8"),
        mimetype="text/markdown",
        headers={
            "Content-Disposition": "attachment; filename=思维导图_AI生成.md",
            "Content-Type": "text/markdown; charset=utf-8",
        },
    )


@app.route("/api/download/docx")
def download_docx():
    path = state.docx_path if state.docx_path and Path(state.docx_path).exists() else None
    if not path:
        # 尝试生成
        md_content = state.ai_md or state.local_md
        if not md_content:
            return error_response("无内容，请先生成学习资料")
        docx_path = PROJECT_ROOT / "综合学习资料_AI生成.docx"
        try:
            convert_markdown_to_docx(md_content, docx_path)
            state.docx_path = str(docx_path)
            path = str(docx_path)
        except Exception as e:
            return error_response(str(e))
    return send_file(path, as_attachment=True, download_name="综合学习资料_AI生成.docx")


@app.route("/api/download/png")
def download_png():
    path = state.mindmap_png_path if state.mindmap_png_path and Path(state.mindmap_png_path).exists() else None
    if path:
        return send_file(path, as_attachment=True, download_name="思维导图_AI生成.png")
    return error_response("图片尚未生成")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    import webbrowser

    port = int(os.environ.get("PORT", 5001))
    print(f"🚀 服务器启动: http://localhost:{port}")

    # 仅首次启动时打开浏览器（避免 debug 重载时反复弹出新窗口）
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        print(f"📚 打开浏览器访问 http://localhost:{port}")
        webbrowser.open(f"http://localhost:{port}")

    # 确保必要目录存在
    state.config.input_dir.mkdir(exist_ok=True)
    state.config.output_md_dir.mkdir(exist_ok=True)
    state.config.prompts_dir.mkdir(exist_ok=True)
    TEMP_OUTPUT.mkdir(exist_ok=True)

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
