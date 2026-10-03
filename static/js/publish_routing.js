// Shared by every page with the "Publish" modal (index, generator, story map).
// Format detection, per-platform eligibility and account connection all come from the server
// (/api/social/format), which uses the same rules as the dispatcher, so the checkboxes always
// match what will actually be posted.
(function () {
  const PLATFORM_IDS = { youtube: "Youtube", facebook: "Facebook", instagram: "Instagram", threads: "Threads", tiktok: "Tiktok", x: "X" };
  let routingRequest = 0;
  let lastRelPath = null;

  const checkbox = (plat) => document.getElementById(`chkPlat${PLATFORM_IDS[plat]}`);
  const titleEl = (plat) =>
    document.getElementById(`platTitle${PLATFORM_IDS[plat]}`) || document.querySelector(`#lblPlat${PLATFORM_IDS[plat]} .font-bold`);

  async function loadPlatformRouting(relPath) {
    const request = ++routingRequest;
    lastRelPath = relPath;
    try {
      const res = await fetch(`/api/social/format?rel_path=${encodeURIComponent(relPath || "")}`);
      const data = await res.json();
      if (request !== routingRequest) return; // another asset was opened meanwhile
      applyPlatformRouting(res.ok && data.success ? data : null, !res.ok || !data.success);
    } catch (e) {
      console.error("Failed to load platform routing:", e);
      if (request === routingRequest) applyPlatformRouting(null, true);
    }
  }

  // routing === null: loading (or failed) state - every platform stays disabled until the server decides
  function applyPlatformRouting(routing, failed = false) {
    const badge = document.getElementById("dispatchFormatBadge");
    const notice = document.getElementById("dispatchPlatformNotice");
    const noticeText = document.getElementById("dispatchPlatformNoticeText");
    const showNotice = (text) => {
      if (!notice || !noticeText) return;
      noticeText.innerText = text || "";
      notice.classList.toggle("hidden", !text);
    };

    if (!routing) {
      if (badge) {
        badge.className = "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-500/20 text-slate-300 border border-slate-500/30";
        badge.innerText = failed ? "FORMAT UNKNOWN" : "DETECTING…";
      }
      for (const plat of Object.keys(PLATFORM_IDS)) {
        const chk = checkbox(plat);
        if (chk) { chk.checked = false; chk.disabled = true; }
      }
      showNotice(failed ? "Could not detect the video format. Close and reopen to retry." : "");
      return;
    }

    if (badge) {
      const vertical = routing.format === "story" || routing.format === "short";
      badge.className = vertical
        ? "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30"
        : "text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30";
      badge.innerText = routing.format === "story" ? `⚡ ${routing.aspect_ratio} STORY`
        : routing.format === "short" ? `📱 ${routing.aspect_ratio} REEL`
        : `🎬 ${routing.aspect_ratio} LONG-FORM`;
    }

    const reasons = [];
    for (const plat of Object.keys(PLATFORM_IDS)) {
      const chk = checkbox(plat);
      if (!chk) continue; // this page has no checkbox for the platform
      const route = (routing.platforms || {})[plat] || { eligible: false, label: plat, reason: "Unsupported" };
      chk.checked = route.eligible;
      chk.disabled = !route.eligible;
      const title = titleEl(plat);
      if (title) {
        title.innerText = route.label;
        title.title = route.reason || "";
      }
      if (!route.eligible && route.reason) reasons.push(route.reason);
    }
    showNotice(reasons.join(" "));

    const metaBtn = document.getElementById("btnConnectMeta");
    const fb = (routing.platforms || {}).facebook;
    if (metaBtn && fb) metaBtn.querySelector("span").innerText = fb.connected ? "Update" : "Connect";
  }

  // Platforms ticked in the modal (disabled ones are never sent)
  function getSelectedPlatforms() {
    return Object.keys(PLATFORM_IDS).filter((plat) => {
      const chk = checkbox(plat);
      return chk && !chk.disabled && chk.checked;
    });
  }

  // ---------- Facebook & Instagram connection (Page access token) ----------
  function openMetaConnectModal() {
    let modal = document.getElementById("modalMetaConnect");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "modalMetaConnect";
      modal.className = "fixed inset-0 z-[70] hidden flex items-center justify-center p-4 bg-black/70";
      modal.innerHTML = `
        <div class="w-full max-w-md bg-[#121620] border border-[#2e394e] rounded-2xl p-5 space-y-3 text-xs shadow-2xl">
          <h3 class="text-sm font-bold text-white">Connect Facebook &amp; Instagram</h3>
          <p class="text-slate-400 leading-relaxed">
            Paste a Facebook Page access token (or a System User token with access to the Page). One token covers the Page and
            its linked Instagram account. It needs the <b class="text-slate-200">pages_manage_posts</b>,
            <b class="text-slate-200">pages_read_engagement</b> and <b class="text-slate-200">instagram_content_publish</b> permissions.
            It is checked with Meta, then saved only on this computer (data/meta_token.json).
          </p>
          <input id="metaTokenInput" type="password" autocomplete="off" spellcheck="false" placeholder="Page access token"
            class="w-full bg-[#181e2b] border border-[#2e394e] text-slate-100 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-blue-500">
          <div id="metaConnectMessage" class="hidden p-2.5 rounded-lg text-[11px]"></div>
          <div class="flex justify-end gap-2 pt-1">
            <button type="button" id="btnMetaCancel" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-semibold">Cancel</button>
            <button type="button" id="btnMetaSave" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold">Check &amp; Save</button>
          </div>
        </div>`;
      document.body.appendChild(modal);
      modal.querySelector("#btnMetaCancel").onclick = () => modal.classList.add("hidden");
      modal.querySelector("#btnMetaSave").onclick = saveMetaToken;
    }
    modal.querySelector("#metaTokenInput").value = "";
    setMetaMessage("");
    modal.classList.remove("hidden");
    modal.querySelector("#metaTokenInput").focus();
  }

  function setMetaMessage(text, kind = "error") {
    const box = document.getElementById("metaConnectMessage");
    if (!box) return;
    box.innerText = text;
    box.className = !text ? "hidden" : kind === "error"
      ? "p-2.5 rounded-lg text-[11px] bg-rose-950/40 border border-rose-500/40 text-rose-300"
      : "p-2.5 rounded-lg text-[11px] bg-amber-950/40 border border-amber-500/40 text-amber-300";
  }

  async function saveMetaToken() {
    const modal = document.getElementById("modalMetaConnect");
    const btn = document.getElementById("btnMetaSave");
    const token = document.getElementById("metaTokenInput").value.trim();
    if (!token) return setMetaMessage("Paste a Page access token first.");
    btn.disabled = true;
    btn.innerText = "Checking…";
    try {
      const res = await fetch("/api/social/meta/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_token: token })
      });
      const data = await res.json();
      if (!data.success) return setMetaMessage(data.error || data.detail || "Meta rejected this token.");
      document.getElementById("metaTokenInput").value = "";
      if (typeof window.refreshPlatformStatusInModal === "function") window.refreshPlatformStatusInModal();
      if (lastRelPath) loadPlatformRouting(lastRelPath);
      if (data.warning) {
        setMetaMessage(data.warning, "warning");
      } else {
        modal.classList.add("hidden");
        if (typeof window.showToast === "function") window.showToast("Facebook & Instagram connected", "success");
      }
    } catch (e) {
      setMetaMessage(`Network error: ${e.message}`);
    } finally {
      btn.disabled = false;
      btn.innerText = "Check & Save";
    }
  }

  window.loadPlatformRouting = loadPlatformRouting;
  window.applyPlatformRouting = applyPlatformRouting;
  window.getSelectedPlatforms = getSelectedPlatforms;
  window.openMetaConnectModal = openMetaConnectModal;
})();
