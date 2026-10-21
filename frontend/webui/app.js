// AUTO-MAS 前后端分离 Web 控制台前端逻辑 (frontend/webui/app.js)

const state = {
  scriptsIndex: [],
  scriptsData: {},
  queuesIndex: [],
  queuesData: {},
  queueSchedules: {},
  runtimeTasks: [],
  scheduleEditor: null,
  schedulePending: false,
  scheduleDraft: '',
  queueDraft: '',
  queueSavePending: false,
  queueCreatePending: false,
  queueDeletePending: new Set(),
  currentEditScriptId: null,
  currentEditQueueId: null,
  childSessionStatus: null,
  globalSettings: null,
  ws: null,
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function showToast(msg) {
  const el = document.getElementById('toast-box');
  if (!el) return;
  el.textContent = msg;
  el.style.display = 'block';
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    el.style.display = 'none';
  }, 3200);
}

function appendTerminalLog(line) {
  const term = document.getElementById('scheduler-log-terminal');
  if (!term) return;
  const ts = new Date().toLocaleTimeString();
  term.textContent += `\n[${ts}] ${line}`;
  term.scrollTop = term.scrollHeight;
}

function clearTerminalLogs() {
  const term = document.getElementById('scheduler-log-terminal');
  if (term) term.textContent = '[系统] 日志已清空。';
}

async function apiCall(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  };
  if (body !== null && method !== 'GET') {
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  return await resp.json();
}

function switchTab(tabName) {
  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-pane').forEach((pane) => {
    pane.style.display = pane.id === `tab-${tabName}` ? 'block' : 'none';
  });
  if (tabName === 'scripts') loadScripts();
  if (tabName === 'queues') loadQueues();
  if (tabName === 'child-session') loadChildSessionStatus();
  if (tabName === 'scheduler') loadRuntimeSnapshot();
  if (tabName === 'history') loadHistory();
  if (tabName === 'settings') loadGlobalSettings();
}

function toggleTheme() {
  document.body.classList.toggle('dark-theme');
  const isDark = document.body.classList.contains('dark-theme');
  const btn = document.getElementById('btn-theme');
  if (btn) btn.textContent = isDark ? '☀ 亮色' : '🌙 暗色';
  localStorage.setItem('automas_theme', isDark ? 'dark' : 'light');
}

// ==================== 1. 健康检查与远程桌面状态 ====================

async function loadHealthAndSummary() {
  try {
    const health = await apiCall('/api/core/health', 'GET');
    const dot = document.getElementById('dot-backend');
    const txt = document.getElementById('txt-backend');
    if (health?.ready && health.backgroundStatus === 'ready') {
      dot.className = 'dot green';
      txt.textContent = '后端已就绪';
    } else {
      dot.className = 'dot yellow';
      txt.textContent = `后端: ${health?.backgroundStatus || '启动中'}`;
    }
  } catch (_) {
    document.getElementById('dot-backend').className = 'dot gray';
    document.getElementById('txt-backend').textContent = '后端未连接';
  }
}

async function loadChildSessionStatus() {
  try {
    const res = await apiCall('/api/child-session/status', 'GET');
    if (res.code !== 200 || !res.data) throw new Error(res.message || '远程桌面状态查询失败');
    const d = res.data;
    state.childSessionStatus = d;
    const hostStatus = d.hostStatus || {};
    const leases = d.activeLeases || [];
    const connected = Boolean(d.hostConnected);
    const hostReady = Boolean(d.hostStatus?.ok);
    const trayMode = hostReady && hostStatus.trayMode === true;
    const watchMode = hostStatus.watchMode !== false;

    const rdpDot = document.getElementById('dot-rdp');
    const rdpTxt = document.getElementById('txt-rdp');
    if (!d.enabled) {
      rdpDot.className = 'dot gray';
      rdpTxt.textContent = '远程桌面: 未启用';
    } else if (leases.length > 0) {
      rdpDot.className = 'dot yellow';
      rdpTxt.textContent = `远程桌面: 已让渡 (${leases[0].caller})`;
    } else if (connected) {
      rdpDot.className = 'dot green';
      rdpTxt.textContent = `远程桌面: #${d.childSessionId ?? '已连接'} (${trayMode ? '托盘静默' : '窗口显示'})`;
    } else {
      rdpDot.className = 'dot yellow';
      rdpTxt.textContent = hostReady ? '远程桌面: 未连接' : '远程桌面: 宿主未就绪';
    }

    document.getElementById('home-rdp-state').textContent = connected
      ? `Session #${d.childSessionId ?? '活跃'}`
      : (!d.enabled ? '已禁用' : (hostReady ? '未连接' : '宿主未就绪'));
    document.getElementById('home-rdp-sub').textContent = !hostReady
      ? '宿主没有响应，请在 BGI 远程桌面页面检查启动状态'
      : trayMode
      ? '默认最小化在系统托盘运行，不干扰主桌面'
      : '当前窗口已在主桌面显示';

    document.getElementById('home-lease-state').textContent =
      leases.length > 0 ? `${leases.length} 个外部借用` : '空闲';
    document.getElementById('home-lease-sub').textContent =
      leases.length > 0
        ? `当前正由 ${leases.map((l) => l.caller).join(', ')} 借用`
        : '相邻子任务间隔自动检查外部请求并让渡';

    // BGI 卡片同步
    const bgiDot = document.getElementById('bgi-card-dot');
    if (bgiDot) {
      bgiDot.className = leases.length > 0 ? 'dot yellow' : (connected ? 'dot green' : 'dot gray');
    }
    const csSid = document.getElementById('cs-session-id');
    if (csSid) {
      csSid.textContent = connected ? `Session #${d.childSessionId} (已连接)` : (hostReady ? '未连接' : '宿主未就绪');
    }
    const csTray = document.getElementById('cs-tray-state');
    if (csTray) {
      csTray.textContent = !hostReady ? '宿主未就绪，无法确认托盘状态' : trayMode ? '系统托盘静默运行（不占任务栏）' : '桌面窗口显示中';
    }
    const csWatch = document.getElementById('cs-watch-state');
    if (csWatch) {
      csWatch.textContent = watchMode ? '观看模式（已屏蔽本机键鼠）' : '普通鼠标模式（可交互）';
    }
    const watchBtn = document.getElementById('bgi-btn-watch');
    if (watchBtn) {
      watchBtn.classList.toggle('active', watchMode);
      watchBtn.textContent = watchMode ? '👁 观看模式' : '🖱 普通鼠标';
    }
    const csSub = document.getElementById('cs-subtask-state');
    if (csSub) {
      csSub.textContent = d.inSubtaskExecution ? '正在执行子任务（间隔处让渡）' : '空闲（可立即让渡外部程序）';
    }

    // 租约表
    const tbody = document.getElementById('leases-table-body');
    if (tbody) {
      if (leases.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">当前无外部程序借用租约，队列可正常连续执行</td></tr>';
      } else {
        tbody.innerHTML = leases
          .map(
            (l) => `<tr>
              <td><code>${l.leaseId.slice(0, 8)}...</code></td>
              <td><strong>${l.caller}</strong></td>
              <td><span class="tag ${l.status === 'granted' ? 'green' : 'amber'}">${l.status}</span></td>
              <td>${l.requestedAt || '-'}</td>
              <td><button class="btn btn-sm" onclick="releaseExternalLease('${l.leaseId}')">回传释放</button></td>
            </tr>`
          )
          .join('');
      }
    }
  } catch (err) {
    console.warn('loadChildSessionStatus error:', err);
    state.childSessionStatus = null;
    document.getElementById('dot-rdp').className = 'dot gray';
    document.getElementById('txt-rdp').textContent = '远程桌面: 状态获取失败';
    document.getElementById('home-rdp-state').textContent = '状态获取失败';
    document.getElementById('home-rdp-sub').textContent = '请检查后端连接后重试';
  }
}

