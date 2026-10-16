/**
 * Antigravity Telegram Bridge - Frontend Controller
 */

let isBotRunningState = false;
let autoScrollTerminal = true;

// DOM Elements
const botStatusPill = document.getElementById('botStatusPill');
const botStatusDot = document.getElementById('botStatusDot');
const botStatusLabel = document.getElementById('botStatusLabel');
const btnToggleBot = document.getElementById('btnToggleBot');
const btnToggleBotText = document.getElementById('btnToggleBotText');

const inputBotToken = document.getElementById('inputBotToken');
const tokenVerifyResult = document.getElementById('tokenVerifyResult');
const botInfoBox = document.getElementById('botInfoBox');
const infoBotName = document.getElementById('infoBotName');
const infoBotUsername = document.getElementById('infoBotUsername');
const infoBotId = document.getElementById('infoBotId');
const linkOpenTelegram = document.getElementById('linkOpenTelegram');

const inputAllowedUsers = document.getElementById('inputAllowedUsers');
const detectedUsersList = document.getElementById('detectedUsersList');
const checkSafeMode = document.getElementById('checkSafeMode');
const saveStatusMsg = document.getElementById('saveStatusMsg');

const badgeGlobalSkill = document.getElementById('badgeGlobalSkill');
const badgeWorkspaceSkill = document.getElementById('badgeWorkspaceSkill');

const statHost = document.getElementById('statHost');
const statPython = document.getElementById('statPython');
const statDisk = document.getElementById('statDisk');
const terminalOutput = document.getElementById('terminalOutput');

// Toast Notification Helper
function showToast(message, icon = 'ℹ️', duration = 3500) {
  const toast = document.getElementById('toastNotification');
  const toastMsg = document.getElementById('toastMessage');
  const toastIcon = document.getElementById('toastIcon');

  toastMsg.textContent = message;
  toastIcon.textContent = icon;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, duration);
}

// Toggle token masking (password / text)
function toggleTokenMask() {
  const btn = document.getElementById('btnToggleTokenVisibility');
  if (inputBotToken.type === 'password') {
    inputBotToken.type = 'text';
    btn.textContent = '🔒';
  } else {
    inputBotToken.type = 'password';
    btn.textContent = '👁';
  }
}

// Copy Code Snippet
function copySnippet(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('تم نسخ الأمر إلى الحافظة! 📋', '✅');
  }).catch(() => {
    prompt('انسخ الأمر التالي:', text);
  });
}

// Fetch System & Bot Status
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    // Update Bot Status Indicator
    isBotRunningState = data.bot_running;
    if (data.bot_running) {
      botStatusDot.className = 'status-dot dot-active';
      botStatusLabel.textContent = `نشط متصل (PID: ${data.bot_pid})`;
      btnToggleBot.className = 'btn btn-danger';
      btnToggleBotText.textContent = 'إيقاف البوت';
      btnToggleBot.querySelector('.btn-icon').textContent = '⏹️';
    } else {
      botStatusDot.className = 'status-dot dot-inactive';
      botStatusLabel.textContent = data.has_token ? 'متوقف (جاهز للتشغيل)' : 'غير متصل (بانتظار التوكن)';
      btnToggleBot.className = 'btn btn-primary';
      btnToggleBotText.textContent = 'تشغيل البوت';
      btnToggleBot.querySelector('.btn-icon').textContent = '▶️';
    }

    // Update System Info Footer
    if (data.system) {
      statHost.textContent = data.system.hostname;
      statPython.textContent = data.system.python;
      statDisk.textContent = `${data.system.free_disk_gb} GB`;
    }

    // Update Skill Badges
    if (data.global_skill_installed) {
      badgeGlobalSkill.className = 'badge badge-success';
      badgeGlobalSkill.textContent = 'مثبت وفعّال';
    } else {
      badgeGlobalSkill.className = 'badge badge-warning';
      badgeGlobalSkill.textContent = 'غير مثبت';
    }

    if (data.workspace_skill_installed) {
      badgeWorkspaceSkill.className = 'badge badge-success';
      badgeWorkspaceSkill.textContent = 'مثبت وفعّال';
    } else {
      badgeWorkspaceSkill.className = 'badge badge-warning';
      badgeWorkspaceSkill.textContent = 'غير مثبت';
    }

    // If bot username is known, display banner
    if (data.bot_username) {
      displayBotInfo({
        name: data.bot_name || 'Antigravity Bot',
        username: data.bot_username,
        id: ''
      });
    }

  } catch (err) {
    botStatusLabel.textContent = 'خطأ في الاتصال بالسيرفر';
    botStatusDot.className = 'status-dot dot-inactive';
  }
}

