# 软考系统架构设计师学习资料生成工具 · 改进方案

> **版本**: v1.0  
> **日期**: 2026-05-13  
> **范围**: 功能增强 + UI 美化

---

## 目录

- [1. 整体改进思路](#1-整体改进思路)
- [2. 逻辑功能层面](#2-逻辑功能层面)
  - [2.1 提示词可视化与动态编辑](#21-提示词可视化与动态编辑)
  - [2.2 知识库可视化与在线编辑](#22-知识库可视化与在线编辑)
  - [2.3 可插拔模块设计（核心增强）](#23-可插拔模块设计核心增强)
  - [2.4 细节表格对比](#24-细节表格对比)
- [3. UI 美化方案](#3-ui-美化方案)
  - [3.1 整体风格与配色体系](#31-整体风格与配色体系)
  - [3.2 布局重构](#32-布局重构)
  - [3.3 组件级优化](#33-组件级优化)
  - [3.4 交互细节](#34-交互细节)
- [4. 实施路线图](#4-实施路线图)
- [5. 附录：修改文件清单](#5-附录修改文件清单)

---

## 1. 整体改进思路

```
┌─────────────────────────────────────────────────────────┐
│                    改进后的系统架构                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 素材管理 │  │ 提示词工作台  │  │ 知识库浏览器     │   │
│  │ (Step1) │  │ (Step1.5)    │  │ (Step1.5)       │   │
│  └────┬────┘  └──────┬───────┘  └───────┬──────────┘   │
│       │              │                  │              │
│       └──────────────┼──────────────────┘              │
│                      ▼                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │          模块化生成引擎 (Step2)                    │  │
│  │  ☑ 考情分析  ☑ 背景  ☑ 基础原理推导               │  │
│  │  ☑ 考点精讲  ☑ 公式总结  ☑ 案例分析               │  │
│  │  ☑ 真题演练  ☑ 难题解析  ☑ 记忆口诀               │  │
│  └──────────────────────┬───────────────────────────┘  │
│                         ▼                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │          结果预览与导出 (Step3)                    │  │
│  │   实时预览 │ 对比视图 │ 分段下载 │ 一键 Word      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 架构演进路径：从流水线到 Agentic Pipeline

基于对 Claude Code 三层 agentic 架构（编排层 → 工具层 → 模型层）的分析，本方案的架构演进分三阶段：

| 阶段 | 架构模式 | 核心特征 | 对标 Claude Code |
|------|---------|---------|-----------------|
| **当前** | 函数式串行流水线 | `main.py` 线性调度，模块硬编码 | — |
| **Phase 1** | 声明式管道 | YAML 编排 + `@tool` 注册 | Skills + 工具层抽象 |
| **Phase 2** | Agentic 循环 | 质量门禁 + 自动重试 + 检查点 | Agentic Loop + Checkpoint |
| **Phase 3** | 可扩展平台 | 上下文记忆 + 子任务隔离 + 动态调度 | Memory + Subagents |

```
Phase 1 (本方案目标)              Phase 2 (后续演进)              Phase 3 (远期目标)
┌──────────────────┐           ┌─────────────────────┐        ┌──────────────────────┐
│  配置驱动            │    →    │  反馈循环              │   →    │  智能编排              │
│                  │           │                     │        │                      │
│  pipeline.yaml  │           │  execute → verify   │        │  Plan → Allocate     │
│  ↓               │           │  ↓           ↓      │        │  ↓          ↓        │
│  tool.execute()  │           │  retry → refine     │        │  Subagent  Subagent  │
│  ↓               │           │                     │        │  ↓          ↓        │
│  save_output()   │           │  checkpoint save    │        │  Merge → Review      │
└──────────────────┘           └─────────────────────┘        └──────────────────────┘
```

---

## 2. 逻辑功能层面

### 2.1 提示词可视化与动态编辑

#### 现状问题

- 提示词模板存放在 `prompts/study_guide.j2`、`prompts/mindmap.j2` 两个文件中
- 用户必须手动打开文本文件才能查看和修改
- 提示词与 UI 完全分离，用户不知道当前 AI 的"人设"和"指令"是什么
- `prompt_agent_学习资料生成.md` 是另一份独立的提示词，与 .j2 内容重复

#### 改进方案

**新增 Step 1.5：提示词工作台**

在 Step1（素材管理）和 Step2（执行生成）之间插入一个**提示词可视化面板**，包含：

```
┌─────────────────────────────────────────────────────────┐
│  Step 1.5: 提示词工作台                                  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │  1️⃣ 系统提示词（System Prompt）                  │   │
│  │  ┌───────────────────────────────────────────┐  │   │
│  │  │  <可编辑文本框>                             │  │   │
│  │  │  你是软考系统架构设计师考前辅导专家...       │  │   │
│  │  └───────────────────────────────────────────┘  │   │
│  │  [重置为默认] [保存修改]                         │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  2️⃣ 用户提示词（User Prompt）                    │   │
│  │  ┌───────────────────────────────────────────┐  │   │
│  │  │  <可编辑文本框>                             │  │   │
│  │  │  请根据以下素材生成综合学习资料...            │  │   │
│  │  └───────────────────────────────────────────┘  │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  3️⃣ 输出结构预览                                │   │
│  │  ☑ 模块勾选 → 对应输出目录结构实时更新显示       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**关键交互设计：**

| 功能 | 实现方式 |
|------|----------|
| 预览当前提示词 | 从 `prompts/` 读取 .j2 文件，用 Jinja2 渲染后展示在文本框 |
| 实时编辑 | 文本框内容 `on_change` 触发 → 更新 session_state |
| 保存修改 | 写回 `.j2` 文件，或存为用户自定义版本（在 prompts/ 下建 `custom/` 子目录） |
| 重置默认 | 从 git 原始版本读取覆盖（或内置 fallback） |
| 变量注入 | 用户在侧边栏设置的 `focus_areas`、`detail_level` 等变量，实时反映到提示词预览中 |

**示例效果：**

当用户勾选了"背景 + 公式总结 + 案例分析"三个模块，且侧边栏设置了"详细"程度，预览区立即显示：

```markdown
## 输出要求
对每个章节输出以下模块：
### 📖 背景
知识点的提出背景、解决什么问题、发展历程
### 🧮 公式总结
核心公式推导、参数含义、适用条件
### 🏗️ 案例分析
真实项目案例、架构选型决策过程、经验教训
```

#### 涉及的代码修改

| 文件 | 修改内容 |
|------|----------|
| `app.py` | 新增 `render_step1_5_prompt_workshop()` 函数；在 `main()` 中 Step1 与 Step2 之间插入 |
| `modules/prompt_manager.py` | 新增 `get_prompt_text()` 获取原始模板文本；`save_prompt_template()` 保存修改 |
| `modules/config_manager.py` | 新增 `prompts_custom_dir` 路径字段 |

---

### 2.2 知识库可视化与在线编辑

#### 现状问题

- 用户看不到每个章节的实际内容，只能看到"大小(字节)"统计
- 无法判断素材质量，不知道 OCR 结果是否准确
- 无法编辑或删除素材

#### 改进方案

**在 Step1 素材管理内扩展知识库浏览器**

```
┌─────────────────────────────────────────────────────────┐
│  知识库浏览器                                            │
├────────────┬────────────────────────────────────────────┤
│  章节列表   │  内容预览                                  │
│            │                                            │
│  ☑ 1.计算机硬件  │  # 计算机硬件                          │
│  ☑ 2.操作系统    │  ## 考情分析                          │
│  ☐ 3.数据库系统  │  历年分值：6-8分                      │
│  ☑ 4.嵌入式技术  │  ...                                 │
│  ☐ 5.计算机网络  │                                       │
│  ...          │  [编辑] [重新OCR] [删除]                 │
├────────────┴────────────────────────────────────────────┤
│  批量操作： ☑ 全选  [批量重新生成] [导出为 ZIP]          │
└─────────────────────────────────────────────────────────┘
```

**关键交互：**

| 功能 | 实现方式 |
|------|----------|
| 左侧树形/列表 | Streamlit 的 `selectbox` 或自定义 HTML 列表，点击切换右侧预览 |
| 右侧预览 | `st.text_area` 或 `st.markdown` 展示内容，可切换"渲染/源码"模式 |
| 编辑 | 双击进入编辑模式，`st.text_area` 直接修改，保存后写入源文件 |
| 重新 OCR | 调用 `process_pdf_to_md` 重新识别 |
| 删除 | 确认对话框后删除源文件 |
| 搜索/过滤 | 在章节列表上方添加搜索框，`st.text_input` + 过滤 |

#### 涉及的代码修改

| 文件 | 修改内容 |
|------|----------|
| `app.py` | `render_step1_material()` 中扩展右侧面板，增加分栏布局和内容预览 |
| `modules/ocr_engine.py` | 确保导出单个文件重新 OCR 的接口 |

---

### 2.3 可插拔模块设计（核心增强）

#### 现状问题

- AI 输出结构固定在六个部分：考情分析、知识点体系、考点精讲、新教材变化、记忆口诀、真题演练
- 用户无法自定义增减模块，无法控制 AI 输出的内容维度
- 用户新增需求：背景、基础原理推导、公式总结、案例分析、难题解析

#### 改进方案

**模块化注册系统**

在 `modules/` 下新增 `content_modules/` 目录，每个模块是一个独立的配置描述：

```
modules/content_modules/
├── __init__.py
├── registry.py          # 模块注册表，管理所有可用模块
├── base_module.py       # 模块基类
├── exam_analysis.py     # 📊 考情分析
├── background.py        # 📖 背景
├── principle.py         # 🔬 基础原理推导
├── formula.py           # 🧮 公式总结
├── case_analysis.py     # 🏗️ 案例分析
├── hard_problem.py      # 🎯 难题解析
├── key_points.py        # 🎯 考点精讲
├── textbook_changes.py  # ⚠️ 新教材变化
├── mnemonics.py         # 📌 记忆口诀
└── exercises.py         # ✅ 真题演练
```

**模块描述示例（`modules/content_modules/background.py`）：**

```python
MODULE_DEF = {
    "id": "background",
    "name": "背景",
    "icon": "📖",
    "emoji": "background",
    "description": "知识点的提出背景、解决什么问题、发展历程",
    "category": "基础理解",
    "enabled_by_default": False,
    "prompt_instruction": (
        "### 📖 背景\n"
        "对于每个核心知识点，补充以下背景信息：\n"
        "- **提出背景**：该知识点是为了解决什么实际问题而提出的\n"
        "- **发展历程**：从提出到成熟的关键演进节点\n"
        "- **适用场景**：什么情况下需要使用该知识点\n"
        "- **局限性**：该方法的限制条件和注意事项"
    ),
}
```

**UI 交互：模块选择面板**

在侧边栏或 Step2 上方增加模块选择区域：

```
┌─────────────────────────────────────────────────────────┐
│  📦 生成模块配置                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  基础理解模块                                           │
│  ☑ 📊 考情分析     ☐ 📖 背景                           │
│  ☐ 🔬 基础原理推导   ☐ 🧮 公式总结                     │
│                                                         │
│  深度拓展模块                                           │
│  ☑ 🎯 考点精讲     ☐ 🏗️ 案例分析                      │
│  ☐ 🎯 难题解析     ☐ ⚠️ 新教材变化                    │
│                                                         │
│  辅助强化模块                                           │
│  ☑ 📌 记忆口诀     ☑ ✅ 真题演练                       │
│                                                         │
│  [全选] [取消全选] [恢复默认]                            │
├─────────────────────────────────────────────────────────┤
│  输出目录结构预览：                                       │
│  # 章节名                                               │
│  ## 📊 考情分析                                         │
│  ## 📖 背景                                             │
│  ## 🧮 公式总结                                         │
│  ## 🎯 考点精讲                                         │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

**动态提示词构建流程：**

```
用户勾选模块列表
    │
    ▼
从 registry 获取已启用模块的 prompt_instruction
    │
    ▼
拼接到 system_prompt 的「输出要求」部分
    │
    ▼
渲染 Jinja2 模板 → 发送给 LLM
```

**提示词模板更新（`prompts/study_guide.j2` 修改）：**

```diff
 ## 输出要求

 ### 1. 综合学习指南（按章节）
 对每个章节输出：
+{% for module in enabled_modules %}
+{{ module.prompt_instruction }}
+{% endfor %}
- - **📊 考情分析**：历年分值分布、考查频次、趋势判断
- - **📝 知识点体系**：用 Mindmap 风格（缩进列表）整理层级知识结构
- - **🎯 考点精讲**：每个核心考点的详细讲解，重点用 **加粗** 标注
- - **⚠️ 新教材变化**：本节第二版相对旧版的增删改内容
- - **📌 记忆口诀/技巧**：助记方法（如果有）
- - **✅ 真题演练**：抽取代表性真题，附答案和解析
```

#### 涉及的代码修改

| 文件 | 修改内容 |
|------|----------|
| `modules/content_modules/__init__.py` | 包初始化 |
| `modules/content_modules/registry.py` | 模块注册表实现，`get_available_modules()`、`get_enabled_modules()` |
| `modules/content_modules/base_module.py` | 模块基类或数据类定义 |
| `modules/content_modules/*.py` | 各模块的 `MODULE_DEF` 定义 |
| `modules/prompt_manager.py` | `build_study_guide_prompt()` 增加 `enabled_modules` 参数，动态构建提示词 |
| `modules/ai_generator.py` | `generate_study_guide()` 透传模块参数 |
| `app.py` | 侧边栏或 Step2 区域新增模块选择 UI；`render_sidebar()` 或新增函数 |
| `prompts/study_guide.j2` | 模板中改用 `{% for module %}` 循环渲染 |

#### 管道化配置：声明式 Pipeline 编排

参照 Claude Code 的 Skills 机制，增加 YAML 声明式管道配置，让整个生成流程成为可组合、可复用的配置文件。

**`pipelines/default.yaml` 示例：**

```yaml
name: "默认学习资料生成"
description: "标准全链路：清洗 → AI 生成 → 思维导图 → Word 导出"

steps:
  - id: local_clean
    tool: local_processor.clean_all
    input: output_md/
    output: 综合学习资料_自动生成.md

  - id: ai_guide
    tool: ai_generator.generate_study_guide
    params:
      modules: [exam_analysis, background, key_points, exercises]
      temperature: 0.3
    depends_on: [local_clean]
    output: 综合学习资料_AI生成.md

  - id: mindmap
    tool: mindmap_generator.generate
    params:
      format: both  # markmap + mermaid
    depends_on: [ai_guide]
    output: output_mindmap/

  - id: word_export
    tool: docx_converter.convert
    params:
      input: 综合学习资料_AI生成.md
      template: templates/default.docx
    depends_on: [ai_guide]
    output: 综合学习资料_AI生成.docx
```

**核心优势：**

| 特性 | 当前硬编码方式 | Pipeline 方式 |
|------|-------------|-------------|
| 步骤编排 | `main()` 函数内写死 | YAML 声明，可随意增删步骤 |
| 步骤复用 | 复制粘贴代码 | 通过 `tool:` 引用即可 |
| 参数调整 | 改代码 | 改 YAML |
| 可视化 | 无 | UI 自动解析 YAML 生成流程视图 |
| 条件分支 | `if` 语句 | YAML `when:` / `depends_on:` |

**涉及的代码修改：**

| 文件 | 修改内容 |
|------|----------|
| `modules/pipeline_engine.py`（新增） | Pipeline 引擎：读取 YAML → 拓扑排序 → 顺序执行每个 step |
| `modules/tool_registry.py`（新增） | `@tool` 装饰器 + 注册表，将函数注册为可调用工具 |
| `modules/base_tool.py`（新增） | 工具基类，定义 `execute()` 接口 |


#### 质量门禁与 Auto-Retry 机制

基于 Claude Code 的 `verify → refine → retry` 闭环，在每个 Pipeline 步骤后加入质量门禁：

```python
class QualityGate:
    """质量门禁：验证输出 → 自动重试 → 人工介入"""
    
    GATES = {
        "ai_guide": [
            Check("content_length", min_chars=5000),
            Check("has_sections", required_sections=["考情分析", "考点精讲"]),
            Check("no_hallucination", forbidden_phrases=["根据网络资料"]),
        ],
        "mindmap": [
            Check("valid_format", formats=["markmap", "mermaid"]),
            Check("not_empty", min_nodes=5),
        ],
        "docx": [
            Check("file_exists"),
            Check("min_pages", min_pages=2),
        ],
    }
    
    @classmethod
    def verify(cls, step_id: str, output_path: str) -> GateResult:
        """验证某一步骤的输出是否达标"""
        checks = cls.GATES.get(step_id, [])
        results = [check.run(output_path) for check in checks]
        return GateResult(
            passed=all(r.passed for r in results),
            details=results,
        )
```

**重试策略：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_retries` | 3 | 最大重试次数 |
| `retry_delay` | 5s | 重试间隔 |
| `backoff_factor` | 2.0 | 指数退避 |
| `refine_on_retry` | true | 重试时自动补充前次错误信息到提示词 |

**UI 中的质量门禁可视化：**

```
  📝 AI 学习资料  ──  ✅ 通过 (12,348字 ✓  模块完整 ✓)
  🧠 AI 思维导图  ──  🔄 重试 1/3 (节点数不足，正在补充...)
  📤 Word 转换    ──  ⏳ 等待中
```

**涉及的代码修改：**

| 文件 | 修改内容 |
|------|----------|
| `modules/quality_gate.py`（新增） | 质量门禁实现：`Check`、`QualityGate.verify()` |
| `modules/pipeline_engine.py`（新增） | Pipeline 中集成自动重试逻辑 |
| `app.py` | UI 中增加质量门禁状态展示 |

---

### 2.4 细节表格对比

### 2.4 细节表格对比

#### 现状 vs 改进：功能特性对比

| 特性 | 当前状态 | 改进后状态 |
|------|---------|-----------|
| 提示词可见性 | 需手动打开 .j2 文件 | UI 内实时预览 + 编辑 |
| 提示词编辑 | 手动编辑文件 | UI 内编辑 + 保存 + 重置 |
| 知识库浏览 | 仅显示文件名和大小 | 文件列表 + 内容预览 + 编辑 |
| 输出模块控制 | 固定 6 个硬编码 | 可插拔，按需勾选 10+ 模块 |
| 模块顺序 | 固定顺序 | 可拖拽调整 |
| 新模块（背景） | 不存在 | 可选启用 |
| 新模块（公式总结） | 不存在 | 可选启用 |
| 新模块（案例分析） | 不存在 | 可选启用 |
| 新模块（难题解析） | 不存在 | 可选启用 |
| 新模块（原理推导） | 不存在 | 可选启用 |
| 管道化 Pipeline 编排 | 硬编码 `main()` 调度 | YAML 声明式编排，UI 可视化流程 |
| 步骤间依赖与容错 | 无（单步失败全链终止） | `depends_on` + 自动跳过/重试 |
| 质量门禁 | 无（输出全靠人工检查） | `QualityGate` 自动验证 + 自动重试 |
| 检查点与恢复 | 无（失败后重头开始） | 每步 checkpoint，支持断点续跑 |
| 工具层抽象 | 函数直接调用 | `@tool` 注册 + 统一 `execute()` 接口 |
| 日志与可观测性 | 仅 `print()` 输出 | Pipeline 执行日志 + 步骤耗时 + 状态追踪 |

---

## 3. UI 美化方案

### 3.1 整体风格与配色体系

#### 色彩系统

采用**蓝灰专业学术风**，契合软考考试场景的严肃性。

```css
/* 色板 */
--primary:       #1a3c6e;   /* 深蓝 - 主色，标题、按钮 */
--primary-light: #2c5f8a;   /* 中蓝 - 二级标题 */
--primary-pale:  #e8f0fe;   /* 浅蓝 - 背景卡片 */
--accent:        #e67e22;   /* 橙色 - 强调色，CTA 按钮 */
--success:       #27ae60;   /* 绿色 - 成功状态 */
--warning:       #f39c12;   /* 黄色 - 警告 */
--danger:        #e74c3c;   /* 红色 - 错误 */
--bg:            #f5f7fa;   /* 背景灰 */
--card-bg:       #ffffff;   /* 卡片白 */
--text:          #2c3e50;   /* 正文深灰 */
--text-light:    #7f8c8d;   /* 辅助文字 */
--border:        #dcdfe6;   /* 边框 */
```

#### 在 Streamlit 中的实现

利用 Streamlit 的 `st.markdown` 注入自定义 CSS：

```python
def inject_custom_css():
    st.markdown("""
    <style>
    /* 全局 */
    .stApp { background-color: #f5f7fa; }
    
    /* 标题 */
    h1 { color: #1a3c6e !important; font-weight: 700 !important; }
    h2 { color: #2c5f8a !important; font-weight: 600 !important; }
    h3 { color: #3a7bbf !important; }
    
    /* 卡片容器 */
    div[data-testid="stVerticalBlock"] > div {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 1rem;
    }
    
    /* 按钮 */
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* 多选框 */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #e8f0fe;
        color: #1a3c6e;
    }
    
    /* 步骤数字标识 */
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #1a3c6e;
        color: white;
        font-weight: 700;
        margin-right: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
```

### 3.2 布局重构

#### 当前布局

```
侧边栏（配置）
┌──────────┐
│          │  Step 1: 素材管理
│  配置面板 │  ─────────────────
│          │  Step 2: 执行生成
│          │  ─────────────────
│          │  Step 3: 结果下载
└──────────┘
```

#### 改进后布局

```
┌─────────────────────────────────────────────────────────┐
│  📚 软考系统架构设计师 · 学习资料生成工作台              │
│  整合 OCR → 清洗 → AI生成 → 思维导图 → Word 导出       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐              │
│  │ ①素材│→│提示词│→│ ②生成│→│ ③结果│→│ 导出 │              │
│  │ 管理 │ │ 工作台│ │ 执行 │ │ 预览 │ │ 下载 │              │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘              │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  当前步骤的内容区域                               │    │
│  │                                                 │    │
│  │  （根据顶部步骤切换）                             │    │
│  │                                                 │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  侧边栏（折叠式配置面板）                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ⚙️ 配置（可折叠）                              │   │
│  │  ▶ API 配置（仅 AI 模式展开）                   │   │
│  │  ▶ 生成偏好                                    │   │
│  │  ▶ 模块配置                                    │   │
│  │  ▶ 关于                                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**顶部步骤导航栏的实现：**

```python
def render_step_navbar():
    """渲染顶部步骤导航"""
    steps = [
        ("📂", "素材管理", "step1"),
        ("✏️", "提示词工作台", "step1_5"),
        ("⚡", "执行生成", "step2"),
        ("👁️", "结果预览", "step3_download"),
        ("📤", "导出", "step3_download"),
    ]
    
    cols = st.columns(len(steps))
    current = st.session_state.get("active_step", "step1")
    
    for i, (icon, label, key) in enumerate(steps):
        with cols[i]:
            is_active = (current == key)
            is_done = st.session_state.get(f"step_{key}_done", False)
            
            bg = "#1a3c6e" if is_active else ("#27ae60" if is_done else "#e0e0e0")
            text_color = "white" if (is_active or is_done) else "#999"
            
            st.markdown(f"""
            <div style="text-align:center; cursor:pointer;"
                 onclick="window.location.href='#'">
                <div style="
                    width:40px; height:40px; border-radius:50%;
                    background:{bg}; color:{text_color};
                    display:inline-flex; align-items:center; justify-content:center;
                    font-size:18px; margin:0 auto; transition:all 0.3s;
                ">{icon}</div>
                <div style="font-size:12px; margin-top:4px; color:{'#1a3c6e' if is_active else '#666'};
                    font-weight:{'700' if is_active else '400'};
                ">{label}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 箭头连接
            if i < len(steps) - 1:
                st.markdown("""
                <div style="text-align:center; color:#ccc; font-size:20px; margin-top:-10px;">→</div>
                """, unsafe_allow_html=True)
```

### 3.3 组件级优化

#### 3.3.1 章节选择器增强

**现状：** 一个简单的 `st.multiselect` 下拉列表

**改进：** 卡片式章节选择器

```python
def render_chapter_cards(available: list[str], selected: list[str]) -> list[str]:
    """渲染卡片式章节选择器"""
    result = []
    
    # 按类别分组
    categories = {
        "基础": ["计算机硬件", "操作系统", "数据库系统", "嵌入式技术", "计算机网络"],
        "进阶": ["软件工程", "面向对象技术", "项目管理", "系统架构设计"],
        "拓展": ["数学与经济管理", "知识产权与标准化"],
        "专题": ["架构案例专题", "论文写作专题"],
    }
    
    for cat_name, cat_chapters in categories.items():
        st.markdown(f"**{cat_name}**")
        cols = st.columns(4)
        for i, ch in enumerate(cat_chapters):
            if ch in available:
                with cols[i % 4]:
                    is_selected = ch in selected
                    bg = "#1a3c6e" if is_selected else "#f0f4f8"
                    fg = "white" if is_selected else "#333"
                    
                    if st.button(
                        f"{'✅ ' if is_selected else ''}{ch}",
                        key=f"card_{ch}",
                        use_container_width=True,
                    ):
                        # 切换选中状态
                        if is_selected:
                            selected.remove(ch)
                        else:
                            selected.append(ch)
                        safe_rerun()
    
    return selected
```

#### 3.3.2 进度与状态可视化

**现状：** 纯文字日志

**改进：** 可视化进度追踪

```python
def render_progress_dashboard():
    """渲染生成进度仪表板"""
    steps = [
        ("🧹 本地清洗", "local"),
        ("📝 AI 学习资料", "ai_guide"),
        ("🧠 AI 思维导图", "ai_mindmap"),
        ("📝 Word 转换", "docx"),
        ("🖼️ 渲染图片", "render_png"),
    ]
    
    for label, step_key in steps:
        status = st.session_state.get(f"status_{step_key}", "pending")
        # pending / running / done / error
        
        icon = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}
        color = {"pending": "#999", "running": "#e67e22", "done": "#27ae60", "error": "#e74c3c"}
        
        st.markdown(f"""
        <div style="display:flex; align-items:center; padding:8px 12px;
                    margin:4px 0; border-radius:8px;
                    background:{'#f0faf0' if status == 'done' else ('#fff8f0' if status == 'running' else '#fafafa')};">
            <span style="font-size:20px; margin-right:12px;">{icon[status]}</span>
            <span style="flex:1; font-weight:{'600' if status == 'running' else '400'};
                        color:{color[status]};">{label}</span>
            <span style="font-size:12px; color:#999;">
                {st.session_state.get(f'time_{step_key}', '')}
            </span>
        </div>
        """, unsafe_allow_html=True)
```

#### 3.3.3 结果对比视图

**现状：** 只展示最终生成内容

**改进：** 分屏对比（AI vs 本地）

```python
def render_comparison_view(ai_md: str, local_md: str):
    """AI 生成 vs 本地清洗 对比视图"""
    tab_ai, tab_local, tab_diff = st.tabs(["🤖 AI 生成", "📄 本地清洗", "🔄 差异对比"])
    
    with tab_ai:
        st.markdown(ai_md[:5000])
        
    with tab_local:
        st.markdown(local_md[:5000])
        
    with tab_diff:
        # 简单的差异对比
        ai_lines = ai_md.split("\n")
        local_lines = local_md.split("\n")
        # 用 simple-diff 或自定义逻辑高亮差异
```

### 3.4 交互细节

#### 3.4.1 流式输出的可视化改进

**现状：** 黑色文字块 + 闪烁光标

**改进：** 打字机效果 + 行号 + 字数统计

```python
def render_streaming_output(buffer: list[str]):
    """美化流式输出"""
    text = "".join(buffer)
    lines = text.count("\n")
    chars = len(text)
    
    # 顶部状态栏
    st.caption(f"⏳ 生成中 · {lines} 行 · {chars:,} 字符")
    
    # 代码块展示
    st.markdown(f"""```markdown
{text}▌
```""")
```

#### 3.4.2 响应式触感反馈

- 按钮点击增加短暂的涟漪效果（CSS `:active`）
- 生成完成时播放通知（Streamlit `st.toast()`）
- 长任务时显示预估剩余时间
- 章节选中状态切换有过渡动画

```css
/* Streamlit 内联扩展示例 */
.stButton button:active {
    transform: scale(0.97) !important;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}
.running-indicator {
    animation: pulse 1.5s infinite;
}
```

#### 3.4.3 暗黑模式支持（可选）

利用 Streamlit 的 `theme` 配置：

```toml
# .streamlit/config.toml
[theme]
primaryColor = "#1a3c6e"
backgroundColor = "#f5f7fa"
secondaryBackgroundColor = "#ffffff"
textColor = "#2c3e50"
font = "sans serif"

[theme.dark]
primaryColor = "#6ea8fe"
backgroundColor = "#1a1a2e"
secondaryBackgroundColor = "#16213e"
textColor = "#e0e0e0"
```

---

## 4. 实施路线图

采用 **RICE 优先级排序法**（Reach × Impact × Confidence × Effort），将任务分为 P0-P3 四个优先级阶段。**每个阶段产出可独立交付**，无需等待全部完成。

```
P0 ── 立即可用 ──────────────────────────────────────────────
  目标：让工具链具备基本可用性 + 最影响日常体验的痛点解决
  (不影响现有功能，可独立部署)

  □ 可插拔模块系统（modules/content_modules/ + registry.py）
  □ 提示词工作台（UI 内编辑/预览/重置提示词）
  □ 知识库浏览器（文件预览 + 内容在线编辑）
  □ UI 美化（CSS 注入 + 步骤导航栏 + 卡片选择器）
  □ Pipeline 声明式配置 YAML + 引擎基础框架

  RICE: Reach=5, Impact=4, Confidence=5, Effort=3 → 总分 100
  预计产出：v0.1 可用版本

P1 ── 质量与可观测性 ────────────────────────────────────────
  目标：让工具链不再是黑盒，每一步都可追踪、可重试

  □ 质量门禁 QualityGate（内容校验 + 自动重试逻辑）
  □ Pipeline 引擎集成质量门禁 + 执行日志
  □ 进度仪表板实时状态展示（步骤耗时/成功/失败/重试）
  □ 检查点系统：每步 checkpoint 支持断点续跑

  RICE: Reach=4, Impact=5, Confidence=4, Effort=3 → 总分 89
  预计产出：v0.2 可靠版本

P2 ── 架构与定制 ────────────────────────────────────────────
  目标：将新架构完善为可扩展平台

  □ @tool 注册机制 + base_tool.py 工具抽象层
  □ 模板市场（预置 5 套配色 + 3 种文档排版风格）
  □ 用户自定义模块：支持 Python 脚本热加载
  □ Mermaid 思维导图风格可配置

  RICE: Reach=3, Impact=4, Confidence=3, Effort=3 → 总分 71
  预计产出：v0.3 可扩展版本

P3 ── 臻于完备 ──────────────────────────────────────────────
  目标：企业级可用性 & 知识沉淀

  □ 全链路集成测试（边界情况/异常链路）
  □ 用户文档（含 AGENTS.md 更新 + 运行速查表）
  □ 多项目工作区支持（一套代码管理多套教材）
  □ 生成质量评估报告（历史对比 + 改进建议）

  RICE: Reach=2, Impact=3, Confidence=3, Effort=4 → 总分 36
  预计产出：v1.0 稳定版本
```

> **RICE 说明**：Reach（影响人数 1-5）× Impact（单个影响 1-5）× Confidence（信心 1-5）÷ Effort（人周估值）。每个 Phase 的总分用以横向对比优先级。P0 总分最高，最值得立即投入。

### 增量交付策略

为避免长分支开发风险，各阶段均遵循 **最小增量原则**：

1. **P0** 直接新增文件，不修改任何原有脚本 — 零风险上线
2. **P1** 在 Pipeline 引擎中插入质量门禁，不影响纯脚本调用路径
3. **P2** 逐步将旧模块迁移至 @tool 注册方式，旧函数保留兼容性封装
4. **P3** 纯新增功能，无破坏性变更

---

## 5. 附录：修改文件清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `modules/content_modules/__init__.py` | 包初始化 |
| `modules/content_modules/registry.py` | 模块注册表 |
| `modules/content_modules/base_module.py` | 模块基类 |
| `modules/content_modules/exam_analysis.py` | 📊 考情分析模块 |
| `modules/content_modules/background.py` | 📖 背景模块 |
| `modules/content_modules/principle.py` | 🔬 基础原理推导模块 |
| `modules/content_modules/formula.py` | 🧮 公式总结模块 |
| `modules/content_modules/case_analysis.py` | 🏗️ 案例分析模块 |
| `modules/content_modules/hard_problem.py` | 🎯 难题解析模块 |
| `modules/content_modules/key_points.py` | 🎯 考点精讲模块 |
| `modules/content_modules/textbook_changes.py` | ⚠️ 新教材变化模块 |
| `modules/content_modules/mnemonics.py` | 📌 记忆口诀模块 |
| `modules/content_modules/exercises.py` | ✅ 真题演练模块 |
| `modules/pipeline_engine.py` | Pipeline 引擎：YAML 读取 → 拓扑排序 → 步骤执行 |
| `modules/tool_registry.py` | `@tool` 装饰器 + 函数注册表 |
| `modules/base_tool.py` | 工具基类：定义 `execute()` 接口 |
| `modules/quality_gate.py` | 质量门禁：`Check` + `QualityGate.verify()` + 自动重试 |
| `pipelines/default.yaml` | 默认 Pipeline 声明式配置文件 |

### 修改文件

| 文件路径 | 修改重点 |
|----------|----------|
| `app.py` | 新增 Step 1.5 提示词工作台；扩展 Step1 知识库浏览器；新增模块选择 UI；注入自定义 CSS；顶部导航栏；卡片式选择器；进度仪表板；质量门禁状态展示 |
| `modules/pipeline_engine.py` | Pipeline 引擎中集成质量门禁 `QualityGate.verify()` + 自动重试 |
| `modules/prompt_manager.py` | `build_study_guide_prompt()` 增加 `enabled_modules` 参数；新增 `get_prompt_text()`、`save_prompt_template()` |
| `modules/ai_generator.py` | `generate_study_guide()` 和 `generate_study_guide_batch()` 透传 `enabled_modules` |
| `modules/config_manager.py` | 新增 `prompts_custom_dir` 路径 |
| `prompts/study_guide.j2` | 模板中改用 `{% for module %}` 动态渲染 |

---

> **总结**：本方案通过**可插拔模块化架构**解决了用户"动态控制 AI 输出方向"的核心需求，同时通过 **提示词工作台** 和 **知识库浏览器** 让用户对 AI 的"输入-处理-输出"全链路拥有完全的可见性和控制力。UI 层面通过 **专业化色彩体系**、**卡片式布局**、**步骤导航** 和 **微交互** 提升整体体验。