async function openRdpWindow(visible) {
  const res = await apiCall('/api/child-session/window', 'POST', { visible });
  showToast(visible ? '已呼出 BetterGI 桌面分身窗口' : '已将桌面分身隐藏回系统托盘');
  await loadChildSessionStatus();
  return res;
}

async function toggleRdpWatchMode() {
  const cur = state.childSessionStatus?.hostStatus?.watchMode !== false;
  await apiCall('/api/child-session/window', 'POST', { watchMode: !cur });
  showToast(!cur ? '已开启观看模式（屏蔽本机键鼠输入）' : '已切换为普通鼠标模式');
  await loadChildSessionStatus();
}

async function sendRdpShortcut(shortcut) {
  await apiCall('/api/child-session/window', 'POST', { shortcut });
  showToast(`已向桌面分身发送快捷键: ${shortcut}`);
}

async function connectRdpSession() {
  showToast('正在请求建立/恢复本地远程桌面连接...');
  await apiCall('/api/child-session/connect', 'POST', {});
  await loadChildSessionStatus();
}

async function logoffRdpSession() {
  if (!confirm('确定要断开并注销本地远程桌面会话吗？')) return;
  await apiCall('/api/child-session/logoff', 'POST', {});
  showToast('已注销本地远程桌面会话');
  await loadChildSessionStatus();
}

async function acquireExternalLease() {
  const caller = document.getElementById('lease-caller-input')?.value || 'ExternalClient';
  const res = await apiCall('/api/child-session/acquire', 'POST', {
    caller,
    disconnectRdpView: true,
    waitForGrant: false,
  });
  showToast(`已为 [${caller}] 申请借用远程桌面 (状态: ${res.leaseStatus || 'granted'})`);
  appendTerminalLog(`[远程桌面让渡] 外部程序 ${caller} 申请借用远程桌面 -> leaseId=${res.leaseId}`);
  await loadChildSessionStatus();
}

async function releaseExternalLease(leaseId = null) {
  const caller = leaseId ? null : (document.getElementById('lease-caller-input')?.value || null);
  const res = await apiCall('/api/child-session/release', 'POST', { leaseId, caller });
  showToast(`已收到外部程序停止使用回传，释放租约 ${res.releasedLeaseIds?.length || 0} 个`);
  appendTerminalLog(`[远程桌面回传] 外部程序已释放远程桌面，队列恢复执行`);
  await loadChildSessionStatus();
}

// ==================== 2. 脚本与多用户管理 ====================

async function loadScripts() {
  try {
    const res = await apiCall('/api/scripts/get', 'POST', {});
    state.scriptsIndex = res.index || [];
    state.scriptsData = res.data || {};
    renderScriptsTable();
    refreshDispatchSelector();
  } catch (err) {
    console.error('loadScripts error:', err);
  }
}

function renderScriptsTable() {
  const tbody = document.getElementById('scripts-table-body');
  if (!tbody) return;
  if (state.scriptsIndex.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted)">暂无脚本配置，点击右上角「新建脚本配置」即可添加</td></tr>';
    return;
  }

  tbody.innerHTML = state.scriptsIndex
    .map((item) => {
      const cfg = state.scriptsData[item.uid] || {};
      const name = cfg.Info?.Name || '未命名脚本';
      const exePath = cfg.Script?.ScriptPath || cfg.Info?.RootPath || '';
      const args = cfg.Script?.Arguments ? ` ${cfg.Script.Arguments}` : '';
      const logPath = cfg.Script?.LogPath || '';
      const isNoLog = !logPath || logPath === '.';
      const hardLimit = cfg.Run?.HardTimeLimit ?? 120;
      const runLimit = cfg.Run?.RunTimeLimit ?? 10;
      const retries = cfg.Run?.RunTimesLimit ?? 3;

      return `<tr>
        <td><strong>${name}</strong></td>
        <td><span class="tag">${item.type}</span></td>
        <td><code>${item.uid.slice(0, 8)}...</code></td>
        <td><code>${exePath}${args}</code></td>
        <td>
          总上限 <strong>${hardLimit}m</strong> /
          ${isNoLog ? '<span class="tag green">无日志模式(退出即成功)</span>' : `日志超时 ${runLimit}m`} /
          重试 ${retries} 次
        </td>
        <td>
          <div class="btn-group">
            <button class="btn btn-sm btn-primary" onclick="openScriptEditor('${item.uid}')">编辑 & 用户</button>
            <button class="btn btn-sm" onclick="startTaskById('${item.uid}')">▶ 运行</button>
            <button class="btn btn-sm btn-danger" onclick="deleteScript('${item.uid}')">删除</button>
          </div>
        </td>
      </tr>`;
    })
    .join('');

  document.getElementById('home-script-queue-count').textContent =
    `${state.scriptsIndex.length} / ${state.queuesIndex.length}`;
}

async function createNewScript() {
  const type = document.getElementById('new-script-type')?.value || 'General';
  const res = await apiCall('/api/scripts/add', 'POST', { type });
  if (res.code === 200 && res.scriptId) {
    showToast(`已创建 ${type} 脚本配置`);
    await loadScripts();
    openScriptEditor(res.scriptId);
  } else {
    showToast(`创建失败: ${res.message || '未知错误'}`);
  }
}

