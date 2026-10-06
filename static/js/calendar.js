// ================= VIDEO POSTING CALENDAR PLANNER =================
// KCT Studio - Multi-Project Automated Social Publishing Calendar

let currentDate = new Date();
let selectedProject = "all";
let activeView = "month"; // "month" | "week" | "queue"
let currentPlatformFilter = "all";
let allProjects = [];
let scheduleData = [];
let activePostDetail = null;

const PLATFORM_ICONS = {
  youtube: { name: "YouTube", icon: "youtube", color: "text-red-500", bg: "bg-red-500/10 border-red-500/30" },
  facebook: { name: "Facebook", icon: "facebook", color: "text-blue-500", bg: "bg-blue-500/10 border-blue-500/30" },
  instagram: { name: "Instagram", icon: "instagram", color: "text-pink-500", bg: "bg-pink-500/10 border-pink-500/30" },
  tiktok: { name: "TikTok", icon: "video", color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/30" },
  x: { name: "X (Twitter)", icon: "twitter", text: "𝕏", color: "text-slate-200", bg: "bg-slate-700/30 border-slate-600/40" }
};

function getSocialSvg(platform, sizeClass = "w-3.5 h-3.5", outline = false) {
  const p = (platform || "").toLowerCase();

  if (outline) {
    if (p === "facebook" || p === "fb") {
      return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>`;
    }
    if (p === "youtube" || p === "yt") {
      return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><path d="m10 15 5-3-5-3z"/></svg>`;
    }
    if (p === "instagram" || p === "inst" || p === "ig") {
      return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>`;
    }
    if (p === "tiktok" || p === "tt") {
      return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5"/></svg>`;
    }
    if (p === "x" || p === "twitter") {
      return `<svg class="${sizeClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4l11.733 16h4.267l-11.733 -16z"/><path d="M4 20l6.768 -6.768m2.46 -2.46l6.772 -6.772"/></svg>`;
    }
  }

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

function formatPostTitle(post) {
  let ep = post.episode_num;
  if (!ep) {
    const raw = `${post.video_rel_path || ''} ${post.video_filename || ''} ${post.title || ''}`;
    const m = raw.match(/(?:reels[/\\]|#|^|\/|_)(\d{1,4})(?:_|\s|-|\.|$)/i);
    if (m) ep = parseInt(m[1], 10);
  }
  const epPrefix = ep ? `#${String(ep).padStart(2, '0')}` : '';
  let cleanTitle = post.title || post.video_filename || '';
  if (ep) {
    cleanTitle = cleanTitle.replace(new RegExp(`^(?:#?\\s*0*${ep}\\s*[-_.:]?\\s*)`, 'i'), '').trim();
  }
  return { epPrefix, title: cleanTitle || post.title || post.video_filename };
}

// ----------------- WEEK-AHEAD STAGING & BUSINESS SUITE STATUS -----------------
const PLAT_NAMES = { youtube: "YouTube", facebook: "Facebook", instagram: "Instagram", tiktok: "TikTok", x: "X" };
const BS_STEP_TEXT = {
  todo: "not scheduled there yet",
  scheduled: "scheduled ✓",
  live: "live ✓",
  missing: "not found on Instagram after 3 days"
};

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// Platforms whose copy is uploaded and waiting on the platform to go live (not posted yet)
function waitingPlatforms(post) {
  return Object.entries(post?.platform_states || {}).filter(([, v]) => v.state === "staged").map(([k]) => k);
}

function platNames(list) {
  return list.map(p => PLAT_NAMES[p] || p).join(" & ");
}

function stageSummaryLines(post) {
  const lines = [];
  const states = post?.platform_states || {};
  const waiting = waitingPlatforms(post);
  if (waiting.length) {
    lines.push({ tone: "text-sky-300", icon: "cloud-check",
      text: `${platNames(waiting)} uploaded. The platform publishes it ${fmtWhen(states[waiting[0]].live_at)}, even if this PC is off.` });
  }
  for (const [p, v] of Object.entries(states)) {
    if (v.state === "stage_failed") {
      lines.push({ tone: "text-amber-300", icon: "cloud-off",
        text: `${PLAT_NAMES[p] || p}: couldn't upload ahead (${v.error}). ${v.gave_up ? "This PC posts it at its time." : "Retrying."}` });
    } else if (v.state === "business_suite") {
      lines.push({ tone: v.step === "missing" ? "text-rose-300" : "text-pink-300", icon: "list-checks",
        text: `${PLAT_NAMES[p] || p}${post.video_rel_path?.includes("/stories/") ? " Story" : ""}: scheduled by hand in Business Suite, ${BS_STEP_TEXT[v.step] || v.step}.` });
    }
  }
  if (post?.video_changed_since_staged) {
    lines.push({ tone: "text-rose-300", icon: "alert-triangle",
      text: "The video changed after it was uploaded. Use Re-stage to replace the waiting copies." });
  }
  return lines;
}

function renderStageSummaryHtml(post) {
  return stageSummaryLines(post).map(l => `
    <div class="flex items-start gap-1.5 ${l.tone}">
      <i data-lucide="${l.icon}" class="w-3 h-3 mt-0.5 shrink-0"></i>
      <span>${escapeHtml(l.text)}</span>
    </div>
  `).join("");
}

// Shows what the server did to copies waiting on platforms (moved, replaced, deleted) after a save or move
function showChangeNotes(data) {
  (data?.notes || []).forEach(n => showCalToast(n, "info"));
  (data?.errors || []).forEach(e => showCalToast(e, "error"));
}

async function movePostToDate(post, targetDateStr) {
  try {
    const res = await fetch(`/api/calendar/schedule/${post.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scheduled_date: targetDateStr,
        scheduled_time: post.scheduled_time || "18:00",
        platforms: post.platforms || ["youtube"],
        force: false
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      const { epPrefix, title } = formatPostTitle(post);
      showCalToast(`📅 Moved ${epPrefix ? epPrefix + ' ' : ''}${title} to ${targetDateStr}`, "success");
      showChangeNotes(data);
      await refreshSchedule();
    } else {
      const errMsg = data.detail || "Cannot move post to that date (daily limit conflict).";
      showCalToast(`⚠️ ${errMsg}`, "error");
    }
  } catch (err) {
    showCalToast(`Error moving post: ${err.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  updatePlatformFilterUI();
  await loadProjects();
  await refreshSchedule();
  lucide.createIcons();
});

// ----------------- TOAST NOTIFICATIONS & AUDIO -----------------
function showCalToast(message, type = "info") {
  const container = document.getElementById("calToastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  const bgCls = type === "success" 
    ? "bg-emerald-950 border-emerald-500/40 text-emerald-200" 
    : type === "error" 
    ? "bg-rose-950 border-rose-500/40 text-rose-200" 
    : "bg-slate-900 border-slate-700 text-slate-200";

  toast.className = `p-3 rounded-xl border shadow-xl flex items-center justify-between gap-3 text-xs pointer-events-auto transition-all duration-300 transform translate-y-2 opacity-0 ${bgCls}`;
  toast.innerHTML = `
    <div class="flex items-center gap-2">
      <i data-lucide="${type === 'success' ? 'check-circle' : type === 'error' ? 'alert-triangle' : 'info'}" class="w-4 h-4 shrink-0"></i>
      <div class="font-medium">${message}</div>
    </div>
  `;

  container.appendChild(toast);
  lucide.createIcons();

  requestAnimationFrame(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  });

  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-y-2");
    setTimeout(() => toast.remove(), 300);
  }, 3500);

  playChime();
}

function playChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.25);
  } catch (e) {}
}

// ----------------- PROJECTS & SCHEDULE LOADING -----------------
async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    const data = await res.json();
    allProjects = data.projects || [];

    const sel = document.getElementById("calProjectSelect");
    const addProjSel = document.getElementById("addPostProjectSelect");

    if (sel) {
      sel.innerHTML = `<option value="all">All Projects</option>`;
      allProjects.forEach(p => {
        if (!p.hidden) {
          const opt = document.createElement("option");
          opt.value = p.path;
          opt.textContent = p.name;
          sel.appendChild(opt);
        }
      });
      if (data.active_project_path) {
        sel.value = data.active_project_path;
        selectedProject = data.active_project_path;
      }
    }

    if (addProjSel) {
      addProjSel.innerHTML = "";
      allProjects.forEach(p => {
        if (!p.hidden) {
          const opt = document.createElement("option");
          opt.value = p.path;
          opt.textContent = p.name;
          addProjSel.appendChild(opt);
        }
      });
      if (data.active_project_path) {
        addProjSel.value = data.active_project_path;
      }
    }
  } catch (e) {
    console.error("Failed to load projects:", e);
  }
}

async function refreshSchedule() {
  try {
    const query = new URLSearchParams();
    if (selectedProject && selectedProject !== "all") {
      query.set("project_path", selectedProject);
    }
    query.set("year", currentDate.getFullYear());
    // For month view, load current month (or allow full year/all)
    const res = await fetch(`/api/calendar/schedule?${query.toString()}`);
    scheduleData = await res.json();
    renderActiveView();
    updateHeaderStats();
  } catch (e) {
    console.error("Failed to refresh schedule:", e);
  }
}

function updateHeaderStats() {
  const schedCount = scheduleData.filter(s => s.status === "scheduled").length;
  const postCount = scheduleData.filter(s => s.status === "posted").length;
  
  const elSched = document.getElementById("statScheduledCount");
  const elPost = document.getElementById("statPostedCount");
  const elQueueBadge = document.getElementById("queueTotalBadge");

  if (elSched) elSched.textContent = schedCount;
  if (elPost) elPost.textContent = postCount;
  if (elQueueBadge) elQueueBadge.textContent = `${schedCount} upcoming`;
}

// ----------------- VIEW SWITCHER & RENDERERS -----------------
function renderActiveView() {
  const vMonth = document.getElementById("viewMonthContainer");
  const vWeek = document.getElementById("viewWeekContainer");
  const vQueue = document.getElementById("viewQueueContainer");

  const btnM = document.getElementById("btnViewMonth");
  const btnW = document.getElementById("btnViewWeek");
  const btnQ = document.getElementById("btnViewQueue");

  const setBtn = (btn, active) => {
    if (active) {
      btn.className = "px-3 py-1 rounded-lg bg-[#FFE614] text-slate-950 font-bold transition shadow-sm";
    } else {
      btn.className = "px-3 py-1 rounded-lg text-slate-400 hover:text-white transition";
    }
  };

  setBtn(btnM, activeView === "month");
  setBtn(btnW, activeView === "week");
  setBtn(btnQ, activeView === "queue");

  if (activeView === "month") {
    vMonth.classList.remove("hidden");
    vWeek.classList.add("hidden");
    vQueue.classList.add("hidden");
    renderMonthView();
  } else if (activeView === "week") {
    vMonth.classList.add("hidden");
    vWeek.classList.remove("hidden");
    vQueue.classList.add("hidden");
    renderWeekView();
  } else if (activeView === "queue") {
    vMonth.classList.add("hidden");
    vWeek.classList.add("hidden");
    vQueue.classList.remove("hidden");
    renderQueueView();
  }
}

