/**
 * AI学习资料生成工作台 — 前端逻辑
 * ========================================
 * 处理所有 UI 交互、API 调用、SSE 流式响应。
 */

// ============================================================
// 全局状态
// ============================================================
const STATE = {
  selectedChapters: [],
  currentStreamSource: null,
  isRunning: false,
};

// ============================================================
// Toast 通知
// ============================================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateX(100%)'; setTimeout(() => toast.remove(), 300); }, 3500);
}

// ============================================================
// 状态指示器
// ============================================================
function setStatus(text, type = 'idle') {
  const dot = document.getElementById('statusDot');
  const label = document.getElementById('statusText');
  dot.className = 'status-dot ' + type;
  label.textContent = text;
}

// ============================================================
// 暗黑模式
// ============================================================
function toggleDarkMode() {
  const html = document.documentElement;
  const btn = document.getElementById('darkModeBtn');
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  btn.textContent = isDark ? '🌙' : '☀️';
  try { sessionStorage.setItem('theme', isDark ? 'light' : 'dark'); } catch(e) {}
}

function loadTheme() {
  try {
    const theme = sessionStorage.getItem('theme');
    if (theme) {
      document.documentElement.setAttribute('data-theme', theme);
      document.getElementById('darkModeBtn').textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  } catch(e) {}
}

// ============================================================
// 侧边栏
// ============================================================
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('open');
}

// ============================================================
// Tab 切换
// ============================================================
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

// ============================================================
// API 通用调用
// ============================================================
async function apiFetch(url, options = {}) {
  const config = {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  };
  try {
    const resp = await fetch(url, config);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      throw new Error(err.error || `请求失败: ${resp.status}`);
    }
    return resp;
  } catch (e) {
    if (e.name !== 'Error') throw e;
    showToast(e.message, 'error');
    throw e;
  }
}

async function apiJSON(url, options = {}) {
  const resp = await apiFetch(url, options);
  return resp.json();
}

// ============================================================
// 配置管理
// ============================================================
async function loadConfig() {
  try {
    const data = await apiJSON('/api/config');
    document.getElementById('runMode').value = data.run_mode || 'api';
    document.getElementById('apiKey').value = '';
    document.getElementById('baseUrl').value = data.base_url || '';
    document.getElementById('modelName').value = data.model || '';
    document.getElementById('maxTokens').value = data.max_tokens || 64000;
    document.getElementById('generationMode').value = data.generation_mode || '完整模式';
    document.getElementById('focusAreas').value = data.focus_areas || '全部章节';
    document.getElementById('detailLevel').value = data.detail_level || '标准';
    document.getElementById('includeMnemonics').checked = data.include_mnemonics !== false;
    document.getElementById('includeExercises').checked = data.include_exercises !== false;
    updateAPIConfigUI(data.is_api_ready);
    if (data.is_api_ready) {
      document.getElementById('apiKey').placeholder = '****已配置****';
    }
  } catch(e) { /* ignore */ }
}