async function openScriptEditor(scriptId) {
  state.currentEditScriptId = scriptId;
  const cfg = state.scriptsData[scriptId];
  if (!cfg) return;

  document.getElementById('script-editor-card').style.display = 'block';
  document.getElementById('edit-script-title').textContent = `${cfg.Info?.Name || '未命名'} (${scriptId.slice(0, 8)})`;
  document.getElementById('ed-script-name').value = cfg.Info?.Name || '';
  document.getElementById('ed-root-path').value = cfg.Info?.RootPath || '';
  document.getElementById('ed-script-path').value = cfg.Script?.ScriptPath || '';
  document.getElementById('ed-script-args').value = cfg.Script?.Arguments || '';
  document.getElementById('ed-hard-limit').value = cfg.Run?.HardTimeLimit ?? 120;
  document.getElementById('ed-retry-limit').value = cfg.Run?.RunTimesLimit ?? 3;
  document.getElementById('ed-log-timeout').value = cfg.Run?.RunTimeLimit ?? 10;
  const lp = cfg.Script?.LogPath || '';
  document.getElementById('ed-log-path').value = lp === '.' ? '' : lp;
  document.getElementById('ed-success-log').value = cfg.Script?.SuccessLog || '';
  document.getElementById('ed-error-log').value = cfg.Script?.ErrorLog || '';

  await loadScriptUsers(scriptId);
}

function closeScriptEditor() {
  state.currentEditScriptId = null;
  document.getElementById('script-editor-card').style.display = 'none';
}

async function saveCurrentScript() {
  const scriptId = state.currentEditScriptId;
  if (!scriptId) return;

  const logPathVal = document.getElementById('ed-log-path').value.trim();
  const payload = {
    scriptId,
    data: {
      Info: {
        Name: document.getElementById('ed-script-name').value.trim() || '未命名脚本',
        RootPath: document.getElementById('ed-root-path').value.trim(),
      },
      Script: {
        ScriptPath: document.getElementById('ed-script-path').value.trim(),
        Arguments: document.getElementById('ed-script-args').value.trim(),
        LogPath: logPathVal,
        SuccessLog: document.getElementById('ed-success-log').value.trim(),
        ErrorLog: document.getElementById('ed-error-log').value.trim(),
      },
      Run: {
        HardTimeLimit: Number(document.getElementById('ed-hard-limit').value) || 120,
        RunTimesLimit: Number(document.getElementById('ed-retry-limit').value) || 3,
        RunTimeLimit: Number(document.getElementById('ed-log-timeout').value) || 10,
      },
    },
  };

  const res = await apiCall('/api/scripts/update', 'POST', payload);
  if (res.code === 200) {
    showToast('脚本配置已保存');
    await loadScripts();
  } else {
    showToast(`保存失败: ${res.message}`);
  }
}

async function deleteScript(scriptId) {
  if (!confirm('确定要删除该脚本配置吗？')) return;
  await apiCall('/api/scripts/delete', 'POST', { scriptId });
  if (state.currentEditScriptId === scriptId) closeScriptEditor();
  showToast('脚本已删除');
  await loadScripts();
}

async function loadScriptUsers(scriptId) {
  const res = await apiCall('/api/scripts/user/get', 'POST', { scriptId });
  const tbody = document.getElementById('script-users-tbody');
  if (!tbody) return;
  const index = res.index || [];
  const data = res.data || {};
  if (index.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">当前脚本暂无用户子配置，点击右上角「添加用户账号」即可创建</td></tr>';
    return;
  }
  tbody.innerHTML = index
    .map((u) => {
      const ucfg = data[u.uid] || {};
      const uname = ucfg.Info?.Name || '默认用户';
      const ustatus = ucfg.Info?.Status !== false;
      const uarg = ucfg.Info?.Argument || '';
      const unotes = ucfg.Info?.Notes || '';
      return `<tr>
        <td><input class="input" style="width:140px" value="${uname}" onchange="updateScriptUserField('${scriptId}','${u.uid}','Name',this.value)" /></td>
        <td>
          <select class="select" onchange="updateScriptUserField('${scriptId}','${u.uid}','Status',this.value==='true')">
            <option value="true" ${ustatus ? 'selected' : ''}>启用</option>
            <option value="false" ${!ustatus ? 'selected' : ''}>跳过</option>
          </select>
        </td>
        <td><input class="input" style="width:220px" placeholder="例如：--user acc1" value="${uarg}" onchange="updateScriptUserField('${scriptId}','${u.uid}','Argument',this.value)" /></td>
        <td><input class="input" style="width:160px" value="${unotes}" onchange="updateScriptUserField('${scriptId}','${u.uid}','Notes',this.value)" /></td>
        <td><button class="btn btn-sm btn-danger" onclick="deleteScriptUser('${scriptId}','${u.uid}')">删除</button></td>
      </tr>`;
    })
    .join('');
}

async function addUserToCurrentScript() {
  if (!state.currentEditScriptId) return;
  await apiCall('/api/scripts/user/add', 'POST', { scriptId: state.currentEditScriptId });
  showToast('已添加新用户账号');
  await loadScriptUsers(state.currentEditScriptId);
}

async function updateScriptUserField(scriptId, userId, key, val) {
  await apiCall('/api/scripts/user/update', 'POST', {
    scriptId,
    userId,
    data: { Info: { [key]: val } },
  });
  showToast('用户配置已自动保存');
}

async function deleteScriptUser(scriptId, userId) {
  await apiCall('/api/scripts/user/delete', 'POST', { scriptId, userId });
  await loadScriptUsers(scriptId);
}

// ==================== 3. 调度队列管理 ====================

async function loadQueues() {
  try {
    const res = await apiCall('/api/queue/get', 'POST', {});
    if (res.code !== 200) throw new Error(res.message || '队列加载失败');
    state.queuesIndex = res.index || [];
    state.queuesData = res.data || {};
    const schedules = await Promise.all(state.queuesIndex.map(async (queue) => {
      try {
        const result = await apiCall('/api/queue/time/get', 'POST', { queueId: queue.uid });
        if (result.code !== 200) throw new Error(result.message || '定时加载失败');
        return [queue.uid, result];
      } catch (error) {
        return [queue.uid, { error: error.message || '定时加载失败' }];
      }
    }));
    state.queueSchedules = Object.fromEntries(schedules);
    renderQueuesTable();
    renderQueueSchedules();
    renderRuntimeTasks(state.runtimeTasks);
    refreshDispatchSelector();
  } catch (err) {
    document.getElementById('queues-table-body').innerHTML =
      `<tr><td colspan="6">加载失败：${escapeHtml(err.message)}，请点击刷新队列重试。</td></tr>`;
    document.getElementById('queue-times-table-body').innerHTML =
      '<tr><td colspan="5">暂时无法查询定时，请刷新重试。</td></tr>';
  }
}