// ----------------- MONTH VIEW RENDERER -----------------
function renderMonthView() {
  const grid = document.getElementById("monthGrid");
  const title = document.getElementById("calMonthTitle");
  if (!grid || !title) return;

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];
  title.textContent = `${monthNames[month]} ${year}`;

  grid.innerHTML = "";

  const firstDayIndex = new Date(year, month, 1).getDay(); // 0 is Sunday
  const daysInCurrentMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const totalCells = firstDayIndex + daysInCurrentMonth <= 35 ? 35 : 42;

  for (let i = 0; i < totalCells; i++) {
    const cell = document.createElement("div");

    let cellYear = year;
    let cellMonth = month;
    let cellDay = 0;
    let isCurrentMonth = true;

    if (i < firstDayIndex) {
      // Prev month
      cellDay = daysInPrevMonth - firstDayIndex + i + 1;
      cellMonth = month - 1;
      if (cellMonth < 0) { cellMonth = 11; cellYear--; }
      isCurrentMonth = false;
    } else if (i >= firstDayIndex + daysInCurrentMonth) {
      // Next month
      cellDay = i - (firstDayIndex + daysInCurrentMonth) + 1;
      cellMonth = month + 1;
      if (cellMonth > 11) { cellMonth = 0; cellYear++; }
      isCurrentMonth = false;
    } else {
      // Current month
      cellDay = i - firstDayIndex + 1;
      isCurrentMonth = true;
    }

    const dateStr = `${cellYear}-${String(cellMonth + 1).padStart(2, '0')}-${String(cellDay).padStart(2, '0')}`;
    const isToday = (dateStr === todayStr);
    const isPast = (dateStr < todayStr);

    cell.setAttribute("data-date", dateStr);

    if (isPast) {
      cell.className = "cal-day-cell cal-day-disabled p-2 flex flex-col justify-start border-b border-r border-[#1a2130] relative";
    } else {
      cell.className = "cal-day-cell p-2 flex flex-col justify-start border-b border-r border-[#1a2130] bg-[#0d1017]/70 hover:bg-[#121722] relative group";
      if (!isCurrentMonth) {
        cell.classList.add("opacity-50", "bg-[#090b10]");
      }

      // Drag & Drop Target Handlers on active/future cells
      cell.addEventListener("dragover", (e) => {
        if (!window.draggedPostId) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        cell.classList.add("drag-target-active");
      });

      cell.addEventListener("dragleave", (e) => {
        if (!cell.contains(e.relatedTarget)) {
          cell.classList.remove("drag-target-active");
        }
      });

      cell.addEventListener("drop", async (e) => {
        e.preventDefault();
        cell.classList.remove("drag-target-active");
        const postId = e.dataTransfer.getData("text/plain") || window.draggedPostId;
        if (!postId) return;

        const post = scheduleData.find(p => p.id === postId);
        if (!post || post.scheduled_date === dateStr) return;

        await movePostToDate(post, dateStr);
      });
    }

    if (isToday) {
      cell.classList.add("ring-1", "ring-[#FFE614]/70", "bg-[#FFE614]/5");
    }

    // Cell Header (Day Number + Quick Add Button)
    const headerEl = document.createElement("div");
    headerEl.className = "flex items-center justify-between mb-1.5 w-full";
    headerEl.innerHTML = `
      <div class="flex items-center gap-1">
        <span class="text-xs font-mono ${isToday ? 'px-1.5 py-0.2 bg-[#FFE614] text-slate-950 font-bold rounded' : isPast ? 'text-slate-600 font-normal' : isCurrentMonth ? 'text-slate-300 font-bold' : 'text-slate-600'}">
          ${cellDay}
        </span>
        ${isToday ? `<span class="text-[9px] font-mono text-[#FFE614] font-bold">TODAY</span>` : ''}
      </div>
      ${!isPast ? `
        <button class="btn-quick-add text-slate-600 hover:text-[#FFE614] opacity-0 group-hover:opacity-100 transition p-0.5" title="Schedule post for ${dateStr}" data-date="${dateStr}">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i>
        </button>
      ` : ''}
    `;
    cell.appendChild(headerEl);

    // Filter Posts for this Date
    const dayPosts = scheduleData.filter(item => {
      if (item.scheduled_date !== dateStr) return false;
      if (currentPlatformFilter !== "all") {
        return item.platforms && item.platforms.includes(currentPlatformFilter);
      }
      return true;
    });

    // Posts Container (auto-adjusts row height, no max-height restriction)
    const postsContainer = document.createElement("div");
    postsContainer.className = "space-y-1.5 w-full flex-1 mt-1";

    dayPosts.forEach(post => {
      const card = renderPostCard(post);
      postsContainer.appendChild(card);
    });

    cell.appendChild(postsContainer);
    grid.appendChild(cell);
  }

  // Attach quick-add handlers
  grid.querySelectorAll(".btn-quick-add").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const dt = btn.getAttribute("data-date");
      openAddPostModal(dt);
    };
  });

  lucide.createIcons();
}

// ----------------- WEEK VIEW RENDERER -----------------
function renderWeekView() {
  const header = document.getElementById("weekHeader");
  const grid = document.getElementById("weekGrid");
  const title = document.getElementById("calMonthTitle");
  if (!header || !grid || !title) return;

  grid.innerHTML = "";
  header.innerHTML = "";

  const curr = new Date(currentDate);
  const firstDay = new Date(curr.setDate(curr.getDate() - curr.getDay())); // Sunday of this week

  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  title.textContent = `Week of ${monthNames[firstDay.getMonth()]} ${firstDay.getDate()}, ${firstDay.getFullYear()}`;

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  for (let i = 0; i < 7; i++) {
    const d = new Date(firstDay);
    d.setDate(firstDay.getDate() + i);

    const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const isToday = (dateStr === todayStr);
    const isPast = (dateStr < todayStr);

    const dayName = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][i];

    // Header column
    const hCol = document.createElement("div");
    hCol.className = `py-2 text-center ${isToday ? 'text-[#FFE614] bg-[#FFE614]/10' : isPast ? 'text-slate-600 opacity-40 bg-[#080a10]' : 'text-slate-300'}`;
    hCol.innerHTML = `
      <div class="text-[10px] uppercase font-mono tracking-wider">${dayName}</div>
      <div class="text-sm font-bold mt-0.5">${d.getDate()}</div>
    `;
    header.appendChild(hCol);

    // Body column
    const bCol = document.createElement("div");
    bCol.setAttribute("data-date", dateStr);
    
    if (isPast) {
      bCol.className = "cal-week-col cal-day-disabled p-2 flex flex-col gap-2 min-h-[450px] border-r border-[#1a2130] bg-[#080a10] opacity-35 cursor-not-allowed";
    } else {
      bCol.className = `cal-week-col p-2 flex flex-col gap-2 min-h-[450px] border-r border-[#1a2130] bg-[#0c0f17] transition ${isToday ? 'bg-[#FFE614]/5 ring-1 ring-[#FFE614]/30' : ''}`;

      // Week drag & drop target
      bCol.addEventListener("dragover", (e) => {
        if (!window.draggedPostId) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        bCol.classList.add("drag-target-active");
      });
      bCol.addEventListener("dragleave", (e) => {
        if (!bCol.contains(e.relatedTarget)) {
          bCol.classList.remove("drag-target-active");
        }
      });
      bCol.addEventListener("drop", async (e) => {
        e.preventDefault();
        bCol.classList.remove("drag-target-active");
        const postId = e.dataTransfer.getData("text/plain") || window.draggedPostId;
        if (!postId) return;
        const post = scheduleData.find(p => p.id === postId);
        if (!post || post.scheduled_date === dateStr) return;
        await movePostToDate(post, dateStr);
      });
    }

    const dayPosts = scheduleData.filter(it => {
      if (it.scheduled_date !== dateStr) return false;
      if (currentPlatformFilter !== "all") {
        return it.platforms && it.platforms.includes(currentPlatformFilter);
      }
      return true;
    });
    dayPosts.forEach(post => {
      const card = renderPostCard(post, true);
      bCol.appendChild(card);
    });

    grid.appendChild(bCol);
  }

  lucide.createIcons();
}

