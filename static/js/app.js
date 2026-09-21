// KCT Studio - AI Video Pipeline Reactive Controller & Notification Center

let ws = null;
let currentProject = null;
let currentFilter = "episodes_default";
let selectedEpisode = null;
let selectedEpisodeNum = null;
let selectedEpisodeObj = null;
let hasRootChapters = false;
let currentSort = "date_desc";
let currentEpisodeSort = "num_asc";
let currentStatusFilter = null;
let allAssets = [];
let allConfiguredProjects = [];
let targetAssetForReject = null;
let targetAssetForModal = null;
let audioCtx = null;
let lastProcessStatus = "idle";

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  initWebSocket();
  loadProjects();
  initTelemetry();
  initDesktopNotifications();
  setupEventListeners();
});

// ================= AUDIO CHIME SYNTHESIZER (WEB AUDIO API) =================
function playChime(type) {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    const now = audioCtx.currentTime;

    if (type === "job_completed") {
      // Harmonic 3-tone finish chime (C5 -> E5 -> G5) resonant bell
      const osc1 = audioCtx.createOscillator();
      const osc2 = audioCtx.createOscillator();
      const osc3 = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc1.type = "sine";
      osc2.type = "sine";
      osc3.type = "triangle";

      osc1.frequency.setValueAtTime(523.25, now);
      osc2.frequency.setValueAtTime(659.25, now + 0.12);
      osc3.frequency.setValueAtTime(783.99, now + 0.24);

      gain.gain.setValueAtTime(0.14, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 1.2);

      osc1.connect(gain);
      osc2.connect(gain);
      osc3.connect(gain);
      gain.connect(audioCtx.destination);

      osc1.start(now);
      osc2.start(now + 0.12);
      osc3.start(now + 0.24);

      osc1.stop(now + 1.2);
      osc2.stop(now + 1.2);
      osc3.stop(now + 1.2);
      return;
    }

    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === "success" || type === "gold") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    } else if (type === "error") {
      osc.type = "triangle";
      osc.frequency.setValueAtTime(320, now);
      osc.frequency.exponentialRampToValueAtTime(220, now + 0.18);
      gain.gain.setValueAtTime(0.09, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
      osc.start(now);
      osc.stop(now + 0.28);
    } else if (type === "warning") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(370, now + 0.15);
      gain.gain.setValueAtTime(0.07, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    }
  } catch (e) {
    // Non-blocking
  }
}

// ================= DESKTOP NOTIFICATIONS & TAB ALERTS =================
let originalDocTitle = document.title || "KCT Studio - AI Video Pipeline";
let titleFlashInterval = null;

function flashDocumentTitle(alertText) {
  if (titleFlashInterval) clearInterval(titleFlashInterval);
  let toggle = false;
  titleFlashInterval = setInterval(() => {
    document.title = toggle ? alertText : originalDocTitle;
    toggle = !toggle;
  }, 1000);
}

window.addEventListener("focus", () => {
  if (titleFlashInterval) {
    clearInterval(titleFlashInterval);
    titleFlashInterval = null;
    document.title = originalDocTitle;
  }
});

function updateNotificationButtonState() {
  const btn = document.getElementById("btnToggleNotifications");
  const icon = document.getElementById("iconNotification");
  const text = document.getElementById("textNotification");
  if (!btn || !("Notification" in window)) return;

  const perm = Notification.permission;
  if (perm === "granted") {
    btn.className = "bg-[#14261e] hover:bg-[#1a382b] text-emerald-300 px-2.5 py-1.5 rounded-lg border border-emerald-600/40 transition text-sm flex items-center gap-1.5";
    btn.title = "Desktop Alerts Active (Click to send test alert)";
    if (icon) icon.className = "w-4 h-4 text-emerald-400";
    if (text) text.textContent = "Alerts On";
  } else if (perm === "denied") {
    btn.className = "bg-[#261616] hover:bg-[#381a1a] text-rose-300 px-2.5 py-1.5 rounded-lg border border-rose-700/40 transition text-sm flex items-center gap-1.5 opacity-75";
    btn.title = "Notifications Blocked in Browser Settings (Click for info)";
    if (icon) icon.className = "w-4 h-4 text-rose-400";
    if (text) text.textContent = "Alerts Blocked";
  } else {
    btn.className = "bg-[#282114] hover:bg-[#3d3119] text-amber-300 px-2.5 py-1.5 rounded-lg border border-amber-600/40 transition text-sm flex items-center gap-1.5 animate-pulse";
    btn.title = "Enable Desktop Notifications (Click to allow)";
    if (icon) icon.className = "w-4 h-4 text-amber-400";
    if (text) text.textContent = "Enable Alerts";
  }
}

function initDesktopNotifications() {
  const btn = document.getElementById("btnToggleNotifications");
  if (!btn) return;

  if (!("Notification" in window)) {
    btn.style.display = "none";
    return;
  }

  updateNotificationButtonState();

  btn.onclick = async () => {
    if (Notification.permission === "granted") {
      triggerDesktopNotification(
        "🔔 KCT Studio: Desktop Alerts Active",
        "You will receive an alert like this when video pipelines finish execution.",
        "info"
      );
      playChime("job_completed");
      showNotification({
        title: "Desktop Alerts Active",
        message: "Desktop notifications and audio chimes are verified and working.",
        type: "success",
        duration: 3500
      });
    } else if (Notification.permission === "denied") {
      showNotification({
        title: "Notifications Blocked",
        message: "Desktop notifications are blocked in your browser. Click the site settings lock icon in your URL bar to allow notifications.",
        type: "warning",
        duration: 7000
      });
    } else {
      const res = await Notification.requestPermission();
      updateNotificationButtonState();
      if (res === "granted") {
        triggerDesktopNotification(
          "🔔 KCT Studio: Desktop Alerts Enabled!",
          "Great! You will now be alerted when any job finishes even if you're working in another application.",
          "success"
        );
        playChime("job_completed");
        showNotification({
          title: "Notifications Enabled",
          message: "You will now be alerted when background jobs finish.",
          type: "success"
        });
      }
    }
  };
}

function triggerDesktopNotification(title, body, type = "info") {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }

  try {
    const cleanBody = (body || "").replace(/<[^>]*>?/gm, "");
    const notif = new Notification(title, {
      body: cleanBody,
      icon: "/static/favicon.svg",
      tag: "kct-studio-pipeline-job",
      renotify: true
    });

    notif.onclick = () => {
      window.focus();
      try { notif.close(); } catch (e) {}
    };
  } catch (err) {
    console.warn("[Notification] Error triggering desktop notification:", err);
  }
}

// ================= ENHANCED TOAST NOTIFICATION SYSTEM =================
function showNotification({
  title = "Notification",
  message = "",
  type = "info",
  duration = 4500,
  details = null
}) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  playChime(type);

  const icons = {
    success: '<i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-400 shrink-0"></i>',
    warning: '<i data-lucide="alert-triangle" class="w-5 h-5 text-amber-400 shrink-0"></i>',
    error: '<i data-lucide="alert-octagon" class="w-5 h-5 text-rose-400 shrink-0"></i>',
    info: '<i data-lucide="info" class="w-5 h-5 text-cyan-400 shrink-0"></i>',
    gold: '<i data-lucide="sparkles" class="w-5 h-5 text-[#FFE614] shrink-0"></i>'
  };

  const toast = document.createElement("div");
  toast.className = `toast-card toast-${type} p-3.5 flex flex-col gap-1 text-xs`;

  toast.innerHTML = `
    <div class="flex items-start justify-between gap-2.5">
      <div class="flex items-start gap-2.5 flex-1 min-w-0">
        ${icons[type] || icons.info}
        <div class="flex-1 min-w-0">
          <div class="font-bold text-slate-100 text-xs tracking-wide">${escapeHtml(title)}</div>
          <div class="text-slate-300 text-[11px] leading-relaxed mt-0.5 break-words">${message}</div>
          ${details ? `<div class="mt-1.5 pt-1.5 border-t border-slate-700/50 text-[10px] text-slate-400 font-mono">${details}</div>` : ""}
        </div>
      </div>
      <button class="toast-close p-1 text-slate-400 hover:text-white transition rounded shrink-0">
        <i data-lucide="x" class="w-3.5 h-3.5"></i>
      </button>
    </div>
    <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
  `;

  container.appendChild(toast);
  lucide.createIcons();

  const dismiss = () => {
    toast.classList.add("dismissing");
    setTimeout(() => {
      toast.remove();
    }, 300);
  };

  toast.querySelector(".toast-close").onclick = dismiss;

  if (duration > 0) {
    setTimeout(dismiss, duration);
  }
}