const scheduleDays = [
  ['Monday', '周一'], ['Tuesday', '周二'], ['Wednesday', '周三'],
  ['Thursday', '周四'], ['Friday', '周五'], ['Saturday', '周六'], ['Sunday', '周日'],
];

function formatScheduleDays(days = []) {
  const selected = scheduleDays.filter(([day]) => days.includes(day));
  return selected.length === 7 ? '每天' : selected.map(([, label]) => label).join('、') || '未设置运行日期';
}

function renderQueueSchedules() {
  const rows = state.queuesIndex.flatMap((queue) => {
    const cfg = state.queuesData[queue.uid] || {};
    const name = escapeHtml(cfg.Info?.Name || '调度队列');
    const schedule = state.queueSchedules[queue.uid];
    if (schedule?.error) return [`<tr><td>${name}</td><td colspan="4">${escapeHtml(schedule.error)}，请刷新重试</td></tr>`];
    return (schedule?.index || []).map((item) => {
      const info = schedule.data[item.uid]?.Info || {};
      const enabled = cfg.Info?.TimeEnabled && !cfg.Info?.CycleEnabled && info.Enabled && info.Days?.length;
      const status = cfg.Info?.CycleEnabled ? '循环队列不使用定时' : !cfg.Info?.TimeEnabled
        ? '队列定时已关闭' : !info.Enabled ? '定时已禁用' : !info.Days?.length ? '未设置运行日期' : '已启用';
      return `<tr><td>${name}</td><td>${escapeHtml(info.Time || '未设置')}</td>
        <td>${formatScheduleDays(info.Days)}</td><td><span class="tag ${enabled ? 'green' : ''}">${status}</span></td>
        <td><div class="btn-group"><button class="btn btn-sm" ${state.schedulePending ? 'disabled' : ''} onclick="openScheduleEditor('${queue.uid}','${item.uid}')">修改</button>
        <button class="btn btn-sm" ${state.schedulePending ? 'disabled' : ''} onclick="toggleSchedule('${queue.uid}','${item.uid}')">${info.Enabled ? '禁用' : '启用'}</button>
        <button class="btn btn-sm btn-danger" ${state.schedulePending ? 'disabled' : ''} onclick="deleteSchedule('${queue.uid}','${item.uid}')">删除定时</button></div></td></tr>`;
    });
  });
  document.getElementById('queue-times-table-body').innerHTML = rows.join('') ||
    '<tr><td colspan="5">暂无定时计划，点击「新增定时」添加。</td></tr>';
}

async function queueRequest(path, body) {
  const result = await apiCall(path, 'POST', body);
  if (result.code !== 200) throw new Error(result.message || '操作失败，请重试');
  return result;
}

function confirmQueueChange(message) {
  const dialog = document.getElementById('queue-confirm-dialog');
  if (dialog.open) return Promise.resolve(false);
  document.getElementById('queue-confirm-message').textContent = message;
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true });
    dialog.returnValue = 'cancel';
    dialog.showModal();
  });
}

function readScheduleDraft() {
  return {
    queueId: document.getElementById('schedule-queue').value,
    Info: {
      Enabled: document.getElementById('schedule-enabled').value === 'true',
      Time: document.getElementById('schedule-time').value,
      Days: Array.from(document.querySelectorAll('#schedule-days-options input:checked'), (input) => input.value),
    },
  };
}

async function closeScheduleEditor() {
  if (state.schedulePending) return false;
  if (state.scheduleEditor && state.scheduleDraft !== JSON.stringify(readScheduleDraft()) &&
    !await confirmQueueChange('有尚未保存的定时修改，确定放弃吗？')) return false;
  state.scheduleEditor = null;
  document.getElementById('schedule-editor-card').style.display = 'none';
  return true;
}