async function updateConfig() {
  const payload = {
    run_mode: document.getElementById('runMode').value,
    generation_mode: document.getElementById('generationMode').value,
    focus_areas: document.getElementById('focusAreas').value,
    detail_level: document.getElementById('detailLevel').value,
    include_mnemonics: document.getElementById('includeMnemonics').checked,
    include_exercises: document.getElementById('includeExercises').checked,
  };

  const apiKey = document.getElementById('apiKey').value.trim();
  if (apiKey) payload.api_key = apiKey;
  const baseUrl = document.getElementById('baseUrl').value.trim();
  if (baseUrl) payload.base_url = baseUrl;
  const model = document.getElementById('modelName').value.trim();
  if (model) payload.model = model;
  const mt = parseInt(document.getElementById('maxTokens').value);
  if (!isNaN(mt)) payload.max_tokens = mt;

  try {
    const data = await apiJSON('/api/config', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (data.is_api_ready !== undefined) updateAPIConfigUI(data.is_api_ready);
  } catch(e) { /* ignore */ }
}

function updateAPIConfigUI(isReady) {
  const el = document.getElementById('apiStatus');
  if (isReady) {
    el.innerHTML = '<span class="badge badge-success">✅ API 已配置</span>';
  } else {
    el.innerHTML = '<span class="badge badge-error">⚠️ API Key 未配置</span>';
  }
}

async function saveAndVerifyConfig() {
  const btn = document.getElementById('verifyBtn');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = '⏳ 验证中...';

  // 先保存配置
  try {
    await updateConfig();
  } catch(e) {
    btn.disabled = false;
    btn.textContent = originalText;
    return;
  }

  // 再验证 API 连通性
  try {
    const data = await apiJSON('/api/config/verify', { method: 'POST' });
    if (data.success) {
      showToast('✅ API 验证成功！模型响应正常', 'success');
      updateAPIConfigUI(true);
    } else {
      showToast('❌ 验证失败: ' + (data.error || '未知错误'), 'error');
      updateAPIConfigUI(false);
    }
  } catch(e) {
    showToast('❌ API 连接失败: ' + e.message, 'error');
    updateAPIConfigUI(false);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

// ============================================================
// 章节管理
// ============================================================
async function loadChapters() {
  try {
    const data = await apiJSON('/api/chapters');
    const grid = document.getElementById('chapterGrid');
    const chapters = data.chapters || [];

    if (chapters.length === 0) {
      grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📂</div><div class="empty-state-text">output_md/ 目录为空，请上传 PDF</div></div>';
      return;
    }

    // Restore selection from server
    STATE.selectedChapters = STATE.selectedChapters.length > 0
      ? STATE.selectedChapters
      : chapters.slice(0, 5);

    grid.innerHTML = chapters.map(ch => `
      <div class="chapter-card ${STATE.selectedChapters.includes(ch) ? 'selected' : ''}"
           data-chapter="${ch}" onclick="toggleChapter('${ch}')">
        <div>${ch}</div>
        <div class="chapter-check">✅ 已选</div>
      </div>
    `).join('');

    updateChapterCount();
    await syncChapterSelection();
  } catch(e) {
    document.getElementById('chapterGrid').innerHTML =
      '<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">加载失败</div></div>';
  }
}

function toggleChapter(name) {
  const idx = STATE.selectedChapters.indexOf(name);
  if (idx >= 0) {
    STATE.selectedChapters.splice(idx, 1);
  } else {
    STATE.selectedChapters.push(name);
  }
  const card = document.querySelector(`.chapter-card[data-chapter="${name}"]`);
  if (card) card.classList.toggle('selected');
  updateChapterCount();
  syncChapterSelection();
}

function selectAllChapters() {
  document.querySelectorAll('.chapter-card').forEach(card => {
    const name = card.dataset.chapter;
    if (!STATE.selectedChapters.includes(name)) {
      STATE.selectedChapters.push(name);
    }
    card.classList.add('selected');
  });
  updateChapterCount();
  syncChapterSelection();
}

function deselectAllChapters() {
  STATE.selectedChapters = [];
  document.querySelectorAll('.chapter-card').forEach(c => c.classList.remove('selected'));
  updateChapterCount();
  syncChapterSelection();
}

function selectFirst5() {
  const chapters = document.querySelectorAll('.chapter-card');
  STATE.selectedChapters = [];
  chapters.forEach((c, i) => {
    if (i < 5) {
      STATE.selectedChapters.push(c.dataset.chapter);
      c.classList.add('selected');
    } else {
      c.classList.remove('selected');
    }
  });
  updateChapterCount();
  syncChapterSelection();
}

function invertSelection() {
  document.querySelectorAll('.chapter-card').forEach(card => {
    const name = card.dataset.chapter;
    const idx = STATE.selectedChapters.indexOf(name);
    if (idx >= 0) {
      STATE.selectedChapters.splice(idx, 1);
      card.classList.remove('selected');
    } else {
      STATE.selectedChapters.push(name);
      card.classList.add('selected');
    }
  });
  updateChapterCount();
  syncChapterSelection();
}

function updateChapterCount() {
  document.getElementById('selectedCount').textContent = `已选 ${STATE.selectedChapters.length} 个章节`;
}

async function syncChapterSelection() {
  try {
    await apiJSON('/api/chapters/select', {
      method: 'POST',
      body: JSON.stringify({ chapters: STATE.selectedChapters }),
    });
  } catch(e) { /* ignore */ }
}

// ============================================================
// 文件上传 & OCR
// ============================================================
async function uploadPDFs(files) {
  if (!files || files.length === 0) return;
  setStatus('上传中...', 'busy');
  const progressEl = document.getElementById('uploadProgress');
  progressEl.innerHTML = '';

  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    progressEl.innerHTML += `<div class="log-line info">📤 上传并转换: ${file.name}</div>`;
    try {
      const data = await apiFetch('/api/upload', {
        method: 'POST',
        body: formData,
        headers: {},
      });
      if (data.md_file) {
        progressEl.innerHTML += `<div class="log-line success">✅ 完成: ${file.name} → ${data.md_file}</div>`;
      } else if (data.ocr_error) {
        progressEl.innerHTML += `<div class="log-line warning">⚠️ 已上传，但 OCR 失败: ${data.ocr_error}</div>`;
      } else {
        progressEl.innerHTML += `<div class="log-line success">✅ 上传完成: ${file.name}</div>`;
      }
    } catch(e) {
      progressEl.innerHTML += `<div class="log-line error">❌ 上传失败: ${file.name}</div>`;
    }
  }

  progressEl.innerHTML += `<div class="log-line success" style="font-weight:600;margin-top:8px;">✅ 全部完成</div>`;
  showToast('上传 & OCR 完成', 'success');
  setStatus('就绪', 'idle');
  loadChapters();
}

async function batchOCR() {
  setStatus('批量 OCR 中...', 'busy');
  const outputEl = document.getElementById('streamOutput');
  outputEl.innerHTML = '';

  try {
    await consumeSSE('/api/ocr/batch', {}, (data) => {
      appendStreamOutput(data.text || '');
    });
    showToast('批量 OCR 完成', 'success');
    loadChapters();
  } catch(e) {
    showToast('批量 OCR 失败: ' + e.message, 'error');
  }
  setStatus('就绪', 'idle');
}

// ============================================================
// Word / Excel 上传转换
// ============================================================
async function uploadWords(files) {
  if (!files || files.length === 0) return;
  setStatus('上传中...', 'busy');
  const progressEl = document.getElementById('wordUploadProgress');
  progressEl.innerHTML = '';
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    progressEl.innerHTML += `<div class="log-line info">📤 上传转换: ${file.name}</div>`;
    try {
      const data = await apiFetch('/api/convert/word', {
        method: 'POST',
        body: formData,
        headers: {},
      });
      const json = JSON.parse(data);
      progressEl.innerHTML += `<div class="log-line success">✅ 转换完成: ${json.md_file}</div>`;
    } catch(e) {
      progressEl.innerHTML += `<div class="log-line error">❌ 转换失败: ${file.name}</div>`;
    }
  }
  progressEl.innerHTML += `<div class="log-line success" style="font-weight:600;margin-top:8px;">✅ 全部完成</div>`;
  showToast('Word 转换完成', 'success');
  setStatus('就绪', 'idle');
  loadChapters();
}

async function uploadExcels(files) {
  if (!files || files.length === 0) return;
  setStatus('上传中...', 'busy');
  const progressEl = document.getElementById('excelUploadProgress');
  progressEl.innerHTML = '';
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    progressEl.innerHTML += `<div class="log-line info">📤 上传转换: ${file.name}</div>`;
    try {
      const data = await apiFetch('/api/convert/excel', {
        method: 'POST',
        body: formData,
        headers: {},
      });
      const json = JSON.parse(data);
      progressEl.innerHTML += `<div class="log-line success">✅ 转换完成: ${json.md_file}</div>`;
    } catch(e) {
      progressEl.innerHTML += `<div class="log-line error">❌ 转换失败: ${file.name}</div>`;
    }
  }
  progressEl.innerHTML += `<div class="log-line success" style="font-weight:600;margin-top:8px;">✅ 全部完成</div>`;
  showToast('Excel 转换完成', 'success');
  setStatus('就绪', 'idle');
  loadChapters();
}