// ================= 1. WEBSOCKET & TERMINAL STREAMING =================
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/logs`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("[WebSocket] Connected to log stream");
    updateTerminalStatus("CONNECTED", "slate");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWsMessage(data);
    } catch (e) {
      console.error("[WebSocket] Parse error:", e);
    }
  };

  ws.onclose = () => {
    console.log("[WebSocket] Disconnected, retrying in 3s...");
    updateTerminalStatus("DISCONNECTED", "rose");
    setTimeout(initWebSocket, 3000);
  };
}

function handleWsMessage(data) {
  const terminal = document.getElementById("terminalOutput");

  if (data.type === "init") {
    setProcessStatus(data.status, data.job);
    if (data.logs && Array.isArray(data.logs)) {
      terminal.innerHTML = "";
      data.logs.forEach(entry => appendLogLine(entry));
    }
  } else if (data.type === "log") {
    appendLogLine(data.entry);
  } else if (data.type === "status") {
    if (lastProcessStatus === "running" && data.status === "completed") {
      const scriptName = data.job?.script || "Pipeline Script";
      const dur = data.job?.duration ? ` in ${data.job.duration}s` : "";
      showNotification({
        title: "Pipeline Completed",
        message: `<b>${scriptName}</b> finished execution successfully${dur} with exit code 0.`,
        type: "success",
        duration: 6500
      });
      triggerDesktopNotification(
        "✅ Pipeline Completed - KCT Studio",
        `${scriptName} finished execution successfully${dur} (Exit Code: 0). Click to view output.`,
        "success"
      );
      flashDocumentTitle("✅ Job Finished! - KCT Studio");
      playChime("job_completed");
    } else if (lastProcessStatus === "running" && data.status === "error") {
      const scriptName = data.job?.script || "Pipeline Script";
      showNotification({
        title: "Pipeline Failed",
        message: `<b>${scriptName}</b> encountered an error. Check console logs.`,
        type: "error",
        duration: 7500
      });
      triggerDesktopNotification(
        "❌ Pipeline Failed - KCT Studio",
        `${scriptName} encountered an error. Click to view terminal logs.`,
        "error"
      );
      flashDocumentTitle("❌ Job Failed! - KCT Studio");
      playChime("error");
    } else if (lastProcessStatus === "running" && data.status === "stopped") {
      showNotification({
        title: "Process Terminated",
        message: "Pipeline process tree aborted. GPU and file locks cleared.",
        type: "warning",
        duration: 4500
      });
      triggerDesktopNotification(
        "⏹ Process Terminated",
        "Pipeline process was stopped by user. Resources cleared.",
        "warning"
      );
    }
    lastProcessStatus = data.status;
    setProcessStatus(data.status, data.job);
  } else if (data.type === "clear_logs") {
    terminal.innerHTML = "<div class='text-slate-500 italic'>Console cleared.</div>";
  } else if (data.type === "pid") {
    showPid(data.pid);
  }
}

function appendLogLine(entry) {
  const terminal = document.getElementById("terminalOutput");
  const lineDiv = document.createElement("div");
  lineDiv.className = `terminal-line terminal-${entry.stream || "stdout"}`;

  const ts = entry.timestamp ? `<span class="text-slate-500 select-none mr-2">[${entry.timestamp}]</span>` : "";
  lineDiv.innerHTML = `${ts}${escapeHtml(entry.line)}`;

  terminal.appendChild(lineDiv);

  if (document.getElementById("chkAutoScroll").checked) {
    terminal.scrollTop = terminal.scrollHeight;
  }
}

function setProcessStatus(status, job) {
  const badge = document.getElementById("processStatusBadge");
  const dot = document.getElementById("statusDot");
  const btnRun = document.getElementById("btnRunPipeline");
  const btnStop = document.getElementById("btnStopPipeline");

  badge.textContent = status.toUpperCase();
  btnStop.classList.remove("glow-rose");

  if (status === "running") {
    badge.className = "font-bold text-emerald-400";
    dot.className = "w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse";
    btnRun.disabled = true;
    btnRun.classList.add("opacity-50", "cursor-not-allowed");
    btnStop.disabled = false;
    btnStop.classList.remove("opacity-60", "cursor-not-allowed");
    btnStop.classList.add("glow-rose");
    if (job && job.pid) showPid(job.pid);
  } else {
    btnRun.disabled = false;
    btnRun.classList.remove("opacity-50", "cursor-not-allowed");
    btnStop.disabled = true;
    btnStop.classList.add("opacity-60", "cursor-not-allowed");
    hidePid();

    if (status === "completed") {
      badge.className = "font-bold text-emerald-300";
      dot.className = "w-2.5 h-2.5 rounded-full bg-emerald-400";
      loadAssets();
    } else if (status === "error") {
      badge.className = "font-bold text-rose-400";
      dot.className = "w-2.5 h-2.5 rounded-full bg-rose-500";
    } else if (status === "stopped") {
      badge.className = "font-bold text-amber-400";
      dot.className = "w-2.5 h-2.5 rounded-full bg-amber-400";
    } else {
      badge.className = "font-bold text-slate-300";
      dot.className = "w-2.5 h-2.5 rounded-full bg-slate-500";
    }
  }
}

function showPid(pid) {
  const b = document.getElementById("processPidBadge");
  b.innerHTML = `PID: <b class="text-slate-300">${pid}</b>`;
  b.classList.remove("hidden");
}

function hidePid() {
  document.getElementById("processPidBadge").classList.add("hidden");
}

function updateTerminalStatus(text, color) {
  const b = document.getElementById("processStatusBadge");
  b.textContent = text;
}

// ================= 2. PROJECT MANAGEMENT =================
async function loadProjects(targetToSelect = null) {
  try {
    const res = await fetch("/api/projects?include_hidden=false");
    const data = await res.json();
    const select = document.getElementById("projectSelect");
    select.innerHTML = "";

    if (!data.projects || data.projects.length === 0) {
      select.innerHTML = "<option value=''>No visible projects (Open Manage to reveal/add)</option>";
      return;
    }

    const activeToUse = targetToSelect || data.active_project;

    data.projects.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.path;
      opt.textContent = `${p.name} ${!p.exists ? " (Missing Path)" : ""}`;
      const isMatch = activeToUse && (
        p.path.toLowerCase() === activeToUse.toLowerCase() ||
        p.path.replace(/\\/g, "/").toLowerCase() === activeToUse.replace(/\\/g, "/").toLowerCase()
      );
      if (isMatch || (!activeToUse && p.is_active)) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });

    if (activeToUse) {
      select.value = activeToUse;
      switchProject(activeToUse, false);
    }
  } catch (e) {
    console.error("Failed to load projects:", e);
  }
}

async function switchProject(path, notify = true) {
  if (!path) return;
  try {
    const select = document.getElementById("projectSelect");
    if (select && select.value !== path) {
      select.value = path;
    }

    const res = await fetch("/api/projects/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path })
    });
    const data = await res.json();
    if (!res.ok || !data.success || !data.scan) {
      showNotification({
        title: "Project Switch Error",
        message: data.detail || data.error || "Unable to activate selected project.",
        type: "error",
        duration: 5000
      });
      return;
    }

    applyProjectScan(data.scan);
    loadAssets();

    if (notify) {
      showNotification({
        title: "Project Loaded",
        message: `Switched workspace to <b>${data.scan.name || path}</b>`,
        type: "info",
        duration: 3500
      });
    }
  } catch (e) {
    showNotification({
      title: "Project Switch Error",
      message: `${e}`,
      type: "error"
    });
  }
}

// Helper functions for dynamic chapters, sections, parts and scripts
function getAvailableChapters(ch = null) {
  const targetCh = ch || selectedEpisodeObj;
  if (targetCh && targetCh.sub_chapters && targetCh.sub_chapters.length > 0) {
    return targetCh.sub_chapters;
  }
  if (currentProject && currentProject.root_chapters && currentProject.root_chapters.length > 0) {
    return currentProject.root_chapters;
  }
  return [];
}

function updateChapterDropdown(ch = null) {
  const chSelect = document.getElementById("selectChapterTarget");
  if (!chSelect) return;

  const availableChapters = getAvailableChapters(ch);
  if (availableChapters.length > 0) {
    chSelect.innerHTML = "";
    availableChapters.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.arg || `--chapter ${c.chapter_num}`;
      opt.textContent = c.clean_title || c.label || c.name || `Chapter_${c.chapter_num}`;
      chSelect.appendChild(opt);
    });

    const allOpt = document.createElement("option");
    allOpt.value = "--all";
    allOpt.textContent = "All Chapters (--all)";
    chSelect.appendChild(allOpt);

    const statusOpt = document.createElement("option");
    statusOpt.value = "--status";
    statusOpt.textContent = "Audit Status (--status)";
    chSelect.appendChild(statusOpt);

    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = "--None--";
    chSelect.appendChild(noneOpt);

    // Default to first chapter (shows Chapter_1, Section_1, etc.)
    chSelect.value = availableChapters[0].arg || `--chapter ${availableChapters[0].chapter_num}`;
  } else {
    // Flat projects without chapters (e.g. Bible Hidden Secrets Revealed) -> --None--
    chSelect.innerHTML = `<option value="">--None--</option>`;
    chSelect.value = "";
  }
}

function updateScriptDropdown(ch = null) {
  const scriptSelect = document.getElementById("selectScript");
  if (!scriptSelect) return;

  const targetCh = ch || selectedEpisodeObj;
  let detectedScripts = [];
  if (targetCh && targetCh.scripts && targetCh.scripts.length > 0) {
    detectedScripts = [...targetCh.scripts];
    if (currentProject && currentProject.scripts) {
      currentProject.scripts.forEach(rs => {
        if (!detectedScripts.some(s => s.filename === rs.filename)) {
          detectedScripts.push(rs);
        }
      });
    }
  } else if (currentProject && currentProject.scripts) {
    detectedScripts = [...currentProject.scripts];
  }

  // Core 3 requested scripts
  const coreScripts = [
    { id: "generate_reel", filename: "generate_reel.py" },
    { id: "generate_video", filename: "generate_video.py" },
    { id: "generate_image", filename: "generate_image.py" }
  ];

  const scriptOptions = [];

  // 1. Add core scripts
  coreScripts.forEach(cs => {
    let actualFn = cs.filename;
    // Check if project uses plural generate_images.py instead
    if (cs.id === "generate_image" && detectedScripts.some(s => s.filename === "generate_images.py")) {
      actualFn = "generate_images.py";
    }
    const found = detectedScripts.find(s => s.filename === actualFn);
    scriptOptions.push({
      id: cs.id,
      label: cs.id,
      filename: actualFn,
      rel_path: found ? found.rel_path : actualFn,
      existsInProject: Boolean(found)
    });
  });

  // 2. Add other detected pipeline scripts in project (e.g. generate_chapter, combine_chapters)
  detectedScripts.forEach(s => {
    const cleanId = (s.filename || "").replace(/\.py$/i, "");
    if (!scriptOptions.some(opt => opt.id === cleanId || opt.filename === s.filename)) {
      scriptOptions.push({
        id: cleanId,
        label: cleanId,
        filename: s.filename,
        rel_path: s.rel_path || s.filename,
        existsInProject: true
      });
    }
  });

  // Render options in dropdown
  scriptSelect.innerHTML = "";
  scriptOptions.forEach(opt => {
    const el = document.createElement("option");
    el.value = opt.filename;
    el.textContent = opt.label;
    if (opt.rel_path) el.setAttribute("data-rel", opt.rel_path);
    scriptSelect.appendChild(el);
  });

  // 3. Default to whichever script the current project uses
  let defaultVal = "generate_reel.py";
  const hasReel = detectedScripts.some(s => s.filename === "generate_reel.py");
  const hasVideo = detectedScripts.some(s => s.filename === "generate_video.py");
  const hasImage = detectedScripts.some(s => s.filename === "generate_image.py" || s.filename === "generate_images.py");
  const hasChapter = detectedScripts.some(s => s.filename === "generate_chapter.py");

  if (hasReel) {
    defaultVal = "generate_reel.py";
  } else if (hasVideo) {
    defaultVal = "generate_video.py";
  } else if (hasChapter) {
    defaultVal = "generate_chapter.py";
  } else if (hasImage) {
    defaultVal = detectedScripts.find(s => s.filename === "generate_images.py") ? "generate_images.py" : "generate_image.py";
  } else if (detectedScripts.length > 0) {
    defaultVal = detectedScripts[0].filename;
  }

  scriptSelect.value = defaultVal;
  updateCommandPreview();
}

function applyProjectScan(scan) {
  if (!scan) return;
  currentProject = scan;

  // 1. Update Project Name & Path in Left Card
  const nameEl = document.getElementById("projNameText");
  if (nameEl) nameEl.textContent = scan.name || "Custom Project";

  const pathEl = document.getElementById("projPathText");
  if (pathEl) {
    pathEl.textContent = scan.path;
    pathEl.title = scan.path;
  }

  // 2. Update Type Icon
  const iconWrapper = document.getElementById("projIconWrapper");
  if (iconWrapper) {
    const iconName = scan.type === "manhwa" ? "film" : scan.type === "documentary" ? "book-open" : "folder";
    iconWrapper.innerHTML = `<i data-lucide="${iconName}" class="w-4 h-4 text-[#FFE614]"></i>`;
  }

  // 3. Update Metric Chips
  const chCount = scan.total_chapters !== undefined ? scan.total_chapters : (scan.chapters ? scan.chapters.length : 0);
  const renCount = scan.rendered_chapters !== undefined ? scan.rendered_chapters : 0;

  const elStatCh = document.getElementById("statChapters");
  if (elStatCh) elStatCh.textContent = chCount;

  const elStatRen = document.getElementById("statRendered");
  if (elStatRen) elStatRen.textContent = `${renCount}/${chCount}`;

  const elStatSc = document.getElementById("statScenes");
  if (elStatSc) elStatSc.textContent = scan.total_scenes !== null && scan.total_scenes !== undefined ? scan.total_scenes : "--";

  const elStatTurn = document.getElementById("statTurnarounds");
  if (elStatTurn) elStatTurn.textContent = scan.has_turnarounds ? "Ready" : "Missing";

  hasRootChapters = !!scan.has_root_chapters;

  // Reset From / To input textboxes on project scan
  const inputFrom = document.getElementById("inputFromEpisode");
  const inputTo = document.getElementById("inputToEpisode");
  if (inputFrom) inputFrom.value = "";
  if (inputTo) inputTo.value = "";

  // 6. Update Episodes Badge & Render Episodes Tab List
  const epBadge = document.getElementById("episodesCountBadge");
  if (epBadge) {
    epBadge.textContent = scan.chapters ? scan.chapters.length : 0;
  }

  // Auto-select first ungenerated episode as default selection if available
  if (scan.chapters && scan.chapters.length > 0) {
    const firstUngenerated = scan.chapters.find(c => !c.has_video || c.video_count === 0);
    const targetCh = firstUngenerated || scan.chapters[0];
    selectedEpisode = targetCh.name;
    selectedEpisodeNum = targetCh.episode_num;
    selectedEpisodeObj = targetCh;

    const badge = document.getElementById("activeEpisodeFilterBadge");
    const nameEl = document.getElementById("activeEpisodeFilterName");
    if (badge && nameEl) {
      const epNumStr = targetCh.episode_num ? targetCh.episode_num.toString().padStart(2, '0') : "01";
      nameEl.textContent = `#${epNumStr} ${targetCh.clean_title || targetCh.name}`;
      badge.classList.remove("hidden");
      badge.classList.add("flex");
    }
    const btnClear = document.getElementById("btnClearEpisodeFilter");
    if (btnClear) btnClear.classList.remove("hidden");
  } else {
    selectedEpisode = null;
    selectedEpisodeNum = null;
    selectedEpisodeObj = null;
  }

  // Populate Script & Chapter dropdowns based on selected episode or root
  updateScriptDropdown(selectedEpisodeObj);
  updateChapterDropdown(selectedEpisodeObj);

  renderEpisodesList(scan.chapters || []);
  updateCommandPreview();

  lucide.createIcons();
}