// Fetch Saved Config on load
async function fetchConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const cfg = await res.json();

    if (cfg.bot_token) {
      inputBotToken.value = cfg.bot_token;
    }
    if (cfg.allowed_chat_ids && cfg.allowed_chat_ids.length > 0) {
      inputAllowedUsers.value = cfg.allowed_chat_ids.join(', ');
    }
    checkSafeMode.checked = cfg.safe_mode !== false;

  } catch (err) {
    console.error('Error fetching config:', err);
  }
}

// Display Bot Info Box
function displayBotInfo(bot) {
  botInfoBox.classList.remove('hidden');
  infoBotName.textContent = bot.name || 'Telegram Bot';
  infoBotUsername.textContent = bot.username;
  if (bot.id) infoBotId.textContent = bot.id;
  linkOpenTelegram.href = `https://t.me/${bot.username}`;
}

// Verify Bot Token
async function verifyBotToken() {
  const token = inputBotToken.value.trim();
  if (!token) {
    tokenVerifyResult.textContent = '⚠️ يرجى إدخال التوكن أولاً';
    tokenVerifyResult.className = 'input-hint error';
    return;
  }

  tokenVerifyResult.textContent = '⏳ جاري الاتصال بخوادم تيليجرام...';
  tokenVerifyResult.className = 'input-hint';

  try {
    const res = await fetch('/api/test_token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: token })
    });
    const result = await res.json();

    if (result.ok) {
      tokenVerifyResult.textContent = `✅ تم التحقق بنجاح! متصل مع @${result.bot_username}`;
      tokenVerifyResult.className = 'input-hint success';
      displayBotInfo({
        name: result.bot_name,
        username: result.bot_username,
        id: result.bot_id
      });
      showToast(`تم التحقق من البوت: @${result.bot_username}`, '✅');
    } else {
      tokenVerifyResult.textContent = `❌ ${result.description}`;
      tokenVerifyResult.className = 'input-hint error';
      showToast(result.description, '❌');
    }
  } catch (err) {
    tokenVerifyResult.textContent = '❌ تعذر الاتصال: ' + err.message;
    tokenVerifyResult.className = 'input-hint error';
  }
}

// Auto-Detect Chat ID
async function detectRecentChatIds() {
  detectedUsersList.classList.remove('hidden');
  detectedUsersList.innerHTML = '<div style="color:var(--text-dim);font-size:0.8rem;">⏳ جاري فحص الرسائل الأخيرة المرسلة للبوت...</div>';

  try {
    const res = await fetch('/api/detect_chat_id', { method: 'POST' });
    const data = await res.json();

    if (!data.ok) {
      detectedUsersList.innerHTML = `<div style="color:var(--accent-rose);font-size:0.8rem;">❌ ${data.description}</div>`;
      return;
    }

    if (!data.users || data.users.length === 0) {
      detectedUsersList.innerHTML = `
        <div style="font-size:0.8rem; color:var(--accent-amber);">
          ℹ️ لم يتم العثور على رسائل حديثة.<br>
          افتح تليجرام وأرسل أي رسالة (مثلاً <code>/start</code> أو <code>مرحبا</code>) للبوت ثم اضغط الزر مرة أخرى.
        </div>
      `;
      return;
    }

    detectedUsersList.innerHTML = '<div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:4px;">المستخدمين المكتشفين:</div>';
    data.users.forEach(u => {
      const row = document.createElement('div');
      row.className = 'detected-user-item';
      row.innerHTML = `
        <div>
          <strong>${u.name || '@' + u.username || 'مستخدم'}</strong> 
          <code>(${u.id})</code>
          <div style="color:var(--text-dim);font-size:0.75rem;">آخر رسالة: "${u.last_text || 'لا يوجد'}"</div>
        </div>
        <button class="btn-sm btn-primary" onclick="addUserIdToInput('${u.id}')">+ تعيين كمدير</button>
      `;
      detectedUsersList.appendChild(row);
    });

  } catch (err) {
    detectedUsersList.innerHTML = `<div style="color:var(--accent-rose);font-size:0.8rem;">❌ خطأ: ${err.message}</div>`;
  }
}

// Add User ID to Input
function addUserIdToInput(uid) {
  const current = inputAllowedUsers.value.trim();
  const list = current ? current.split(',').map(s => s.trim()) : [];
  if (!list.includes(String(uid))) {
    list.push(String(uid));
    inputAllowedUsers.value = list.join(', ');
    showToast(`تمت إضافة الآيدي ${uid}! اضغط "حفظ الإعدادات" للاعتماد.`, '✅');
  }
}