// ============================================================
// SSE 流式消费
// ============================================================
function consumeSSE(url, body, onData) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.responseType = 'text';

    let lastIndex = 0;

    xhr.onprogress = () => {
      const newText = xhr.responseText.substring(lastIndex);
      lastIndex = xhr.responseText.length;
      const lines = newText.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            if (onData) onData(data);
          } catch(e) { /* ignore parse errors */ }
        } else if (line.startsWith('event: done')) {
          // completion
        } else if (line.startsWith('event: error')) {
          // error handled below
        }
      }
    };

    xhr.onload = () => {
      // Process remaining data
      const remaining = xhr.responseText.substring(lastIndex);
      for (const line of remaining.split('\n')) {
        if (line.startsWith('event: error')) {
          reject(new Error('SSE 错误'));
          return;
        }
      }
      resolve();
    };

    xhr.onerror = () => reject(new Error('连接失败'));
    xhr.send(JSON.stringify(body));
  });
}

// 更健壮的 SSE 消费（使用 EventSource-like，但用 fetch + reader）
async function* streamSSE(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.substring(6));
        } catch(e) { /* skip */ }
      } else if (line.startsWith('event: done')) {
        return; // done
      } else if (line.startsWith('event: error')) {
        throw new Error('SSE 返回错误');
      }
    }
  }
}