// ================= SOCIAL MEDIA & METADATA HELPERS =================
function getSocialSvg(platform, sizeClass = "w-3.5 h-3.5") {
  const p = (platform || "").toLowerCase();
  if (p === "facebook" || p === "fb") {
    return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>`;
  }
  if (p === "youtube" || p === "yt") {
    return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`;
  }
  if (p === "instagram" || p === "inst" || p === "ig") {
    return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>`;
  }
  if (p === "tiktok" || p === "tt") {
    return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="currentColor"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.24 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>`;
  }
  if (p === "x" || p === "twitter") {
    return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`;
  }
  return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>`;
}

function isPlatformPosted(published, platform) {
  if (!published || typeof published !== "object") return false;
  const p = (platform || "").toLowerCase();
  const aliases = {
    facebook: ["facebook", "fb"],
    youtube: ["youtube", "yt"],
    instagram: ["instagram", "inst", "ig"],
    tiktok: ["tiktok", "tt"],
    x: ["x", "twitter"]
  };
  const keysToCheck = aliases[p] || [p];
  for (const key of keysToCheck) {
    const val = published[key];
    if (val) {
      if (typeof val === "boolean" && val) return true;
      if (typeof val === "object" && (val.status === "published" || val.status === "success" || val.posted === true || val.manual === true)) return true;
      if (typeof val === "string" && val.length > 0) return true;
    }
  }
  return false;
}

function getEpisodeSocialStatus(ch) {
  const status = {
    facebook: false,
    youtube: false,
    instagram: false,
    tiktok: false,
    x: false
  };
  if (!allAssets || !Array.isArray(allAssets)) return status;

  for (const a of allAssets) {
    const matches = (
      (a.episode_folder && (a.episode_folder === ch.name || a.episode_folder === ch.rel_path)) ||
      (a.episode_rel_path && (a.episode_rel_path === ch.rel_path || a.episode_rel_path === ch.name)) ||
      (a.episode_num !== undefined && a.episode_num !== null && ch.episode_num !== undefined && ch.episode_num !== null && a.episode_num === ch.episode_num) ||
      (a.rel_path && ch.rel_path && (a.rel_path.startsWith(ch.rel_path + "/") || a.rel_path.includes(ch.name)))
    );

    if (matches && a.published) {
      if (isPlatformPosted(a.published, "facebook")) status.facebook = true;
      if (isPlatformPosted(a.published, "youtube")) status.youtube = true;
      if (isPlatformPosted(a.published, "instagram")) status.instagram = true;
      if (isPlatformPosted(a.published, "tiktok")) status.tiktok = true;
      if (isPlatformPosted(a.published, "x")) status.x = true;
    }
  }
  return status;
}

function renderEpisodeSocialIndicators(status) {
  const platforms = [
    { key: "facebook", name: "Facebook", activeCls: "text-[#1877F2]" },
    { key: "youtube", name: "YouTube", activeCls: "text-red-500" },
    { key: "instagram", name: "Instagram", activeCls: "text-rose-400" },
    { key: "tiktok", name: "TikTok", activeCls: "text-cyan-300" },
    { key: "x", name: "X", activeCls: "text-slate-100" }
  ];

  const iconsHtml = platforms.map(p => {
    const posted = status[p.key];
    const colorCls = posted ? `${p.activeCls} opacity-100 scale-105` : `text-slate-600 opacity-20`;
    return `<span class="${colorCls} transition inline-flex items-center" title="${p.name}: ${posted ? 'Posted' : 'Not posted'}">${getSocialSvg(p.key, 'w-2.5 h-2.5')}</span>`;
  }).join("");

  return `
    <div class="flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-950/60 border border-slate-800/60 shadow-inner" title="Social media posting status for episode">
      ${iconsHtml}
    </div>
  `;
}

function renderSocialBadge(platform, isPosted, relPath = null) {
  const configs = {
    facebook: {
      name: "Facebook",
      activeCls: "text-[#1877F2] bg-[#1877F2]/15 border-[#1877F2]/50 shadow-[0_0_8px_rgba(24,119,242,0.3)]",
      inactiveCls: "text-slate-600 bg-slate-900/40 border-slate-800/40 opacity-25 hover:opacity-75 hover:text-slate-300"
    },
    youtube: {
      name: "YouTube",
      activeCls: "text-red-500 bg-red-500/15 border-red-500/50 shadow-[0_0_8px_rgba(239,68,68,0.3)]",
      inactiveCls: "text-slate-600 bg-slate-900/40 border-slate-800/40 opacity-25 hover:opacity-75 hover:text-slate-300"
    },
    instagram: {
      name: "Instagram",
      activeCls: "text-rose-400 bg-rose-500/15 border-rose-500/50 shadow-[0_0_8px_rgba(244,63,94,0.3)]",
      inactiveCls: "text-slate-600 bg-slate-900/40 border-slate-800/40 opacity-25 hover:opacity-75 hover:text-slate-300"
    },
    tiktok: {
      name: "TikTok",
      activeCls: "text-cyan-300 bg-cyan-500/15 border-cyan-500/50 shadow-[0_0_8px_rgba(6,182,212,0.3)]",
      inactiveCls: "text-slate-600 bg-slate-900/40 border-slate-800/40 opacity-25 hover:opacity-75 hover:text-slate-300"
    },
    x: {
      name: "X",
      activeCls: "text-slate-100 bg-white/15 border-white/40 shadow-[0_0_8px_rgba(255,255,255,0.2)]",
      inactiveCls: "text-slate-600 bg-slate-900/40 border-slate-800/40 opacity-25 hover:opacity-75 hover:text-slate-300"
    }
  };
  const cfg = configs[platform] || configs.facebook;
  const cls = isPosted ? cfg.activeCls : cfg.inactiveCls;
  const svg = getSocialSvg(platform, "w-3.5 h-3.5");
  const title = `${cfg.name}: ${isPosted ? "Posted (click to mark unposted)" : "Not posted (click to mark posted)"}`;
  
  return `
    <button type="button" class="btn-socmed-toggle px-1.5 py-1 rounded border transition flex items-center justify-center cursor-pointer ${cls}" 
            data-platform="${platform}" 
            data-rel="${escapeHtml(relPath || '')}" 
            data-posted="${isPosted ? 'true' : 'false'}" 
            title="${title}">
      ${svg}
    </button>
  `;
}

function updateModalSocialCheckboxes(asset) {
  if (!asset) return;
  const pub = asset.published || {};
  const setCheck = (id, plat) => {
    const el = document.getElementById(id);
    if (el) el.checked = isPlatformPosted(pub, plat);
  };
  setCheck("checkSocmedFb", "facebook");
  setCheck("checkSocmedYt", "youtube");
  setCheck("checkSocmedInst", "instagram");
  setCheck("checkSocmedTt", "tiktok");
  setCheck("checkSocmedX", "x");
}

async function openMetadata(relPath) {
  try {
    const res = await fetch("/api/assets/open_metadata", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rel_path: relPath })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showNotification({
        title: "Metadata Opened",
        message: `Opened <b>${escapeHtml(data.filename || 'metadata.txt')}</b> in editor`,
        type: "info",
        duration: 3500
      });
    } else {
      showNotification({
        title: "Metadata Error",
        message: data.detail || "Failed to open metadata file",
        type: "error",
        duration: 5000
      });
    }
  } catch (err) {
    showNotification({
      title: "Metadata Error",
      message: err.message,
      type: "error"
    });
  }
}

async function toggleSocialStatus(relPath, platform, newStatus) {
  try {
    const res = await fetch("/api/assets/social_toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rel_path: relPath,
        platform: platform,
        posted: newStatus
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      const asset = allAssets.find(a => a.rel_path === relPath);
      if (asset) {
        if (!asset.published) asset.published = {};
        if (newStatus) {
          asset.published[platform] = { status: "published", time: Date.now() / 1000 };
        } else {
          delete asset.published[platform];
        }
      }
      renderAssets(allAssets);
      if (currentProject && currentProject.chapters) {
        renderEpisodesList(currentProject.chapters);
      }
      if (targetAssetForModal && targetAssetForModal.rel_path === relPath) {
        updateModalSocialCheckboxes(targetAssetForModal);
      }
      const platLabel = platform.charAt(0).toUpperCase() + platform.slice(1);
      showNotification({
        title: `${platLabel} Updated`,
        message: newStatus ? `Marked as posted to ${platLabel}` : `Marked as unposted from ${platLabel}`,
        type: newStatus ? "success" : "info",
        duration: 2000
      });
    } else {
      showNotification({
        title: "Social Update Failed",
        message: data.detail || "Could not update social status",
        type: "error"
      });
    }
  } catch (err) {
    showNotification({
      title: "Social Update Error",
      message: err.message,
      type: "error"
    });
  }
}

// ================= NUMBERED EPISODES TAB & CONTROLLER =================
function setupLeftTabs() {
  const tabEpisodes = document.getElementById("tabBtnEpisodes");
  const tabPresets = document.getElementById("tabBtnPresets");
  const viewEpisodes = document.getElementById("tabEpisodesView");
  const viewPresets = document.getElementById("tabPresetsView");

  if (!tabEpisodes || !tabPresets) return;

  tabEpisodes.onclick = () => {
    tabEpisodes.className = "flex-1 py-1.5 px-3 text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 bg-[#FFE614] text-slate-950 shadow";
    tabPresets.className = "flex-1 py-1.5 px-3 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 bg-transparent text-slate-400 hover:text-slate-200 hover:bg-[#181e2b]";
    viewEpisodes.classList.remove("hidden");
    viewPresets.classList.add("hidden");
  };

  tabPresets.onclick = () => {
    tabPresets.className = "flex-1 py-1.5 px-3 text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 bg-[#FFE614] text-slate-950 shadow";
    tabEpisodes.className = "flex-1 py-1.5 px-3 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1.5 bg-transparent text-slate-400 hover:text-slate-200 hover:bg-[#181e2b]";
    viewPresets.classList.remove("hidden");
    viewEpisodes.classList.add("hidden");
  };
}