// ----------------- QUEUE / AGENDA VIEW RENDERER -----------------
function renderQueueView() {
  const container = document.getElementById("queueList");
  if (!container) return;
  container.innerHTML = "";

  const sorted = [...scheduleData]
    .filter(it => currentPlatformFilter === "all" || (it.platforms && it.platforms.includes(currentPlatformFilter)))
    .sort((a, b) => (a.scheduled_datetime_iso || "").localeCompare(b.scheduled_datetime_iso || ""));

  if (sorted.length === 0) {
    container.innerHTML = `
      <div class="p-8 text-center text-slate-500 border border-dashed border-slate-800 rounded-2xl">
        <i data-lucide="calendar" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
        <p class="text-xs font-semibold">No scheduled video posts in the queue</p>
        <p class="text-[11px] text-slate-600 mt-1">Click "Auto-Schedule Approved" or "Add Post" to plan future video publishing.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  sorted.forEach(post => {
    const item = document.createElement("div");
    const isPosted = post.status === "posted";
    const isFailed = post.status === "failed";

    item.className = `p-3.5 rounded-xl border flex flex-wrap items-center justify-between gap-4 transition ${
      isPosted 
        ? 'bg-emerald-950/20 border-emerald-900/40 text-emerald-300' 
        : isFailed 
        ? 'bg-rose-950/20 border-rose-900/40 text-rose-300' 
        : 'bg-[#141a27] border-[#222b3e] text-slate-200 hover:border-[#FFE614]/40'
    }`;

    // Format readable date and time
    let formattedDate = post.scheduled_date;
    try {
      const [y, m, d] = post.scheduled_date.split("-").map(Number);
      const dt = new Date(y, m - 1, d);
      formattedDate = dt.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    } catch (e) {}

    const qTheme = getProjectTheme(post.project_name || post.project_path);
    const isRetrying = post.status === "retrying";
    item.innerHTML = `
      <div class="flex items-center gap-3.5 min-w-0 flex-1">
        <img src="${post.thumbnail_url}" alt="Thumbnail" class="w-16 h-10 object-cover rounded-lg bg-black border border-slate-800 shrink-0" onerror="this.src='/static/favicon.png';">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
              isPosted ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50' :
              isFailed ? 'bg-rose-900/60 text-rose-300 border border-rose-700/50' :
              isRetrying ? 'bg-amber-900/60 text-amber-300 border border-amber-700/50 animate-pulse' :
              (post.staged || post.pre_uploaded) ? 'bg-sky-950 text-sky-300 border border-sky-700/60 shadow-xs' :
              'bg-cyan-950 text-cyan-300 border border-cyan-800'
            }">
              ${isRetrying ? `RETRYING (${post.retry_count || 1}/3)` : (post.staged || post.pre_uploaded) ? '☁️ STAGED IN CLOUD' : post.status.toUpperCase()}
            </span>
            <span class="inline-flex items-center justify-center w-5 h-5 rounded-md border ${qTheme.badgeCls} shrink-0 select-none shadow-xs" title="Project: ${qTheme.name}">
              <i data-lucide="${qTheme.icon}" class="w-3 h-3 ${qTheme.iconCls}"></i>
            </span>
            <span class="text-xs font-mono text-slate-300 font-semibold truncate">${qTheme.name}</span>
          </div>
          ${(() => {
            const { epPrefix, title } = formatPostTitle(post);
            return `
              <div class="font-bold text-xs text-slate-100 truncate mt-0.5" title="${epPrefix ? epPrefix + ' ' : ''}${title}">
                ${epPrefix ? `<span class="text-amber-400 font-mono font-bold mr-1.5">${epPrefix}</span>` : ''}<span>${title}</span>
              </div>
            `;
          })()}
          <div class="flex items-center gap-2.5 mt-0.5">
            <div class="text-[11px] font-mono text-amber-300 font-bold flex items-center gap-1.5">
              <i data-lucide="clock" class="w-3 h-3 text-amber-400"></i>
              <span>${formattedDate} at ${post.scheduled_time}</span>
            </div>
            ${post.duration ? `
              <span class="text-[9.5px] font-mono font-bold text-slate-300 flex items-center gap-1 bg-slate-900/90 border border-slate-700/60 px-1.5 py-0.5 rounded shrink-0 shadow-xs" title="Video Duration: ${post.duration}">
                <i data-lucide="play" class="w-2 h-2 fill-amber-400 text-amber-400 shrink-0"></i>
                <span>${post.duration}</span>
              </span>
            ` : ''}
          </div>
          ${stageSummaryLines(post).length ? `<div class="mt-1 space-y-0.5 text-[10.5px]">${renderStageSummaryHtml(post)}</div>` : ''}
        </div>
      </div>

      <!-- Platforms & Actions -->
      <div class="flex items-center gap-3 shrink-0">
        <div class="flex items-center gap-1.5">
          ${renderPlatformBadges(post.platforms, post)}
        </div>
        <div class="flex items-center gap-1.5">
          ${!isPosted ? `
            <button class="btn-stage-queue px-2.5 py-1 rounded-lg ${post.staged ? 'bg-cyan-600/40 text-cyan-200 border-cyan-500/60' : 'bg-cyan-600/20 hover:bg-cyan-600 text-cyan-300 hover:text-white border-cyan-500/30'} border text-xs font-bold transition flex items-center gap-1" data-id="${post.id}" title="${post.staged ? 'Re-Stage in Cloud (YouTube, Facebook)' : 'Pre-Upload & Stage to Cloud (YouTube, Facebook)'}">
              <i data-lucide="${post.staged ? 'cloud-check' : 'cloud-upload'}" class="w-3 h-3"></i>
              <span>${post.staged ? 'Staged' : 'Stage'}</span>
            </button>
            <button class="btn-post-now-queue px-2.5 py-1 rounded-lg bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/40 text-xs font-bold transition flex items-center gap-1" data-id="${post.id}" title="Publish Now">
              <i data-lucide="send" class="w-3 h-3"></i>
              <span>Post Now</span>
            </button>
          ` : ''}
          <button class="btn-open-detail p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition" data-id="${post.id}" title="View Details">
            <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
          </button>
          <button class="btn-delete-post p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition" data-id="${post.id}" title="Cancel Post">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `;

    container.appendChild(item);
  });

  attachQueueActions();
  lucide.createIcons();
}

function attachQueueActions() {
  document.querySelectorAll(".btn-open-detail").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      openDetailModal(id);
    };
  });
  document.querySelectorAll(".btn-stage-queue").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-id");
      await executePreUpload(id);
    };
  });
  document.querySelectorAll(".btn-post-now-queue").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-id");
      await executePostNow(id);
    };
  });
  document.querySelectorAll(".btn-delete-post").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-id");
      await executeDeletePost(id);
    };
  });
}

// ----------------- PROJECT THEMES & IDENTIFIERS -----------------
function getProjectTheme(projectNameOrPath) {
  const name = (projectNameOrPath || '').toLowerCase();

  // 1. Curated project themes
  if (name.includes("bible") || name.includes("secrets") || name.includes("bhsr") || name.includes("bhrs")) {
    if (name.includes("youtube") || name.includes("yt")) {
      return {
        name: "BHRS - Youtube",
        icon: "film",
        badgeCls: "bg-red-500/20 border-red-500/50 shadow-[0_0_8px_rgba(239,68,68,0.25)]",
        iconCls: "text-red-400"
      };
    }
    return {
      name: "Bible Hidden Secrets",
      icon: "book-open",
      badgeCls: "bg-purple-500/20 border-purple-500/50 shadow-[0_0_8px_rgba(168,85,247,0.25)]",
      iconCls: "text-purple-300"
    };
  }

  if (name.includes("manhwa") || name.includes("cinema") || name.includes("recap")) {
    if (name.includes("recap")) {
      return {
        name: "Manhwa Recap",
        icon: "fast-forward",
        badgeCls: "bg-emerald-500/20 border-emerald-500/50 shadow-[0_0_8px_rgba(16,185,129,0.25)]",
        iconCls: "text-emerald-300"
      };
    }
    return {
      name: "Manhwa Cinema Lab",
      icon: "clapperboard",
      badgeCls: "bg-cyan-500/20 border-cyan-500/50 shadow-[0_0_8px_rgba(6,182,212,0.25)]",
      iconCls: "text-cyan-300"
    };
  }

  // 2. Deterministic palette for other projects
  const dynamicPalettes = [
    { icon: "sparkles", badgeCls: "bg-amber-500/20 border-amber-500/50 shadow-[0_0_8px_rgba(245,158,11,0.25)]", iconCls: "text-amber-300" },
    { icon: "flame", badgeCls: "bg-rose-500/20 border-rose-500/50 shadow-[0_0_8px_rgba(244,63,94,0.25)]", iconCls: "text-rose-300" },
    { icon: "compass", badgeCls: "bg-indigo-500/20 border-indigo-500/50 shadow-[0_0_8px_rgba(99,102,241,0.25)]", iconCls: "text-indigo-300" },
    { icon: "layers", badgeCls: "bg-teal-500/20 border-teal-500/50 shadow-[0_0_8px_rgba(20,184,166,0.25)]", iconCls: "text-teal-300" },
    { icon: "zap", badgeCls: "bg-orange-500/20 border-orange-500/50 shadow-[0_0_8px_rgba(249,115,22,0.25)]", iconCls: "text-orange-300" },
    { icon: "video", badgeCls: "bg-blue-500/20 border-blue-500/50 shadow-[0_0_8px_rgba(59,130,246,0.25)]", iconCls: "text-blue-300" },
    { icon: "tv", badgeCls: "bg-violet-500/20 border-violet-500/50 shadow-[0_0_8px_rgba(139,92,246,0.25)]", iconCls: "text-violet-300" },
    { icon: "wand-2", badgeCls: "bg-fuchsia-500/20 border-fuchsia-500/50 shadow-[0_0_8px_rgba(217,70,239,0.25)]", iconCls: "text-fuchsia-300" },
    { icon: "play", badgeCls: "bg-lime-500/20 border-lime-500/50 shadow-[0_0_8px_rgba(132,204,22,0.25)]", iconCls: "text-lime-300" }
  ];

  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  const picked = dynamicPalettes[hash % dynamicPalettes.length];

  return {
    name: projectNameOrPath || "Project",
    icon: picked.icon,
    badgeCls: picked.badgeCls,
    iconCls: picked.iconCls
  };
}

// ----------------- POST CARD COMPONENT -----------------
function renderPostCard(post, isExpanded = false) {
  const card = document.createElement("div");
  const isPosted = post.status === "posted";
  const isFailed = post.status === "failed";
  const isRetrying = post.status === "retrying";
  const isDraggable = true;
  const projTheme = getProjectTheme(post.project_name || post.project_path);

  card.className = `cal-card p-2 rounded-xl border text-[11px] select-none cursor-grab active:cursor-grabbing ${
    isPosted 
      ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-200 hover:border-emerald-600' 
      : isFailed 
      ? 'bg-rose-950/40 border-rose-800/50 text-rose-200 hover:border-rose-600' 
      : isRetrying
      ? 'bg-amber-950/40 border-amber-800/50 text-amber-200 hover:border-amber-600'
      : 'bg-[#151c2a] border-[#253248] text-slate-200 hover:border-[#FFE614]/60'
  }`;

  card.setAttribute("data-id", post.id);
  card.setAttribute("data-date", post.scheduled_date);

  if (isDraggable) {
    card.setAttribute("draggable", "true");
    card.addEventListener("dragstart", (e) => {
      e.stopPropagation();
      e.dataTransfer.setData("text/plain", post.id);
      e.dataTransfer.effectAllowed = "move";
      card.classList.add("is-dragging");
      window.draggedPostId = post.id;
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("is-dragging");
      window.draggedPostId = null;
      document.querySelectorAll(".cal-day-cell, .cal-week-col").forEach(c => c.classList.remove("drag-target-active"));
    });
  }

  card.onclick = (e) => {
    if (!card.classList.contains("is-dragging")) {
      openDetailModal(post.id);
    }
  };

  const { epPrefix, title } = formatPostTitle(post);

  card.innerHTML = `
    <!-- Header: Unique Project Color Square Icon + Time + Status -->
    <div class="flex items-center justify-between gap-1.5 mb-1.5">
      <div class="flex items-center gap-1.5 min-w-0">
        <!-- Project Unique Square Icon -->
        <span class="inline-flex items-center justify-center w-5 h-5 rounded-md border ${projTheme.badgeCls} shrink-0 select-none shadow-xs" title="Project: ${projTheme.name || post.project_name || 'Project'}">
          <i data-lucide="${projTheme.icon}" class="w-3 h-3 ${projTheme.iconCls} shrink-0"></i>
        </span>
        <!-- Time -->
        <span class="font-mono font-bold text-[10px] text-amber-300 flex items-center gap-1 shrink-0">
          <i data-lucide="clock" class="w-2.5 h-2.5 text-amber-400"></i>
          <span>${post.scheduled_time}</span>
        </span>
      </div>

      <!-- Status Badge -->
      <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded shrink-0 ${
        isPosted ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
        isFailed ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
        isRetrying ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse' :
        (post.staged || post.pre_uploaded) ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-xs' :
        'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
      }">
        ${isPosted ? 'POSTED' : isRetrying ? `RETRYING (${post.retry_count || 1}/3)` : isFailed ? 'FAILED' : (post.staged || post.pre_uploaded) ? '☁️ STAGED' : 'QUEUED'}
      </span>
    </div>

    <!-- Video Info Row: Thumbnail + Title -->
    <div class="flex items-center gap-1.5 mb-2">
      <img src="${post.thumbnail_url}" alt="" class="w-8 h-5 object-cover rounded bg-black shrink-0 border border-slate-700/60 pointer-events-none" onerror="this.src='/static/favicon.png';">
      <div class="font-bold text-[10.5px] truncate flex-1 text-slate-100" title="${epPrefix ? epPrefix + ' ' : ''}${title}">
        ${epPrefix ? `<span class="text-amber-400 font-mono font-bold mr-1">${epPrefix}</span>` : ''}<span>${title}</span>
      </div>
    </div>

    <!-- Bottom Row: Enlarged Socmed Icons on Left, Video Duration on Right -->
    <div class="flex items-center justify-between gap-1.5 pt-1.5 border-t border-slate-700/40">
      <div class="flex items-center gap-1">
        ${renderPlatformBadges(post.platforms, post)}
      </div>

      ${post.duration ? `
        <span class="text-[9.5px] font-mono font-bold text-slate-300 flex items-center gap-1 bg-slate-900/90 border border-slate-700/60 px-1.5 py-0.5 rounded shrink-0 shadow-xs" title="Video Duration: ${post.duration}">
          <i data-lucide="play" class="w-2 h-2 fill-amber-400 text-amber-400 shrink-0"></i>
          <span>${post.duration}</span>
        </span>
      ` : ''}
    </div>
  `;

  return card;
}

function renderPlatformBadges(platforms, post = null) {
  let targetPlatforms = platforms;
  if (post && post.project_path) {
    // If post is scheduled, dynamically inherit platforms from project if available
    const proj = allProjects.find(p => p.path === post.project_path || (p.path && p.path.toLowerCase() === post.project_path.toLowerCase()));
    if (proj && proj.social_platforms) {
      const enabled = Object.entries(proj.social_platforms).filter(([k, v]) => v === true).map(([k]) => k);
      if (enabled.length > 0 && (!targetPlatforms || targetPlatforms.length === 0 || post.status === 'scheduled')) {
        targetPlatforms = enabled;
      }
    }
  }

  if (!targetPlatforms || targetPlatforms.length === 0) return '';

  const isPostPosted = post && post.status === "posted";

  // Enlarged w-6 h-6 containers with w-3.5 h-3.5 icons for clear visibility
  const configs = {
    youtube: {
      name: "YouTube",
      activeBg: "bg-red-500/20 border-red-500/60 shadow-[0_0_8px_rgba(239,68,68,0.3)]",
      activeColor: "text-red-500",
      disabledBg: "bg-slate-900/80 border-slate-700/80 shadow-xs",
      disabledColor: "text-slate-400 opacity-75 hover:opacity-100",
      svg: (active) => getSocialSvg("youtube", active ? "w-3.5 h-3.5 text-red-500" : "w-3.5 h-3.5 text-slate-400", true)
    },
    facebook: {
      name: "Facebook",
      activeBg: "bg-[#1877F2]/20 border-[#1877F2]/60 shadow-[0_0_8px_rgba(24,119,242,0.3)]",
      activeColor: "text-[#1877F2]",
      disabledBg: "bg-slate-900/80 border-slate-700/80 shadow-xs",
      disabledColor: "text-slate-400 opacity-75 hover:opacity-100",
      svg: (active) => getSocialSvg("facebook", active ? "w-3.5 h-3.5 text-[#1877F2]" : "w-3.5 h-3.5 text-slate-400", true)
    },
    instagram: {
      name: "Instagram",
      activeBg: "bg-rose-500/20 border-rose-500/60 shadow-[0_0_8px_rgba(244,63,94,0.3)]",
      activeColor: "text-rose-400",
      disabledBg: "bg-slate-900/80 border-slate-700/80 shadow-xs",
      disabledColor: "text-slate-400 opacity-75 hover:opacity-100",
      svg: (active) => getSocialSvg("instagram", active ? "w-3.5 h-3.5 text-rose-400" : "w-3.5 h-3.5 text-slate-400", true)
    },
    tiktok: {
      name: "TikTok",
      activeBg: "bg-cyan-500/20 border-cyan-500/60 shadow-[0_0_8px_rgba(6,182,212,0.3)]",
      activeColor: "text-cyan-300",
      disabledBg: "bg-slate-900/80 border-slate-700/80 shadow-xs",
      disabledColor: "text-slate-400 opacity-75 hover:opacity-100",
      svg: (active) => getSocialSvg("tiktok", active ? "w-3.5 h-3.5 text-cyan-300" : "w-3.5 h-3.5 text-slate-400", true)
    },
    x: {
      name: "X",
      activeBg: "bg-white/20 border-white/60 shadow-[0_0_8px_rgba(255,255,255,0.25)]",
      activeColor: "text-slate-100",
      disabledBg: "bg-slate-900/80 border-slate-700/80 shadow-xs",
      disabledColor: "text-slate-400 opacity-75 hover:opacity-100",
      svg: (active) => getSocialSvg("x", active ? "w-3 h-3 text-slate-100" : "w-3 h-3 text-slate-400", true)
    }
  };

  return targetPlatforms.map(p => {
    const key = (p || '').toLowerCase();
    const cfg = configs[key] || {
      name: p,
      activeBg: "bg-slate-700/40 border-slate-500/60",
      activeColor: "text-slate-200",
      disabledBg: "bg-slate-900/80 border-slate-700/80 shadow-xs",
      disabledColor: "text-slate-400 opacity-75 hover:opacity-100",
      svg: () => `<span class="text-[10px] font-bold">${p.toUpperCase()}</span>`
    };

    const st = post?.platform_states?.[key];
    const isWaiting = st?.state === "staged";

    let isSuccess = false;
    const pubList = post?.published_platforms || [];
    if (pubList.includes(key) && !isWaiting) {
      isSuccess = true;
    } else if (isPostPosted) {
      if (post?.dispatch_result?.platforms?.[key]) {
        const pStat = (post.dispatch_result.platforms[key].status || '').toLowerCase();
        isSuccess = pStat === "published" || pStat === "success" || (post.dispatch_result?.dry_run && pStat === "simulated");
      }
    }

    let badgeBg = isSuccess ? cfg.activeBg : cfg.disabledBg;
    const badgeColor = isSuccess ? cfg.activeColor : cfg.disabledColor;
    const statusText = post?.dispatch_result?.platforms?.[key]?.status || (isSuccess ? "posted" : "scheduled");
    let title = isSuccess
      ? `${cfg.name}: Successfully posted`
      : `${cfg.name}: ${statusText === 'queued' ? 'Queued / Not yet posted' : 'Not posted'}`;

    // Corner dot: uploaded and waiting (sky), Business Suite step (pink / green / red), upload-ahead problem (amber)
    let dot = "";
    if (isWaiting) {
      badgeBg = "bg-sky-500/15 border-sky-400/60 shadow-[0_0_8px_rgba(56,189,248,0.25)]";
      dot = "bg-sky-400";
      title = `${cfg.name}: uploaded, goes live ${fmtWhen(st.live_at)} (the platform publishes it, even if this PC is off)`;
    } else if (st?.state === "business_suite") {
      dot = st.step === "missing" ? "bg-rose-400" : (st.step === "todo" ? "bg-pink-400" : "bg-emerald-400");
      title = `${cfg.name}: scheduled by hand in Business Suite, ${BS_STEP_TEXT[st.step] || st.step}`;
    } else if (st?.state === "stage_failed") {
      dot = "bg-amber-400";
      title = `${cfg.name}: couldn't upload ahead (${st.error}). ${st.gave_up ? "This PC posts it at its time." : "Retrying."}`;
    }

    return `
      <span class="relative inline-flex items-center justify-center w-6 h-6 rounded-md border ${badgeBg} ${isWaiting ? cfg.activeColor : badgeColor} transition-all duration-200 shrink-0" title="${escapeHtml(title)}">
        ${cfg.svg(isSuccess || isWaiting)}
        ${dot ? `<span class="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${dot} ring-1 ring-slate-950"></span>` : ''}
      </span>
    `;
  }).join('');
}

