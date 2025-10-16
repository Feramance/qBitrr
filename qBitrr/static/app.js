const headers = () => {
    const h = { "Content-Type": "application/json" };
    const t = localStorage.getItem("token");
    if (t) h["Authorization"] = "Bearer " + t;
    return h;
};

// Store token from URL query if present (for first-load auth)
(function () {
    try {
        const params = new URLSearchParams(window.location.search);
        const t = params.get("token");
        if (t) localStorage.setItem("token", t);
    } catch (_) {
        /* ignore */
    }
})();

let currentArr = null; // { type: 'radarr'|'sonarr', cat, targetId }
async function bootstrapToken() {
    try {
        const r = await fetch("/api/token");
        const d = await r.json();
        if (d.token) localStorage.setItem("token", d.token);
    } catch (_) {
        /* ignore */
    }
}
function globalSearch(q) {
    if (!currentArr) return;
    if (currentArr.type === "radarrAll") {
        radarrAggSearch(q);
    } else if (currentArr.type === "sonarrAll") {
        sonarrAggSearch(q);
    } else if (currentArr.type === "radarr") {
        filterRadarr(currentArr.cat, currentArr.targetId, q);
    } else if (currentArr.type === "sonarr") {
        filterSonarr(currentArr.cat, currentArr.targetId, q);
    }
}

function saveToken() {
    const t = document.getElementById("token").value;
    localStorage.setItem("token", t);
}
async function showTokenLocal() {
    try {
        const r = await fetch("/api/token");
        const d = await r.json();
        if (d.token) {
            document.getElementById("token").value = d.token;
        } else {
            alert(d.error || "Not available");
        }
    } catch (e) {
        alert("Not available");
    }
}
function show(id) {
    for (const s of document.querySelectorAll("section"))
        s.style.display = "none";
    const el = document.getElementById(id);
    if (el) el.style.display = "block";
}
function activate(id) {
    ["processes", "logs", "radarr", "sonarr", "config"].forEach((t) => {
        const link = document.getElementById("tab-" + t);
        if (link) link.classList.toggle("active", t === id);
    });
    show(id);
}

async function loadStatus() {
    const [s, p, a] = await Promise.all([
        fetch("/api/status", { headers: headers() })
            .then((r) => r.json())
            .catch((_) => ({ qbit: { alive: false }, arrs: [] })),
        fetch("/api/processes", { headers: headers() })
            .then((r) => r.json())
            .catch((_) => ({ processes: [] })),
        fetch("/api/arr", { headers: headers() })
            .then((r) => r.json())
            .catch((_) => ({ arr: [] })),
    ]);
    const qb =
        s.qbit && s.qbit.alive
            ? "<span class=ok>qBit OK</span>"
            : "<span class=bad>qBit DOWN</span>";
    const nameByCat = {};
    for (const it of a.arr || []) {
        nameByCat[it.category] = it.name || it.category;
    }
    const aliveByCat = {};
    for (const proc of p.processes || []) {
        if (proc.alive) aliveByCat[proc.category] = true;
        if (!nameByCat[proc.category])
            nameByCat[proc.category] = proc.name || proc.category;
    }
    const cats = new Set([
        ...(s.arrs ? s.arrs.map((x) => x.category) : []),
        ...Object.keys(aliveByCat),
    ]);
    let arrText = "";
    for (const cat of cats) {
        const alive =
            aliveByCat[cat] ??
            (s.arrs
                ? s.arrs.find((x) => x.category === cat)?.alive || false
                : false);
        const label = nameByCat[cat] || cat;
        arrText += `${label}:${alive ? "OK" : "DOWN"} `;
    }
    document.getElementById("status").innerHTML = qb + " | " + arrText;
}