function renderEpisodesList(chapters) {
  const container = document.getElementById("episodeFolderList");
  const badge = document.getElementById("episodesCountBadge");
  if (!container) return;

  if (badge) {
    badge.textContent = chapters ? chapters.length : 0;
  }

  if (!chapters || chapters.length === 0) {
    container.innerHTML = `
      <div class="py-8 text-center text-slate-500 text-xs">
        <i data-lucide="folder-x" class="w-6 h-6 mx-auto mb-1 opacity-40"></i>
        <p>No numbered episode folders detected.</p>
        <p class="text-[10px] text-slate-600 mt-0.5">Folders must begin with numbers (e.g. 01_..., 1-..., chapter_1).</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  let list = [...chapters];

  // 1. Quick search / filter in episodes
  const searchInput = document.getElementById("inputEpisodeSearch");
  const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
  if (query) {
    list = list.filter(ch =>
      (ch.clean_title && ch.clean_title.toLowerCase().includes(query)) ||
      (ch.name && ch.name.toLowerCase().includes(query)) ||
      (ch.rel_path && ch.rel_path.toLowerCase().includes(query)) ||
      (ch.episode_num !== undefined && ch.episode_num.toString().includes(query))
    );
  }

  // 2. Sort episodes: num_asc (default), num_desc, ungenerated_first, name_asc, name_desc, vids_desc
  const sortMode = currentEpisodeSort || "num_asc";
  list.sort((a, b) => {
    if (sortMode === "num_asc") {
      return (a.episode_num || 0) - (b.episode_num || 0);
    } else if (sortMode === "num_desc") {
      return (b.episode_num || 0) - (a.episode_num || 0);
    } else if (sortMode === "ungenerated_first") {
      const aGen = (a.video_count || 0) > 0 ? 1 : 0;
      const bGen = (b.video_count || 0) > 0 ? 1 : 0;
      if (aGen !== bGen) return aGen - bGen;
      return (a.episode_num || 0) - (b.episode_num || 0);
    } else if (sortMode === "name_asc") {
      return (a.clean_title || a.name).localeCompare(b.clean_title || b.name);
    } else if (sortMode === "name_desc") {
      return (b.clean_title || b.name).localeCompare(a.clean_title || a.name);
    } else if (sortMode === "vids_desc") {
      return (b.video_count || 0) - (a.video_count || 0) || ((a.episode_num || 0) - (b.episode_num || 0));
    }
    return 0;
  });

  if (list.length === 0) {
    container.innerHTML = `
      <div class="py-6 text-center text-slate-500 text-xs">
        <i data-lucide="search-x" class="w-5 h-5 mx-auto mb-1 opacity-40"></i>
        <p>No episodes matching "${escapeHtml(query)}"</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = "";

  let firstUngenerated = null;
  let firstUngeneratedElement = null;

  list.forEach(ch => {
    const item = document.createElement("div");
    const isSelected = selectedEpisode && (selectedEpisode === ch.name || selectedEpisode === ch.rel_path);
    const isUngenerated = !ch.video_count || ch.video_count === 0;
    const isFirstUngenerated = isUngenerated && !firstUngenerated;
    if (isFirstUngenerated) {
      firstUngenerated = ch;
    }

    item.className = `episode-item p-2.5 rounded-lg border transition cursor-pointer flex items-center justify-between gap-2.5 text-xs ${
      isSelected
        ? "bg-[#FFE614]/15 border-[#FFE614] shadow-sm ring-1 ring-[#FFE614]/30"
        : isFirstUngenerated
        ? "bg-[#161b26] border-amber-500/50 hover:bg-[#1e2638] hover:border-amber-400"
        : "bg-[#161b26] border-[#263147] hover:bg-[#1e2638] hover:border-slate-500"
    }`;

    item.setAttribute("data-folder", ch.name);
    item.setAttribute("data-rel", ch.rel_path);
    item.setAttribute("data-epnum", ch.episode_num);
    item.setAttribute("data-title", ch.clean_title || ch.name);

    if (isFirstUngenerated) {
      firstUngeneratedElement = item;
    }

    const epNumStr = ch.episode_num ? ch.episode_num.toString().padStart(2, '0') : "01";
    const displayTitle = ch.clean_title || ch.name;

    item.innerHTML = `
      <div class="flex items-center gap-2.5 min-w-0 flex-1">
        <span class="text-xs font-mono font-bold px-2 py-0.5 rounded ${
          isSelected 
            ? 'bg-[#FFE614] text-slate-950 font-black' 
            : isFirstUngenerated 
            ? 'bg-amber-950/80 text-amber-300 border border-amber-500/50' 
            : 'bg-slate-800 text-[#FFE614] border border-[#FFE614]/30'
        } shrink-0">
          #${epNumStr}
        </span>
        <div class="min-w-0 flex-1">
          <div class="font-bold text-slate-200 truncate ${isSelected ? 'text-[#FFE614]' : isFirstUngenerated ? 'text-amber-200' : ''}" title="${escapeHtml(displayTitle)}">
            ${escapeHtml(displayTitle)}
          </div>
          <div class="text-[10px] text-slate-400 font-mono truncate" title="${escapeHtml(ch.rel_path || ch.name)}">
            ${escapeHtml(ch.rel_path || ch.name)}
          </div>
        </div>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        ${isFirstUngenerated 
          ? `<span class="text-[9px] px-1.5 py-0.5 rounded font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40" title="Next ungenerated video/reel">NEXT</span>` 
          : ''}
        ${renderEpisodeSocialIndicators(getEpisodeSocialStatus(ch))}
        ${ch.video_count > 0 
          ? `<span class="text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 flex items-center gap-1">
               <i data-lucide="play" class="w-2.5 h-2.5 fill-emerald-400"></i> ${ch.video_count}
             </span>`
          : `<span class="text-[10px] px-1.5 py-0.5 rounded font-mono text-slate-500 bg-slate-800/60 border border-slate-700/50">0 vids</span>`
        }
        ${ch.has_audio ? '<i data-lucide="mic" class="w-3 h-3 text-cyan-400 shrink-0" title="Audio voiceover available"></i>' : ''}
        ${ch.has_script ? '<i data-lucide="file-text" class="w-3 h-3 text-amber-400 shrink-0" title="Script / transcript ready"></i>' : ''}
      </div>
    `;

    item.onclick = () => {
      if (selectedEpisode === ch.name || selectedEpisode === ch.rel_path) {
        clearEpisodeFilter();
      } else {
        selectEpisodeFilter(ch);
      }
    };

    container.appendChild(item);
  });

  // Update Jump to Next Ungenerated button in header
  const jumpBtn = document.getElementById("btnJumpToUngenerated");
  const jumpText = document.getElementById("btnJumpToUngeneratedText");
  if (jumpBtn && jumpText) {
    if (firstUngenerated) {
      const epNumStr = firstUngenerated.episode_num ? firstUngenerated.episode_num.toString().padStart(2, '0') : "--";
      jumpText.textContent = `Next: #${epNumStr}`;
      jumpBtn.classList.remove("hidden");
      jumpBtn.onclick = (e) => {
        e.stopPropagation();
        if (firstUngeneratedElement) {
          container.scrollTo({ top: Math.max(0, firstUngeneratedElement.offsetTop - 4), behavior: "smooth" });
        }
      };
    } else {
      jumpBtn.classList.add("hidden");
    }
  }

  // Default line up / scroll to the first ungenerated video/reel (or selected episode)
  setTimeout(() => {
    let targetEl = null;
    if (selectedEpisode) {
      targetEl = container.querySelector(`[data-folder="${selectedEpisode}"], [data-rel="${selectedEpisode}"]`);
    } else if (!query && firstUngeneratedElement) {
      targetEl = firstUngeneratedElement;
    }

    if (targetEl) {
      container.scrollTop = Math.max(0, targetEl.offsetTop - 4);
    }
  }, 40);

  lucide.createIcons();
}

function selectEpisodeFilter(ch) {
  selectedEpisode = ch.name;
  selectedEpisodeNum = ch.episode_num;
  selectedEpisodeObj = ch;

  // Clear From and To textboxes when an episode is explicitly selected
  const inputFrom = document.getElementById("inputFromEpisode");
  const inputTo = document.getElementById("inputToEpisode");
  if (inputFrom) inputFrom.value = "";
  if (inputTo) inputTo.value = "";

  // Update header filter badge
  const badge = document.getElementById("activeEpisodeFilterBadge");
  const nameEl = document.getElementById("activeEpisodeFilterName");
  if (badge && nameEl) {
    const epNumStr = ch.episode_num ? ch.episode_num.toString().padStart(2, '0') : "01";
    nameEl.textContent = `#${epNumStr} ${ch.clean_title || ch.name}`;
    badge.classList.remove("hidden");
    badge.classList.add("flex");
  }

  // Show clear button in left tab
  const btnClear = document.getElementById("btnClearEpisodeFilter");
  if (btnClear) btnClear.classList.remove("hidden");

  // Re-render episode list items with active border
  if (currentProject && currentProject.chapters) {
    renderEpisodesList(currentProject.chapters);
  }

  // Update scripts and chapters for this episode
  updateScriptDropdown(ch);
  updateChapterDropdown(ch);

  // Filter video catalog
  renderAssets(allAssets);

  updateCommandPreview();

  showNotification({
    title: `Episode #${ch.episode_num}`,
    message: `Selected Episode <b>#${ch.episode_num} ${escapeHtml(ch.clean_title || ch.name)}</b>`,
    type: "info",
    duration: 2000
  });
}

function clearEpisodeFilter() {
  selectedEpisode = null;
  selectedEpisodeNum = null;
  selectedEpisodeObj = null;

  // Hide header filter badge
  const badge = document.getElementById("activeEpisodeFilterBadge");
  if (badge) {
    badge.classList.add("hidden");
    badge.classList.remove("flex");
  }

  // Hide clear button in left tab
  const btnClear = document.getElementById("btnClearEpisodeFilter");
  if (btnClear) btnClear.classList.add("hidden");

  // Re-render episode list items
  if (currentProject && currentProject.chapters) {
    renderEpisodesList(currentProject.chapters);
  }

  // Reset script and chapter dropdowns to root level
  updateScriptDropdown(null);
  updateChapterDropdown(null);

  // Re-render video catalog
  renderAssets(allAssets);

  updateCommandPreview();
}

function handleFromToInput() {
  const inputFrom = document.getElementById("inputFromEpisode");
  const inputTo = document.getElementById("inputToEpisode");
  const fromVal = inputFrom ? inputFrom.value.trim() : "";
  const toVal = inputTo ? inputTo.value.trim() : "";
  const chSelect = document.getElementById("selectChapterTarget");

  const availableChapters = getAvailableChapters(selectedEpisodeObj);
  const hasChapters = availableChapters.length > 0;

  if (fromVal || toVal) {
    // If chapters/sections/parts are available:
    // "in case of multiple chapters from and to, chapter dropdown should show 'Chapter_1' and commands should correctly form accordingly"
    if (hasChapters && chSelect) {
      if (!chSelect.value || chSelect.value === "--all" || chSelect.value === "--status") {
        chSelect.value = availableChapters[0].arg || `--chapter ${availableChapters[0].chapter_num}`;
      }
    } else if (chSelect) {
      chSelect.value = "";
    }

    // In flat episode projects without sub-chapters, deselect single episode when range is entered
    if (!hasChapters) {
      selectedEpisode = null;
      selectedEpisodeNum = null;
      selectedEpisodeObj = null;
    }

    // Update header filter badge to show range
    const badge = document.getElementById("activeEpisodeFilterBadge");
    const nameEl = document.getElementById("activeEpisodeFilterName");
    if (badge && nameEl) {
      nameEl.textContent = `Range: #${fromVal || '?'}${toVal ? ' - #' + toVal : ''}`;
      badge.classList.remove("hidden");
      badge.classList.add("flex");
    }
    const btnClear = document.getElementById("btnClearEpisodeFilter");
    if (btnClear) btnClear.classList.remove("hidden");

    if (currentProject && currentProject.chapters) {
      renderEpisodesList(currentProject.chapters);
    }
  } else {
    // Both cleared -> restore default
    if (hasChapters && chSelect) {
      chSelect.value = availableChapters[0].arg || `--chapter ${availableChapters[0].chapter_num}`;
    }
    if (!hasChapters) {
      if (currentProject && currentProject.chapters && currentProject.chapters.length > 0) {
        const firstUngenerated = currentProject.chapters.find(c => !c.has_video || c.video_count === 0);
        const targetCh = firstUngenerated || currentProject.chapters[0];
        selectedEpisode = targetCh.name;
        selectedEpisodeNum = targetCh.episode_num;
        selectedEpisodeObj = targetCh;

        const badge = document.getElementById("activeEpisodeFilterBadge");
        const nameEl = document.getElementById("activeEpisodeFilterName");
        if (badge && nameEl) {
          const epNumStr = targetCh.episode_num ? targetCh.episode_num.toString().padStart(2, '0') : "01";
          nameEl.textContent = `#${epNumStr} ${targetCh.clean_title || targetCh.name}`;
          badge.classList.remove("hidden");
          badge.classList.add("flex");
        }
        const btnClear = document.getElementById("btnClearEpisodeFilter");
        if (btnClear) btnClear.classList.remove("hidden");
        renderEpisodesList(currentProject.chapters);
      } else {
        const badge = document.getElementById("activeEpisodeFilterBadge");
        if (badge) {
          badge.classList.add("hidden");
          badge.classList.remove("flex");
        }
        const btnClear = document.getElementById("btnClearEpisodeFilter");
        if (btnClear) btnClear.classList.add("hidden");
      }
    }
  }

  updateCommandPreview();
}

function getActivePipelineConfig() {
  const scriptSelect = document.getElementById("selectScript");
  const script = scriptSelect ? scriptSelect.value : "";
  const selectedScriptOpt = scriptSelect ? scriptSelect.selectedOptions[0] : null;
  const scriptRelPath = selectedScriptOpt ? selectedScriptOpt.getAttribute("data-rel") : (selectedEpisodeObj && selectedEpisodeObj.rel_path ? `${selectedEpisodeObj.rel_path}/${script}` : script);

  const chSelect = document.getElementById("selectChapterTarget");
  const targetChapter = chSelect ? chSelect.value : "";
  const inputFrom = document.getElementById("inputFromEpisode");
  const inputTo = document.getElementById("inputToEpisode");
  const fromVal = inputFrom ? inputFrom.value.trim() : "";
  const toVal = inputTo ? inputTo.value.trim() : "";
  const chkAds = document.getElementById("checkboxAds");
  const useAds = chkAds ? chkAds.checked : false;

  const availableChapters = getAvailableChapters(selectedEpisodeObj);
  const hasChapters = availableChapters.length > 0;

  const args = [];
  let modeLabel = "Default";

  // 1. Range arguments (--from and --to) takes priority when supplied
  if (fromVal || toVal) {
    modeLabel = `Range #${fromVal || '?'}${toVal ? '-#' + toVal : ''}`;
    if (fromVal) {
      args.push("--from", fromVal);
    }
    if (toVal) {
      args.push("--to", toVal);
    }
  }
  // 2. Or Chapter Scope (when chapters/sections/parts are available)
  else if (hasChapters && targetChapter && targetChapter !== "custom" && targetChapter !== "--None--") {
    if (targetChapter === "--all") {
      modeLabel = "All Chapters";
      args.push("--all");
    } else if (targetChapter === "--status") {
      modeLabel = "Status";
      args.push("--status");
    } else {
      modeLabel = targetChapter;
      args.push(...targetChapter.split(" ").filter(Boolean));
    }
  }
  // 3. Or Single Selected Episode (for flat projects like Bible Hidden Secrets Revealed: --episode 81)
  else if (!hasChapters && selectedEpisodeNum !== null && selectedEpisodeNum !== undefined) {
    modeLabel = `Ep #${selectedEpisodeNum}`;
    args.push("--episode", String(selectedEpisodeNum));
  } else {
    modeLabel = "Default";
  }

  // 4. Ads checkbox
  if (useAds) {
    args.push("--ads");
  }

  return { script, scriptRelPath, args, modeLabel };
}

function updateCommandPreview() {
  const { script, args, modeLabel } = getActivePipelineConfig();
  const badgeEl = document.getElementById("launcherModeBadge");
  if (badgeEl) {
    badgeEl.textContent = modeLabel;
  }

  const cmdInput = document.getElementById("inputCommandLine");
  if (cmdInput) {
    const scriptName = script || "generate_reel.py";
    const cmdStr = `python ${scriptName} ${args.join(" ")}`.trim();
    cmdInput.value = cmdStr;
  }
}

// ================= PROJECT MANAGER MODAL (HIDE / REMOVE SAFE) =================
async function openManageProjectsModal() {
  const modal = document.getElementById("manageProjectsModal");
  modal.classList.remove("hidden");
  await fetchAndRenderProjectsList();
}

function closeManageProjectsModal() {
  document.getElementById("manageProjectsModal").classList.add("hidden");
}

async function fetchAndRenderProjectsList() {
  try {
    const res = await fetch("/api/projects?include_hidden=true");
    const data = await res.json();
    allConfiguredProjects = data.projects || [];
    renderManageProjectsList();
  } catch (e) {
    console.error("Error loading project list:", e);
  }
}

function renderManageProjectsList() {
  const container = document.getElementById("manageProjectsList");
  const query = document.getElementById("inputManageProjectSearch").value.toLowerCase().trim();
  const showHidden = document.getElementById("chkShowHiddenProjects").checked;

  let filtered = allConfiguredProjects;
  if (!showHidden) {
    filtered = filtered.filter(p => !p.hidden);
  }
  if (query) {
    filtered = filtered.filter(p =>
      p.name.toLowerCase().includes(query) ||
      p.path.toLowerCase().includes(query) ||
      p.type.toLowerCase().includes(query)
    );
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="py-10 text-center text-slate-500 text-xs">
        <i data-lucide="folder-x" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
        <p>No projects found matching filters.</p>
        <p class="text-[11px] text-slate-600 mt-1">Check "Show Hidden Projects" or add a new project.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = "";

  filtered.forEach(p => {
    const row = document.createElement("div");
    row.className = "studio-card p-3 flex flex-wrap items-center justify-between gap-3 bg-[#161b26] border border-[#263147]";

    const isCurrentActive = currentProject && currentProject.path.toLowerCase() === p.path.toLowerCase();

    row.innerHTML = `
      <div class="flex items-start gap-3 min-w-0 flex-1">
        <div class="w-9 h-9 rounded-lg bg-[#1e2638] flex items-center justify-center text-cyan-400 shrink-0 border border-[#2b374f]">
          <i data-lucide="${p.type === 'manhwa' ? 'film' : p.type === 'documentary' ? 'book-open' : 'folder'}" class="w-4 h-4"></i>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-bold text-slate-100 text-xs truncate max-w-xs">${escapeHtml(p.name)}</span>
            <span class="text-[10px] px-2 py-0.2 rounded font-mono bg-slate-800 text-slate-400 border border-slate-700 uppercase">${escapeHtml(p.type)}</span>
            ${isCurrentActive ? '<span class="text-[10px] px-2 py-0.2 rounded font-bold font-mono bg-[#FFE614]/20 text-[#FFE614] border border-[#FFE614]/50">ACTIVE</span>' : ''}
            ${p.hidden ? '<span class="text-[10px] px-2 py-0.2 rounded font-mono bg-slate-700/60 text-slate-300 border border-slate-600">HIDDEN</span>' : ''}
            ${!p.exists ? '<span class="text-[10px] px-2 py-0.2 rounded font-mono bg-rose-950/40 text-rose-400 border border-rose-900/50">PATH NOT FOUND</span>' : ''}
          </div>
          <div class="text-[11px] text-slate-400 font-mono truncate max-w-md mt-0.5" title="${p.path}">
            ${p.path}
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center gap-1.5 shrink-0">
        ${!isCurrentActive && p.exists ? `
          <button class="btn-activate-proj px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 rounded text-xs font-semibold transition" data-path="${escapeHtml(p.path)}">
            Select
          </button>
        ` : ''}

        <!-- Edit Project Name & Folder Location -->
        <button class="btn-edit-proj p-1.5 text-slate-400 hover:text-[#FFE614] hover:bg-slate-800 rounded border border-transparent hover:border-[#FFE614]/40 transition text-xs flex items-center gap-1" title="Edit project name or directory path" data-path="${escapeHtml(p.path)}" data-name="${escapeHtml(p.name)}" data-type="${escapeHtml(p.type || 'custom')}">
          <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
          <span class="hidden sm:inline">Edit</span>
        </button>

        <!-- Hide/Unhide Toggle -->
        <button class="btn-toggle-hide-proj p-1.5 ${p.hidden ? 'text-cyan-400 hover:bg-cyan-950/40 border border-cyan-500/40' : 'text-slate-400 hover:text-amber-400 hover:bg-slate-800 border border-transparent'} rounded transition text-xs flex items-center gap-1" title="${p.hidden ? 'Unhide project in main dropdown' : 'Hide project from main dropdown (safe)'}" data-path="${escapeHtml(p.path)}" data-hidden="${p.hidden}">
          <i data-lucide="${p.hidden ? 'eye' : 'eye-off'}" class="w-3.5 h-3.5"></i>
          <span class="hidden sm:inline">${p.hidden ? 'Unhide' : 'Hide'}</span>
        </button>

        <!-- Remove from Studio List (Files Safe) -->
        <button class="btn-remove-proj p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded border border-transparent hover:border-rose-500/40 transition text-xs flex items-center gap-1" title="Unlink from Studio list (Files safe on disk)" data-path="${escapeHtml(p.path)}" data-name="${escapeHtml(p.name)}">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          <span class="hidden sm:inline">Unlink</span>
        </button>
      </div>
    `;

    container.appendChild(row);
  });

  lucide.createIcons();
  attachManageProjectEvents();
}

function attachManageProjectEvents() {
  document.querySelectorAll(".btn-activate-proj").forEach(btn => {
    btn.onclick = async () => {
      const path = btn.getAttribute("data-path");
      await switchProject(path, true);
      closeManageProjectsModal();
      loadProjects(path);
    };
  });

  document.querySelectorAll(".btn-edit-proj").forEach(btn => {
    btn.onclick = () => {
      const path = btn.getAttribute("data-path");
      const name = btn.getAttribute("data-name");
      const type = btn.getAttribute("data-type") || "custom";
      openEditProjectModal(path, name, type);
    };
  });

  document.querySelectorAll(".btn-toggle-hide-proj").forEach(btn => {
    btn.onclick = async () => {
      const path = btn.getAttribute("data-path");
      const isCurrentlyHidden = btn.getAttribute("data-hidden") === "true";
      await toggleHideProject(path, !isCurrentlyHidden);
    };
  });

  document.querySelectorAll(".btn-remove-proj").forEach(btn => {
    btn.onclick = async () => {
      const path = btn.getAttribute("data-path");
      const name = btn.getAttribute("data-name");
      if (confirm(`Unlink "${name}" from KCT Studio?\n\nSafety Guarantee: Your folders and files on disk will NOT be deleted.`)) {
        await removeProjectFromList(name, path);
      }
    };
  });
}

function openEditProjectModal(path, name, type) {
  document.getElementById("editProjectOldPath").value = path;
  document.getElementById("editProjectName").value = name;
  document.getElementById("editProjectPath").value = path;
  document.getElementById("editProjectType").value = type || "custom";
  document.getElementById("editProjectModal").classList.remove("hidden");
}

function closeEditProjectModal() {
  document.getElementById("editProjectModal").classList.add("hidden");
}

async function handleSaveEditProject(e) {
  e.preventDefault();
  const oldPath = document.getElementById("editProjectOldPath").value;
  const name = document.getElementById("editProjectName").value.trim();
  const newPath = document.getElementById("editProjectPath").value.trim();
  const type = document.getElementById("editProjectType").value;

  if (!name || !newPath) {
    showNotification({
      title: "Missing Information",
      message: "Please specify both a project name and folder path.",
      type: "warning"
    });
    return;
  }

  try {
    const res = await fetch("/api/projects/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        old_path: oldPath,
        name: name,
        new_path: newPath,
        type: type
      })
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      showNotification({
        title: "Update Failed",
        message: data.detail || data.error || "Unable to update project.",
        type: "error",
        duration: 5000
      });
      return;
    }

    showNotification({
      title: "Project Updated",
      message: `Saved changes for <b>${escapeHtml(name)}</b>.`,
      type: "success",
      duration: 3500
    });

    closeEditProjectModal();
    await fetchAndRenderProjectsList();
    await loadProjects(newPath);
  } catch (err) {
    showNotification({
      title: "Update Error",
      message: `${err}`,
      type: "error"
    });
  }
}