async function openScheduleEditor(queueId = '', timeSetId = '') {
  if (!await closeScheduleEditor()) return;
  if (!state.queuesIndex.length) { showToast('请先新建调度队列，再添加定时'); return; }
  const info = state.queueSchedules[queueId]?.data?.[timeSetId]?.Info;
  if (timeSetId && !info) { showToast('定时数据已变化，请刷新列表后重试'); return; }
  state.scheduleEditor = { queueId, timeSetId };
  document.getElementById('schedule-editor-title').textContent = timeSetId ? '修改定时' : '新增定时';
  document.getElementById('schedule-queue').innerHTML = state.queuesIndex.map((queue) =>
    `<option value="${queue.uid}">${escapeHtml(state.queuesData[queue.uid]?.Info?.Name || queue.uid)}</option>`).join('');
  document.getElementById('schedule-queue').value = queueId || state.queuesIndex[0].uid;
  document.getElementById('schedule-time').value = info?.Time || '06:10';
  document.getElementById('schedule-enabled').value = String(info?.Enabled ?? true);
  const days = info?.Days || scheduleDays.map(([day]) => day);
  document.getElementById('schedule-days-options').innerHTML = scheduleDays.map(([day, label]) =>
    `<label><input type="checkbox" value="${day}" ${days.includes(day) ? 'checked' : ''} /> ${label}</label>`).join('');
  document.getElementById('schedule-editor-error').textContent = '';
  document.getElementById('schedule-editor-card').style.display = 'block';
  updateScheduleQueueHint();
  state.scheduleDraft = JSON.stringify(readScheduleDraft());
  document.getElementById('schedule-editor-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function updateScheduleQueueHint() {
  const info = state.queuesData[document.getElementById('schedule-queue').value]?.Info;
  document.getElementById('schedule-queue-hint').textContent = info?.CycleEnabled
    ? '该队列是循环队列，定时启动不会生效。请改选普通队列。'
    : !info?.TimeEnabled ? '该队列的定时总开关已关闭。保存后请在「编辑队列」中启用。'
      : '按本机时间触发；修改所属队列会将此定时移到目标队列。';
}

async function saveSchedule(event) {
  event.preventDefault();
  if (state.schedulePending || !state.scheduleEditor) return;
  const errorBox = document.getElementById('schedule-editor-error');
  errorBox.textContent = '';
  const draft = readScheduleDraft();
  if (!draft.queueId || !/^([01]\d|2[0-3]):[0-5]\d$/.test(draft.Info.Time) || !draft.Info.Days.length) {
    errorBox.textContent = '请选择所属队列、有效时间和至少一个重复日期。'; return;
  }
  if (state.queuesData[draft.queueId]?.Info?.CycleEnabled) {
    errorBox.textContent = '循环队列不使用定时启动，请选择普通队列。'; return;
  }
  state.schedulePending = true;
  document.getElementById('schedule-editor-fields').disabled = true;
  document.getElementById('schedule-save-button').textContent = '保存中...';
  const original = state.scheduleEditor;
  let createdId = '';
  try {
    let timeSetId = original.timeSetId;
    if (!timeSetId || original.queueId !== draft.queueId) {
      const added = await queueRequest('/api/queue/time/add', { queueId: draft.queueId });
      if (!added.timeSetId) throw new Error('未返回新定时编号，请刷新检查');
      createdId = timeSetId = added.timeSetId;
    }
    await queueRequest('/api/queue/time/update', { queueId: draft.queueId, timeSetId, data: { Info: draft.Info } });
    if (original.timeSetId && original.queueId !== draft.queueId) {
      await queueRequest('/api/queue/time/delete', { queueId: original.queueId, timeSetId: original.timeSetId });
    }
    createdId = '';
    state.scheduleEditor = null;
    document.getElementById('schedule-editor-card').style.display = 'none';
    showToast('定时已保存');
    await loadQueues();
  } catch (error) {
    let message = error.message;
    if (createdId) {
      try { await queueRequest('/api/queue/time/delete', { queueId: draft.queueId, timeSetId: createdId }); }
      catch (_) { message += '；新增项未能清理，请刷新列表检查目标队列，避免重复定时。'; }
    }
    errorBox.textContent = `保存失败：${message}`;
  } finally {
    state.schedulePending = false;
    document.getElementById('schedule-editor-fields').disabled = false;
    document.getElementById('schedule-save-button').textContent = '保存定时';
    renderQueueSchedules();
  }
}

async function toggleSchedule(queueId, timeSetId) {
  if (state.schedulePending) return;
  const info = state.queueSchedules[queueId]?.data?.[timeSetId]?.Info;
  if (!info) return;
  state.schedulePending = true;
  renderQueueSchedules();
  try {
    await queueRequest('/api/queue/time/update', { queueId, timeSetId, data: { Info: { Enabled: !info.Enabled } } });
    await loadQueues();
  } catch (error) { showToast(`修改定时失败：${error.message}`); }
  finally { state.schedulePending = false; renderQueueSchedules(); }
}

async function deleteSchedule(queueId, timeSetId) {
  if (state.schedulePending) return;
  const info = state.queueSchedules[queueId]?.data?.[timeSetId]?.Info;
  if (!info || !await confirmQueueChange(`删除「${state.queuesData[queueId]?.Info?.Name}」的 ${formatScheduleDays(info.Days)} ${info.Time} 定时？不会停止已启动的任务。`)) return;
  state.schedulePending = true;
  renderQueueSchedules();
  try {
    await queueRequest('/api/queue/time/delete', { queueId, timeSetId });
    if (state.scheduleEditor?.queueId === queueId && state.scheduleEditor?.timeSetId === timeSetId) {
      state.scheduleEditor = null;
      document.getElementById('schedule-editor-card').style.display = 'none';
    }
    await loadQueues(); showToast('定时已删除');
  } catch (error) { showToast(`删除定时失败：${error.message}`); }
  finally { state.schedulePending = false; renderQueueSchedules(); }
}

function renderQueuesTable() {
  const tbody = document.getElementById('queues-table-body');
  if (!tbody) return;
  if (state.queuesIndex.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted)">暂无调度队列，点击右上角「新建调度队列」添加</td></tr>';
    return;
  }
  tbody.innerHTML = state.queuesIndex
    .map((q) => {
      const cfg = state.queuesData[q.uid] || {};
      const qname = cfg.Info?.Name || '默认调度队列';
      const startup = { Never: '不运行', Always: '每次启动', DailyFirst: '每天首次启动' }[cfg.Info?.StartUpMode] || '不运行';
      const power = cfg.Info?.AfterAccomplish || 'NoAction';
      const schedule = state.queueSchedules[q.uid];
      const times = (schedule?.index || []).map((item) => schedule.data[item.uid]?.Info)
        .filter((info) => info?.Enabled).map((info) => `${formatScheduleDays(info.Days)} ${info.Time}`);
      const scheduleText = schedule?.error ? '定时加载失败' : cfg.Info?.CycleEnabled ? '循环队列'
        : !cfg.Info?.TimeEnabled ? '定时已关闭' : times.join('；') || '未设置启用的定时';
      const running = state.runtimeTasks.some((task) => task.queueId === q.uid);
      return `<tr>
        <td><strong>${escapeHtml(qname)}</strong></td>
        <td><code>${q.uid.slice(0, 8)}...</code></td>
        <td>${escapeHtml(scheduleText)}</td>
        <td>${startup}</td>
        <td>${power}</td>
        <td>
          <div class="btn-group">
            <button class="btn btn-sm btn-primary" onclick="openQueueEditor('${q.uid}')">编辑队列</button>
            <button class="btn btn-sm" ${running ? 'disabled' : ''} onclick="startTaskById('${q.uid}')">${running ? '本轮运行中' : '▶ 立即启动队列'}</button>
            <button class="btn btn-sm btn-danger" ${running || state.queueDeletePending.has(q.uid) ? 'disabled' : ''} onclick="deleteQueue('${q.uid}')">${state.queueDeletePending.has(q.uid) ? '删除中...' : '删除队列'}</button>
          </div>
        </td>
      </tr>`;
    })
    .join('');

  document.getElementById('home-script-queue-count').textContent =
    `${state.scriptsIndex.length} / ${state.queuesIndex.length}`;
}

async function createNewQueue() {
  if (state.queueCreatePending || !await closeQueueEditor()) return;
  state.queueCreatePending = true;
  document.getElementById('queue-create-button').disabled = true;
  document.getElementById('queue-create-button').textContent = '创建中...';
  try {
    const res = await queueRequest('/api/queue/add', {});
    if (!res.queueId) throw new Error('未返回队列编号，请刷新检查');
    showToast('已创建新调度队列');
    await loadQueues();
    await openQueueEditor(res.queueId);
  } catch (error) { showToast(`新建队列失败：${error.message}`); }
  finally {
    state.queueCreatePending = false;
    document.getElementById('queue-create-button').disabled = false;
    document.getElementById('queue-create-button').textContent = '新建调度队列';
  }
}