// ============================================================
// 流式输出显示
// ============================================================
function appendStreamOutput(text) {
  const el = document.getElementById('streamOutput');
  // Remove placeholder
  if (el.querySelector('span') && el.children.length === 1 && el.querySelector('span').style.color) {
    el.innerHTML = '';
  }
  // Remove cursor if present
  const cursor = el.querySelector('.cursor');
  if (cursor) cursor.remove();

  // Append text
  el.insertAdjacentHTML('beforeend', text);

  // Add cursor back
  el.insertAdjacentHTML('beforeend', '<span class="cursor"></span>');
  el.scrollTop = el.scrollHeight;
}

function clearLogs() {
  document.getElementById('streamOutput').innerHTML = '<div class="log-line info" style="color:var(--text-muted);">等待操作...</div>';
}

function appendLogLine(text, type = 'info') {
  const el = document.getElementById('streamOutput');
  if (el.querySelector('span') && el.children.length === 1 && el.querySelector('span').style.color) {
    el.innerHTML = '';
  }
  // Remove cursor
  const cursor = el.querySelector('.cursor');
  if (cursor) cursor.remove();

  el.insertAdjacentHTML('beforeend', `<div class="log-line ${type}">${text}</div>`);

  // Add cursor back
  el.insertAdjacentHTML('beforeend', '<span class="cursor"></span>');
  el.scrollTop = el.scrollHeight;
}

async function refreshLogs() {
  try {
    const data = await apiJSON('/api/logs?n=10');
    if (data.logs && data.logs.length > 0) {
      const lastLog = data.logs[data.logs.length - 1];
      appendLogLine(lastLog, 'info');
    }
  } catch(e) { /* ignore */ }
}

// ============================================================
// 执行操作
// ============================================================

async function runLocalCleaning() {
  if (STATE.selectedChapters.length === 0) {
    showToast('请先选择章节', 'warning');
    return;
  }
  if (STATE.isRunning) { showToast('正在执行中，请等待', 'warning'); return; }

  STATE.isRunning = true;
  setStatus('本地清洗中...', 'busy');
  const outputEl = document.getElementById('streamOutput');
  outputEl.innerHTML = '';
  appendStreamOutput('🔄 开始本地清洗重组...\n');

  try {
    const data = await apiJSON('/api/process/local', {
      method: 'POST',
      body: JSON.stringify({ chapters: STATE.selectedChapters }),
    });
    appendStreamOutput(`✅ 本地清洗完成，共 ${data.length.toLocaleString()} 字符\n`);
    showToast('本地清洗完成', 'success');
    updatePipelineStep('local', true);
    refreshStats();
    setStatus('就绪', 'idle');
  } catch(e) {
    appendStreamOutput(`❌ 失败: ${e.message}\n`);
    showToast('本地清洗失败', 'error');
    setStatus('错误', 'error');
  }
  STATE.isRunning = false;
}

async function runAIGuide() {
  if (STATE.selectedChapters.length === 0) {
    showToast('请先选择章节', 'warning');
    return;
  }
  if (STATE.isRunning) { showToast('正在执行中，请等待', 'warning'); return; }

  const runMode = document.getElementById('runMode').value;
  if (runMode !== 'api') {
    showToast('请切换为 API 模式', 'warning');
    return;
  }

  STATE.isRunning = true;
  setStatus('AI 生成中...', 'busy');
  const outputEl = document.getElementById('streamOutput');
  outputEl.innerHTML = '';
  appendStreamOutput('🔄 开始 AI 学习资料生成...\n\n');

  try {
    let fullText = '';
    for await (const data of streamSSE('/api/process/ai-guide', {
      chapters: STATE.selectedChapters,
    })) {
      if (data.text) {
        fullText += data.text;
        // Show the last part in streaming
        outputEl.innerHTML = '';
        // Only show last 2000 chars for performance
        const display = fullText.length > 5000
          ? '...（内容较长，继续生成中）\n\n' + fullText.slice(-2000)
          : fullText;
        appendStreamOutput(display);

        if (data.text.includes('✅')) {
          // status messages
        }
      }
    }
    appendStreamOutput('\n\n✅ AI 学习资料生成完成！\n');
    showToast('AI 学习资料生成完成', 'success');
    updatePipelineStep('ai_guide', true);
    refreshStats();
    setStatus('就绪', 'idle');
  } catch(e) {
    appendStreamOutput(`\n❌ 失败: ${e.message}\n`);
    showToast('AI 生成失败: ' + e.message, 'error');
    setStatus('错误', 'error');
  }
  STATE.isRunning = false;
}

