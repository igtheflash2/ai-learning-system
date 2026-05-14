#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF OCR 引擎模块
================
将扫描版/图片版 PDF 通过 OCR 转为 Markdown 文本。
基于 rapidocr-onnxruntime + PyMuPDF + OpenCV。

前置条件：pip install rapidocr-onnxruntime pymupdf opencv-python numpy
"""

import re
import time
from pathlib import Path
from typing import Optional


def sanitize_filename(name: str) -> str:
    """去除文件名中的非法字符"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "untitled"


def _import_deps():
    """延迟导入依赖，避免模块加载时失败"""
    try:
        import cv2
        import fitz
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        return cv2, fitz, np, RapidOCR
    except ImportError as e:
        raise ImportError(
            f"OCR 依赖未安装: {e}\n"
            "请运行: pip install rapidocr-onnxruntime pymupdf opencv-python numpy"
        ) from e


def ocr_single_pdf(
    pdf_path: Path,
    dpi: int = 100,
    progress_callback: Optional[callable] = None,
) -> str:
    """
    对单个 PDF 文件执行 OCR，返回 Markdown 格式文本。

    Args:
        pdf_path: PDF 文件路径
        dpi: 渲染分辨率（越高越清晰但越慢）
        progress_callback: 可选的进度回调函数，签名: callback(current_page, total_pages, page_text)

    Returns:
        Markdown 格式的完整文本
    """
    cv2, fitz, np, RapidOCR = _import_deps()

    doc = fitz.open(str(pdf_path))
    engine = RapidOCR()
    pages_text = []
    total = len(doc)

    try:
        for page_num in range(total):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # 转为 numpy 数组
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            elif pix.n in (1, 2):
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            result, _ = engine(img)
            if result:
                lines = [item[1] for item in result]
                text = "\n".join(lines)
            else:
                text = ""

            if text.strip():
                pages_text.append(text)

            if progress_callback:
                progress_callback(page_num + 1, total, text)
    finally:
        doc.close()

    return "\n\n---\n\n".join(pages_text)


def process_pdf_to_md(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 100,
    progress_callback: Optional[callable] = None,
) -> Path:
    """
    处理单个 PDF 并保存为 Markdown 文件。

    Returns:
        生成的 Markdown 文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    text = ocr_single_pdf(pdf_path, dpi=dpi, progress_callback=progress_callback)

    if not text.strip():
        text = "[No extractable text content.]"

    md_name = sanitize_filename(pdf_path.stem) + ".md"
    md_path = output_dir / md_name
    md_content = f"# {pdf_path.stem}\n\n{text}\n"
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def batch_process_pdfs(
    input_dir: Path,
    output_dir: Path,
    dpi: int = 100,
    progress_callback: Optional[callable] = None,
) -> list[Path]:
    """
    批量处理目录下所有 PDF。

    Returns:
        生成的所有 Markdown 文件路径列表
    """
    pdf_files = sorted(input_dir.glob("*.pdf"))
    results = []
    total_start = time.time()

    for pdf_path in pdf_files:
        file_start = time.time()
        md_path = process_pdf_to_md(pdf_path, output_dir, dpi=dpi, progress_callback=progress_callback)
        elapsed = time.time() - file_start
        results.append(md_path)

    total_elapsed = time.time() - total_start
    return results