async function loadProcesses() {
    const r = await fetch("/api/processes", { headers: headers() });
    const d = await r.json();
    let html =
        "<table><tr><th>Category</th><th>Name</th><th>Kind</th><th>PID</th><th>Alive</th><th>Actions</th></tr>";
    for (const p of d.processes) {
        html += `<tr><td>${p.category}</td><td>${p.name}</td><td>${
            p.kind
        }</td><td>${p.pid || ""}</td><td>${
            p.alive ? "<span class=ok>yes</span>" : "<span class=bad>no</span>"
        }</td><td><button onclick=restart('${p.category}','${
            p.kind
        }')>Restart</button></td></tr>`;
    }
    html += "</table>";
    document.getElementById("procOut").innerHTML = html;
}
async function restart(category, kind) {
    await fetch(`/api/processes/${category}/${kind}/restart`, {
        method: "POST",
        headers: headers(),
    });
    loadProcesses();
}
async function restartAll() {
    await fetch("/api/processes/restart_all", {
        method: "POST",
        headers: headers(),
    });
    loadProcesses();
}
async function rebuildArrs() {
    await fetch("/api/arr/rebuild", { method: "POST", headers: headers() });
    loadProcesses();
    loadArrList();
}
function toast(msg, type = "") {
    const wrap = document.getElementById("toasts");
    if (!wrap) return;
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => {
        el.style.opacity = "0";
    }, 2800);
    setTimeout(() => {
        wrap.removeChild(el);
    }, 3500);
}
async function applyLogLevel() {
    const lv = document.getElementById("logLevel").value;
    const res = await fetch("/api/loglevel", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ level: lv }),
    });
    if (res.ok) {
        toast("Log level set to " + lv, "success");
    } else {
        toast("Failed to set log level", "error");
    }
}

async function refreshLogList() {
    const r = await fetch("/api/logs", { headers: headers() });
    const d = await r.json();
    const sel = document.getElementById("logSelect");
    if (!sel) return;
    sel.innerHTML = "";
    for (const f of d.files) {
        const opt = document.createElement("option");
        opt.value = f;
        opt.textContent = f;
        sel.appendChild(opt);
    }
    if (d.files && d.files.length) {
        sel.value = d.files[0];
        startLogFollow();
    }
}
async function loadLogs() {
    await refreshLogList();
}
async function tail(name) {
    const t = localStorage.getItem("token");
    const q = t ? `?token=${encodeURIComponent(t)}` : "";
    const r = await fetch(`/api/logs/${name}${q}`);
    const c = await r.text();
    const el = document.getElementById("logTail");
    if (!el) return;
    el.textContent = c;
    el.dataset.filename = name;
    el.scrollTop = el.scrollHeight;
}
function downloadCurrent() {
    const sel = document.getElementById("logSelect");
    const name = sel && sel.value;
    if (!name) return;
    const t = localStorage.getItem("token");
    const q = t ? `?token=${encodeURIComponent(t)}` : "";
    window.location = `/api/logs/${name}/download${q}`;
}
let logTimer = null;
function startLogFollow() {
    if (logTimer) clearInterval(logTimer);
    const sel = document.getElementById("logSelect");
    if (!sel) return;
    const run = () => {
        const live = document.getElementById("logFollow");
        if (live && !live.checked) return;
        if (sel.value) tail(sel.value);
    };
    run();
    logTimer = setInterval(run, 2000);
}
document.addEventListener("change", (e) => {
    if (e.target && e.target.id === "logSelect") {
        startLogFollow();
    }
});

const radarrState = {};
const sonarrState = {};
const arrIndex = { radarr: {}, sonarr: {} };
async function loadArrList() {
    const [arrRes, procRes] = await Promise.all([
        fetch("/api/arr", { headers: headers() }),
        fetch("/api/processes", { headers: headers() }),
    ]);
    const d = await arrRes.json();
    const procs = await procRes.json();
    const nameByCat = {};
    for (const p of procs.processes || [])
        nameByCat[p.category] = p.name || p.category;
    const radarrCats = [];
    const sonarrCats = [];
    for (const a of d.arr) {
        const name = a.name || nameByCat[a.category] || a.category;
        if (a.type === "radarr") { radarrCats.push(a.category); arrIndex && (arrIndex.radarr = arrIndex.radarr || {}, arrIndex.radarr[a.category] = name); }
        if (a.type === "sonarr") { sonarrCats.push(a.category); arrIndex && (arrIndex.sonarr = arrIndex.sonarr || {}, arrIndex.sonarr[a.category] = name); }
    }
    const rnav = document.getElementById("radarrNav");
    if (rnav) rnav.innerHTML = `<button class="btn" onclick="loadRadarrAllInstances(window.__radarrCats)">Load All Radarr</button>`;
    const snav = document.getElementById("sonarrNav");
    if (snav) snav.innerHTML = `<button class="btn" onclick="loadSonarrAllInstances(window.__sonarrCats)">Load All Sonarr</button>`;
    // Store cats on window for button handlers
    window.__radarrCats = radarrCats;
    window.__sonarrCats = sonarrCats;
}
async function restartArr(cat) {
    const res = await fetch(`/api/arr/${cat}/restart`, {
        method: "POST",
        headers: headers(),
    });
    if (res.ok) {
        toast("Restarted " + cat, "success");
    } else {
        toast("Failed to restart " + cat, "error");
    }
}