function updateAddModalPlatformsForProject(projectPath) {
  if (!projectPath) return;
  const proj = allProjects.find(p => p.path === projectPath || (p.path && p.path.toLowerCase() === projectPath.toLowerCase()));
  const platforms = proj?.social_platforms || {};

  const anyConfigured = Object.keys(platforms).length > 0;

  const setPlat = (id, key, defaultVal = false) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (anyConfigured) {
      el.checked = platforms[key] === true;
    } else {
      el.checked = defaultVal;
    }
  };

  setPlat("addPlatYt", "youtube", true);
  setPlat("addPlatFb", "facebook", false);
  setPlat("addPlatInst", "instagram", false);
  setPlat("addPlatTt", "tiktok", false);
  setPlat("addPlatX", "x", false);

  checkCollisionLive();
}

// ----------------- MODAL: ADD POST -----------------
async function openAddPostModal(defaultDate = null) {
  const modal = document.getElementById("modalAddPost");
  const inputDate = document.getElementById("addPostDate");
  const inputTime = document.getElementById("addPostTime");
  const selProj = document.getElementById("addPostProjectSelect");

  if (!modal) return;

  const targetProj = (selectedProject && selectedProject !== "all") ? selectedProject : (selProj ? selProj.value : null);
  if (selProj && targetProj) {
    selProj.value = targetProj;
  }

  updateAddModalPlatformsForProject(targetProj);

  // Load project defaults
  try {
    const q = targetProj ? `?project_path=${encodeURIComponent(targetProj)}` : '';
    const res = await fetch(`/api/social/config${q}`);
    const cfg = await res.json();
    if (inputTime) inputTime.value = cfg.default_posting_time || "18:00";
  } catch (e) {}

  // Date setup
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  if (inputDate) {
    inputDate.setAttribute("min", todayStr);
  }

  if (defaultDate) {
    if (inputDate) inputDate.value = defaultDate;
  } else {
    // Fetch next available free slot
    try {
      const q = targetProj ? `?project_path=${encodeURIComponent(targetProj)}` : '';
      const sres = await fetch(`/api/calendar/next_slot${q}`);
      const sdata = await sres.json();
      if (inputDate && sdata.date) inputDate.value = sdata.date;
      if (inputTime && sdata.time) inputTime.value = sdata.time;
    } catch (e) {
      if (inputDate) inputDate.value = todayStr;
    }
  }

  await loadUnpostedVideos(targetProj);
  checkCollisionLive();
  modal.classList.remove("hidden");
  lucide.createIcons();
}