async function runAIMindmap() {
  if (STATE.selectedChapters.length === 0) {
    showToast('请先选择章节', 'warning');
    return;
  }
  if (STATE.isRunning) { showToast('正在执行中，请等待', 'warning'); return; }

  const runMode = document.getElementById('runMode').value;
  if (runMode !== 'api') {
    showToast('请切换为 API 模式', 'warning');
    return;
  }

  STATE.isRunning = true;
  setStatus('思维导图生成中...', 'busy');
  const outputEl = document.getElementById('streamOutput');
  outputEl.innerHTML = '';
  appendStreamOutput('🔄 开始 AI 思维导图生成...\n\n');

  try {
    let fullText = '';
    for await (const data of streamSSE('/api/process/ai-mindmap', {
      chapters: STATE.selectedChapters,
    })) {
      if (data.text) {
        fullText += data.text;
        outputEl.innerHTML = '';
        const display = fullText.length > 5000
          ? '...（内容较长，继续生成中）\n\n' + fullText.slice(-2000)
          : fullText;
        appendStreamOutput(display);
      }
    }
    appendStreamOutput('\n\n✅ 思维导图生成完成！\n');
    showToast('思维导图生成完成', 'success');
    updatePipelineStep('mindmap', true);
    refreshStats();
    setStatus('就绪', 'idle');
  } catch(e) {
    appendStreamOutput(`\n❌ 失败: ${e.message}\n`);
    showToast('思维导图生成失败', 'error');
    setStatus('错误', 'error');
  }
  STATE.isRunning = false;
}

async function runFullPipeline() {
  if (STATE.selectedChapters.length === 0) {
    showToast('请先选择章节', 'warning');
    return;
  }
  if (STATE.isRunning) { showToast('正在执行中，请等待', 'warning'); return; }

  const runMode = document.getElementById('runMode').value;
  if (runMode !== 'api') {
    showToast('请切换为 API 模式', 'warning');
    return;
  }

  STATE.isRunning = true;
  setStatus('全链路执行中...', 'busy');
  const outputEl = document.getElementById('streamOutput');
  outputEl.innerHTML = '';
  appendStreamOutput('🚀 开始全链路执行...\n\n');

  try {
    // Phase 1: POST to start background pipeline, get task_id
    const resp = await fetch('/api/process/pipeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chapters: STATE.selectedChapters }),
    });
    if (!resp.ok) throw new Error(`启动失败: HTTP ${resp.status}`);
    const { task_id } = await resp.json();
    appendStreamOutput(`📋 任务已创建 (${task_id.slice(0, 8)}...)\n\n`);

    // Phase 2: consume SSE stream via GET EventSource
    await new Promise((resolve, reject) => {
      const es = new EventSource(`/api/process/pipeline/stream/${task_id}`);

      es.addEventListener('status', (e) => {
        try {
          const text = JSON.parse(e.data);
          appendLogLine(text, text.includes('✅') ? 'success' : 'info');
          if (text.includes('Step 1')) updatePipelineStep('local', true);
          if (text.includes('Step 2')) updatePipelineStep('ai_guide', true);
          if (text.includes('Step 3')) updatePipelineStep('mindmap', true);
          if (text.includes('Step 4')) updatePipelineStep('docx', true);
          if (text.includes('Step 5')) updatePipelineStep('png', true);
          if (text.includes('全链路执行完成')) updatePipelineStep('png', true);
        } catch (_) { /* ignore parse errors */ }
      });

      es.addEventListener('error', () => {
        es.close();
        reject(new Error('任务执行出错'));
      });

      es.addEventListener('done', () => {
        es.close();
        resolve();
      });

      es.onerror = () => {
        es.close();
        reject(new Error('SSE 连接断开'));
      };
    });

    appendStreamOutput('\n🎉 全链路执行完成！\n');
    showToast('全链路执行完成！🎉', 'success');
    refreshStats();
    loadResults();
    setStatus('就绪', 'idle');
  } catch(e) {
    appendStreamOutput(`\n❌ 失败: ${e.message}\n`);
    showToast('全链路执行失败', 'error');
    setStatus('错误', 'error');
  }
  STATE.isRunning = false;
}

