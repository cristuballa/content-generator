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

document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
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
    cell.className = "cal-day-cell p-2 flex flex-col justify-between border-b border-r border-[#1a2130] bg-[#0d1017]/70 hover:bg-[#121722] relative group";

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
      cell.classList.add("opacity-35", "bg-[#090b10]");
    } else if (i >= firstDayIndex + daysInCurrentMonth) {
      // Next month
      cellDay = i - (firstDayIndex + daysInCurrentMonth) + 1;
      cellMonth = month + 1;
      if (cellMonth > 11) { cellMonth = 0; cellYear++; }
      isCurrentMonth = false;
      cell.classList.add("opacity-35", "bg-[#090b10]");
    } else {
      // Current month
      cellDay = i - firstDayIndex + 1;
      isCurrentMonth = true;
    }

    const dateStr = `${cellYear}-${String(cellMonth + 1).padStart(2, '0')}-${String(cellDay).padStart(2, '0')}`;
    const isToday = (dateStr === todayStr);

    if (isToday) {
      cell.classList.add("ring-1", "ring-[#FFE614]/70", "bg-[#FFE614]/5");
    }

    // Cell Header (Day Number + Quick Add Button)
    const headerEl = document.createElement("div");
    headerEl.className = "flex items-center justify-between mb-1.5";
    headerEl.innerHTML = `
      <div class="flex items-center gap-1">
        <span class="text-xs font-mono font-bold ${isToday ? 'px-1.5 py-0.2 bg-[#FFE614] text-slate-950 rounded' : isCurrentMonth ? 'text-slate-300' : 'text-slate-600'}">
          ${cellDay}
        </span>
        ${isToday ? `<span class="text-[9px] font-mono text-[#FFE614] font-bold">TODAY</span>` : ''}
      </div>
      <button class="btn-quick-add text-slate-600 hover:text-[#FFE614] opacity-0 group-hover:opacity-100 transition p-0.5" title="Schedule post for ${dateStr}" data-date="${dateStr}">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i>
      </button>
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

    // Posts Container
    const postsContainer = document.createElement("div");
    postsContainer.className = "space-y-1.5 flex-1 overflow-y-auto max-h-[140px] custom-scrollbar";

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

    const dayName = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][i];

    // Header column
    const hCol = document.createElement("div");
    hCol.className = `py-2 text-center ${isToday ? 'text-[#FFE614] bg-[#FFE614]/10' : 'text-slate-300'}`;
    hCol.innerHTML = `
      <div class="text-[10px] uppercase font-mono tracking-wider">${dayName}</div>
      <div class="text-sm font-bold mt-0.5">${d.getDate()}</div>
    `;
    header.appendChild(hCol);

    // Body column
    const bCol = document.createElement("div");
    bCol.className = `p-2 flex flex-col gap-2 min-h-[450px] border-r border-[#1a2130] bg-[#0c0f17] ${isToday ? 'bg-[#FFE614]/5' : ''}`;

    const dayPosts = scheduleData.filter(it => it.scheduled_date === dateStr);
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

  const sorted = [...scheduleData].sort((a, b) => (a.scheduled_datetime_iso || "").localeCompare(b.scheduled_datetime_iso || ""));

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

    item.innerHTML = `
      <div class="flex items-center gap-3.5 min-w-0 flex-1">
        <img src="${post.thumbnail_url}" alt="Thumbnail" class="w-16 h-10 object-cover rounded-lg bg-black border border-slate-800 shrink-0" onerror="this.src='/static/favicon.png';">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
              isPosted ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50' :
              isFailed ? 'bg-rose-900/60 text-rose-300 border border-rose-700/50' :
              'bg-cyan-950 text-cyan-300 border border-cyan-800'
            }">
              ${post.status.toUpperCase()}
            </span>
            <span class="text-xs font-mono text-slate-400 font-semibold truncate">${post.project_name || ''}</span>
          </div>
          <div class="font-bold text-xs text-slate-100 truncate mt-0.5" title="${post.title || post.video_filename}">
            ${post.title || post.video_filename}
          </div>
          <div class="text-[11px] font-mono text-amber-300 font-bold flex items-center gap-1.5 mt-0.5">
            <i data-lucide="clock" class="w-3 h-3 text-amber-400"></i>
            <span>${formattedDate} at ${post.scheduled_time}</span>
          </div>
        </div>
      </div>

      <!-- Platforms & Actions -->
      <div class="flex items-center gap-3 shrink-0">
        <div class="flex items-center gap-1.5">
          ${renderPlatformBadges(post.platforms)}
        </div>
        <div class="flex items-center gap-1.5">
          ${!isPosted ? `
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

// ----------------- POST CARD COMPONENT -----------------
function renderPostCard(post, isExpanded = false) {
  const card = document.createElement("div");
  const isPosted = post.status === "posted";
  const isFailed = post.status === "failed";

  card.className = `cal-card p-1.5 rounded-lg border text-[11px] cursor-pointer ${
    isPosted 
      ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-200' 
      : isFailed 
      ? 'bg-rose-950/40 border-rose-800/50 text-rose-200' 
      : 'bg-[#151c2a] border-[#253248] text-slate-200 hover:border-[#FFE614]/60'
  }`;

  card.onclick = () => openDetailModal(post.id);

  card.innerHTML = `
    <div class="flex items-center justify-between gap-1 mb-1">
      <span class="font-mono font-bold text-[10px] text-amber-300 flex items-center gap-1">
        <i data-lucide="clock" class="w-2.5 h-2.5"></i> ${post.scheduled_time}
      </span>
      <span class="text-[9px] font-mono px-1 py-0.2 rounded ${
        isPosted ? 'bg-emerald-500/20 text-emerald-400 font-bold' :
        isFailed ? 'bg-rose-500/20 text-rose-400 font-bold' :
        'bg-cyan-500/15 text-cyan-300'
      }">
        ${isPosted ? 'POSTED' : isFailed ? 'FAILED' : 'QUEUED'}
      </span>
    </div>

    <div class="flex items-center gap-1.5 mb-1.5">
      <img src="${post.thumbnail_url}" alt="" class="w-8 h-5 object-cover rounded bg-black shrink-0 border border-slate-700/60" onerror="this.src='/static/favicon.png';">
      <div class="font-bold text-[10.5px] truncate flex-1 text-slate-100" title="${post.title || post.video_filename}">
        ${post.title || post.video_filename}
      </div>
    </div>

    <div class="flex items-center gap-1 pt-1 border-t border-slate-700/30">
      ${renderPlatformBadges(post.platforms)}
    </div>
  `;

  return card;
}

function renderPlatformBadges(platforms = []) {
  if (!platforms || platforms.length === 0) return '';
  return platforms.map(p => {
    const info = PLATFORM_ICONS[p] || { name: p, icon: "share-2", color: "text-slate-400", bg: "bg-slate-800 border-slate-700" };
    if (p === "x") {
      return `<span class="w-4 h-4 rounded flex items-center justify-center font-black text-[9px] bg-slate-800 text-slate-100 border border-slate-700" title="X (Twitter)">𝕏</span>`;
    }
    return `
      <span class="w-4 h-4 rounded flex items-center justify-center ${info.bg} ${info.color} border" title="${info.name}">
        <i data-lucide="${info.icon}" class="w-2.5 h-2.5"></i>
      </span>
    `;
  }).join('');
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

  // Load project defaults
  try {
    const q = targetProj ? `?project_path=${encodeURIComponent(targetProj)}` : '';
    const res = await fetch(`/api/social/config${q}`);
    const cfg = await res.json();
    if (inputTime) inputTime.value = cfg.default_posting_time || "18:00";
  } catch (e) {}

  // Date setup
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
      if (inputDate) inputDate.value = new Date().toISOString().split("T")[0];
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
    alertText.innerHTML = `<b>Daily Limit Conflict:</b> ${inputDate} already has scheduled posts for: ${conflicts.join(", ")}. Only 1 post per account per day is allowed.`;
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.classList.add("opacity-50", "cursor-not-allowed");
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
function openDetailModal(postId) {
  const post = scheduleData.find(p => p.id === postId);
  if (!post) return;
  activePostDetail = post;

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
    badgeStatus.textContent = post.status.toUpperCase();
    badgeStatus.className = `text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase ${
      post.status === 'posted' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
      post.status === 'failed' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
      'bg-cyan-950 text-cyan-400 border border-cyan-800'
    }`;
  }
  if (badgeProject) badgeProject.textContent = post.project_name || '';
  if (imgThumb) imgThumb.src = post.thumbnail_url;
  if (elTitle) elTitle.textContent = post.title || post.video_filename;
  if (elFile) elFile.textContent = post.video_rel_path;
  if (elPlatforms) elPlatforms.innerHTML = renderPlatformBadges(post.platforms);
  if (inputDate) inputDate.value = post.scheduled_date;
  if (inputTime) inputTime.value = post.scheduled_time;

  if (boxResult && textResult) {
    if (post.dispatch_result || post.error) {
      boxResult.classList.remove("hidden");
      textResult.textContent = JSON.stringify(post.dispatch_result || { error: post.error }, null, 2);
    } else {
      boxResult.classList.add("hidden");
    }
  }

  modal.classList.remove("hidden");
  lucide.createIcons();
}

async function saveDetailChanges() {
  if (!activePostDetail) return;
  const newDate = document.getElementById("detailEditDate")?.value;
  const newTime = document.getElementById("detailEditTime")?.value;

  try {
    const res = await fetch(`/api/calendar/schedule/${activePostDetail.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_date: newDate, scheduled_time: newTime })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      document.getElementById("modalPostDetail").classList.add("hidden");
      showCalToast("Schedule updated successfully.", "success");
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Failed to update schedule.", "error");
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  }
}

async function executePostNow(postId) {
  const targetId = postId || (activePostDetail ? activePostDetail.id : null);
  if (!targetId) return;

  try {
    showCalToast("Triggering social media dispatch...", "info");
    const res = await fetch(`/api/calendar/schedule/${targetId}/post_now`, { method: "POST" });
    const data = await res.json();
    if (res.ok && data.success) {
      showCalToast("Video successfully published to social feeds!", "success");
      document.getElementById("modalPostDetail")?.classList.add("hidden");
      await refreshSchedule();
    } else {
      showCalToast(data.entry?.error || "Publishing failed.", "error");
      await refreshSchedule();
    }
  } catch (e) {
    showCalToast(`${e.message}`, "error");
  }
}

async function executeDeletePost(postId) {
  const targetId = postId || (activePostDetail ? activePostDetail.id : null);
  if (!targetId) return;

  if (!confirm("Remove this video from the posting schedule?")) return;

  try {
    const res = await fetch(`/api/calendar/schedule/${targetId}`, { method: "DELETE" });
    const data = await res.json();
    if (res.ok && data.success) {
      showCalToast("Post removed from schedule.", "info");
      document.getElementById("modalPostDetail")?.classList.add("hidden");
      await refreshSchedule();
    } else {
      showCalToast(data.detail || "Failed to delete post", "error");
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
      document.querySelectorAll(".platform-filter-btn").forEach(b => {
        b.className = "platform-filter-btn px-2 py-0.5 rounded-lg text-[11px] font-bold text-slate-400 hover:text-white bg-slate-800/60 border border-slate-700/50 transition flex items-center gap-1";
      });
      btn.className = "platform-filter-btn px-2 py-0.5 rounded-lg text-[11px] font-bold bg-[#FFE614] text-slate-950 transition flex items-center gap-1";
      currentPlatformFilter = btn.getAttribute("data-filter");
      renderActiveView();
    };
  });

  // Action buttons
  document.getElementById("btnOpenAddPost").onclick = () => openAddPostModal();
  document.getElementById("btnAutoSchedule").onclick = runAutoScheduleBulk;

  // Add post modal
  document.getElementById("btnCloseAddPostModal").onclick = () => document.getElementById("modalAddPost").classList.add("hidden");
  document.getElementById("btnCancelAddPost").onclick = () => document.getElementById("modalAddPost").classList.add("hidden");
  document.getElementById("btnSubmitAddPost").onclick = submitAddPost;
  document.getElementById("addPostProjectSelect").onchange = (e) => loadUnpostedVideos(e.target.value);
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
  document.getElementById("btnPostNow").onclick = () => executePostNow();
  document.getElementById("btnDeletePost").onclick = () => executeDeletePost();

  // Keyboard navigation
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.getElementById("modalAddPost")?.classList.add("hidden");
      document.getElementById("modalPostDetail")?.classList.add("hidden");
    }
  });
}