async function loadUnpostedVideos(projectPath) {
  const selVideo = document.getElementById("addPostVideoSelect");
  const countEl = document.getElementById("addPostVideoCount");
  if (!selVideo) return;

  selVideo.innerHTML = `<option value="">Loading approved videos...</option>`;
  try {
    const q = projectPath ? `?project_path=${encodeURIComponent(projectPath)}` : '';
    const res = await fetch(`/api/calendar/unposted_approved_videos${q}`);
    const data = await res.json();
    const videos = data.videos || [];

    selVideo.innerHTML = "";
    if (videos.length === 0) {
      selVideo.innerHTML = `<option value="">(No approved unposted videos available)</option>`;
      if (countEl) countEl.textContent = "0 available";
    } else {
      videos.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.rel_path;
        opt.textContent = `${v.chapter_tag || ''} - ${v.clean_title || v.filename}`;
        selVideo.appendChild(opt);
      });
      if (countEl) countEl.textContent = `${videos.length} approved videos ready`;
    }
  } catch (e) {
    selVideo.innerHTML = `<option value="">Failed to load videos</option>`;
  }
}

function getSelectedPlatformsInAddModal() {
  const plats = [];
  if (document.getElementById("addPlatYt")?.checked) plats.push("youtube");
  if (document.getElementById("addPlatFb")?.checked) plats.push("facebook");
  if (document.getElementById("addPlatInst")?.checked) plats.push("instagram");
  if (document.getElementById("addPlatTt")?.checked) plats.push("tiktok");
  if (document.getElementById("addPlatX")?.checked) plats.push("x");
  return plats;
}

function checkCollisionLive() {
  const inputDate = document.getElementById("addPostDate")?.value;
  const selProj = document.getElementById("addPostProjectSelect")?.value;
  const alertEl = document.getElementById("addPostCollisionAlert");
  const alertText = document.getElementById("addPostCollisionText");
  const submitBtn = document.getElementById("btnSubmitAddPost");

  if (!inputDate || !selProj || !alertEl || !alertText) return;

  const plats = getSelectedPlatformsInAddModal();
  const conflicts = [];

  scheduleData.forEach(it => {
    if (it.scheduled_date === inputDate && it.status !== "failed" && it.status !== "cancelled") {
      it.platforms.forEach(p => {
        if (plats.includes(p)) {
          conflicts.push(`${p.toUpperCase()} (${it.title || it.video_filename})`);
        }
      });
    }
  });

  if (conflicts.length > 0) {
    alertEl.classList.remove("hidden");
    alertText.innerHTML = `<b>Same-Day Schedule:</b> ${inputDate} already has scheduled posts for: ${conflicts.join(", ")}. This video will be scheduled as an additional post on this date.`;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  } else {
    alertEl.classList.add("hidden");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }
}

async function submitAddPost() {
  const projPath = document.getElementById("addPostProjectSelect")?.value;
  const videoRel = document.getElementById("addPostVideoSelect")?.value;
  const sDate = document.getElementById("addPostDate")?.value;
  const sTime = document.getElementById("addPostTime")?.value;
  const plats = getSelectedPlatformsInAddModal();

  if (!projPath || !videoRel || !sDate || !sTime) {
    showCalToast("Please complete all required schedule fields.", "error");
    return;
  }
  if (plats.length === 0) {
    showCalToast("Select at least one platform to publish to.", "error");
    return;
  }

  const btn = document.getElementById("btnSubmitAddPost");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Scheduling...";
  }

  try {
    const res = await fetch("/api/calendar/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_path: projPath,
        video_rel_path: videoRel,
        scheduled_date: sDate,
        scheduled_time: sTime,
        platforms: plats
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      document.getElementById("modalAddPost").classList.add("hidden");
      showCalToast(`Scheduled <b>${data.entry.title}</b> for ${sDate} at ${sTime}`, "success");
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Failed to schedule video post", "error");
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Schedule Post";
    }
  }
}

// ----------------- MODAL: POST DETAIL / EDIT -----------------
let activeModalPlatforms = new Set();

function openDetailModal(postId) {
  const post = scheduleData.find(p => p.id === postId);
  if (!post) return;
  activePostDetail = post;

  // Published platforms for this post
  const publishedPlatforms = post.published_platforms || [];
  if (post.dispatch_result && post.dispatch_result.platforms) {
    for (const [k, v] of Object.entries(post.dispatch_result.platforms)) {
      const st = (v.status || '').toLowerCase();
      if ((st === 'published' || st === 'success') && !publishedPlatforms.includes(k)) {
        publishedPlatforms.push(k);
      }
    }
  }

  // Candidate platforms for this post
  let candidatePlatforms = post.platforms && post.platforms.length > 0 ? [...post.platforms] : [];
  if (candidatePlatforms.length === 0 && post.project_path) {
    const proj = allProjects.find(p => p.path === post.project_path || (p.path && p.path.toLowerCase() === post.project_path.toLowerCase()));
    if (proj && proj.social_platforms) {
      candidatePlatforms = Object.entries(proj.social_platforms).filter(([k, v]) => v === true).map(([k]) => k);
    }
  }
  if (candidatePlatforms.length === 0) {
    candidatePlatforms = ["youtube"];
  }

  // Rule: Socmed icons outlined should ONLY be enabled by default if NOT posted to that platform.
  // A copy uploaded and waiting to go live is not posted yet, so it stays ticked (un-ticking it deletes that copy).
  const waiting = waitingPlatforms(post);
  const unpostedPlatforms = candidatePlatforms.filter(p => !publishedPlatforms.includes(p) || waiting.includes(p));
  activeModalPlatforms = new Set(unpostedPlatforms);

  const stageInfo = document.getElementById("detailStageInfo");
  if (stageInfo) {
    const html = renderStageSummaryHtml(post);
    stageInfo.innerHTML = html;
    stageInfo.classList.toggle("hidden", !html);
  }

  const modal = document.getElementById("modalPostDetail");
  const badgeStatus = document.getElementById("detailStatusBadge");
  const badgeProject = document.getElementById("detailProjectBadge");
  const imgThumb = document.getElementById("detailThumb");
  const elTitle = document.getElementById("detailTitle");
  const elFile = document.getElementById("detailFile");
  const elPlatforms = document.getElementById("detailPlatforms");
  const inputDate = document.getElementById("detailEditDate");
  const inputTime = document.getElementById("detailEditTime");
  const boxResult = document.getElementById("detailResultBox");
  const textResult = document.getElementById("detailResultText");

  if (badgeStatus) {
    const isRetrying = post.status === 'retrying';
    const isStaged = post.staged || post.pre_uploaded;
    badgeStatus.textContent = isRetrying ? `RETRYING (${post.retry_count || 1}/3)` : isStaged ? '☁️ STAGED IN CLOUD' : (post.status || 'scheduled').toUpperCase();
    badgeStatus.className = `text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase ${
      post.status === 'posted' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
      post.status === 'failed' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
      isRetrying ? 'bg-amber-950 text-amber-300 border border-amber-800 animate-pulse' :
      isStaged ? 'bg-sky-950 text-sky-300 border border-sky-700/80 shadow-xs' :
      'bg-cyan-950 text-cyan-400 border border-cyan-800'
    }`;
  }
  const dTheme = getProjectTheme(post.project_name || post.project_path);
  if (badgeProject) {
    badgeProject.className = "flex items-center gap-1.5 min-w-0";
    badgeProject.innerHTML = `
      <span class="inline-flex items-center justify-center w-5 h-5 rounded-md border ${dTheme.badgeCls} shrink-0 select-none shadow-xs" title="Project: ${dTheme.name}">
        <i data-lucide="${dTheme.icon}" class="w-3 h-3 ${dTheme.iconCls}"></i>
      </span>
      <span class="text-xs font-mono text-slate-300 font-bold truncate">${dTheme.name}</span>
    `;
  }
  if (imgThumb) imgThumb.src = post.thumbnail_url;
  const { epPrefix, title } = formatPostTitle(post);
  if (elTitle) {
    elTitle.innerHTML = `${epPrefix ? `<span class="text-amber-400 font-mono font-bold mr-1.5">${epPrefix}</span>` : ''}<span>${title}</span>`;
  }
  if (elFile) {
    elFile.innerHTML = `
      <div class="flex items-center justify-between gap-2">
        <span class="truncate">${post.video_rel_path}</span>
        ${post.duration ? `
          <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700/70 text-slate-200 font-mono text-[10px] font-bold shrink-0">
            <i data-lucide="play" class="w-2 h-2 fill-amber-400 text-amber-400"></i>
            <span>${post.duration}</span>
          </span>
        ` : ''}
      </div>
    `;
  }
  if (elPlatforms) {
    const displayList = activeModalPlatforms.size > 0 ? Array.from(activeModalPlatforms) : (post.platforms || ["youtube"]);
    elPlatforms.innerHTML = renderPlatformBadges(displayList, post);
  }
  if (inputDate) {
    inputDate.value = post.scheduled_date;
    const today = new Date();
    inputDate.setAttribute("min", `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`);
  }
  if (inputTime) inputTime.value = post.scheduled_time;

  if (boxResult && textResult) {
    if (post.dispatch_result || post.error || post.next_retry_at) {
      boxResult.classList.remove("hidden");
      const details = {};
      if (post.status === "retrying") {
        details.retry_status = `Retrying (Attempt ${post.retry_count || 1}/3)`;
        details.next_retry_at = post.next_retry_at;
      }
      if (post.error) details.error = post.error;
      if (post.retry_history && post.retry_history.length > 0) details.retry_history = post.retry_history;
      if (post.dispatch_result) details.dispatch_result = post.dispatch_result;
      textResult.textContent = JSON.stringify(details, null, 2);
    } else {
      boxResult.classList.add("hidden");
    }
  }

  const btnMarkStatus = document.getElementById("btnMarkStatus");
  if (btnMarkStatus) {
    if (post.status === "posted") {
      btnMarkStatus.className = "px-2.5 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold transition flex items-center gap-1 shrink-0";
      btnMarkStatus.title = "Mark this video as Scheduled (Unposted)";
      btnMarkStatus.innerHTML = `<i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i><span id="btnMarkStatusLabel">Mark Scheduled</span>`;
    } else {
      btnMarkStatus.className = "px-2.5 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold transition flex items-center gap-1 shrink-0";
      btnMarkStatus.title = "Manually mark this video as Posted";
      btnMarkStatus.innerHTML = `<i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i><span id="btnMarkStatusLabel">Mark Posted</span>`;
    }
  }

  renderDetailPlatformToggles();

  modal.classList.remove("hidden");
  lucide.createIcons();
}