async function loadRadarr(cat, targetId) {
    const ps = parseInt(
        document.getElementById(`${targetId}_ps`).value || "50"
    );
    const q = document.getElementById(`${targetId}`).dataset.filter || "";
    const page = radarrState[cat]?.page || 0;
    const r = await fetch(
        `/api/radarr/${cat}/movies?q=${encodeURIComponent(
            q
        )}&page=${page}&page_size=${ps}`,
        { headers: headers() }
    );
    const d = await r.json();
    radarrState[cat] = { page, counts: d.counts, total: d.total };
    currentArr = { type: "radarr", cat, targetId };
    renderRadarr(cat, targetId, d.movies, d.total, ps);
}
function renderRadarr(cat, targetId, items, total, ps) {
    const page = radarrState[cat].page || 0;
    const pages = Math.max(1, Math.ceil(total / ps));
    let html = `<p>Counts: ${radarrState[cat].counts.available} / ${
        radarrState[cat].counts.monitored
    } — Page ${page + 1} of ${pages} (total ${total})</p>`;
    html +=
        "<table><tr><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>";
    for (const m of items) {
        html += `<tr><td>${m.title}</td><td>${m.year || ""}</td><td>${
            m.monitored
        }</td><td>${m.hasFile}</td></tr>`;
    }
    html += "</table>";
    document.getElementById(targetId).innerHTML = html;
}
function pageRadarr(cat, targetId, delta) {
    radarrState[cat] = radarrState[cat] || { page: 0 };
    const ps = parseInt(
        document.getElementById(`${targetId}_ps`).value || "50"
    );
    const total = radarrState[cat].total || 0;
    const maxPage = Math.max(0, Math.ceil(total / ps) - 1);
    radarrState[cat].page = Math.min(
        maxPage,
        Math.max(0, (radarrState[cat].page || 0) + delta)
    );
    loadRadarr(cat, targetId);
}
function filterRadarr(cat, targetId, q) {
    try { radarrState[cat] = { page: 0 }; } catch(_) {}
    loadRadarrAll(cat, q);
}

async function loadSonarr(cat, targetId) {
    const ps = parseInt(
        document.getElementById(`${targetId}_ps`).value || "25"
    );
    const q = document.getElementById(`${targetId}`).dataset.filter || "";
    const page = sonarrState[cat]?.page || 0;
    const r = await fetch(
        `/api/sonarr/${cat}/series?q=${encodeURIComponent(
            q
        )}&page=${page}&page_size=${ps}`,
        { headers: headers() }
    );
    const d = await r.json();
    sonarrState[cat] = { page, counts: d.counts, total: d.total };
    currentArr = { type: "sonarr", cat, targetId };
    renderSonarr(cat, targetId, d.series, d.total, ps);
}
function renderSonarr(cat, targetId, series, total, ps) {
    const page = sonarrState[cat].page || 0;
    const pages = Math.max(1, Math.ceil(total / ps));
    let html = `<p>Counts: ${sonarrState[cat].counts.available} / ${
        sonarrState[cat].counts.monitored
    } — Page ${page + 1} of ${pages} (total ${total})</p>`;
    for (const s of series) {
        html += `<details><summary>${s.series.title} — ${s.totals.available} / ${s.totals.monitored}</summary>`;
        const seasons = Object.entries(s.seasons).sort((a, b) => a[0] - b[0]);
        for (const [sn, sv] of seasons) {
            html += `<details style='margin-left:12px'><summary>Season ${sn} — ${sv.available} / ${sv.monitored}</summary>`;
            html +=
                "<table><tr><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>";
            for (const e of sv.episodes) {
                html += `<tr><td>${e.episodeNumber}</td><td>${
                    e.title || ""
                }</td><td>${e.monitored}</td><td>${e.hasFile}</td><td>${
                    e.airDateUtc || ""
                }</td></tr>`;
            }
            html += "</table></details>";
        }
        html += "</details>";
    }
    document.getElementById(targetId).innerHTML = html;
}
function pageSonarr(cat, targetId, delta) {
    sonarrState[cat] = sonarrState[cat] || { page: 0 };
    const ps = parseInt(
        document.getElementById(`${targetId}_ps`).value || "25"
    );
    const total = sonarrState[cat].total || 0;
    const maxPage = Math.max(0, Math.ceil(total / ps) - 1);
    sonarrState[cat].page = Math.min(
        maxPage,
        Math.max(0, (sonarrState[cat].page || 0) + delta)
    );
    loadSonarr(cat, targetId);
}
function filterSonarr(cat, targetId, q) {
    try { sonarrState[cat] = { page: 0 }; } catch(_) {}
    loadSonarrAll(cat, q);
}