// ============================================================
// Pipeline 进度更新
// ============================================================
function updatePipelineStep(step, done) {
  const el = document.querySelector(`.pipeline-step[data-step="${step}"]`);
  if (!el) return;

  if (done) {
    el.classList.add('done');
    el.classList.remove('active');
    el.querySelector('.pipeline-status').textContent = '✅ 已完成';
  } else {
    el.classList.add('active');
    el.querySelector('.pipeline-status').textContent = '⏳ 进行中...';
  }

  // Update total progress
  const doneSteps = document.querySelectorAll('.pipeline-step.done').length;
  const total = document.querySelectorAll('.pipeline-step').length;
  document.getElementById('pipelineTotal').textContent = `${doneSteps}/${total} 阶段`;
  document.getElementById('pipelineProgress').style.width = `${(doneSteps / total) * 100}%`;

  if (doneSteps === total) {
    document.getElementById('pipelineTotal').textContent = '✅ 全部完成';
  }
}

function resetPipelineSteps() {
  document.querySelectorAll('.pipeline-step').forEach(el => {
    el.classList.remove('done', 'active');
    el.querySelector('.pipeline-status').textContent = '未执行';
  });
  document.getElementById('pipelineTotal').textContent = '0/5 阶段';
  document.getElementById('pipelineProgress').style.width = '0%';
}

// ============================================================
// 统计信息刷新
// ============================================================
async function refreshStats() {
  try {
    const data = await apiJSON('/api/content/comparison');
    document.getElementById('statLocalLen').textContent =
      data.local.length > 0 ? (data.local.length / 10000).toFixed(1) + '万' : '—';
    document.getElementById('statAiLen').textContent =
      data.ai.length > 0 ? (data.ai.length / 10000).toFixed(1) + '万' : '—';
    document.getElementById('statMindmapLen').textContent =
      data.mindmap.length > 0 ? (data.mindmap.length / 10000).toFixed(1) + '万' : '—';
  } catch(e) { /* ignore */ }
}

// ============================================================
// 结果加载
// ============================================================
async function loadResults() {
  try {
    const status = await apiJSON('/api/status');

    // Update pipeline steps from status
    if (status.has_local) updatePipelineStep('local', true);
    if (status.has_ai) updatePipelineStep('ai_guide', true);
    if (status.has_mindmap) updatePipelineStep('mindmap', true);
    if (status.has_docx) updatePipelineStep('docx', true);
    if (status.has_png) updatePipelineStep('png', true);

    // Load previews
    const guide = await apiJSON('/api/content/study-guide');
    const previewEl = document.getElementById('studyGuidePreview');
    if (guide.content) {
      previewEl.innerHTML = `<pre class="preview-content">${escapeHtml(guide.content.slice(0, 3000))}${guide.content.length > 3000 ? '\n\n...（截断）' : ''}</pre>`;
    }

    const mm = await apiJSON('/api/content/mindmap');
    const mmEl = document.getElementById('mindmapPreview');
    if (mm.content) {
      mmEl.innerHTML = `<pre class="preview-content">${escapeHtml(mm.content.slice(0, 3000))}${mm.content.length > 3000 ? '\n\n...（截断）' : ''}</pre>`;
    }

    // Status badges
    document.getElementById('docxStatus').textContent = status.has_docx ? '📝 Word: ✅ 已生成' : '📝 Word: 未生成';
    document.getElementById('docxStatus').className = status.has_docx ? 'badge badge-success' : 'badge';
    document.getElementById('pngStatus').textContent = status.has_png ? '🖼️ PNG: ✅ 已生成' : '🖼️ PNG: 未生成';
    document.getElementById('pngStatus').className = status.has_png ? 'badge badge-success' : 'badge';

    // Comparison
    const comparisonEl = document.getElementById('comparisonArea');
    if (guide.content || status.has_local) {
      comparisonEl.innerHTML = `
        <div class="comparison-grid">
          <div class="card">
            <div class="card-title">🤖 AI 生成</div>
            <div class="stat-value">${status.has_ai ? (guide.content ? guide.content.length.toLocaleString() : '—') : '—'}</div>
            <div class="stat-label">总字符</div>
          </div>
          <div class="card">
            <div class="card-title">🧹 本地重组</div>
            <div class="stat-value">${status.has_local ? document.getElementById('statLocalLen').textContent : '—'}</div>
            <div class="stat-label">总字符</div>
          </div>
        </div>
      `;
    }
  } catch(e) { /* ignore */ }
}