function renderDetailPlatformToggles() {
  const container = document.getElementById("detailPlatformToggles");
  if (!container || !activePostDetail) return;

  const publishedPlatforms = activePostDetail.published_platforms || [];

  const platformsList = [
    { 
      key: "youtube", 
      name: "YouTube", 
      activeBg: "bg-red-500/20 border-red-500/60 shadow-[0_0_8px_rgba(239,68,68,0.25)]", 
      svg: (act) => getSocialSvg("youtube", act ? "w-4 h-4 text-red-500" : "w-4 h-4 text-slate-400", true) 
    },
    { 
      key: "facebook", 
      name: "Facebook", 
      activeBg: "bg-[#1877F2]/20 border-[#1877F2]/60 shadow-[0_0_8px_rgba(24,119,242,0.25)]", 
      svg: (act) => getSocialSvg("facebook", act ? "w-4 h-4 text-[#1877F2]" : "w-4 h-4 text-slate-400", true) 
    },
    { 
      key: "instagram", 
      name: "Instagram", 
      activeBg: "bg-rose-500/20 border-rose-500/60 shadow-[0_0_8px_rgba(244,63,94,0.25)]", 
      svg: (act) => getSocialSvg("instagram", act ? "w-4 h-4 text-rose-400" : "w-4 h-4 text-slate-400", true) 
    },
    { 
      key: "tiktok", 
      name: "TikTok", 
      activeBg: "bg-cyan-500/20 border-cyan-500/60 shadow-[0_0_8px_rgba(6,182,212,0.25)]", 
      svg: (act) => getSocialSvg("tiktok", act ? "w-4 h-4 text-cyan-300" : "w-4 h-4 text-slate-400", true) 
    },
    { 
      key: "x", 
      name: "X", 
      activeBg: "bg-white/20 border-white/60 shadow-[0_0_8px_rgba(255,255,255,0.25)]", 
      svg: (act) => getSocialSvg("x", act ? "w-3.5 h-3.5 text-slate-100" : "w-3.5 h-3.5 text-slate-400", true) 
    },
  ];

  const waiting = waitingPlatforms(activePostDetail);

  container.innerHTML = platformsList.map(p => {
    const isSelected = activeModalPlatforms.has(p.key);
    const isWaiting = waiting.includes(p.key);
    const isPublished = publishedPlatforms.includes(p.key) && !isWaiting;

    const btnClass = isSelected
      ? `relative p-1.5 rounded-lg border cursor-pointer transition ${p.activeBg} hover:brightness-110`
      : isPublished
      ? `relative p-1.5 rounded-lg border border-slate-700/80 bg-slate-900/80 text-slate-400 opacity-60 hover:opacity-100 hover:border-slate-500 cursor-pointer transition`
      : `relative p-1.5 rounded-lg border border-slate-800 bg-slate-950/60 text-slate-500 opacity-40 hover:opacity-80 hover:border-slate-600 cursor-pointer transition`;

    const checkmarkHtml = isSelected
      ? `<span class="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 text-slate-950 flex items-center justify-center text-[9px] font-black shadow-sm leading-none select-none">✓</span>`
      : ``;

    const statusBadgeHtml = isPublished
      ? `<span class="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 ring-1 ring-slate-950" title="Already posted on ${p.name}"></span>`
      : ``;

    const tooltip = isWaiting
      ? `${p.name}: uploaded, waiting to go live. ${isSelected ? 'Un-ticking it and saving deletes that copy' : 'Will be deleted when you save (click to keep it)'}`
      : isPublished
      ? `${p.name}: Already published. ${isSelected ? 'Selected to REPOST (Click to disable)' : 'Not selected (Click to enable repost)'}`
      : `${p.name}: ${isSelected ? 'Selected to post (Click to disable)' : 'Not selected (Click to enable)'}`;

    return `
      <button type="button" data-plat="${p.key}" class="detail-plat-toggle-btn ${btnClass}" title="${tooltip}">
        ${p.svg(isSelected)}
        ${checkmarkHtml}
        ${statusBadgeHtml}
      </button>
    `;
  }).join('');

  container.querySelectorAll(".detail-plat-toggle-btn").forEach(btn => {
    btn.onclick = (e) => {
      e.preventDefault();
      const platKey = btn.getAttribute("data-plat");
      if (activeModalPlatforms.has(platKey)) {
        activeModalPlatforms.delete(platKey);
      } else {
        activeModalPlatforms.add(platKey);
      }
      renderDetailPlatformToggles();
    };
  });

  updateDetailModalUI();
}

function updateDetailModalUI() {
  if (!activePostDetail) return;
  const waiting = waitingPlatforms(activePostDetail);
  const publishedPlatforms = (activePostDetail.published_platforms || []).filter(p => !waiting.includes(p));
  const selectedList = Array.from(activeModalPlatforms);

  const elPlatforms = document.getElementById("detailPlatforms");
  if (elPlatforms) {
    const displayList = selectedList.length > 0 ? selectedList : (activePostDetail.platforms || ["youtube"]);
    elPlatforms.innerHTML = renderPlatformBadges(displayList, activePostDetail);
  }

  const btnPostNow = document.getElementById("btnPostNow");
  if (btnPostNow) {
    if (selectedList.length === 0) {
      btnPostNow.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i><span>Post Now</span>`;
      btnPostNow.className = "px-3.5 py-1.5 bg-slate-800/80 text-slate-500 border border-slate-700/50 rounded-xl text-xs font-bold transition flex items-center gap-1 cursor-not-allowed opacity-60";
      btnPostNow.title = "Select one or more platforms above to post or repost";
      btnPostNow.disabled = true;
    } else {
      btnPostNow.disabled = false;
      const isAllPublished = selectedList.length > 0 && selectedList.every(p => publishedPlatforms.includes(p));
      const isRepost = isAllPublished;

      if (isRepost) {
        btnPostNow.innerHTML = `<i data-lucide="repeat" class="w-3.5 h-3.5"></i><span>Repost Now</span>`;
        btnPostNow.className = "px-3.5 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1 shadow cursor-pointer";
        btnPostNow.title = `Re-publish video to selected platform(s): ${selectedList.join(', ')}`;
      } else {
        btnPostNow.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i><span>Post Now</span>`;
        btnPostNow.className = "px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1 shadow cursor-pointer";
        btnPostNow.title = `Publish video to unposted platform(s): ${selectedList.filter(p => !publishedPlatforms.includes(p)).join(', ')}`;
      }
    }
  }

  const btnPreUpload = document.getElementById("btnPreUpload");
  if (btnPreUpload) {
    const isPosted = activePostDetail.status === "posted";
    const schedulableSelected = selectedList.filter(p => ["youtube", "facebook"].includes(p));

    if (isPosted) {
      btnPreUpload.classList.add("hidden");
    } else {
      btnPreUpload.classList.remove("hidden");
      if (schedulableSelected.length === 0) {
        btnPreUpload.innerHTML = `<i data-lucide="cloud-upload" class="w-3.5 h-3.5"></i><span>Stage in Cloud</span>`;
        btnPreUpload.className = "px-3.5 py-1.5 bg-slate-800/80 text-slate-500 border border-slate-700/50 rounded-xl text-xs font-bold transition flex items-center gap-1 cursor-not-allowed opacity-60";
        btnPreUpload.title = "Select YouTube or Facebook above to pre-upload and stage in the cloud";
        btnPreUpload.disabled = true;
      } else {
        btnPreUpload.disabled = false;
        const isStaged = schedulableSelected.some(p => waiting.includes(p));
        if (isStaged) {
          btnPreUpload.innerHTML = `<i data-lucide="cloud-check" class="w-3.5 h-3.5 text-cyan-300"></i><span>Re-Stage Cloud</span>`;
          btnPreUpload.className = "px-3.5 py-1.5 bg-cyan-700 hover:bg-cyan-600 text-cyan-100 rounded-xl text-xs font-bold transition flex items-center gap-1 shadow cursor-pointer border border-cyan-500/50";
          btnPreUpload.title = `Pre-upload and re-stage video to: ${schedulableSelected.join(', ').toUpperCase()}`;
        } else {
          btnPreUpload.innerHTML = `<i data-lucide="cloud-upload" class="w-3.5 h-3.5"></i><span>Stage in Cloud</span>`;
          btnPreUpload.className = "px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1 shadow cursor-pointer";
          btnPreUpload.title = `Pre-upload video now and stage natively for scheduled release on: ${schedulableSelected.join(', ').toUpperCase()}`;
        }
      }
    }
  }
  lucide.createIcons();
}