async function loadConfig() {
    try {
        const r = await fetch("/api/config", { headers: headers() });
        const d = await r.json();
        document.getElementById("cfgOut").textContent = JSON.stringify(
            d,
            null,
            2
        );
        if (d.Settings && typeof d.Settings.WebUIToken !== "undefined") {
            document.getElementById("configToken").value =
                d.Settings.WebUIToken || "";
        }
    } catch (e) {
        try {
            const r = await fetch("/api/token");
            const d = await r.json();
            if (d.token) {
                document.getElementById("configToken").value = d.token;
            }
        } catch (_) {
            /* ignore */
        }
    }
}
const pending = {};
function addChange() {
    const k = document.getElementById("cfgKey").value;
    const v = document.getElementById("cfgVal").value;
    try {
        pending[k] = JSON.parse(v);
    } catch {
        pending[k] = v;
    }
    document.getElementById("changes").textContent = JSON.stringify(
        { changes: pending },
        null,
        2
    );
}
async function saveChanges() {
    await fetch("/api/config", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ changes: pending }),
    });
    alert("Saved");
    for (const k of Object.keys(pending)) delete pending[k];
    document.getElementById("changes").textContent = "";
}

// default view
// add modern navigation helpers and improved sections
function activate(id) {
    ["processes", "logs", "radarr", "sonarr", "config"].forEach((t) => {
        const link = document.getElementById("tab-" + t);
        if (link) link.classList.toggle("active", t === id);
    });
    show(id);
    if (id === "config") {
        renderConfigForms();
    }
}
async function refreshLogList() {
    const r = await fetch("/api/logs", { headers: headers() });
    const d = await r.json();
    const sel = document.getElementById("logSelect");
    if (!sel) return;
    sel.innerHTML = "";
    for (const f of d.files) {
        const opt = document.createElement("option");
        opt.value = f;
        opt.textContent = f;
        sel.appendChild(opt);
    }
    if (d.files?.length) {
        sel.value = d.files[0];
        startLogFollow();
    }
}
async function loadLogs() {
    await refreshLogList();
}
async function tail(name) {
    const t = localStorage.getItem("token");
    const q = t ? `?token=${encodeURIComponent(t)}` : "";
    const r = await fetch(`/api/logs/${name}${q}`);
    const c = await r.text();
    const el = document.getElementById("logTail");
    if (!el) return;
    el.textContent = c;
    el.dataset.filename = name;
    el.scrollTop = el.scrollHeight;
}
function downloadCurrent() {
    const sel = document.getElementById("logSelect");
    const name = sel && sel.value;
    if (!name) return;
    const t = localStorage.getItem("token");
    const q = t ? `?token=${encodeURIComponent(t)}` : "";
    window.location = `/api/logs/${name}/download${q}`;
}
document.addEventListener("change", (e) => {
    if (e.target && e.target.id === "logSelect") {
        startLogFollow();
    }
});