async function toggleHideProject(path, hiddenState) {
  try {
    const res = await fetch("/api/projects/toggle_hide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, hidden: hiddenState })
    });
    const data = await res.json();
    if (data.success) {
      showNotification({
        title: hiddenState ? "Project Hidden" : "Project Unhidden",
        message: `Project visibility in main dropdown updated. Files on disk are safe.`,
        type: "info",
        duration: 3000
      });
      await fetchAndRenderProjectsList();
      loadProjects();
    }
  } catch (e) {
    showNotification({
      title: "Action Error",
      message: `${e}`,
      type: "error"
    });
  }
}

async function removeProjectFromList(name, path) {
  try {
    const res = await fetch("/api/projects/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path })
    });
    const data = await res.json();
    if (data.success) {
      showNotification({
        title: "Project Unlinked",
        message: `<b>${escapeHtml(name)}</b> was removed from Studio list.<br><span class="text-emerald-400">All folder contents on disk remain untouched.</span>`,
        type: "warning",
        duration: 4500
      });

      await fetchAndRenderProjectsList();
      await loadProjects(data.active_project);
    } else {
      showNotification({
        title: "Remove Error",
        message: data.detail || "Unable to unlink project",
        type: "error"
      });
    }
  } catch (e) {
    showNotification({
      title: "Remove Failed",
      message: `${e}`,
      type: "error"
    });
  }
}

