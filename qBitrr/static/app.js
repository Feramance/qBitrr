const headers = () => {
    const h = { "Content-Type": "application/json" };
    const t = localStorage.getItem("token");
    if (t) h["Authorization"] = "Bearer " + t;
    return h;
};

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
    const r = await fetch("/api/status", { headers: headers() });
    const d = await r.json();
    const qb = d.qbit.alive
        ? "<span class=ok>qBit OK</span>"
        : "<span class=bad>qBit DOWN</span>";
    let arr = "";
    for (const a of d.arrs) {
        arr += `${a.category}:${a.alive ? "OK" : "DOWN"} `;
    }
    document.getElementById("status").innerHTML = qb + " | " + arr;
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
async function loadArrList() {
    const r = await fetch("/api/arr", { headers: headers() });
    const d = await r.json();
    let rs = "",
        ss = "";
    for (const a of d.arr) {
        if (a.type === "radarr") {
            const id = `radarrOut_${a.category}`;
            rs += `<div><div><input placeholder='filter' oninput=filterRadarr('${a.category}','${id}',this.value) /><input id='${id}_ps' type='number' value='50' style='width:60px'/> <button onclick=pageRadarr('${a.category}','${id}',-1)>Prev</button> <button onclick=pageRadarr('${a.category}','${id}',1)>Next</button> <button onclick=loadRadarr('${a.category}','${id}')>Load ${a.category}</button> <button onclick=restartArr('${a.category}')>Restart</button></div><div id='${id}'></div></div>`;
        }
        if (a.type === "sonarr") {
            const id = `sonarrOut_${a.category}`;
            ss += `<div><div><input placeholder='filter' oninput=filterSonarr('${a.category}','${id}',this.value) /><input id='${id}_ps' type='number' value='25' style='width:60px'/> <button onclick=pageSonarr('${a.category}','${id}',-1)>Prev</button> <button onclick=pageSonarr('${a.category}','${id}',1)>Next</button> <button onclick=loadSonarr('${a.category}','${id}')>Load ${a.category}</button> <button onclick=restartArr('${a.category}')>Restart</button></div><div id='${id}'></div></div>`;
        }
    }
    document.getElementById("radarrList").innerHTML = rs;
    document.getElementById("sonarrList").innerHTML = ss;
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
    document.getElementById(`${targetId}`).dataset.filter = q;
    radarrState[cat] = { page: 0 };
    loadRadarr(cat, targetId);
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
    document.getElementById(`${targetId}`).dataset.filter = q;
    sonarrState[cat] = { page: 0 };
    loadSonarr(cat, targetId);
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

// default view
activate("processes");
loadProcesses();
loadStatus();

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