// Config form renderer
function inputField(label, id, value, type = "text") {
    return `<div class="field"><label for="${id}">${label}</label><input id="${id}" type="${type}" value="${
        value ?? ""
    }"/></div>`;
}
function checkboxField(label, id, checked) {
    return `<div class="field"><label><input id="${id}" type="checkbox" ${
        checked ? "checked" : ""
    }/> ${label}</label></div>`;
}
function selectField(label, id, value, options) {
    const opts = options
        .map(
            (o) =>
                `<option ${
                    String(o) == String(value) ? "selected" : ""
                }>${o}</option>`
        )
        .join("");
    return `<div class="field"><label for="${id}">${label}</label><select id="${id}">${opts}</select></div>`;
}
async function renderConfigForms() {
    const r = await fetch("/api/config", { headers: headers() });
    const cfg = await r.json();
    const root = document.getElementById("configForms");
    if (!root) return;
    root.innerHTML = "";
    let html =
        '<div class="card"><div class="card-header">Settings</div><div class="card-body">';
    html += selectField(
        "Console Level",
        "cfg_ConsoleLevel",
        cfg.Settings?.ConsoleLevel || "INFO",
        ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"]
    );
    html += checkboxField("Logging", "cfg_Logging", !!cfg.Settings?.Logging);
    html += inputField(
        "Completed Download Folder",
        "cfg_CompletedDownloadFolder",
        cfg.Settings?.CompletedDownloadFolder
    );
    html += inputField("Free Space", "cfg_FreeSpace", cfg.Settings?.FreeSpace);
    html += inputField(
        "Free Space Folder",
        "cfg_FreeSpaceFolder",
        cfg.Settings?.FreeSpaceFolder
    );
    html += checkboxField(
        "Auto Pause/Resume",
        "cfg_AutoPauseResume",
        !!cfg.Settings?.AutoPauseResume
    );
    html += inputField(
        "No Internet Sleep (s)",
        "cfg_NoInternetSleepTimer",
        cfg.Settings?.NoInternetSleepTimer,
        "number"
    );
    html += inputField(
        "Loop Sleep (s)",
        "cfg_LoopSleepTimer",
        cfg.Settings?.LoopSleepTimer,
        "number"
    );
    html += inputField(
        "Search Loop Delay (s)",
        "cfg_SearchLoopDelay",
        cfg.Settings?.SearchLoopDelay,
        "number"
    );
    html += inputField(
        "Failed Category",
        "cfg_FailedCategory",
        cfg.Settings?.FailedCategory
    );
    html += inputField(
        "Recheck Category",
        "cfg_RecheckCategory",
        cfg.Settings?.RecheckCategory
    );
    html += checkboxField("Tagless", "cfg_Tagless", !!cfg.Settings?.Tagless);
    html += inputField(
        "Ignore Torrents Younger Than (s)",
        "cfg_IgnoreTorrentsYoungerThan",
        cfg.Settings?.IgnoreTorrentsYoungerThan,
        "number"
    );
    html += inputField(
        "WebUI Host",
        "cfg_WebUIHost",
        cfg.Settings?.WebUIHost || "0.0.0.0"
    );
    html += inputField(
        "WebUI Port",
        "cfg_WebUIPort",
        cfg.Settings?.WebUIPort || 6969,
        "number"
    );
    html +=
        inputField(
            "WebUI Token",
            "cfg_WebUIToken",
            cfg.Settings?.WebUIToken || "",
            "password"
        ) +
        '<label class="hint"><input type="checkbox" onchange="toggleTokenVisibility(\'cfg_WebUIToken\', this)"/> Show</label>';
    html += "</div></div>";
    html +=
        '<div class="card" style="margin-top:12px"><div class="card-header">qBit</div><div class="card-body">';
    html += checkboxField(
        "Disabled",
        "cfg_qBit_Disabled",
        !!cfg.qBit?.Disabled
    );
    html += inputField("Host", "cfg_qBit_Host", cfg.qBit?.Host);
    html += inputField("Port", "cfg_qBit_Port", cfg.qBit?.Port, "number");
    html += inputField("UserName", "cfg_qBit_UserName", cfg.qBit?.UserName);
    html +=
        inputField(
            "Password",
            "cfg_qBit_Password",
            cfg.qBit?.Password,
            "password"
        ) +
        '<label class="hint"><input type="checkbox" onchange="toggleTokenVisibility(\'cfg_qBit_Password\', this)"/> Show</label>';
    html += "</div></div>";
    for (const key of Object.keys(cfg)) {
        if (/(rad|son|anim)arr/i.test(key)) {
            const sec = cfg[key] || {};
            html += `<div class="card" style="margin-top:12px"><div class="card-header">${key}</div><div class="card-body">`;
            html += checkboxField(
                "Managed",
                `cfg_${key}_Managed`,
                !!sec.Managed
            );
            html += inputField("URI", `cfg_${key}_URI`, sec.URI);
            html +=
                inputField(
                    "API Key",
                    `cfg_${key}_APIKey`,
                    sec.APIKey,
                    "password"
                ) +
                `<label class="hint"><input type="checkbox" onchange="toggleTokenVisibility('cfg_${key}_APIKey', this)"/> Show</label>`;
            html += inputField("Category", `cfg_${key}_Category`, sec.Category);
            html += "</div></div>";
        }
    }
    root.innerHTML = html;
}
async function submitConfigForms() {
    const changes = {};
    const get = (id) => document.getElementById(id);
    changes["Settings.ConsoleLevel"] = get("cfg_ConsoleLevel").value;
    changes["Settings.Logging"] = get("cfg_Logging").checked;
    changes["Settings.CompletedDownloadFolder"] = get(
        "cfg_CompletedDownloadFolder"
    ).value;
    changes["Settings.FreeSpace"] = get("cfg_FreeSpace").value;
    changes["Settings.FreeSpaceFolder"] = get("cfg_FreeSpaceFolder").value;
    changes["Settings.AutoPauseResume"] = get("cfg_AutoPauseResume").checked;
    changes["Settings.NoInternetSleepTimer"] = Number(
        get("cfg_NoInternetSleepTimer").value || 0
    );
    changes["Settings.LoopSleepTimer"] = Number(
        get("cfg_LoopSleepTimer").value || 0
    );
    changes["Settings.SearchLoopDelay"] = Number(
        get("cfg_SearchLoopDelay").value || 0
    );
    changes["Settings.FailedCategory"] = get("cfg_FailedCategory").value;
    changes["Settings.RecheckCategory"] = get("cfg_RecheckCategory").value;
    changes["Settings.Tagless"] = get("cfg_Tagless").checked;
    changes["Settings.IgnoreTorrentsYoungerThan"] = Number(
        get("cfg_IgnoreTorrentsYoungerThan").value || 0
    );
    changes["Settings.WebUIHost"] = get("cfg_WebUIHost").value;
    changes["Settings.WebUIPort"] = Number(get("cfg_WebUIPort").value || 6969);
    changes["Settings.WebUIToken"] = get("cfg_WebUIToken").value;
    changes["qBit.Disabled"] = get("cfg_qBit_Disabled").checked;
    changes["qBit.Host"] = get("cfg_qBit_Host").value;
    changes["qBit.Port"] = Number(get("cfg_qBit_Port").value || 0);
    changes["qBit.UserName"] = get("cfg_qBit_UserName").value;
    changes["qBit.Password"] = get("cfg_qBit_Password").value;
    const cards = document.querySelectorAll("#configForms .card .card-header");
    for (const header of cards) {
        const key = header.textContent.trim();
        if (/(rad|son|anim)arr/i.test(key)) {
            const m = (id) => document.getElementById(`cfg_${key}_${id}`);
            if (m("Managed")) changes[`${key}.Managed`] = m("Managed").checked;
            if (m("URI")) changes[`${key}.URI`] = m("URI").value;
            if (m("APIKey")) changes[`${key}.APIKey`] = m("APIKey").value;
            if (m("Category")) changes[`${key}.Category`] = m("Category").value;
        }
    }
    await fetch("/api/config", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ changes }),
    });
    alert("Saved");
}