// ================= 3. HARDWARE TELEMETRY =================
function initTelemetry() {
  fetchTelemetry();
  setInterval(fetchTelemetry, 3500);
}

async function fetchTelemetry() {
  try {
    const res = await fetch("/api/system/stats");
    const data = await res.json();

    if (data.gpus && data.gpus.length > 0) {
      const gpu = data.gpus[0];
      document.getElementById("gpuName").textContent = `${gpu.name}:`;
      document.getElementById("gpuVram").textContent = `${gpu.used_mb} / ${gpu.total_mb} MB (${gpu.percent}%)`;
      document.getElementById("gpuTemp").textContent = `${gpu.temperature}°C`;
      document.getElementById("gpuTelemetry").classList.remove("hidden");
    }

    const comfy = data.comfyui;
    const ind = document.getElementById("comfyIndicator");
    const statusText = document.getElementById("comfyStatus");
    if (comfy && comfy.online) {
      if (comfy.busy || comfy.status === "busy") {
        ind.className = "w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_#f59e0b] animate-pulse";
        statusText.textContent = "Busy (Generating) :8188";
        statusText.className = "text-amber-400 font-semibold";
      } else {
        ind.className = "w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]";
        statusText.textContent = "Online :8188";
        statusText.className = "text-emerald-400 font-semibold";
      }
    } else {
      ind.className = "w-2 h-2 rounded-full bg-slate-500";
      statusText.textContent = "Offline";
      statusText.className = "text-slate-400";
    }
  } catch (e) {
    // Silent
  }
}

// ================= 4. PIPELINE EXECUTION =================
async function executePipeline(scriptName, argsList = [], scriptRelPath = null, commandStr = null) {
  if (!commandStr && !scriptName) {
    showNotification({
      title: "Missing Command / Script",
      message: "Please enter a valid command line or select a pipeline script to execute.",
      type: "warning"
    });
    return;
  }

  showNotification({
    title: "Pipeline Dispatched",
    message: commandStr ? `Executing: <b>${commandStr}</b>` : `Executing <b>${scriptName}</b> ${argsList.join(" ")}`,
    type: "info",
    duration: 3500
  });

  try {
    const payload = commandStr
      ? { command_str: commandStr }
      : {
          script_name: scriptName,
          script_rel_path: scriptRelPath,
          args: argsList
        };

    const res = await fetch("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      showNotification({
        title: "Pipeline Launch Error",
        message: data.detail || data.error || "Failed to start subprocess",
        type: "error",
        duration: 6000
      });
    }
  } catch (e) {
    showNotification({
      title: "Launch Failed",
      message: `${e}`,
      type: "error"
    });
  }
}

async function stopPipeline() {
  try {
    const res = await fetch("/api/pipeline/stop", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showNotification({
        title: "Process Terminated",
        message: `Safely killed ${data.killed_processes} process(es). GPU & locks released.`,
        type: "warning",
        duration: 4000
      });
    }
  } catch (e) {
    showNotification({
      title: "Stop Error",
      message: `${e}`,
      type: "error"
    });
  }
}