async function openQueueEditor(queueId) {
  if (state.currentEditQueueId && !await closeQueueEditor()) return;
  state.currentEditQueueId = queueId;
  const cfg = state.queuesData[queueId] || {};
  document.getElementById('queue-editor-card').style.display = 'block';
  document.getElementById('edit-queue-title').textContent = cfg.Info?.Name || '调度队列';
  document.getElementById('ed-queue-name').value = cfg.Info?.Name || '';
  document.getElementById('ed-queue-startup').value = cfg.Info?.StartUpMode || 'Never';
  document.getElementById('ed-queue-power').value = cfg.Info?.AfterAccomplish || 'NoAction';
  document.getElementById('ed-queue-timed').value = String(Boolean(cfg.Info?.TimeEnabled));
  document.getElementById('ed-queue-timed').disabled = Boolean(cfg.Info?.CycleEnabled);
  document.getElementById('queue-editor-error').textContent = '';
  state.queueDraft = JSON.stringify(readQueueDraft());

  const sel = document.getElementById('queue-add-script-select');
  if (sel) {
    sel.innerHTML = state.scriptsIndex
      .map((s) => `<option value="${s.uid}">${state.scriptsData[s.uid]?.Info?.Name || s.uid}</option>`)
      .join('');
  }
  await loadQueueItems(queueId);
  document.getElementById('queue-editor-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function readQueueDraft() {
  return {
    Name: document.getElementById('ed-queue-name').value.trim(),
    StartUpMode: document.getElementById('ed-queue-startup').value,
    AfterAccomplish: document.getElementById('ed-queue-power').value,
    TimeEnabled: document.getElementById('ed-queue-timed').value === 'true',
  };
}

async function closeQueueEditor() {
  if (state.queueSavePending) return false;
  if (state.currentEditQueueId && state.queueDraft !== JSON.stringify(readQueueDraft()) &&
    !await confirmQueueChange('有尚未保存的队列设置，确定放弃吗？')) return false;
  state.currentEditQueueId = null;
  document.getElementById('queue-editor-card').style.display = 'none';
  return true;
}

async function saveCurrentQueue() {
  const queueId = state.currentEditQueueId;
  if (!queueId || state.queueSavePending) return;
  const info = readQueueDraft();
  const errorBox = document.getElementById('queue-editor-error');
  errorBox.textContent = '';
  if (!info.Name) { errorBox.textContent = '请输入队列名称。'; return; }
  state.queueSavePending = true;
  document.getElementById('queue-save-button').disabled = true;
  document.getElementById('queue-save-button').textContent = '保存中...';
  try {
    await queueRequest('/api/queue/update', { queueId, data: { Info: info } });
    state.queueDraft = JSON.stringify(info);
    document.getElementById('edit-queue-title').textContent = info.Name;
    showToast('队列配置已保存');
    await loadQueues();
  } catch (error) { errorBox.textContent = `保存失败：${error.message}`; }
  finally {
    state.queueSavePending = false;
    document.getElementById('queue-save-button').disabled = false;
    document.getElementById('queue-save-button').textContent = '保存队列设置';
  }
}

async function loadQueueItems(queueId) {
  const res = await apiCall('/api/queue/item/get', 'POST', { queueId });
  const tbody = document.getElementById('queue-items-tbody');
  if (!tbody) return;
  const index = res.index || [];
  const data = res.data || {};
  if (index.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted)">队列中暂无子任务，请从上方下拉框选择脚本并点击「加入队列」</td></tr>';
    return;
  }
  tbody.innerHTML = index
    .map((item, idx) => {
      const icfg = data[item.uid] || {};
      const sid = icfg.Info?.ScriptId || '';
      const sname = state.scriptsData[sid]?.Info?.Name || sid || '未绑定';
      return `<tr>
        <td>#${idx + 1}</td>
        <td><code>${item.uid.slice(0, 8)}...</code></td>
        <td><strong>${sname}</strong></td>
        <td><button class="btn btn-sm btn-danger" onclick="deleteQueueItem('${queueId}','${item.uid}')">移除</button></td>
      </tr>`;
    })
    .join('');
}

async function addScriptItemToQueue() {
  const queueId = state.currentEditQueueId;
  const scriptId = document.getElementById('queue-add-script-select')?.value;
  if (!queueId || !scriptId) return;
  const addRes = await apiCall('/api/queue/item/add', 'POST', { queueId });
  if (addRes.queueItemId) {
    await apiCall('/api/queue/item/update', 'POST', {
      queueId,
      queueItemId: addRes.queueItemId,
      data: { Info: { ScriptId: scriptId } },
    });
    showToast('已将脚本加入调度队列');
    await loadQueueItems(queueId);
  }
}

async function deleteQueueItem(queueId, queueItemId) {
  await apiCall('/api/queue/item/delete', 'POST', { queueId, queueItemId });
  await loadQueueItems(queueId);
}

async function deleteQueue(queueId) {
  if (state.queueDeletePending.has(queueId) || state.queueSavePending || state.schedulePending) return;
  const name = state.queuesData[queueId]?.Info?.Name || '调度队列';
  if (!await confirmQueueChange(`删除「${name}」及其全部定时和队列项？脚本本身不会删除。`)) return;
  state.queueDeletePending.add(queueId);
  renderQueuesTable();
  try {
    const snapshot = await apiCall('/api/dispatch/runtime-snapshot');
    if (!Array.isArray(snapshot.tasks)) throw new Error('无法确认运行状态，请稍后重试');
    if (snapshot.tasks.some((task) => task.queueId === queueId)) throw new Error('队列正在运行，请等待本轮结束后再删除');
    await queueRequest('/api/queue/delete', { queueId });
    if (state.currentEditQueueId === queueId) {
      state.currentEditQueueId = null;
      document.getElementById('queue-editor-card').style.display = 'none';
    }
    if (state.scheduleEditor?.queueId === queueId || (state.scheduleEditor && document.getElementById('schedule-queue').value === queueId)) {
      state.scheduleEditor = null;
      document.getElementById('schedule-editor-card').style.display = 'none';
    }
    await loadQueues(); showToast('队列及所属定时已删除');
  } catch (error) { showToast(`删除队列失败：${error.message}`); }
  finally { state.queueDeletePending.delete(queueId); renderQueuesTable(); }
}

// ==================== 4. 调度中心、任务启停与上下任务导航 ====================

function refreshDispatchSelector() {
  const sel = document.getElementById('dispatch-target-select');
  if (!sel) return;
  const options = [];
  state.queuesIndex.forEach((q) => {
    const name = state.queuesData[q.uid]?.Info?.Name || q.uid;
    options.push(`<option value="${q.uid}">[队列] ${name}</option>`);
  });
  state.scriptsIndex.forEach((s) => {
    const name = state.scriptsData[s.uid]?.Info?.Name || s.uid;
    options.push(`<option value="${s.uid}">[单脚本] ${name} (${s.type})</option>`);
  });
  sel.innerHTML = options.length
    ? options.join('')
    : '<option value="">请先在「脚本管理」或「调度队列」中创建配置</option>';
}

async function startSelectedDispatchTarget() {
  const targetId = document.getElementById('dispatch-target-select')?.value;
  if (!targetId) {
    showToast('请先选择或创建一个队列/脚本');
    return;
  }
  await startTaskById(targetId);
}