// default view – auto-load needed data
document.addEventListener("DOMContentLoaded", async () => {
    try {
        await bootstrapToken();
        activate("processes");
        loadProcesses();
        loadStatus();
        await refreshLogList();
        await loadArrList();
    } catch (e) {
        /* ignore */
    }
});

// Load full Radarr dataset for an instance and render a single table
async function loadRadarrAll(cat, q = "") {
    currentArr = { type: "radarr", cat, targetId: "radarrContent" };
    const content = document.getElementById("radarrContent");
    if (!content) return;
    content.innerHTML = '<span class="hint">Loading movies…</span>';
    const pageSize = 500;
    let page = 0;
    let all = [];
    while (true) {
        const r = await fetch(`/api/radarr/${cat}/movies?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`, { headers: headers() });
        if (!r.ok) break;
        const d = await r.json();
        all = all.concat(d.movies || []);
        if (!d.movies || d.movies.length < pageSize) break;
        page += 1;
        if (page > 100) break;
    }
    renderRadarrAllTable(all);
}
function renderRadarrAllTable(items) {
    const content = document.getElementById("radarrContent");
    if (!content) return;
    let html = '';
    html += `<div class="row"><div class="col field"><input placeholder="search movies" oninput="globalSearch(this.value)"/></div></div>`;
    html += "<table><tr><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>";
    for (const m of items) {
        html += `<tr><td>${m.title || ''}</td><td>${m.year || ''}</td><td>${m.monitored ? 'Yes' : 'No'}</td><td>${m.hasFile ? 'Yes' : 'No'}</td></tr>`;
    }
    html += "</table>";
    content.innerHTML = html;
}

