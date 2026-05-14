#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel 统计图表生成模块
======================
检测 Markdown 表格中的数值列，调用 matplotlib 自动生成统计图表。

前置条件：pip install matplotlib pandas
"""

import json
import re
from pathlib import Path
from typing import Callable, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互后端，兼容无 GUI 环境
    import matplotlib.pyplot as plt
    import pandas as pd
    HAS_MPL = True

    # ========== 中文字体配置 ==========
    # Windows 系字体候选（按优先级排列）
    _CN_FONT_NAMES = [
        'Microsoft YaHei',       # 微软雅黑（Windows）
        'SimHei',                # 黑体
        'SimSun',                # 宋体
        'PingFang SC',           # macOS 苹方
        'WenQuanYi Micro Hei',   # Linux 文泉驿
        'Noto Sans CJK SC',
        'STSong',
        'AR PL UMing CN',
    ]
    _cn_font_set = False
    for _name in _CN_FONT_NAMES:
        try:
            plt.rcParams['font.sans-serif'] = [_name] + plt.rcParams.get('font.sans-serif', ['DejaVu Sans'])
            plt.rcParams['axes.unicode_minus'] = False
            _cn_font_set = True
            break
        except Exception:
            continue
except ImportError:
    HAS_MPL = False


# ============================================================
# Markdown 表格解析
# ============================================================

def _parse_md_tables(md_text: str) -> list[dict]:
    """从 Markdown 文本中提取所有表格，每张表返回 {name, headers, rows}"""
    tables = []
    lines = md_text.split('\n')
    i = 0
    table_counter = 0

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and line.endswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(lines[i].strip())
                i += 1

            if len(rows) < 2:
                continue

            # 跳过可能的分隔行（内容全是 ---）
            data_start = 0
            if '---' in rows[1]:
                data_start = 2
            else:
                data_start = 1

            header_cells = [c.strip() for c in rows[0].split('|')[1:-1]]
            data_rows = []
            for r in rows[data_start:]:
                cells = [c.strip() for c in r.split('|')[1:-1]]
                if cells:
                    data_rows.append(cells)

            if data_rows and header_cells:
                table_counter += 1
                tables.append({
                    'name': f'Table_{table_counter}',
                    'headers': header_cells,
                    'rows': data_rows,
                })
        else:
            i += 1

    return tables


# ============================================================
# 数值列检测
# ============================================================

def _detect_numeric_columns(headers: list[str], rows: list[list[str]]) -> list[dict]:
    """检测数值列，返回每列的统计信息"""
    numeric_cols = []

    for col_idx in range(len(headers)):
        col_values = []
        for row in rows:
            if col_idx < len(row):
                val = row[col_idx].replace(',', '').replace('%', '') \
                              .replace('¥', '').replace('$', '').strip()
                try:
                    col_values.append(float(val))
                except ValueError:
                    col_values.append(None)
            else:
                col_values.append(None)

        # 如果该列有 >= 60% 的解析成功值，视为数值列
        valid = [v for v in col_values if v is not None]
        if len(valid) >= max(3, len(rows) * 0.6):
            numeric_cols.append({
                'index': col_idx,
                'name': headers[col_idx] if col_idx < len(headers) else f'Column_{col_idx}',
                'values': col_values,
                'valid_values': valid,
            })

    return numeric_cols


def _find_label_column(headers: list[str], numeric_indices: set[int]) -> Optional[int]:
    """找第一个非数值列作为 x 轴标签"""
    for ci in range(len(headers)):
        if ci not in numeric_indices and len(headers[ci]) < 30:
            return ci
    return None


def _auto_chart_type(numeric_cols: list, label_exists: bool) -> str:
    """自动判断最佳图表类型"""
    n = len(numeric_cols)
    if n == 1:
        return 'bar' if label_exists else 'bar'
    if n == 2:
        return 'scatter'
    if n >= 3:
        return 'radar'
    return 'bar'


def _build_filename(sheet_name: str, table_index: int) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', '_', sheet_name)
    return f"chart_{safe}_{table_index}.png"


# ============================================================
# 图表生成器
# ============================================================

def generate_charts_from_md(
    md_content: str,
    output_dir: Path,
    sheet_name: str = "Sheet1",
) -> list[dict]:
    """
    从 Markdown 表格文本生成统计图表。

    Args:
        md_content: 包含 Markdown 表格的文本
        output_dir: 图表输出目录
        sheet_name: Sheet 名称，用于命名文件

    Returns:
        图表信息列表：[{title, path, type, columns, data_rows, summary}]
    """
    if not HAS_MPL:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = _parse_md_tables(md_content)
    charts = []

    for tbl_idx, table in enumerate(tables):
        headers = table['headers']
        rows = table['rows']
        numeric_cols = _detect_numeric_columns(headers, rows)

        if not numeric_cols:
            continue

        numeric_indices = {nc['index'] for nc in numeric_cols}
        label_col = _find_label_column(headers, numeric_indices)

        # 构建 labels
        labels = []
        for row in rows:
            if label_col is not None and label_col < len(row):
                labels.append(row[label_col])
            else:
                labels.append(str(len(labels) + 1))

        # 过滤无效行：所有数值列均为空的行跳过
        valid_indices = []
        for ri in range(len(rows)):
            if not all(nc['values'][ri] is None for nc in numeric_cols):
                valid_indices.append(ri)

        if len(valid_indices) < 2:
            continue

        labels = [labels[ri] for ri in valid_indices]
        values: dict[str, list[Optional[float]]] = {}
        for nc in numeric_cols:
            values[nc['name']] = [nc['values'][ri] for ri in valid_indices]

        # --- 自动判断图表类型 ---
        chart_type = _auto_chart_type(numeric_cols, label_col is not None)
        chart_filename = _build_filename(sheet_name, tbl_idx + 1)
        chart_path = output_dir / chart_filename

        fig, ax = plt.subplots(figsize=(10, max(5, len(labels) * 0.35 + 2)))

        try:
            if chart_type == 'bar':
                x = range(len(labels))
                n_groups = len(numeric_cols)
                bar_width = 0.8 / n_groups
                colors = ['#2c5f8a', '#e8a020', '#4caf50', '#e53935', '#7b1fa2']

                for gi, nc in enumerate(numeric_cols):
                    positions = [xi + gi * bar_width for xi in x]
                    bars = ax.bar(
                        positions,
                        [v or 0 for v in values[nc['name']]],
                        bar_width,
                        label=nc['name'],
                        color=colors[gi % len(colors)],
                        alpha=0.85,
                    )
                    for bar, v in zip(bars, values[nc['name']]):
                        if v is not None:
                            ax.text(
                                bar.get_x() + bar.get_width() / 2, bar.get_height(),
                                f'{v:.1f}', ha='center', va='bottom', fontsize=7,
                            )

                ax.set_xticks([xi + bar_width * (n_groups - 1) / 2 for xi in x])
                ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)

            elif chart_type == 'scatter' and len(numeric_cols) >= 2:
                x_vals = values[numeric_cols[0]['name']]
                y_vals = values[numeric_cols[1]['name']]
                ax.scatter(x_vals, y_vals, s=60, alpha=0.7, c='#2c5f8a', zorder=3)
                for i, label in enumerate(labels):
                    ax.annotate(
                        label,
                        (x_vals[i], y_vals[i]),
                        fontsize=7, alpha=0.8,
                        xytext=(5, 5), textcoords='offset points',
                    )
                ax.set_xlabel(numeric_cols[0]['name'], fontsize=10)
                ax.set_ylabel(numeric_cols[1]['name'], fontsize=10)
                ax.grid(True, alpha=0.3)

            elif chart_type == 'radar':
                angles = [n / len(numeric_cols) * 2 * 3.14159 for n in range(len(numeric_cols))]
                angles += angles[:1]

                max_rows = min(len(labels), 12)
                colors_radar = ['#2c5f8a', '#e8a020', '#4caf50', '#e53935',
                                '#7b1fa2', '#00bcd4', '#ff5722', '#795548',
                                '#607d8b', '#9c27b0', '#3f51b5', '#009688']

                for ri in range(max_rows):
                    vals = [(values[nc['name']][ri] or 0) for nc in numeric_cols]
                    vals += vals[:1]
                    ax.plot(angles, vals, 'o-', label=labels[ri],
                            linewidth=1.2, markersize=3,
                            color=colors_radar[ri % len(colors_radar)])

                ax.set_xticks(angles[:-1])
                ax.set_xticklabels([nc['name'] for nc in numeric_cols], fontsize=8)
                ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=7)

            # 标题
            title = f"{sheet_name} — {table['name']}"
            ax.set_title(title, fontsize=13, fontweight='bold', color='#1a3c6e', pad=12)
            fig.tight_layout()
            fig.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            charts.append({
                'title': title,
                'path': str(chart_path),
                'type': chart_type,
                'sheet': sheet_name,
                'columns': [nc['name'] for nc in numeric_cols],
                'data_rows': len(valid_indices),
            })
        except Exception:
            plt.close(fig)
            continue

    return charts


def generate_charts_from_excel(
    excel_path: Path,
    output_dir: Path,
) -> list[dict]:
    """
    直接处理 Excel 文件，提取文本后生成图表。

    Args:
        excel_path: .xlsx / .xls 文件路径
        output_dir: 图表输出目录

    Returns:
        图表信息列表
    """
    ext = excel_path.suffix.lower()

    if ext == '.xlsx':
        try:
            import openpyxl
        except ImportError:
            return []
        text_parts = []
        charts = []
        wb = openpyxl.load_workbook(str(excel_path), data_only=True, read_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            # 构建此 sheet 的 Markdown 文本
            lines = []
            for idx, row in enumerate(ws.iter_rows(values_only=True)):
                values = [str(v).strip() if v is not None else '' for v in row]
                lines.append("| " + " | ".join(values) + " |")
                if idx == 0:
                    lines.append("| " + " | ".join(["---"] * len(values)) + " |")
            md_text = "\n".join(lines)
            if md_text.strip():
                sheet_charts = generate_charts_from_md(md_text, output_dir, sheet_name)
                charts.extend(sheet_charts)
        wb.close()
        return charts

    elif ext == '.xls':
        try:
            import xlrd
        except ImportError:
            return []
        charts = []
        wb = xlrd.open_workbook(str(excel_path))
        for sheet_idx in range(wb.nsheets):
            ws = wb.sheet_by_index(sheet_idx)
            lines = []
            for row_idx in range(ws.nrows):
                values = [str(ws.cell_value(row_idx, c)).strip() for c in range(ws.ncols)]
                lines.append("| " + " | ".join(values) + " |")
                if row_idx == 0:
                    lines.append("| " + " | ".join(["---"] * ws.ncols) + " |")
            md_text = "\n".join(lines)
            if md_text.strip():
                sheet_charts = generate_charts_from_md(md_text, output_dir, ws.name)
                charts.extend(sheet_charts)
        return charts

    return []


# ============================================================
# LLM 驱动的智能图表生成
# ============================================================

CHART_SPEC_SYSTEM_PROMPT = """你是一位数据分析师。下面是一个或多个 Markdown 表格，请分析每个表格的数据，决定应该生成哪些有价值的统计图表。