// ================= 5. ASSET CATALOG & MODERATION =================
async function loadAssets() {
  const showHidden = document.getElementById("chkShowHidden").checked;
  const url = `/api/assets?include_hidden=${showHidden}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    allAssets = data.assets || [];
    renderAssets(allAssets);
    if (currentProject && currentProject.chapters) {
      renderEpisodesList(currentProject.chapters);
    }
  } catch (e) {
    console.error("Failed to load assets:", e);
  }
}

function renderAssets(assets) {
  const grid = document.getElementById("assetGrid");
  const countBadge = document.getElementById("assetCountBadge");
  const search = document.getElementById("inputAssetSearch").value.toLowerCase().trim();

  let filtered = [...assets];

  // 1. Episode / Scope Filter:
  if (selectedEpisode) {
    filtered = filtered.filter(a =>
      a.episode_folder === selectedEpisode ||
      a.episode_rel_path === selectedEpisode ||
      a.rel_path.includes(selectedEpisode)
    );
  } else if (currentFilter === "episodes_default") {
    // By default, only show videos that belong to next-down level numbered folder/episodes
    const hasNumbered = assets.some(a => a.in_numbered_episode);
    if (hasNumbered) {
      filtered = filtered.filter(a => a.in_numbered_episode);
    }
  } else if (currentFilter === "final_master") {
    filtered = filtered.filter(a => a.category === "final_master");
  } else if (currentFilter === "chapter_reel") {
    filtered = filtered.filter(a => a.category === "chapter_reel" || a.in_numbered_episode);
  }
  // If currentFilter === "all", show everything across all folders/levels

  // 2. Status Filter
  if (currentStatusFilter) {
    filtered = filtered.filter(a => a.status === currentStatusFilter);
  }

  // 3. Search Filter
  if (search) {
    filtered = filtered.filter(a =>
      a.filename.toLowerCase().includes(search) ||
      a.chapter_tag.toLowerCase().includes(search) ||
      a.rel_path.toLowerCase().includes(search) ||
      (a.episode_folder && a.episode_folder.toLowerCase().includes(search))
    );
  }

  // 4. Sorting: Date (latest -> oldest default), Date (oldest -> latest), Name (A -> Z), Name (Z -> A)
  const sortMode = currentSort || "date_desc";
  filtered.sort((a, b) => {
    if (sortMode === "date_desc") {
      return (b.modified || 0) - (a.modified || 0);
    } else if (sortMode === "date_asc") {
      return (a.modified || 0) - (b.modified || 0);
    } else if (sortMode === "name_asc") {
      return a.filename.localeCompare(b.filename);
    } else if (sortMode === "name_desc") {
      return b.filename.localeCompare(a.filename);
    }
    return 0;
  });

  countBadge.textContent = `${filtered.length} Video${filtered.length === 1 ? "" : "s"}`;

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-span-2 py-16 text-center text-slate-500">
        <i data-lucide="video-off" class="w-10 h-10 mx-auto mb-2 opacity-40"></i>
        <p class="text-sm font-medium">No video files found matching filters.</p>
        <p class="text-xs text-slate-600 mt-1">Run a pipeline stage to generate chapter or final videos.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  grid.innerHTML = "";

  filtered.forEach(asset => {
    const card = document.createElement("div");
    card.className = "studio-card p-4 flex flex-col justify-between group h-fit self-start";

    let statusClass = "badge-pending";
    let statusIcon = "clock";
    if (asset.status === "approved") {
      statusClass = "badge-approved";
      statusIcon = "check-circle";
    } else if (asset.status === "rejected") {
      statusClass = "badge-rejected";
      statusIcon = "x-circle";
    } else if (asset.hidden) {
      statusClass = "badge-hidden";
      statusIcon = "eye-off";
    }

    const pub = asset.published || {};
    const isMaster = asset.category === "final_master";

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between gap-2 mb-2.5">
          <div class="flex items-center gap-1.5 min-w-0">
            <span class="text-[11px] px-2.5 py-0.5 rounded font-mono font-bold truncate ${isMaster ? "bg-[#FFE614]/20 text-[#FFE614] border border-[#FFE614]/40" : "bg-[#181e2b] text-cyan-400 border border-[#232a3b]"}">
              ${isMaster ? "★ MASTER FINAL STORY" : asset.chapter_tag}
            </span>
            <button class="btn-open-meta px-2 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-[#FFE614] border border-slate-700 text-[11px] font-mono flex items-center gap-1 transition shadow-sm shrink-0 cursor-pointer" title="Open video metadata in Notepad" data-rel="${escapeHtml(asset.rel_path)}">
              <i data-lucide="file-text" class="w-3 h-3 text-[#FFE614]"></i>
              <span>Meta</span>
            </button>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            ${asset.hidden ? `<span class="badge-hidden text-[10px] px-1.5 py-0.5 rounded font-mono">HIDDEN</span>` : ""}
            <span class="${statusClass} text-[11px] px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
              <i data-lucide="${statusIcon}" class="w-3 h-3"></i>
              ${asset.status.toUpperCase()}
            </span>
          </div>
        </div>

        <div class="relative bg-[#0d1017] rounded-lg overflow-hidden aspect-video border border-[#222a36] mb-3 flex items-center justify-center group-hover:border-[#FFE614]/50 transition cursor-pointer btn-preview bg-gradient-to-br from-[#141b27] via-[#0d1017] to-[#182130]" data-rel="${asset.rel_path}">
          <img class="w-full h-full object-cover opacity-85 group-hover:opacity-100 transition duration-200" 
               src="${asset.thumbnail_url || ('/api/thumbnail/' + encodeURI(asset.rel_path))}" 
               loading="lazy" 
               alt="${escapeHtml(asset.filename)}"
               onerror="this.style.display='none'; this.nextElementSibling.classList.remove('hidden');">
          <div class="absolute inset-0 flex flex-col items-center justify-center text-slate-600 group-hover:text-slate-400 transition select-none hidden">
            <i data-lucide="film" class="w-10 h-10 opacity-20 group-hover:opacity-40 transition"></i>
          </div>
          <div class="absolute inset-0 bg-black/25 group-hover:bg-black/10 flex items-center justify-center transition">
            <div class="w-11 h-11 rounded-full bg-[#FFE614]/90 text-slate-950 flex items-center justify-center shadow-[0_0_15px_rgba(255,230,20,0.4)] group-hover:scale-110 group-hover:bg-[#FFE614] transition">
              <i data-lucide="play" class="w-5 h-5 fill-slate-950 ml-0.5"></i>
            </div>
          </div>
          <span class="absolute bottom-2 left-2 text-[10px] font-mono bg-black/70 px-1.5 py-0.5 rounded text-slate-300 border border-slate-700/60">
            ${asset.resolution}
          </span>
          <span class="absolute bottom-2 right-2 text-[10px] font-mono bg-black/80 px-2 py-0.5 rounded text-amber-300 font-bold border border-amber-500/30">
            ${asset.duration}
          </span>
        </div>

        <div class="mb-3">
          <div class="text-xs font-bold text-slate-200 truncate" title="${asset.filename}">${asset.filename}</div>
          <div class="flex items-center gap-3 text-[11px] font-mono text-slate-400 mt-1">
            <span>${asset.resolution}</span>
            <span>•</span>
            <span>${asset.size_mb} MB</span>
            <span>•</span>
            <span>${asset.modified_str}</span>
          </div>
          ${asset.notes ? `<div class="mt-2 text-[11px] text-rose-300/90 bg-rose-950/30 p-1.5 rounded border border-rose-900/40"><b>Notes:</b> ${escapeHtml(asset.notes)}</div>` : ""}
        </div>
      </div>

      <div class="pt-3 border-t border-[#212836] flex items-center justify-between gap-2">
        <div class="flex items-center gap-1" title="Social media posting status (click icon to toggle)">
          ${renderSocialBadge('facebook', isPlatformPosted(pub, 'facebook'), asset.rel_path)}
          ${renderSocialBadge('youtube', isPlatformPosted(pub, 'youtube'), asset.rel_path)}
          ${renderSocialBadge('instagram', isPlatformPosted(pub, 'instagram'), asset.rel_path)}
          ${renderSocialBadge('tiktok', isPlatformPosted(pub, 'tiktok'), asset.rel_path)}
          ${renderSocialBadge('x', isPlatformPosted(pub, 'x'), asset.rel_path)}
        </div>

        <div class="flex items-center gap-1.5">
          <button class="btn-hide p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition" title="${asset.hidden ? "Unhide Video" : "Hide Video"}" data-rel="${asset.rel_path}" data-hidden="${asset.hidden}">
            <i data-lucide="${asset.hidden ? "eye" : "eye-off"}" class="w-3.5 h-3.5"></i>
          </button>

          <button class="btn-regen p-1.5 text-amber-400 hover:text-amber-300 rounded hover:bg-amber-950/30 transition" title="Regenerate this video" data-rel="${asset.rel_path}">
            <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
          </button>

          <button class="btn-reject p-1.5 text-rose-400 hover:text-rose-300 rounded hover:bg-rose-950/30 transition" title="Reject Video" data-rel="${asset.rel_path}">
            <i data-lucide="x-circle" class="w-3.5 h-3.5"></i>
          </button>

          <button class="btn-approve px-2.5 py-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 rounded text-xs font-bold transition flex items-center gap-1 shadow" title="Approve Video & Auto-Publish" data-rel="${asset.rel_path}">
            <i data-lucide="check" class="w-3.5 h-3.5"></i>
            <span>Approve</span>
          </button>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });

  lucide.createIcons();
  attachCardEvents();
}

function attachCardEvents() {
  document.querySelectorAll(".btn-open-meta").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const rel = btn.getAttribute("data-rel");
      if (rel) await openMetadata(rel);
    };
  });

  document.querySelectorAll(".btn-socmed-toggle").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const rel = btn.getAttribute("data-rel");
      const plat = btn.getAttribute("data-platform");
      const posted = btn.getAttribute("data-posted") === "true";
      if (rel && plat) await toggleSocialStatus(rel, plat, !posted);
    };
  });
  document.querySelectorAll(".btn-preview").forEach(btn => {
    btn.onclick = () => {
      const rel = btn.getAttribute("data-rel");
      openVideoModal(rel);
    };
  });

  document.querySelectorAll(".btn-approve").forEach(btn => {
    btn.onclick = async () => {
      const rel = btn.getAttribute("data-rel");
      await updateAssetStatus(rel, "approved");
    };
  });

  document.querySelectorAll(".btn-reject").forEach(btn => {
    btn.onclick = () => {
      targetAssetForReject = btn.getAttribute("data-rel");
      document.getElementById("rejectNotes").value = "";
      document.getElementById("rejectModal").classList.remove("hidden");
    };
  });

  document.querySelectorAll(".btn-regen").forEach(btn => {
    btn.onclick = async () => {
      const rel = btn.getAttribute("data-rel");
      await regenerateAsset(rel);
    };
  });

  document.querySelectorAll(".btn-hide").forEach(btn => {
    btn.onclick = async () => {
      const rel = btn.getAttribute("data-rel");
      const currentHidden = btn.getAttribute("data-hidden") === "true";
      await toggleAssetHide(rel, !currentHidden);
    };
  });
}

// ================= 6. MODALS & API ACTIONS =================
function openVideoModal(relPath) {
  const asset = allAssets.find(a => a.rel_path === relPath);
  if (!asset) return;

  targetAssetForModal = asset;
  document.getElementById("modalVideoTitle").textContent = asset.filename;
  document.getElementById("modalChapterBadge").textContent = asset.chapter_tag;
  document.getElementById("modalRes").innerHTML = `<i data-lucide="monitor" class="w-3.5 h-3.5 inline mr-1"></i>${asset.resolution}`;
  document.getElementById("modalDur").innerHTML = `<i data-lucide="clock" class="w-3.5 h-3.5 inline mr-1"></i>${asset.duration}`;
  document.getElementById("modalSize").innerHTML = `<i data-lucide="hard-drive" class="w-3.5 h-3.5 inline mr-1"></i>${asset.size_mb} MB`;

  const badge = document.getElementById("modalStatusBadge");
  badge.textContent = asset.status.toUpperCase();
  badge.className = `px-2 py-0.5 rounded text-[11px] font-bold ${asset.status === "approved" ? "badge-approved" : asset.status === "rejected" ? "badge-rejected" : "badge-pending"}`;

  const player = document.getElementById("modalVideoPlayer");
  player.poster = asset.thumbnail_url || (`/api/thumbnail/${encodeURI(asset.rel_path)}`);
  player.src = `/api/media/${asset.rel_path}`;
  player.load();
  player.play().catch(() => {});

  updateModalSocialCheckboxes(asset);

  document.getElementById("videoModal").classList.remove("hidden");
  lucide.createIcons();
}

function closeVideoModal() {
  const player = document.getElementById("modalVideoPlayer");
  player.pause();
  player.src = "";
  player.poster = "";
  document.getElementById("videoModal").classList.add("hidden");
  targetAssetForModal = null;
}

async function updateAssetStatus(relPath, status, notes = null) {
  try {
    const res = await fetch("/api/assets/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rel_path: relPath,
        status: status,
        notes: notes,
        auto_publish: true
      })
    });
    const data = await res.json();
    if (data.success) {
      const fileName = relPath.split("/").pop();

      if (status === "approved") {
        const isDryRun = data.social_dispatch?.dry_run !== false;
        showNotification({
          title: "✨ Video Approved & Dispatched",
          message: `<b>${fileName}</b> has been approved.<br>
            <span class="${isDryRun ? 'text-amber-300' : 'text-emerald-400'} font-semibold">
              ${isDryRun ? '🟡 Sandbox Simulated Dispatch' : '🟢 Live Feed Dispatch'}
            </span>`,
          type: isDryRun ? "gold" : "success",
          duration: 6000,
          details: "Automated targets: YouTube, Facebook, TikTok, X"
        });
      } else if (status === "rejected") {
        showNotification({
          title: "Video Rejected",
          message: `<b>${fileName}</b> marked as rejected.<br><span class="text-rose-300">Feedback: "${notes || 'No notes provided'}"</span>`,
          type: "error",
          duration: 4500
        });
      }

      loadAssets();
    }
  } catch (e) {
    showNotification({
      title: "Update Error",
      message: `${e}`,
      type: "error"
    });
  }
}

async function toggleAssetHide(relPath, hidden) {
  try {
    const res = await fetch("/api/assets/hide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rel_path: relPath, hidden: hidden })
    });
    const data = await res.json();
    if (data.success) {
      const fileName = relPath.split("/").pop();
      showNotification({
        title: hidden ? "Asset Hidden" : "Asset Unhidden",
        message: `<b>${fileName}</b> is now ${hidden ? "archived from" : "visible in"} the main catalog.`,
        type: "info",
        duration: 3000
      });
      loadAssets();
    }
  } catch (e) {
    showNotification({
      title: "Hide Error",
      message: `${e}`,
      type: "error"
    });
  }
}

async function regenerateAsset(relPath) {
  const fileName = relPath.split("/").pop();
  showNotification({
    title: "🔄 Regeneration Triggered",
    message: `Re-dispatching pipeline script for <b>${fileName}</b>...`,
    type: "info",
    duration: 4000
  });

  try {
    const res = await fetch("/api/assets/regenerate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rel_path: relPath })
    });
    const data = await res.json();
    if (data.success) {
      loadAssets();
    } else {
      showNotification({
        title: "Regenerate Failed",
        message: data.detail || "Unable to queue script",
        type: "error",
        duration: 5000
      });
    }
  } catch (e) {
    showNotification({
      title: "Regeneration Error",
      message: `${e}`,
      type: "error"
    });
  }
}

// ================= 7. EVENT LISTENERS =================
function setupEventListeners() {
  setupLeftTabs();

  const projSelect = document.getElementById("projectSelect");
  if (projSelect) {
    projSelect.addEventListener("change", (e) => {
      if (e.target.value) switchProject(e.target.value, true);
    });
    projSelect.addEventListener("input", (e) => {
      if (e.target.value) switchProject(e.target.value, true);
    });
    projSelect.onchange = (e) => {
      if (e.target.value) switchProject(e.target.value, true);
    };
  }

  document.getElementById("btnRefreshProject").onclick = () => {
    const current = document.getElementById("projectSelect").value;
    if (current) {
      switchProject(current, true);
      showNotification({
        title: "Project Rescanned",
        message: "Refreshed directories, scripts, and chapter status.",
        type: "info",
        duration: 2500
      });
    }
  };

  // Quick Hide / Remove active project from left card
  document.getElementById("btnQuickHideProject").onclick = async () => {
    if (!currentProject || !currentProject.path) return;
    await toggleHideProject(currentProject.path, true);
  };

  document.getElementById("btnQuickRemoveProject").onclick = async () => {
    if (!currentProject || !currentProject.path) return;
    if (confirm(`Unlink "${currentProject.name}" from KCT Studio?\n\nSafety Guarantee: All folders, videos, and files on disk will NOT be deleted.`)) {
      await removeProjectFromList(currentProject.name, currentProject.path);
    }
  };

  // Project Manager Modal Triggers
  document.getElementById("btnManageProjects").onclick = openManageProjectsModal;
  document.getElementById("btnCloseManageProjectsModal").onclick = closeManageProjectsModal;
  document.getElementById("btnDoneManageProjects").onclick = closeManageProjectsModal;
  document.getElementById("chkShowHiddenProjects").onchange = renderManageProjectsList;
  document.getElementById("inputManageProjectSearch").oninput = renderManageProjectsList;
  document.getElementById("btnOpenAddFromManager").onclick = () => {
    closeManageProjectsModal();
    document.getElementById("addProjectModal").classList.remove("hidden");
  };

  document.querySelectorAll(".preset-btn").forEach(btn => {
    btn.onclick = () => {
      const script = btn.getAttribute("data-script");
      const argsRaw = btn.getAttribute("data-args");
      const args = argsRaw ? argsRaw.split(" ").filter(Boolean) : [];
      executePipeline(script, args);
    };
  });

  // Range & Optional Flag Event Listeners
  const inputFrom = document.getElementById("inputFromEpisode");
  if (inputFrom) {
    inputFrom.addEventListener("input", handleFromToInput);
  }

  const inputTo = document.getElementById("inputToEpisode");
  if (inputTo) {
    inputTo.addEventListener("input", handleFromToInput);
  }

  const chkAds = document.getElementById("checkboxAds");
  if (chkAds) {
    chkAds.addEventListener("change", updateCommandPreview);
  }

  const scriptSelect = document.getElementById("selectScript");
  if (scriptSelect) {
    scriptSelect.addEventListener("change", updateCommandPreview);
  }

  const chSelect = document.getElementById("selectChapterTarget");
  if (chSelect) {
    chSelect.addEventListener("change", () => {
      if (chSelect.value && chSelect.value !== "--None--") {
        const fromEl = document.getElementById("inputFromEpisode");
        const toEl = document.getElementById("inputToEpisode");
        if (fromEl) fromEl.value = "";
        if (toEl) toEl.value = "";
      }
      updateCommandPreview();
    });
  }

  const cmdInput = document.getElementById("inputCommandLine");
  if (cmdInput) {
    cmdInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("btnRunPipeline").click();
      }
    });
  }

  document.getElementById("btnRunPipeline").onclick = () => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then(() => updateNotificationButtonState());
    }

    const cmdLine = document.getElementById("inputCommandLine");
    const rawCmd = cmdLine ? cmdLine.value.trim() : "";
    if (rawCmd) {
      executePipeline(null, [], null, rawCmd);
    } else {
      const { script, scriptRelPath, args } = getActivePipelineConfig();
      if (!script) {
        showNotification({
          title: "Missing Script",
          message: "Please enter a valid command line or select a pipeline script to execute.",
          type: "warning"
        });
        return;
      }
      executePipeline(script, args, scriptRelPath);
    }
  };

  document.getElementById("btnStopPipeline").onclick = () => {
    stopPipeline();
  };

  document.getElementById("btnClearConsole").onclick = async () => {
    await fetch("/api/pipeline/clear_logs", { method: "POST" });
    showNotification({
      title: "Console Cleared",
      message: "Terminal output buffer was wiped.",
      type: "info",
      duration: 2000
    });
  };

  document.getElementById("btnCopyLogs").onclick = () => {
    const terminal = document.getElementById("terminalOutput");
    navigator.clipboard.writeText(terminal.innerText).then(() => {
      showNotification({
        title: "📋 Logs Copied",
        message: "Console output successfully copied to clipboard.",
        type: "success",
        duration: 2500
      });
    });
  };

  document.querySelectorAll(".filter-tab").forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll(".filter-tab").forEach(t => {
        t.className = "filter-tab px-3 py-1 rounded-lg bg-[#181e2b] text-slate-300 hover:bg-[#222a3b]";
      });
      tab.className = "filter-tab active px-3 py-1 rounded-lg bg-[#FFE614] text-slate-950 font-bold";

      currentFilter = tab.getAttribute("data-filter") || "episodes_default";
      currentStatusFilter = tab.getAttribute("data-status") || null;

      // When "All Content" is selected, clear any specific episode focus so user sees all project videos
      if (currentFilter === "all") {
        selectedEpisode = null;
        const badge = document.getElementById("activeEpisodeFilterBadge");
        if (badge) {
          badge.classList.add("hidden");
          badge.classList.remove("flex");
        }
        const btnClear = document.getElementById("btnClearEpisodeFilter");
        if (btnClear) btnClear.classList.add("hidden");
        if (currentProject && currentProject.chapters) {
          renderEpisodesList(currentProject.chapters);
        }
      }

      renderAssets(allAssets);
    };
  });

  // Sort dropdown change listener
  const sortSelect = document.getElementById("selectAssetSort");
  if (sortSelect) {
    sortSelect.onchange = () => {
      currentSort = sortSelect.value;
      renderAssets(allAssets);
    };
  }

  // Clear episode filter buttons
  const btnClearEp = document.getElementById("btnClearEpisodeFilter");
  if (btnClearEp) btnClearEp.onclick = clearEpisodeFilter;

  const btnResetEp = document.getElementById("btnResetEpisodeFilter");
  if (btnResetEp) btnResetEp.onclick = clearEpisodeFilter;

  // Episode sorting & search listeners in Left Tab 1
  const epSortSelect = document.getElementById("selectEpisodeSort");
  if (epSortSelect) {
    epSortSelect.onchange = () => {
      currentEpisodeSort = epSortSelect.value;
      if (currentProject && currentProject.chapters) {
        renderEpisodesList(currentProject.chapters);
      }
    };
  }

  const epSearchInput = document.getElementById("inputEpisodeSearch");
  if (epSearchInput) {
    epSearchInput.oninput = () => {
      if (currentProject && currentProject.chapters) {
        renderEpisodesList(currentProject.chapters);
      }
    };
  }

  // Edit Project Modal Listeners
  const btnCloseEditProj = document.getElementById("btnCloseEditProjectModal");
  if (btnCloseEditProj) btnCloseEditProj.onclick = closeEditProjectModal;

  const btnCancelEditProj = document.getElementById("btnCancelEditProject");
  if (btnCancelEditProj) btnCancelEditProj.onclick = closeEditProjectModal;

  const formEditProj = document.getElementById("formEditProject");
  if (formEditProj) formEditProj.onsubmit = handleSaveEditProject;

  document.getElementById("chkShowHidden").onchange = () => {
    loadAssets();
  };

  document.getElementById("btnRefreshCatalog").onclick = () => {
    loadAssets();
    showNotification({
      title: "Catalog Refreshed",
      message: "Scanned all video files and rendered chapters.",
      type: "info",
      duration: 2500
    });
  };

  document.getElementById("inputAssetSearch").oninput = () => {
    renderAssets(allAssets);
  };

  document.getElementById("btnCloseVideoModal").onclick = closeVideoModal;
  document.getElementById("videoModal").onclick = (e) => {
    if (e.target.id === "videoModal") closeVideoModal();
  };

  const btnModalMeta = document.getElementById("modalBtnOpenMeta");
  if (btnModalMeta) {
    btnModalMeta.onclick = async () => {
      if (targetAssetForModal) {
        await openMetadata(targetAssetForModal.rel_path);
      }
    };
  }

  // Video modal social posted checkboxes
  [
    { id: "checkSocmedFb", plat: "facebook" },
    { id: "checkSocmedYt", plat: "youtube" },
    { id: "checkSocmedInst", plat: "instagram" },
    { id: "checkSocmedTt", plat: "tiktok" },
    { id: "checkSocmedX", plat: "x" }
  ].forEach(({ id, plat }) => {
    const el = document.getElementById(id);
    if (el) {
      el.onchange = async () => {
        if (targetAssetForModal) {
          await toggleSocialStatus(targetAssetForModal.rel_path, plat, el.checked);
        }
      };
    }
  });

  document.getElementById("modalBtnApprove").onclick = async () => {
    if (targetAssetForModal) {
      await updateAssetStatus(targetAssetForModal.rel_path, "approved");
      closeVideoModal();
    }
  };

  document.getElementById("modalBtnReject").onclick = () => {
    if (targetAssetForModal) {
      targetAssetForReject = targetAssetForModal.rel_path;
      closeVideoModal();
      document.getElementById("rejectNotes").value = "";
      document.getElementById("rejectModal").classList.remove("hidden");
    }
  };

  document.getElementById("modalBtnRegen").onclick = async () => {
    if (targetAssetForModal) {
      const rel = targetAssetForModal.rel_path;
      closeVideoModal();
      await regenerateAsset(rel);
    }
  };

  document.getElementById("btnCloseRejectModal").onclick = () => {
    document.getElementById("rejectModal").classList.add("hidden");
  };
  document.getElementById("btnCancelReject").onclick = () => {
    document.getElementById("rejectModal").classList.add("hidden");
  };
  document.getElementById("btnConfirmReject").onclick = async () => {
    if (targetAssetForReject) {
      const notes = document.getElementById("rejectNotes").value.trim();
      await updateAssetStatus(targetAssetForReject, "rejected", notes);
      document.getElementById("rejectModal").classList.add("hidden");
      targetAssetForReject = null;
    }
  };

  document.getElementById("btnAddProject").onclick = () => {
    document.getElementById("addProjectModal").classList.remove("hidden");
  };
  document.getElementById("btnCloseAddProjectModal").onclick = () => {
    document.getElementById("addProjectModal").classList.add("hidden");
  };
  document.getElementById("btnCancelAddProj").onclick = () => {
    document.getElementById("addProjectModal").classList.add("hidden");
  };
  document.getElementById("btnSaveAddProj").onclick = async () => {
    const name = document.getElementById("newProjName").value.trim();
    const path = document.getElementById("newProjPath").value.trim();
    const type = document.getElementById("newProjType").value;

    if (!name || !path) {
      showNotification({
        title: "Validation Error",
        message: "Please provide both a project name and a valid directory path.",
        type: "warning"
      });
      return;
    }

    try {
      const res = await fetch("/api/projects/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name, path: path, type: type })
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById("addProjectModal").classList.add("hidden");
        showNotification({
          title: "Project Added",
          message: `Added and activated <b>${name}</b>`,
          type: "success"
        });
        loadProjects(path);
      } else {
        showNotification({
          title: "Failed to Add Project",
          message: data.detail || "Directory invalid",
          type: "error"
        });
      }
    } catch (e) {
      showNotification({
        title: "Error",
        message: `${e}`,
        type: "error"
      });
    }
  };

  document.getElementById("btnSocialSettings").onclick = async () => {
    try {
      const res = await fetch("/api/social/config");
      const cfg = await res.json();
      document.getElementById("socialDryRun").checked = cfg.dry_run !== false;
      document.getElementById("socialAutoPublish").checked = cfg.auto_publish_on_approve !== false;
      document.getElementById("socialWebhookUrl").value = cfg.webhook_url || "";
      document.getElementById("enableYt").checked = cfg.youtube?.enabled !== false;
      document.getElementById("enableFb").checked = cfg.facebook?.enabled !== false;
      document.getElementById("enableTiktok").checked = cfg.tiktok?.enabled !== false;
      document.getElementById("enableX").checked = cfg.x?.enabled !== false;

      document.getElementById("socialModal").classList.remove("hidden");
    } catch (e) {
      console.error("Failed to load social config:", e);
    }
  };

  document.getElementById("btnCloseSocialModal").onclick = () => {
    document.getElementById("socialModal").classList.add("hidden");
  };
  document.getElementById("btnCancelSocial").onclick = () => {
    document.getElementById("socialModal").classList.add("hidden");
  };
  document.getElementById("btnSaveSocial").onclick = async () => {
    const updateData = {
      dry_run: document.getElementById("socialDryRun").checked,
      auto_publish_on_approve: document.getElementById("socialAutoPublish").checked,
      webhook_url: document.getElementById("socialWebhookUrl").value.trim(),
      youtube: { enabled: document.getElementById("enableYt").checked },
      facebook: { enabled: document.getElementById("enableFb").checked },
      tiktok: { enabled: document.getElementById("enableTiktok").checked },
      x: { enabled: document.getElementById("enableX").checked }
    };

    try {
      await fetch("/api/social/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updateData)
      });
      document.getElementById("socialModal").classList.add("hidden");
      showNotification({
        title: "Settings Saved",
        message: "Social automation presets & webhooks updated successfully.",
        type: "success",
        duration: 3500
      });
    } catch (e) {
      showNotification({
        title: "Save Failed",
        message: `${e}`,
        type: "error"
      });
    }
  };
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