let dispatchStartPending = false;

function chooseDesktopFallback(reason) {
  const dialog = document.getElementById('desktop-fallback-dialog');
  document.getElementById('desktop-fallback-reason').textContent = reason;
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue), { once: true });
    dialog.returnValue = 'cancel';
    dialog.showModal();
  });
}

async function startTaskById(taskId) {
  if (dispatchStartPending) return;
  dispatchStartPending = true;
  try {
    if (state.queuesData[taskId]) {
      const snapshot = await apiCall('/api/dispatch/runtime-snapshot');
      if (!Array.isArray(snapshot.tasks)) throw new Error('无法确认队列状态，请稍后重试');
      if (snapshot.tasks.some((task) => task.queueId === taskId)) {
        throw new Error('该队列已在运行，请等待本轮结束');
      }
    }
    let remoteError = '';
    try {
      const desktop = await apiCall('/api/child-session/status');
      if (desktop.code !== 200 || !desktop.data?.enabled) {
        throw new Error(desktop.message || '远程桌面未启用');
      }
      const connection = await apiCall('/api/child-session/connect', 'POST', {});
      if (connection.code !== 200 || !connection.data?.hostConnected) {
        throw new Error(connection.message || '远程桌面连接未就绪');
      }
    } catch (error) {
      remoteError = error instanceof Error ? error.message : String(error);
    }
    if (remoteError) {
      const choice = await chooseDesktopFallback(remoteError);
      if (choice !== 'manual' && choice !== 'main') return;
      const snapshot = await apiCall('/api/dispatch/runtime-snapshot');
      if (!Array.isArray(snapshot.tasks) || snapshot.tasks.length > 0) {
        throw new Error('请等待当前任务结束后再切换桌面执行模式');
      }
      const setting = await apiCall('/api/setting/update', 'POST', {
        data: { ChildSession: { Enabled: choice === 'manual' } },
      });
      if (setting.code !== 200) {
        throw new Error(setting.message || '无法切换桌面执行模式');
      }
      if (choice === 'manual') {
        switchTab('child-session');
        showToast('已启用远程桌面，请点击建立/恢复常驻连接，连接成功后再次运行任务');
        return;
      }
      await loadChildSessionStatus();
    }
    const res = await apiCall('/api/dispatch/start', 'POST', {
      mode: 'AutoProxy',
      taskId,
    });
    if (res.code !== 200 || !res.taskId) {
      const detail = Array.isArray(res.detail)
        ? res.detail.map((item) => item.msg).join('；')
        : res.detail;
      throw new Error(res.message || detail || '服务未返回任务编号，请检查后端日志');
    }
    showToast(`任务已启动 (taskId=${res.taskId.slice(0, 8)}...)`);
    appendTerminalLog(`[任务启动] 已提交任务: ${taskId}`);
    switchTab('scheduler');
    await loadRuntimeSnapshot();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    showToast(`启动失败: ${message}`);
    appendTerminalLog(`[启动失败] ${message}`);
  } finally {
    dispatchStartPending = false;
  }
}

async function stopAllTasks() {
  await apiCall('/api/dispatch/stop', 'POST', { taskId: 'ALL' });
  showToast('已发送停止全部任务指令（强制执行 3 遍 taskkill /F /T）');
  appendTerminalLog('[强制清理] 已停止全部任务并执行 3 遍 taskkill /F /T');
  await loadRuntimeSnapshot();
}

async function triggerNavAction(action) {
  const res = await apiCall(`/api/dispatch/navigation/${action}`, 'POST', {});
  const info = res?.data || {};
  const msg = `导航控制 [${action}] -> ${info.action || res.status}`;
  showToast(msg);
  appendTerminalLog(`[热键/导航控制] ${JSON.stringify(info)}`);
  await loadRuntimeSnapshot();
}

async function updatePowerSign(powerSign) {
  await apiCall('/api/dispatch/set/power', 'POST', { powerSign });
  showToast(`已设置任务完成后电源动作: ${powerSign}`);
}

function renderRuntimeTasks(tasks) {
  const expandedTasks = new Set(Array.from(
    document.querySelectorAll('.runtime-task-card details[open]'), (detail) => detail.dataset.taskId,
  ));
  document.getElementById('home-running-count').textContent = String(tasks.length);
  document.getElementById('home-running-sub').textContent = tasks.length ? '执行进度每 4 秒自动刷新' : '当前没有运行中的任务';
  const content = tasks.map((task) => {
    const steps = task.task_info || [];
    const running = steps.filter((step) => step.status === '运行');
    const finished = steps.filter((step) => ['完成', '异常', '跳过'].includes(step.status)).length;
    const queueName = state.queuesData[task.queueId]?.Info?.Name;
    const scriptName = state.scriptsData[task.scriptId]?.Info?.Name;
    const name = queueName || scriptName || (task.queueId ? '调度队列' : '脚本任务');
    const users = running.flatMap((step) => (step.userList || [])
      .filter((user) => user.status === '运行').map((user) => user.name));
    const abnormal = steps.filter((step) => step.status === '异常' || step.userList?.some((user) => user.status === '异常')).length;
    return `<article class="runtime-task-card">
      <div class="runtime-task-heading"><strong>${escapeHtml(name)}</strong>
        <span class="tag ${task.stopping ? '' : 'green'}">${task.stopping ? '正在停止' : '执行中'}</span></div>
      <div>当前任务：${escapeHtml(running.map((step) => step.name).join('、') || (task.stopping ? '等待清理完成' : '等待下一步骤或释放资源'))}</div>
      ${users.length ? `<div>当前用户：${escapeHtml(users.join('、'))}</div>` : ''}
      <div class="form-hint">进度：${finished} / ${steps.length} 项已结束${abnormal ? `，${abnormal} 项出现异常` : ''}</div>
      <details data-task-id="${escapeHtml(task.taskId)}" ${expandedTasks.has(task.taskId) ? 'open' : ''}><summary>查看全部步骤</summary><ol class="runtime-step-list">${steps.map((step) =>
        `<li>${escapeHtml(step.name)} — ${escapeHtml(step.status)}</li>`).join('')}</ol></details>
      <div class="form-hint">任务编号：${escapeHtml(task.taskId)}</div>
    </article>`;
  }).join('');
  document.getElementById('home-runtime-tasks').innerHTML = content;
  document.getElementById('runtime-tasks-box').innerHTML = content || '当前暂无正在运行的任务。';
}

let runtimeSnapshotPending = false;