// Load full Sonarr dataset for an instance and render a flattened episodes table
async function loadSonarrAll(cat, q = "") {
    currentArr = { type: "sonarr", cat, targetId: "sonarrContent" };
    const content = document.getElementById("sonarrContent");
    if (!content) return;
    content.innerHTML = '<span class="hint">Loading series…</span>';
    const pageSize = 200;
    let page = 0;
    let allSeries = [];
    while (true) {
        const r = await fetch(`/api/sonarr/${cat}/series?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`, { headers: headers() });
        if (!r.ok) break;
        const d = await r.json();
        allSeries = allSeries.concat(d.series || []);
        if (!d.series || d.series.length < pageSize) break;
        page += 1;
        if (page > 200) break;
    }
    const rows = [];
    for (const s of allSeries) {
        const seriesTitle = s.series?.title || '';
        for (const [sn, sv] of Object.entries(s.seasons || {})) {
            for (const e of (sv.episodes || [])) {
                rows.push({ series: seriesTitle, season: sn, ep: e.episodeNumber, title: e.title || '', monitored: !!e.monitored, hasFile: !!e.hasFile, air: e.airDateUtc || '' });
            }
        }
    }
    renderSonarrAllTable(rows);
}
function renderSonarrAllTable(rows) {
    const content = document.getElementById("sonarrContent");
    if (!content) return;
    let html = '';
    html += `<div class="row"><div class="col field"><input placeholder="search episodes" oninput="globalSearch(this.value)"/></div></div>`;
    html += "<table><tr><th>Series</th><th>Season</th><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>";
    for (const r of rows) {
        html += `<tr><td>${r.series}</td><td>${r.season}</td><td>${r.ep}</td><td>${r.title}</td><td>${r.monitored ? 'Yes':'No'}</td><td>${r.hasFile ? 'Yes':'No'}</td><td>${r.air}</td></tr>`;
    }
    html += "</table>";
    content.innerHTML = html;
}

// Config helpers for token visibility and saving
function toggleTokenVisibility(inputId, cb) {
    const el = document.getElementById(inputId);
    if (!el) return;
    el.type = cb.checked ? "text" : "password";
}
async function saveTokenToConfig() {
    const val = document.getElementById("configToken").value;
    if (!val) {
        alert("Token cannot be empty");
        return;
    }
    await fetch("/api/config", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ changes: { "Settings.WebUIToken": val } }),
    });
    alert("Token saved");
    localStorage.setItem("token", val);
}

// Aggregated views across all instances with loading placeholders and pagination
const radarrAgg = { items: [], filtered: [], page: 0, pageSize: 50, q: "" };
function radarrAggApply() {
    const ql = (radarrAgg.q || "").toLowerCase();
    if (!ql) radarrAgg.filtered = radarrAgg.items;
    else radarrAgg.filtered = radarrAgg.items.filter(m => (m.title||'').toLowerCase().includes(ql) || (m.__instance||'').toLowerCase().includes(ql));
    const totalPages = Math.max(1, Math.ceil(radarrAgg.filtered.length / radarrAgg.pageSize));
    radarrAgg.page = Math.min(radarrAgg.page, totalPages - 1);
}
function renderRadarrAgg() {
    const content = document.getElementById('radarrContent');
    if (!content) return;
    radarrAggApply();
    const start = radarrAgg.page * radarrAgg.pageSize;
    const items = radarrAgg.filtered.slice(start, start + radarrAgg.pageSize);
    let html = '';
    html += `<div class="row"><div class="col field"><input placeholder="search movies" value="${radarrAgg.q}" oninput="radarrAggSearch(this.value)"/></div></div>`;
    html += '<table><tr><th>Instance</th><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>';
    for (const m of items) {
        html += `<tr><td>${m.__instance||''}</td><td>${m.title||''}</td><td>${m.year||''}</td><td>${m.monitored?'Yes':'No'}</td><td>${m.hasFile?'Yes':'No'}</td></tr>`;
    }
    html += '</table>';
    const totalPages = Math.max(1, Math.ceil(radarrAgg.filtered.length / radarrAgg.pageSize));
    html += `<div class="row" style="margin-top:8px"><div class="col">Page ${radarrAgg.page+1} of ${totalPages} (${radarrAgg.filtered.length} items)</div><div class="col" style="text-align:right"><button class="btn" onclick="radarrAggPage(-1)">Prev</button> <button class="btn" onclick="radarrAggPage(1)">Next</button></div></div>`;
    content.innerHTML = html;
}
function radarrAggPage(d) {
    const totalPages = Math.max(1, Math.ceil(radarrAgg.filtered.length / radarrAgg.pageSize));
    radarrAgg.page = Math.min(totalPages-1, Math.max(0, radarrAgg.page + d));
    renderRadarrAgg();
}
function radarrAggSearch(q) { radarrAgg.q = q||""; radarrAgg.page = 0; renderRadarrAgg(); }
async function loadRadarrAllInstances(cats) {
    currentArr = { type: 'radarrAll' };
    const content = document.getElementById('radarrContent');
    if (!content) return;
    content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading Radarr…</div>';
    radarrAgg.items = [];
    for (const cat of (cats||[])) {
        const label = (arrIndex.radarr && arrIndex.radarr[cat]) || cat;
        let page = 0, pageSize = 500;
        while (true) {
            const r = await fetch(`/api/radarr/${cat}/movies?q=&page=${page}&page_size=${pageSize}`, { headers: headers() });
            if (!r.ok) break;
            const d = await r.json();
            for (const m of (d.movies||[])) radarrAgg.items.push({ ...m, __instance: label });
            if (!d.movies || d.movies.length < pageSize) break;
            page += 1; if (page > 100) break;
        }
    }
    radarrAgg.page = 0; radarrAgg.q = ""; renderRadarrAgg();
}