// ============================================================
// 下载
// ============================================================
function downloadMD() {
  window.open('/api/download/md', '_blank');
}

function downloadMindmapMD() {
  window.open('/api/download/mindmap-md', '_blank');
}

async function convertToDocx() {
  try {
    const data = await apiJSON('/api/convert/docx', { method: 'POST' });
    showToast('Word 文档已生成', 'success');
    updatePipelineStep('docx', true);
    document.getElementById('docxStatus').textContent = '📝 Word: ✅ 已生成';
    document.getElementById('docxStatus').className = 'badge badge-success';
  } catch(e) {
    showToast('Word 转换失败: ' + e.message, 'error');
  }
}

function downloadDocx() {
  window.open('/api/download/docx', '_blank');
}

function downloadPNG() {
  window.open('/api/download/png', '_blank');
}

// ============================================================
// 提示词工作台
// ============================================================
async function loadPromptList() {
  try {
    const data = await apiJSON('/api/prompts');
    const sel = document.getElementById('promptSelector');
    sel.innerHTML = data.prompts.map(p => `<option value="${p}">${p}</option>`).join('');
    if (data.prompts.length > 0) {
      loadPrompt();
    }
  } catch(e) { /* ignore */ }
}

async function loadPrompt() {
  const name = document.getElementById('promptSelector').value;
  if (!name) return;
  try {
    const data = await apiJSON(`/api/prompts/${encodeURIComponent(name)}`);
    document.getElementById('promptEditor').value = data.content || '';
  } catch(e) { showToast('加载提示词失败', 'error'); }
}