判断规则：
1. 图表类型可选：`bar`（柱状图）、`horizontal_bar`（横向柱状图）、`line`（折线图）、`pie`（饼图）、`scatter`（散点图）、`radar`（雷达图）
2. 选择原则：
   - `bar`：比较多个类别的数值大小（最常用），多个数值列用分组柱状图
   - `horizontal_bar`：类别名较长（>4汉字）且类别数>4时优选，便于阅读
   - `line`：x 轴为有序类别（年份、阶段、排名序号等），展示趋势
   - `pie`：各部分之和 ≈ 100% 的占比数据，仅 3~7 个类别时使用
   - `scatter`：两个数值列，观察相关性/分布
   - `radar`：多维度对比（至少3个数值列，且维度数3~8）
3. 如果表格较小（<=5行），优先用 bar 或 pie
4. 如果表格较大（>10行），只选最有代表性的列，可以生成多张不同角度的图表
5. 务必确保 `x_column` 和 `y_columns` 中的列名与表头精确匹配

请严格按照以下 JSON 格式返回，不要包含任何额外说明：
{"charts": [{"chart_type": "bar", "title": "清晰的图表标题", "x_column": "X轴列名", "y_columns": ["数值列名1"], "description": "图表解读"}]}

如果表格中没有数值数据或无法生成有意义的图表，返回 {"charts": []}"""


def _build_chart_prompt(tables: list[dict]) -> str:
    """将表格数据格式化为发送给 LLM 的文本"""
    lines = []
    for table in tables:
        lines.append(f"## {table['name']}")
        lines.append("| " + " | ".join(table['headers']) + " |")
        lines.append("| " + " | ".join(["---"] * len(table['headers'])) + " |")
        for row in table['rows']:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines)


def _parse_chart_specs(llm_response: str) -> list[dict]:
    """从 LLM 响应中 JSON 抽取图表规格"""
    # 用正则提取 JSON 对象
    json_match = re.search(r'\{[\s\S]*?"charts"[\s\S]*?\}', llm_response)
    if not json_match:
        return []
    try:
        data = json.loads(json_match.group())
        specs = data.get("charts", [])
        valid = []
        for spec in specs:
            if spec.get("chart_type") and spec.get("title") and spec.get("y_columns"):
                valid.append(spec)
        return valid
    except (json.JSONDecodeError, KeyError):
        return []


def _render_chart_from_spec(
    spec: dict,
    headers: list[str],
    rows: list[list[str]],
    output_path: Path,
    sheet_name: str,
) -> Optional[dict]:
    """
    根据 LLM 指定的规格渲染一张统计图表。

    Returns:
        图表信息 dict 或 None（渲染失败时）
    """
    chart_type = spec["chart_type"]
    title = spec["title"]
    x_col_name = spec.get("x_column", "")
    y_col_names = spec.get("y_columns", [])

    # ========== 列索引匹配 ==========
    def _find_col(name: str) -> Optional[int]:
        name_stripped = name.strip()
        # 精确匹配
        for i, h in enumerate(headers):
            if h.strip() == name_stripped:
                return i
        # 模糊匹配（包含关系）
        for i, h in enumerate(headers):
            if name_stripped in h.strip() or h.strip() in name_stripped:
                return i
        return None

    x_idx = _find_col(x_col_name) if x_col_name else None
    if x_idx is None and headers:
        x_idx = 0  # 默认第一列

    y_indices: list[int] = []
    for yn in y_col_names:
        idx = _find_col(yn)
        if idx is not None:
            y_indices.append(idx)

    if not y_indices:
        return None

    # ========== 数据提取 ==========
    labels: list[str] = []
    plot_values: dict[str, list[float]] = {}

    for yi, idx in enumerate(y_indices):
        col_name = y_col_names[yi] if yi < len(y_col_names) else headers[idx]
        plot_values[col_name] = []

    valid_rows = 0
    for row in rows:
        x_val = row[x_idx] if x_idx is not None and x_idx < len(row) else ""
        y_vals = []
        ok = True
        for idx in y_indices:
            if idx < len(row):
                raw = row[idx].replace(',', '').replace('%', '') \
                              .replace('¥', '').replace('$', '').strip()
                try:
                    y_vals.append(float(raw))
                except ValueError:
                    y_vals.append(0.0)
                    ok = False
            else:
                y_vals.append(0.0)
                ok = False
        if not ok:
            continue
        valid_rows += 1
        labels.append(x_val if x_val else str(valid_rows))
        for yi, v in enumerate(y_vals):
            col_name = y_col_names[yi] if yi < len(y_col_names) else headers[y_indices[yi]]
            plot_values[col_name].append(v)

    if valid_rows < 2:
        return None

    # ========== matplotlib 渲染 ==========
    fig, ax = plt.subplots(figsize=(10, max(5, len(labels) * 0.35 + 2)))

    colors = ['#2c5f8a', '#e8a020', '#4caf50', '#e53935', '#7b1fa2',
              '#00bcd4', '#ff5722', '#795548', '#607d8b', '#9c27b0']

    try:
        if chart_type == 'line':
            for gi, (col_name, vals) in enumerate(plot_values.items()):
                ax.plot(range(len(vals)), vals, 'o-',
                        linewidth=2, markersize=6, label=col_name,
                        color=colors[gi % len(colors)])
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)
            ax.grid(True, alpha=0.3)

        elif chart_type == 'pie':
            first_col = list(plot_values.values())[0]
            ax.pie(first_col, labels=labels, autopct='%1.1f%%',
                   colors=colors[:len(labels)],
                   startangle=90, textprops={'fontsize': 8})
            ax.axis('equal')

        elif chart_type == 'horizontal_bar':
            for gi, (col_name, vals) in enumerate(plot_values.items()):
                bars = ax.barh(range(len(vals)), vals, 0.6, label=col_name,
                               color=colors[gi % len(colors)], alpha=0.85)
                for bar, v in zip(bars, vals):
                    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                            f'{v:.1f}', ha='left', va='center', fontsize=7)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=8)
            ax.invert_yaxis()
            ax.grid(True, alpha=0.3, axis='x')

        elif chart_type == 'scatter':
            col_names = list(plot_values.keys())
            if len(col_names) >= 2:
                x_vals = plot_values[col_names[0]]
                y_vals = plot_values[col_names[1]]
                ax.scatter(x_vals, y_vals, s=80, alpha=0.7, c='#2c5f8a', zorder=3)
                for i, label in enumerate(labels):
                    ax.annotate(label, (x_vals[i], y_vals[i]),
                                fontsize=7, alpha=0.8,
                                xytext=(5, 5), textcoords='offset points')
                ax.set_xlabel(col_names[0], fontsize=10)
                ax.set_ylabel(col_names[1], fontsize=10)
                ax.grid(True, alpha=0.3)

        elif chart_type == 'radar':
            col_names = list(plot_values.keys())
            angles = [n / len(col_names) * 2 * 3.14159 for n in range(len(col_names))]
            angles += angles[:1]
            colors_radar = ['#2c5f8a', '#e8a020', '#4caf50', '#e53935',
                            '#7b1fa2', '#00bcd4', '#ff5722', '#795548',
                            '#607d8b', '#9c27b0', '#3f51b5', '#009688']
            max_rows = min(len(labels), 8)
            for ri in range(max_rows):
                vals = [plot_values[cn][ri] for cn in col_names]
                vals += vals[:1]
                ax.plot(angles, vals, 'o-', label=labels[ri],
                        linewidth=1.2, markersize=3,
                        color=colors_radar[ri % len(colors_radar)])
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(col_names, fontsize=8)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=7)

        else:  # bar (default)
            x = range(len(labels))
            n_groups = len(plot_values)
            bar_width = 0.8 / max(n_groups, 1)
            for gi, (col_name, vals) in enumerate(plot_values.items()):
                positions = [xi + gi * bar_width for xi in x]
                bars = ax.bar(positions, vals, bar_width, label=col_name,
                              color=colors[gi % len(colors)], alpha=0.85)
                for bar, v in zip(bars, vals):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                            f'{v:.1f}', ha='center', va='bottom', fontsize=7)
            ax.set_xticks([xi + bar_width * (n_groups - 1) / 2 for xi in x])
            ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)

        ax.set_title(title, fontsize=13, fontweight='bold', color='#1a3c6e', pad=12)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)

        return {
            'title': title,
            'path': str(output_path),
            'type': chart_type,
            'sheet': sheet_name,
            'columns': list(plot_values.keys()),
            'data_rows': valid_rows,
        }
    except Exception:
        plt.close(fig)
        return None


def generate_charts_from_md_with_llm(
    md_content: str,
    output_dir: Path,
    sheet_name: str = "Sheet1",
    cfg: Optional["AppConfig"] = None,
    add_log: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """
    调用 LLM 分析 Markdown 表格并智能生成统计图表。

    流程：
    1. 解析 Markdown 表格（复用现有解析器）
    2. 调用 LLM 分析数据并返回 JSON 图表规格
    3. 根据规格渲染 matplotlib 图表

    Args:
        md_content: 包含 Markdown 表格的文本
        output_dir: 图表输出目录
        sheet_name: Sheet 名称，用于命名文件
        cfg: LLM 配置（为 None 或不可用时回退到无 LLM 模式）
        add_log: 日志回调函数

    Returns:
        图表信息列表：[{title, path, type, columns, data_rows, ...}]
    """
    from .config_manager import AppConfig as _AppConfig

    if not HAS_MPL:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = _parse_md_tables(md_content)
    if not tables:
        return []

    # 无 LLM 配置时的回退
    if cfg is None or not cfg.is_api_ready():
        if add_log:
            add_log("LLM 未配置，使用自动图表模式")
        return generate_charts_from_md(md_content, output_dir, sheet_name)

    if add_log:
        add_log(f"正在调用 LLM 分析 {len(tables)} 个表格，确定最佳图表方案...")

    # 构建提示词
    table_text = _build_chart_prompt(tables)
    user_prompt = f"请分析以下表格数据，返回应该生成的图表规格：\n\n{table_text}"

    try:
        from .ai_generator import call_llm
        llm_response = call_llm(
            messages=[
                {"role": "system", "content": CHART_SPEC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            config=cfg,
            stream=False,
        )
    except Exception as e:
        if add_log:
            add_log(f"LLM 图表分析失败（{e}），回退到自动模式")
        return generate_charts_from_md(md_content, output_dir, sheet_name)

    # 解析 LLM 返回的图表规格
    specs = _parse_chart_specs(llm_response)
    if not specs:
        if add_log:
            add_log("LLM 未返回有效图表规格，回退到自动模式")
        return generate_charts_from_md(md_content, output_dir, sheet_name)

    if add_log:
        add_log(f"LLM 建议生成 {len(specs)} 张图表")

    # 逐一渲染
    charts = []
    for spec_idx, spec in enumerate(specs):
        # 找到规格对应的表格（通过 x_column 匹配表头）
        target_table = None
        x_col = spec.get("x_column", "")
        for table in tables:
            if x_col and any(x_col.strip() == h.strip() for h in table['headers']):
                target_table = table
                break
        if target_table is None:
            # 如果没精确匹配，用第一个足够宽的表格
            for table in tables:
                if len(table['headers']) > 1:
                    target_table = table
                    break
        if target_table is None:
            continue

        safe_sheet = re.sub(r'[\\/:*?"<>|]', '_', sheet_name)
        chart_filename = f"chart_{safe_sheet}_{spec_idx + 1}.png"
        chart_path = output_dir / chart_filename

        result = _render_chart_from_spec(
            spec,
            target_table['headers'],
            target_table['rows'],
            chart_path,
            sheet_name,
        )
        if result:
            charts.append(result)
            if add_log:
                add_log(f"  ✓ 图表 {spec_idx + 1}: {result['title']} ({result['type']})")

    if not charts:
        if add_log:
            add_log("LLM 图表全部渲染失败，回退到自动模式")
        return generate_charts_from_md(md_content, output_dir, sheet_name)

    return charts


def generate_charts_from_knowledge_base(
    output_md_dir: Path,
    chart_output_dir: Path,
    cfg: Optional["AppConfig"] = None,
    add_log: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """
    扫描知识点 Markdown 目录，自动为每个文件生成统计图表。

    Args:
        output_md_dir: 存放知识点 Markdown 文件的目录路径
        chart_output_dir: 图表输出目录
        cfg: LLM 配置（可选，传入后启用 LLM 智能分析）
        add_log: 日志回调函数

    Returns:
        所有文件的图表信息聚合列表
    """
    if not HAS_MPL:
        return []

    chart_output_dir = Path(chart_output_dir)
    output_md_dir = Path(output_md_dir)
    chart_output_dir.mkdir(parents=True, exist_ok=True)

    if not output_md_dir.is_dir():
        if add_log:
            add_log(f"知识点目录不存在: {output_md_dir}")
        return []

    md_files = sorted(output_md_dir.glob("*.md"))
    if not md_files:
        if add_log:
            add_log(f"知识点目录中未找到 .md 文件: {output_md_dir}")
        return []

    if add_log:
        add_log(f"扫描到 {len(md_files)} 个知识点文件，开始生成图表...")

    all_charts: list[dict] = []
    for md_file in md_files:
        stem = md_file.stem
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as e:
            if add_log:
                add_log(f"  跳过 {md_file.name}（读取失败: {e}）")
            continue

        if not content.strip():
            continue

        if add_log:
            add_log(f"  处理: {md_file.name} ({len(content)} 字符)")

        file_charts = generate_charts_from_md_with_llm(
            md_content=content,
            output_dir=chart_output_dir / stem,
            sheet_name=stem,
            cfg=cfg,
            add_log=add_log,
        )
        all_charts.extend(file_charts)

    if add_log:
        add_log(f"知识库图表生成完成，共生成 {len(all_charts)} 张图表")

    return all_charts