async function saveDetailChanges() {
  if (!activePostDetail) return;
  const newDate = document.getElementById("detailEditDate")?.value;
  const newTime = document.getElementById("detailEditTime")?.value;
  const platforms = Array.from(activeModalPlatforms);
  const finalPlatforms = platforms.length > 0 ? platforms : (activePostDetail.platforms || ["youtube"]);

  const dropped = waitingPlatforms(activePostDetail).filter(p => !finalPlatforms.includes(p));
  if (dropped.length && !confirm(`${platNames(dropped)} is un-ticked. Saving deletes the ${platNames(dropped)} copy that is uploaded and waiting to go live. Continue?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/calendar/schedule/${activePostDetail.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scheduled_date: newDate,
        scheduled_time: newTime,
        platforms: finalPlatforms
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      document.getElementById("modalPostDetail").classList.add("hidden");
      showCalToast("Schedule and platforms updated successfully.", "success");
      showChangeNotes(data);
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Failed to update schedule.", "error");
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  }
}

async function togglePostStatusManual() {
  if (!activePostDetail) return;
  const currentStatus = activePostDetail.status;
  const targetStatus = currentStatus === "posted" ? "scheduled" : "posted";
  const newDate = document.getElementById("detailEditDate")?.value || activePostDetail.scheduled_date;
  const newTime = document.getElementById("detailEditTime")?.value || activePostDetail.scheduled_time || "18:00";
  const platforms = Array.from(activeModalPlatforms && activeModalPlatforms.size > 0 ? activeModalPlatforms : (activePostDetail.platforms || ["youtube"]));

  try {
    const res = await fetch(`/api/calendar/schedule/${activePostDetail.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scheduled_date: newDate,
        scheduled_time: newTime,
        platforms: platforms,
        status: targetStatus
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showCalToast(`Card marked as ${targetStatus.toUpperCase()} successfully.`, "success");
      document.getElementById("modalPostDetail")?.classList.add("hidden");
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Failed to update status", "error");
    }
  } catch (err) {
    showCalToast(`Error: ${err.message}`, "error");
  }
}

async function executePostNow(postId) {
  const targetId = postId || (activePostDetail ? activePostDetail.id : null);
  if (!targetId) return;

  const targetPost = scheduleData.find(p => p.id === targetId) || activePostDetail;
  // A copy waiting to go live isn't posted yet: Post Now publishes it instead of uploading a second one
  const publishedPlatforms = (targetPost?.published_platforms || []).filter(p => !waitingPlatforms(targetPost).includes(p));

  let platforms = [];
  if (activePostDetail && activePostDetail.id === targetId) {
    if (!activeModalPlatforms || activeModalPlatforms.size === 0) {
      showCalToast("Please select at least one platform above to post or repost.", "warning");
      return;
    }
    platforms = Array.from(activeModalPlatforms);
  } else if (targetPost?.platforms && targetPost.platforms.length > 0) {
    const unposted = targetPost.platforms.filter(p => !publishedPlatforms.includes(p));
    platforms = unposted.length > 0 ? unposted : targetPost.platforms;
  } else {
    platforms = ["youtube"];
  }

  const isAllPublished = platforms.length > 0 && platforms.every(p => publishedPlatforms.includes(p));
  const isRepost = isAllPublished || platforms.some(p => publishedPlatforms.includes(p));

  try {
    showCalToast(isRepost ? "Triggering social media re-publish..." : "Triggering social media dispatch...", "info");
    const platQuery = encodeURIComponent(platforms.join(","));
    const url = `/api/calendar/schedule/${targetId}/post_now?force_republish=true&platforms=${platQuery}`;
    const res = await fetch(url, { method: "POST" });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (parseErr) {
      throw new Error(`Server returned error (${res.status}): ${text || res.statusText}`);
    }
    if (res.ok && data.success) {
      const successMsg = isRepost 
        ? "Video successfully re-posted to social feeds!" 
        : "Video successfully published to social feeds!";
      showCalToast(successMsg, "success");

      // Trigger browser desktop notification if supported
      if ("Notification" in window && Notification.permission === "granted") {
        try {
          const { epPrefix, title } = formatPostTitle(targetPost);
          const fullTitle = `${epPrefix ? epPrefix + ' ' : ''}${title}`;
          new Notification(isRepost ? "KCT Studio - Video Re-posted!" : "KCT Studio - Video Published!", {
            body: `"${fullTitle}" has been posted to ${platforms.join(', ').toUpperCase()}.`,
            icon: targetPost.thumbnail_url || "/static/favicon.png"
          });
        } catch (_) {}
      }

      document.getElementById("modalPostDetail")?.classList.add("hidden");
      await refreshSchedule();
    } else {
      const errMsg = data.entry?.error || data.detail || (data.dispatch?.platforms?.youtube?.message) || "Publishing failed.";
      showCalToast(errMsg, "error");
      await refreshSchedule();
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  }
}

async function executePreUpload(postId) {
  const targetId = postId || (activePostDetail ? activePostDetail.id : null);
  if (!targetId) return;

  const targetPost = scheduleData.find(p => p.id === targetId) || activePostDetail;
  let platforms = [];
  if (activePostDetail && activePostDetail.id === targetId) {
    if (!activeModalPlatforms || activeModalPlatforms.size === 0) {
      showCalToast("Please select at least one platform above to stage in the cloud.", "warning");
      return;
    }
    platforms = Array.from(activeModalPlatforms);
  } else if (targetPost?.platforms && targetPost.platforms.length > 0) {
    platforms = targetPost.platforms;
  } else {
    platforms = ["youtube"];
  }

  const cloudPlatforms = platforms.filter(p => ["youtube", "facebook"].includes(p));
  if (cloudPlatforms.length === 0) {
    showCalToast("Only YouTube and Facebook support native cloud staging. For other platforms, use Post Now.", "warning");
    return;
  }

  // Copies already waiting are replaced (deleted, then uploaded again), e.g. after a re-render or caption change
  const toReplace = waitingPlatforms(targetPost).filter(p => cloudPlatforms.includes(p));
  if (toReplace.length && !confirm(`Re-stage replaces the ${platNames(toReplace)} copy waiting to go live: it is deleted and uploaded again. Continue?`)) {
    return;
  }

  try {
    showCalToast(`☁️ Pre-uploading & staging to ${cloudPlatforms.join(', ').toUpperCase()} in the cloud...`, "info");
    const platQuery = encodeURIComponent(cloudPlatforms.join(","));
    const url = `/api/calendar/schedule/${targetId}/pre_upload?platforms=${platQuery}${toReplace.length ? "&replace=true" : ""}`;
    const res = await fetch(url, { method: "POST" });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (parseErr) {
      throw new Error(`Server returned error (${res.status}): ${text || res.statusText}`);
    }

    if (res.ok && data.success) {
      showCalToast("☁️ Video successfully uploaded & staged in the cloud! Platform will publish on scheduled release.", "success");

      // Desktop notification
      if ("Notification" in window && Notification.permission === "granted") {
        try {
          const { epPrefix, title } = formatPostTitle(targetPost);
          const fullTitle = `${epPrefix ? epPrefix + ' ' : ''}${title}`;
          new Notification("KCT Studio - Staged in Cloud!", {
            body: `"${fullTitle}" is now pre-uploaded and staged on ${cloudPlatforms.join(', ').toUpperCase()}.`,
            icon: targetPost.thumbnail_url || "/static/favicon.png"
          });
        } catch (_) {}
      }

      document.getElementById("modalPostDetail")?.classList.add("hidden");
      await refreshSchedule();
    } else {
      const errMsg = data.entry?.error || data.detail || (data.dispatch?.message) || "Pre-upload staging failed.";
      showCalToast(errMsg, "error");
      await refreshSchedule();
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  }
}

async function executeDeletePost(postId) {
  const targetId = postId || (activePostDetail ? activePostDetail.id : null);
  if (!targetId) return;

  const targetPost = scheduleData.find(p => p.id === targetId) || activePostDetail;
  const waiting = waitingPlatforms(targetPost);
  const question = waiting.length
    ? `Remove this video from the posting schedule?\n\nIt is already uploaded and waiting to go live on ${platNames(waiting)}. Those copies will be deleted so it doesn't go out.`
    : "Remove this video from the posting schedule?";
  if (!confirm(question)) return;

  try {
    const res = await fetch(`/api/calendar/schedule/${targetId}`, { method: "DELETE" });
    const data = await res.json();
    if (res.ok && data.success) {
      const deleted = data.deleted_copies || [];
      showCalToast(deleted.length ? `Post removed, and its waiting ${platNames(deleted)} copy deleted.` : "Post removed from schedule.", "info");
      document.getElementById("modalPostDetail")?.classList.add("hidden");
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Failed to remove post", "error");
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  }
}

// ----------------- BULK AUTO-SCHEDULER -----------------
async function runAutoScheduleBulk() {
  const btn = document.getElementById("btnAutoSchedule");
  const origText = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Auto-Scheduling...</span>`;
    lucide.createIcons();
  }

  try {
    const targetProj = (selectedProject && selectedProject !== "all") ? selectedProject : null;
    const res = await fetch("/api/calendar/auto_schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_path: targetProj })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      if (data.scheduled_count > 0) {
        showCalToast(`⚡ Successfully scheduled <b>${data.scheduled_count} videos</b> into consecutive future daily slots!`, "success");
      } else {
        showCalToast("All approved videos are already scheduled or posted.", "info");
      }
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Auto-schedule failed", "error");
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
      lucide.createIcons();
    }
  }
}

// ----------------- META BUSINESS SUITE CHECKLIST -----------------
// Instagram (reels, stories) and Facebook Stories can't be held as scheduled posts through the API, so the project
// schedules them by hand in Business Suite. This panel lists the coming week's ones with their captions.
let bsTasks = [];

function bsProjectPath() {
  return selectedProject && selectedProject !== "all" ? selectedProject : null;
}

async function openBusinessSuitePanel() {
  document.getElementById("modalBusinessSuite").classList.remove("hidden");
  await Promise.all([loadBusinessSuiteSettings(), loadBusinessSuiteTasks()]);
}

async function loadBusinessSuiteSettings() {
  const q = bsProjectPath() ? `?project_path=${encodeURIComponent(bsProjectPath())}` : "";
  try {
    const cfg = await (await fetch(`/api/social/config${q}`)).json();
    document.getElementById("bsStageDays").value = cfg.stage_ahead_days ?? 0;
    document.getElementById("bsReelTimes").value = (cfg.reel_posting_times || ["07:30", "17:30", "20:30"]).join(", ");
    document.getElementById("bsIgToggle").checked = !!(cfg.business_suite || {}).instagram;
    document.getElementById("bsFbStoriesToggle").checked = !!(cfg.business_suite || {}).facebook_stories;
    document.getElementById("bsSettingsProject").textContent = cfg.project_name || "Active project";
    document.getElementById("bsDryRunNote").classList.toggle("hidden", cfg.dry_run === false);
  } catch (e) {
    showCalToast(`Couldn't load the scheduling settings: ${e.message}`, "error");
  }
}

async function saveBusinessSuiteSettings() {
  const days = Math.max(0, Math.min(30, parseInt(document.getElementById("bsStageDays").value, 10) || 0));
  const reelTimes = document.getElementById("bsReelTimes").value.split(/[,\s]+/).map(t => t.trim()).filter(Boolean);
  const badTime = reelTimes.find(t => !/^([01]\d|2[0-3]):[0-5]\d$/.test(t));
  if (badTime || !reelTimes.length) {
    showCalToast(`Reel times must look like 07:30, 17:30${badTime ? ` ("${badTime}" doesn't)` : ""}.`, "error");
    return;
  }
  const body = {
    project_path: bsProjectPath(),
    stage_ahead_days: days,
    reel_posting_times: reelTimes,
    business_suite: {
      instagram: document.getElementById("bsIgToggle").checked,
      facebook_stories: document.getElementById("bsFbStoriesToggle").checked
    }
  };
  try {
    const res = await fetch("/api/social/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showCalToast(days > 0
      ? `Saved. Posts in the next ${days} day${days === 1 ? "" : "s"} are uploaded to YouTube & Facebook ahead of time.`
      : "Saved. Uploading ahead is off.", "success");
    await Promise.all([loadBusinessSuiteSettings(), loadBusinessSuiteTasks(), refreshSchedule()]);
  } catch (e) {
    showCalToast(`Couldn't save the settings: ${e.message}`, "error");
  }
}

async function loadBusinessSuiteTasks() {
  const list = document.getElementById("bsTaskList");
  list.innerHTML = `<div class="text-xs text-slate-500 p-4 text-center">Loading…</div>`;
  const q = new URLSearchParams({ days: "7" });
  if (bsProjectPath()) q.set("project_path", bsProjectPath());
  try {
    const data = await (await fetch(`/api/calendar/business_suite?${q.toString()}`)).json();
    if (data.planner_url) document.getElementById("bsPlannerLink").href = data.planner_url;
    bsTasks = data.tasks || [];
    renderBusinessSuiteTasks();
  } catch (e) {
    list.innerHTML = `<div class="text-xs text-rose-300 p-4">Couldn't load the checklist: ${escapeHtml(e.message)}</div>`;
  }
}

function renderBusinessSuiteTasks() {
  const list = document.getElementById("bsTaskList");
  if (!bsTasks.length) {
    list.innerHTML = `
      <div class="p-6 text-center text-slate-500 border border-dashed border-slate-800 rounded-2xl text-xs">
        Nothing to schedule by hand in the next 7 days.<br>
        <span class="text-[11px] text-slate-600">Tick Instagram / Facebook Stories above, and put the week's posts on the calendar.</span>
      </div>`;
    return;
  }

  const byDay = {};
  bsTasks.forEach((t, i) => {
    const day = t.due.slice(0, 10);
    (byDay[day] = byDay[day] || []).push({ ...t, idx: i });
  });

  list.innerHTML = Object.entries(byDay).map(([day, tasks]) => {
    const [y, m, d] = day.split("-").map(Number);
    const dayLabel = new Date(y, m - 1, d).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
    return `
      <div>
        <div class="text-[11px] font-bold text-amber-300 uppercase tracking-wide mb-2">${dayLabel}</div>
        <div class="space-y-2">
          ${tasks.map(t => {
            const done = t.step === "scheduled" || t.step === "live";
            const stepBadge = t.step === "live"
              ? `<a href="${escapeHtml(t.url || '#')}" target="_blank" rel="noopener noreferrer" class="text-emerald-300 font-bold">✓ Live</a>`
              : t.step === "missing"
              ? `<span class="text-rose-300 font-bold" title="No Instagram reel with this caption was found within 3 days of its time">Not found on Instagram</span>`
              : `<label class="flex items-center gap-1.5 cursor-pointer ${done ? 'text-emerald-300' : 'text-slate-300'}">
                   <input type="checkbox" class="bs-tick accent-emerald-500" data-idx="${t.idx}" ${done ? 'checked' : ''}>
                   Scheduled in Business Suite
                 </label>`;
            return `
              <div class="flex gap-3 p-3 rounded-xl border ${done ? 'border-emerald-900/50 bg-emerald-950/10' : 'border-[#242f44] bg-[#151b28]'}">
                <img src="${escapeHtml(t.thumbnail_url || '')}" alt="" class="w-12 h-20 object-cover rounded-lg bg-black border border-slate-800 shrink-0" onerror="this.src='/static/favicon.png';">
                <div class="min-w-0 flex-1 space-y-1.5">
                  <div class="flex flex-wrap items-center gap-2 text-xs">
                    <span class="font-mono font-bold text-amber-300">${t.due.slice(11, 16)}</span>
                    <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${t.platform === 'instagram' ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30' : 'bg-[#1877F2]/15 text-blue-300 border border-[#1877F2]/30'}">${escapeHtml(t.label)}</span>
                    <span class="font-semibold text-slate-100 truncate">${escapeHtml(t.title || t.video_rel_path)}</span>
                  </div>
                  ${t.caption ? `<pre class="font-sans text-[11px] text-slate-300 whitespace-pre-wrap bg-slate-950/60 border border-slate-800 rounded-lg p-2 max-h-24 overflow-y-auto custom-scrollbar">${escapeHtml(t.caption)}</pre>` : ''}
                  ${t.caption_error ? `<div class="text-[11px] text-rose-300">Couldn't build the caption: ${escapeHtml(t.caption_error)}</div>` : ''}
                  <div class="flex flex-wrap items-center gap-2 text-[11px]">
                    ${t.caption ? `<button class="bs-copy px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center gap-1" data-idx="${t.idx}"><i data-lucide="copy" class="w-3 h-3"></i>Copy caption</button>` : ''}
                    <button class="bs-reveal px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center gap-1" data-idx="${t.idx}"><i data-lucide="folder-open" class="w-3 h-3"></i>Show video</button>
                    ${!t.is_story ? `<a href="${escapeHtml(t.thumbnail_url || '#')}" target="_blank" rel="noopener noreferrer" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center gap-1"><i data-lucide="image" class="w-3 h-3"></i>Cover image</a>` : ''}
                    <span class="ml-auto">${stepBadge}</span>
                  </div>
                </div>
              </div>`;
          }).join("")}
        </div>
      </div>`;
  }).join("");

  list.querySelectorAll(".bs-copy").forEach(btn => {
    btn.onclick = async () => {
      const t = bsTasks[+btn.dataset.idx];
      try {
        await navigator.clipboard.writeText(t.caption);
        showCalToast("Caption copied. Paste it into Business Suite.", "success");
      } catch (e) {
        showCalToast(`Couldn't copy: ${e.message}`, "error");
      }
    };
  });
  list.querySelectorAll(".bs-reveal").forEach(btn => {
    btn.onclick = async () => {
      const t = bsTasks[+btn.dataset.idx];
      try {
        const res = await fetch("/api/calendar/reveal_video", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_path: t.project_path, video_rel_path: t.video_rel_path })
        });
        if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
      } catch (e) {
        showCalToast(`Couldn't open the folder: ${e.message}`, "error");
      }
    };
  });
  list.querySelectorAll(".bs-tick").forEach(cb => {
    cb.onchange = async () => {
      const t = bsTasks[+cb.dataset.idx];
      try {
        const res = await fetch(`/api/calendar/schedule/${t.post_id}/manual/${t.platform}?done=${cb.checked}`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        t.step = cb.checked ? "scheduled" : "todo";
        renderBusinessSuiteTasks();
        refreshSchedule();
      } catch (e) {
        cb.checked = !cb.checked;
        showCalToast(`Couldn't save: ${e.message}`, "error");
      }
    };
  });
  lucide.createIcons();
}

// ----------------- EVENT LISTENERS SETUP -----------------
function setupEventListeners() {
  // Month navigation
  document.getElementById("btnCalPrev").onclick = () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    refreshSchedule();
  };
  document.getElementById("btnCalNext").onclick = () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    refreshSchedule();
  };
  document.getElementById("btnCalToday").onclick = () => {
    currentDate = new Date();
    refreshSchedule();
  };

  // View switches
  document.getElementById("btnViewMonth").onclick = () => { activeView = "month"; renderActiveView(); };
  document.getElementById("btnViewWeek").onclick = () => { activeView = "week"; renderActiveView(); };
  document.getElementById("btnViewQueue").onclick = () => { activeView = "queue"; renderActiveView(); };

  // Project selector
  document.getElementById("calProjectSelect").onchange = (e) => {
    selectedProject = e.target.value;
    refreshSchedule();
  };

  // Platform filters
  document.querySelectorAll(".platform-filter-btn").forEach(btn => {
    btn.onclick = () => {
      currentPlatformFilter = btn.getAttribute("data-filter");
      updatePlatformFilterUI();
      renderActiveView();
    };
  });
}

function updatePlatformFilterUI() {
  document.querySelectorAll(".platform-filter-btn").forEach(btn => {
    const f = btn.getAttribute("data-filter");
    const isActive = (f === currentPlatformFilter);
    if (f === "all") {
      btn.className = `platform-filter-btn px-2.5 py-1 rounded-lg text-xs font-bold transition shadow-sm ${
        isActive 
          ? 'bg-[#FFE614] text-slate-950 ring-1 ring-[#FFE614]' 
          : 'bg-slate-800/60 text-slate-400 hover:text-white border border-slate-700/50'
      }`;
    } else {
      btn.className = `platform-filter-btn w-8 h-8 rounded-lg transition flex items-center justify-center cursor-pointer border ${
        isActive 
          ? 'bg-[#FFE614]/25 border-[#FFE614] ring-2 ring-[#FFE614]/60 shadow-[0_0_10px_rgba(255,230,20,0.3)]' 
          : 'bg-slate-800/60 border-slate-700/50 hover:bg-slate-700/50'
      }`;
    }
  });

  // Action buttons
  document.getElementById("btnOpenAddPost").onclick = () => openAddPostModal();
  document.getElementById("btnAutoSchedule").onclick = runAutoScheduleBulk;

  // Business Suite checklist
  document.getElementById("btnBusinessSuite").onclick = openBusinessSuitePanel;
  document.getElementById("btnCloseBusinessSuite").onclick = () => document.getElementById("modalBusinessSuite").classList.add("hidden");
  document.getElementById("btnRefreshBusinessSuite").onclick = loadBusinessSuiteTasks;
  document.getElementById("btnSaveBsSettings").onclick = saveBusinessSuiteSettings;

  // Add post modal
  document.getElementById("btnCloseAddPostModal").onclick = () => document.getElementById("modalAddPost").classList.add("hidden");
  document.getElementById("btnCancelAddPost").onclick = () => document.getElementById("modalAddPost").classList.add("hidden");
  document.getElementById("btnSubmitAddPost").onclick = submitAddPost;
  document.getElementById("addPostProjectSelect").onchange = (e) => {
    loadUnpostedVideos(e.target.value);
    updateAddModalPlatformsForProject(e.target.value);
  };
  document.getElementById("addPostDate").onchange = checkCollisionLive;
  document.querySelectorAll("#modalAddPost input[type='checkbox']").forEach(cb => cb.onchange = checkCollisionLive);

  document.getElementById("btnAddPostAutoSlot").onclick = async () => {
    const proj = document.getElementById("addPostProjectSelect")?.value;
    const plats = getSelectedPlatformsInAddModal();
    const q = new URLSearchParams();
    if (proj) q.set("project_path", proj);
    if (plats.length) q.set("platforms", plats.join(","));
    try {
      const res = await fetch(`/api/calendar/next_slot?${q.toString()}`);
      const data = await res.json();
      if (data.date) document.getElementById("addPostDate").value = data.date;
      if (data.time) document.getElementById("addPostTime").value = data.time;
      checkCollisionLive();
    } catch (e) {}
  };

  // Detail modal
  document.getElementById("btnCloseDetailModal").onclick = () => document.getElementById("modalPostDetail").classList.add("hidden");
  document.getElementById("btnSaveDetailChanges").onclick = saveDetailChanges;
  const btnPreUploadEl = document.getElementById("btnPreUpload");
  if (btnPreUploadEl) btnPreUploadEl.onclick = () => executePreUpload();
  document.getElementById("btnPostNow").onclick = () => executePostNow();
  document.getElementById("btnDeletePost").onclick = () => executeDeletePost();
  const btnMark = document.getElementById("btnMarkStatus");
  if (btnMark) btnMark.onclick = togglePostStatusManual;
  const btnHdrStatus = document.getElementById("btnHeaderStatusToggle");
  if (btnHdrStatus) btnHdrStatus.onclick = togglePostStatusManual;

  // Desktop notification permission
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }

  // Keyboard navigation
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.getElementById("modalAddPost")?.classList.add("hidden");
      document.getElementById("modalPostDetail")?.classList.add("hidden");
      document.getElementById("modalBusinessSuite")?.classList.add("hidden");
    }
  });
}