async function savePrompt() {
  const name = document.getElementById('promptSelector').value;
  const content = document.getElementById('promptEditor').value;
  if (!name) return;
  try {
    await apiJSON(`/api/prompts/${encodeURIComponent(name)}`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
    showToast('提示词已保存', 'success');
  } catch(e) { showToast('保存失败', 'error'); }
}

async function resetPrompt() {
  const name = document.getElementById('promptSelector').value;
  if (!name) return;
  try {
    await apiJSON(`/api/prompts/${encodeURIComponent(name)}/reset`, { method: 'POST' });
    showToast('提示词已重置', 'success');
    loadPrompt();
  } catch(e) { showToast('重置失败', 'error'); }
}

let _aiSuggestion = null;

async function aiEditPrompt() {
  const currentContent = document.getElementById('promptEditor').value;
  const modification = document.getElementById('promptModRequest').value.trim();
  if (!modification) {
    showToast('请输入修改要求', 'warning');
    return;
  }

  try {
    const data = await apiJSON('/api/prompts/ai-edit', {
      method: 'POST',
      body: JSON.stringify({ current_content: currentContent, modification }),
    });
    _aiSuggestion = data.suggestion;
    document.getElementById('aiSuggestionBefore').textContent = currentContent.slice(0, 3000);
    document.getElementById('aiSuggestionAfter').textContent = data.suggestion.slice(0, 3000);
    document.getElementById('aiSuggestionArea').style.display = 'block';
    showToast('AI 修改建议已生成', 'success');
  } catch(e) {
    showToast('AI 修改失败: ' + e.message, 'error');
  }
}

async function applyAISuggestion() {
  if (!_aiSuggestion) return;
  document.getElementById('promptEditor').value = _aiSuggestion;
  await savePrompt();
  document.getElementById('aiSuggestionArea').style.display = 'none';
  _aiSuggestion = null;
  showToast('AI 建议已应用', 'success');
}

function dismissAISuggestion() {
  document.getElementById('aiSuggestionArea').style.display = 'none';
  _aiSuggestion = null;
}


// ============================================================
// 基于全部知识库生成模板
// ============================================================

async function generatePromptFromKB() {
  const btn = document.getElementById('genFromKBBtn');
  const status = document.getElementById('genFromKBStatus');
  const targetName = document.getElementById('promptSelector').value || 'study_guide.j2';

  btn.disabled = true;
  btn.textContent = '⏳ 生成中...';
  status.textContent = '正在扫描知识库并调用 AI 生成，请稍候...';
  status.className = 'text-muted';

  try {
    const data = await apiJSON('/api/prompts/generate-from-kb', {
      method: 'POST',
      body: JSON.stringify({ target_name: targetName }),
    });

    if (data.success) {
      status.innerHTML = `✅ 基于 ${data.file_count} 个知识库文件生成完成，已保存为 <strong>${data.name}</strong>`;
      status.className = 'text-success';

      // 刷新并选中目标模板
      await loadPromptList();
      document.getElementById('promptSelector').value = data.name;
      await loadPrompt();

      // 显示预览
      document.getElementById('genFromKBPreview').textContent = data.preview || data.content.slice(0, 2000);
      document.getElementById('genFromKBPreviewArea').style.display = 'block';
      showToast(`✅ 模板已基于 ${data.file_count} 个素材文件生成`, 'success');
    } else {
      status.textContent = '❌ 生成失败: ' + (data.error || '未知错误');
      status.className = 'text-error';
    }
  } catch(e) {
    status.textContent = '❌ 生成失败: ' + e.message;
    status.className = 'text-error';
  } finally {
    btn.disabled = false;
    btn.textContent = '📚 AI 基于全部知识库生成模板';
  }
}


// ============================================================
// 知识库浏览器
// ============================================================
async function loadKBFileList() {
  try {
    const data = await apiJSON('/api/files');
    const sel = document.getElementById('kbFileSelector');
    sel.innerHTML = data.files.map(f => `<option value="${f.name}">${f.name} (${f.size_kb}KB)</option>`).join('');
    if (data.files.length > 0) loadKBFile();
  } catch(e) { /* ignore */ }
}

async function loadKBFile() {
  const sel = document.getElementById('kbFileSelector');
  const name = sel.value;
  if (!name) return;
  try {
    const data = await apiJSON(`/api/files/${encodeURIComponent(name)}`);
    document.getElementById('kbEditor').value = data.content || '';
    document.getElementById('kbFileInfo').textContent = `${data.name} · ${(data.content || '').length.toLocaleString()} 字符`;
  } catch(e) { showToast('加载文件失败', 'error'); }
}

async function saveKBFile() {
  const sel = document.getElementById('kbFileSelector');
  const name = sel.value;
  const content = document.getElementById('kbEditor').value;
  if (!name) return;
  try {
    await apiJSON(`/api/files/${encodeURIComponent(name)}`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
    showToast('文件已保存', 'success');
  } catch(e) { showToast('保存失败', 'error'); }
}

async function deleteKBFile() {
  const sel = document.getElementById('kbFileSelector');
  const name = sel.value;
  if (!name) return;
  if (!confirm(`确认删除 ${name}？`)) return;
  try {
    await apiFetch(`/api/files/${encodeURIComponent(name)}`, { method: 'DELETE' });
    showToast('文件已删除', 'success');
    loadKBFileList();
  } catch(e) { showToast('删除失败', 'error'); }
}

// ============================================================
// 工具函数
// ============================================================
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ============================================================
// 定期刷新状态
// ============================================================
async function pollStatus() {
  try {
    const status = await apiJSON('/api/status');
    // Update pipeline checkboxes
    if (status.has_local) updatePipelineStep('local', true);
    if (status.has_ai) updatePipelineStep('ai_guide', true);
    if (status.has_mindmap) updatePipelineStep('mindmap', true);
    if (status.has_docx) updatePipelineStep('docx', true);
    if (status.has_png) updatePipelineStep('png', true);

    // Update results tab if we have content
    const guideEl = document.getElementById('studyGuidePreview');
    if (status.has_ai || status.has_local) {
      const guide = await apiJSON('/api/content/study-guide');
      if (guide.content && !guideEl.querySelector('pre')) {
        guideEl.innerHTML = `<pre class="preview-content">${escapeHtml(guide.content.slice(0, 3000))}${guide.content.length > 3000 ? '\n\n...（截断）' : ''}</pre>`;
      }
    }
  } catch(e) { /* ignore */ }
}

// ============================================================
// 初始化
// ============================================================
async function init() {
  loadTheme();
  await loadConfig();
  await loadChapters();
  await loadPromptList();
  await loadKBFileList();
  await refreshStats();
  await loadResults();
  setStatus('就绪', 'idle');

  // Poll for status updates every 10 seconds
  setInterval(pollStatus, 10000);
}

document.addEventListener('DOMContentLoaded', init);
