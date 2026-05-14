"""Extract text from Word (.doc / .docx) documents and save as Markdown."""

import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path

try:
    from docx import Document
except ImportError:
    Document = None

# --- .doc conversion backends ---
# Windows: win32com
try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

# Linux: LibreOffice headless
_HAS_LIBRE_OFFICE: bool | None = None


def _check_libreoffice() -> bool:
    global _HAS_LIBRE_OFFICE
    if _HAS_LIBRE_OFFICE is not None:
        return _HAS_LIBRE_OFFICE
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--version"],
            capture_output=True, timeout=10,
        )
        _HAS_LIBRE_OFFICE = True
    except Exception:
        _HAS_LIBRE_OFFICE = False
    return _HAS_LIBRE_OFFICE

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output_md")


def sanitize_filename(name: str) -> str:
    """Remove or replace characters unsafe for filenames."""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "untitled"


def convert_doc_to_docx(doc_path: Path) -> Path:
    """Convert a .doc file to .docx.

    Backend selection (auto):
      - Windows → win32com (Microsoft Word)
      - Linux   → LibreOffice --headless
    """
    temp_docx = Path(tempfile.mktemp(suffix=".docx"))

    if platform.system() == "Windows":
        if not HAS_WIN32COM:
            raise RuntimeError(
                "Windows 下需要 pywin32 才能处理 .doc 文件，请安装: pip install pywin32"
            )
        pythoncom.CoInitialize()
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = False
            doc = word.Documents.Open(str(doc_path.resolve()), ReadOnly=True)
            doc.SaveAs(str(temp_docx.resolve()), FileFormat=16)  # 16 = wdFormatXMLDocument
            doc.Close()
            word.Quit()
        except Exception:
            temp_docx.unlink(missing_ok=True)
            raise
        finally:
            pythoncom.CoUninitialize()
        return temp_docx

    # Linux / Other: LibreOffice headless
    if not _check_libreoffice():
        raise RuntimeError(
            "Linux 下需要安装 LibreOffice 才能处理 .doc 文件。\n"
            "安装命令: sudo apt install libreoffice  (Ubuntu/Debian)\n"
            "或者: sudo dnf install libreoffice  (Fedora)"
        )
    out_dir = Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "docx",
             "--outdir", str(out_dir.resolve()), str(doc_path.resolve())],
            check=True, capture_output=True, timeout=120,
        )
        candidates = list(out_dir.glob("*.docx"))
        if not candidates:
            raise RuntimeError("LibreOffice 转换完成但未找到输出 .docx 文件")
        result_docx = candidates[0]
        result_docx.rename(temp_docx)
        return temp_docx
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice 转换失败: {e.stderr.decode() if e.stderr else e}"
        ) from e
    finally:
        # Clean up temp output directory
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


def extract_docx_text(docx_path: Path) -> str:
    """Extract all text from a .docx file, preserving heading structure."""
    doc = Document(str(docx_path))
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            paragraphs.append("")
            continue

        style_name = para.style.name.lower() if para.style else ""

        # Map Word heading styles to Markdown headings
        if "heading" in style_name or "标题" in style_name:
            try:
                level = int(style_name.replace("heading", "").replace("标题", "").strip())
                level = max(1, min(level, 6))
            except ValueError:
                level = 1
            paragraphs.append(f"{'#' * level} {text}")
        else:
            paragraphs.append(text)

    # Also extract text from tables
    table_texts = []
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(" | ".join(cells))
        # Add separator line for markdown table if more than one row
        if len(rows) > 1:
            header = rows[0]
            sep = " | ".join(["---"] * len(row.cells))
            table_texts.extend([header, sep] + rows[1:])
        else:
            table_texts.extend(rows)
        table_texts.append("")  # blank line after table

    body = "\n".join(paragraphs)
    if table_texts:
        body += "\n\n" + "\n".join(table_texts)

    return body.strip()


def main() -> None:
    if Document is None:
        print("请安装 python-docx: pip install python-docx")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    word_files = sorted(
        [p for p in INPUT_DIR.iterdir() if p.suffix.lower() in (".docx", ".doc")]
    )
    if not word_files:
        print("No .docx / .doc files found in input/.")
        return

    total_start = time.time()
    for src_path in word_files:
        file_start = time.time()
        print(f"Processing: {src_path.name}")

        # Convert .doc → temp .docx if needed
        is_doc = src_path.suffix.lower() == ".doc"
        temp_path = None
        if is_doc:
            try:
                temp_path = convert_doc_to_docx(src_path)
                docx_path = temp_path
            except RuntimeError as e:
                print(f"  Error: {e}")
                continue
        else:
            docx_path = src_path

        text = extract_docx_text(docx_path)
        if not text.strip():
            print(f"  Warning: No text extracted from {src_path.name}")
            text = "[No extractable text content.]"

        # Clean up temp file
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

        md_name = sanitize_filename(src_path.stem + ".md")
        md_path = OUTPUT_DIR / md_name
        md_content = f"# {src_path.stem}\n\n{text}\n"
        md_path.write_text(md_content, encoding="utf-8")

        elapsed = time.time() - file_start
        print(f"  Saved ({elapsed:.1f}s): {md_path}")

    total_elapsed = time.time() - total_start
    print(f"\nDone. {len(word_files)} file(s) converted in {total_elapsed:.1f}s -> {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