// Save Configuration
async function saveConfiguration() {
  const token = inputBotToken.value.trim();
  const rawUsers = inputAllowedUsers.value.trim();
  const userIds = rawUsers ? rawUsers.split(',').map(s => s.trim()).filter(Boolean) : [];
  const safeMode = checkSafeMode.checked;

  saveStatusMsg.textContent = '⏳ جاري الحفظ...';

  try {
    const res = await fetch('/api/save_config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bot_token: token,
        allowed_chat_ids: userIds,
        safe_mode: safeMode
      })
    });
    const result = await res.json();
    if (result.ok) {
      saveStatusMsg.textContent = '✅ تم الحفظ!';
      showToast('تم حفظ الإعدادات بنجاح!', '💾');
      fetchStatus();
      setTimeout(() => { saveStatusMsg.textContent = ''; }, 3000);
    } else {
      saveStatusMsg.textContent = '❌ فشل الحفظ';
    }
  } catch (err) {
    saveStatusMsg.textContent = '❌ خطأ: ' + err.message;
  }
}

// Toggle Bot Daemon State
async function toggleBotState() {
  btnToggleBot.disabled = true;
  const endpoint = isBotRunningState ? '/api/bot/stop' : '/api/bot/start';

  try {
    const res = await fetch(endpoint, { method: 'POST' });
    const data = await res.json();
    showToast(data.message, data.ok ? '✅' : '⚠️');
    await fetchStatus();
    fetchLogs();
  } catch (err) {
    showToast('فشل تغيير حالة البوت: ' + err.message, '❌');
  } finally {
    btnToggleBot.disabled = false;
  }
}

// Send Test Notification
async function sendTestNotification() {
  const title = document.getElementById('inputTestTitle').value.trim();
  const message = document.getElementById('inputTestMessage').value.trim();
  const level = document.getElementById('selectTestLevel').value;
  const btn = document.getElementById('btnSendTest');

  if (!message) {
    showToast('يرجى كتابة نص الرسالة أولاً', '⚠️');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span>⏳ جاري الإرسال...</span>';

  try {
    const res = await fetch('/api/send_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, message, level })
    });
    const data = await res.json();

    if (data.ok) {
      showToast(data.message, '🚀');
      fetchLogs();
    } else {
      showToast(data.description || 'فشل الإرسال', '❌');
    }
  } catch (err) {
    showToast('خطأ بالشبكة: ' + err.message, '❌');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🚀 إرسال للتليجرام</span>';
  }
}

// Sync Local and Global Skills
async function syncSkills() {
  showToast('جاري مزامنة السكيل...', '🔄');
  try {
    const res = await fetch('/api/sync_skills', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      showToast(data.message, '✅');
      fetchStatus();
    } else {
      showToast(data.description, '❌');
    }
  } catch (err) {
    showToast('خطأ أثناء المزامنة: ' + err.message, '❌');
  }
}

// Fetch Logs for Terminal
async function fetchLogs() {
  try {
    const res = await fetch('/api/logs');
    if (!res.ok) return;
    const data = await res.json();

    if (!data.logs || data.logs.length === 0) {
      terminalOutput.innerHTML = '<div class="term-line info">[System] لا توجد سجلات بعد. سيظهر النشاط هنا فور بدء العمل...</div>';
      return;
    }

    terminalOutput.innerHTML = '';
    data.logs.forEach(line => {
      const lineEl = document.createElement('div');
      lineEl.className = 'term-line';
      if (line.includes('[ERROR]') || line.includes('❌') || line.includes('Unauthorized')) {
        lineEl.classList.add('error');
      } else if (line.includes('[SUCCESS]') || line.includes('✅') || line.includes('paired')) {
        lineEl.classList.add('success');
      } else if (line.includes('[CMD]') || line.includes('executing')) {
        lineEl.classList.add('cmd');
      } else if (line.includes('[WARNING]') || line.includes('⚠️')) {
        lineEl.classList.add('warn');
      } else {
        lineEl.classList.add('info');
      }
      lineEl.textContent = line;
      terminalOutput.appendChild(lineEl);
    });

    if (autoScrollTerminal) {
      terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }
  } catch (err) {
    console.error('Error fetching logs:', err);
  }
}

function clearLocalLogsView() {
  terminalOutput.innerHTML = '<div class="term-line info">[Terminal cleared]</div>';
}

// Initialize on Load
window.addEventListener('DOMContentLoaded', () => {
  fetchStatus();
  fetchConfig();
  fetchLogs();

  // Periodic polling for status and logs
  setInterval(fetchStatus, 4000);
  setInterval(fetchLogs, 5000);
});