const sonarrAgg = { rows: [], filtered: [], page: 0, pageSize: 100, q: "" };
function sonarrAggApply() {
    const ql = (sonarrAgg.q || "").toLowerCase();
    if (!ql) sonarrAgg.filtered = sonarrAgg.rows;
    else sonarrAgg.filtered = sonarrAgg.rows.filter(r => (r.series||'').toLowerCase().includes(ql) || (r.__instance||'').toLowerCase().includes(ql) || (r.title||'').toLowerCase().includes(ql));
    const totalPages = Math.max(1, Math.ceil(sonarrAgg.filtered.length / sonarrAgg.pageSize));
    sonarrAgg.page = Math.min(sonarrAgg.page, totalPages - 1);
}
function renderSonarrAgg() {
    const content = document.getElementById('sonarrContent');
    if (!content) return;
    sonarrAggApply();
    const start = sonarrAgg.page * sonarrAgg.pageSize;
    const rows = sonarrAgg.filtered.slice(start, start + sonarrAgg.pageSize);
    let html = '';
    html += `<div class="row"><div class="col field"><input placeholder="search episodes" value="${sonarrAgg.q}" oninput="sonarrAggSearch(this.value)"/></div></div>`;
    html += '<table><tr><th>Instance</th><th>Series</th><th>Season</th><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>';
    for (const r of rows) {
        html += `<tr><td>${r.__instance||''}</td><td>${r.series}</td><td>${r.season}</td><td>${r.ep}</td><td>${r.title}</td><td>${r.monitored?'Yes':'No'}</td><td>${r.hasFile?'Yes':'No'}</td><td>${r.air}</td></tr>`;
    }
    html += '</table>';
    const totalPages = Math.max(1, Math.ceil(sonarrAgg.filtered.length / sonarrAgg.pageSize));
    html += `<div class="row" style="margin-top:8px"><div class="col">Page ${sonarrAgg.page+1} of ${totalPages} (${sonarrAgg.filtered.length} rows)</div><div class="col" style="text-align:right"><button class="btn" onclick="sonarrAggPage(-1)">Prev</button> <button class="btn" onclick="sonarrAggPage(1)">Next</button></div></div>`;
    content.innerHTML = html;
}
function sonarrAggPage(d) {
    const totalPages = Math.max(1, Math.ceil(sonarrAgg.filtered.length / sonarrAgg.pageSize));
    sonarrAgg.page = Math.min(totalPages-1, Math.max(0, sonarrAgg.page + d));
    renderSonarrAgg();
}
function sonarrAggSearch(q) { sonarrAgg.q = q||""; sonarrAgg.page = 0; renderSonarrAgg(); }
async function loadSonarrAllInstances(cats) {
    currentArr = { type: 'sonarrAll' };
    const content = document.getElementById('sonarrContent');
    if (!content) return;
    content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading Sonarr…</div>';
    sonarrAgg.rows = [];
    for (const cat of (cats||[])) {
        const label = (arrIndex.sonarr && arrIndex.sonarr[cat]) || cat;
        let page = 0, pageSize = 200;
        while (true) {
            const r = await fetch(`/api/sonarr/${cat}/series?q=&page=${page}&page_size=${pageSize}`, { headers: headers() });
            if (!r.ok) break;
            const d = await r.json();
            const series = d.series || [];
            for (const s of series) {
                const seriesTitle = s.series?.title || '';
                for (const [sn, sv] of Object.entries(s.seasons || {})) {
                    for (const e of (sv.episodes || [])) {
                        sonarrAgg.rows.push({ __instance: label, series: seriesTitle, season: sn, ep: e.episodeNumber, title: e.title || '', monitored: !!e.monitored, hasFile: !!e.hasFile, air: e.airDateUtc || '' });
                    }
                }
            }
            if (!series || series.length < pageSize) break;
            page += 1; if (page > 200) break;
        }
    }
    sonarrAgg.page = 0; sonarrAgg.q = ""; renderSonarrAgg();
}