async function loadRuntimeSnapshot() {
  if (runtimeSnapshotPending) return;
  runtimeSnapshotPending = true;
  const status = document.getElementById('home-runtime-status');
  try {
    const snap = await apiCall('/api/dispatch/runtime-snapshot', 'GET');
    if (!Array.isArray(snap.tasks)) throw new Error(snap.message || '运行状态查询失败');
    state.runtimeTasks = snap.tasks;
    renderRuntimeTasks(snap.tasks);
    renderQueuesTable();
    status.textContent = snap.tasks.length ? `最近更新：${new Date().toLocaleTimeString()}，每 4 秒刷新` : '当前暂无正在运行的任务。';
  } catch (error) {
    status.textContent = `运行状态刷新失败：${error.message}；保留上次结果，将自动重试。`;
  } finally {
    runtimeSnapshotPending = false;
  }
}

// ==================== 5. 历史记录与全局设置 ====================

async function loadHistory() {
  const box = document.getElementById('history-container');
  if (!box) return;
  try {
    const today = new Date().toISOString().slice(0, 10);
    const start = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
    const res = await apiCall('/api/history/search', 'POST', {
      mode: '按日合并',
      start_date: start,
      end_date: today,
    });
    const data = res?.data || {};
    const dates = Object.keys(data);
    if (dates.length === 0) {
      box.innerHTML = '最近 7 天暂无历史执行记录。';
      return;
    }
    box.innerHTML = dates
      .map((d) => `<div style="margin-bottom:10px"><strong>📅 ${d}</strong>: 共 ${Object.keys(data[d] || {}).length} 项用户执行记录</div>`)
      .join('');
  } catch (err) {
    box.innerHTML = '加载历史记录失败。';
  }
}

async function loadGlobalSettings() {
  try {
    const res = await apiCall('/api/setting/get', 'POST', {});
    const d = res?.data || {};
    state.globalSettings = d;

    const cs = d.ChildSession || {};
    const hk = d.Hotkey || {};
    const fn = d.Function || {};
    const nf = d.Notify || {};

    document.getElementById('set-cs-enabled').value = String(cs.Enabled !== false);
    document.getElementById('set-cs-hidden').value = String(cs.StartHidden !== false);
    document.getElementById('set-cs-res').value = cs.Resolution || '2560x1440';
    document.getElementById('set-cs-watch').value = String(cs.WatchMode !== false);

    document.getElementById('set-hk-enabled').value = String(hk.Enabled !== false);
    document.getElementById('set-hk-toggle').value = hk.ToggleStartStop || 'Ctrl+Alt+S';
    document.getElementById('set-hk-prev').value = hk.PreviousTask || 'Ctrl+Alt+Left';
    document.getElementById('set-hk-next').value = hk.NextTask || 'Ctrl+Alt+Right';

    document.getElementById('set-fn-sleep').value = String(Boolean(fn.IfAllowSleep));
    document.getElementById('set-notify-mode').value = nf.SendTaskResultTime || '不推送';
    document.getElementById('set-notify-sc').value = nf.ServerChanKey || '';

    document.getElementById('txt-hotkey-summary').textContent =
      `${hk.ToggleStartStop || 'Ctrl+Alt+S'} | ${hk.PreviousTask || 'Ctrl+Alt+Left'} / ${hk.NextTask || 'Ctrl+Alt+Right'}`;
  } catch (err) {
    console.warn('loadGlobalSettings error:', err);
  }
}

async function saveGlobalSettings() {
  const payload = {
    data: {
      ChildSession: {
        Enabled: document.getElementById('set-cs-enabled').value === 'true',
        StartHidden: document.getElementById('set-cs-hidden').value === 'true',
        Resolution: document.getElementById('set-cs-res').value,
        WatchMode: document.getElementById('set-cs-watch').value === 'true',
      },
      Hotkey: {
        Enabled: document.getElementById('set-hk-enabled').value === 'true',
        ToggleStartStop: document.getElementById('set-hk-toggle').value.trim() || 'Ctrl+Alt+S',
        PreviousTask: document.getElementById('set-hk-prev').value.trim() || 'Ctrl+Alt+Left',
        NextTask: document.getElementById('set-hk-next').value.trim() || 'Ctrl+Alt+Right',
      },
      Function: {
        IfAllowSleep: document.getElementById('set-fn-sleep').value === 'true',
      },
      Notify: {
        SendTaskResultTime: document.getElementById('set-notify-mode').value,
        ServerChanKey: document.getElementById('set-notify-sc').value.trim(),
      },
    },
  };
  const res = await apiCall('/api/setting/update', 'POST', payload);
  if (res.code === 200) {
    await apiCall('/api/dispatch/hotkeys/reload', 'POST', {});
    showToast('全局设置已保存，全局热键与远程桌面配置已生效');
    await loadGlobalSettings();
    await loadChildSessionStatus();
  } else {
    showToast(`保存失败: ${res.message}`);
  }
}

async function testNotification() {
  const res = await apiCall('/api/setting/test_notify', 'POST', {});
  showToast(res.message || (res.code === 200 ? '测试通知已发送' : '通知发送失败'));
}

// ==================== 6. WebSocket 实时事件订阅 ====================

function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${proto}//${location.host}/api/core/ws`;
  const tag = document.getElementById('ws-conn-tag');

  try {
    const ws = new WebSocket(wsUrl);
    state.ws = ws;
    ws.onopen = () => {
      if (tag) {
        tag.textContent = 'WS 已连接';
        tag.className = 'tag green';
      }
      appendTerminalLog('[WebSocket] 已连接至 AUTO-MAS 实时事件总线');
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type && msg.type !== 'ping') {
          appendTerminalLog(`[${msg.type}] ${JSON.stringify(msg.data || {})}`);
          if (msg.type.startsWith('task.')) {
            loadRuntimeSnapshot();
          }
        }
      } catch (_) {}
    };
    ws.onclose = () => {
      if (tag) {
        tag.textContent = 'WS 重连中';
        tag.className = 'tag amber';
      }
      setTimeout(connectWebSocket, 3000);
    };
  } catch (_) {}
}

async function refreshAll() {
  await Promise.all([
    loadHealthAndSummary(),
    loadChildSessionStatus(),
    loadScripts(),
    loadQueues(),
    loadRuntimeSnapshot(),
    loadGlobalSettings(),
  ]);
}

window.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('automas_theme') === 'dark') {
    document.body.classList.add('dark-theme');
    const btn = document.getElementById('btn-theme');
    if (btn) btn.textContent = '☀ 亮色';
  }
  refreshAll();
  connectWebSocket();
  setInterval(() => {
    loadHealthAndSummary();
    loadChildSessionStatus();
    loadRuntimeSnapshot();
  }, 4000);
});
