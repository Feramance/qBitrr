const headers = () => ({ "Content-Type": "application/json" });

// Ensure functions are available for inline onclick/oninput handlers
try {
    if (typeof window !== "undefined") {
        if (typeof loadStatus === "function") window.loadStatus = loadStatus;
        if (typeof loadProcesses === "function")
            window.loadProcesses = loadProcesses;
        if (typeof restart === "function") window.restart = restart;
        if (typeof restartAll === "function") window.restartAll = restartAll;
        if (typeof rebuildArrs === "function") window.rebuildArrs = rebuildArrs;
        if (typeof applyLogLevel === "function")
            window.applyLogLevel = applyLogLevel;
        if (typeof refreshLogList === "function")
            window.refreshLogList = refreshLogList;
        if (typeof downloadCurrent === "function")
            window.downloadCurrent = downloadCurrent;
        if (typeof loadArrList === "function") window.loadArrList = loadArrList;
        if (typeof globalSearch === "function")
            window.globalSearch = globalSearch;
        if (typeof renderConfigForms === "function")
            window.renderConfigForms = renderConfigForms;
        if (typeof submitConfigForms === "function")
            window.submitConfigForms = submitConfigForms;
        if (typeof addArrInstance === "function")
            window.addArrInstance = addArrInstance;
        if (typeof loadRadarrAllInstances === "function")
            window.loadRadarrAllInstances = loadRadarrAllInstances;
        if (typeof loadSonarrAllInstances === "function")
            window.loadSonarrAllInstances = loadSonarrAllInstances;
        if (typeof loadRadarrAll === "function")
            window.loadRadarrAll = loadRadarrAll;
        if (typeof loadSonarrAll === "function")
            window.loadSonarrAll = loadSonarrAll;
    }
} catch (e) {
    /* ignore */
}

try {
    window.loadProcesses = loadProcesses;
    window.restart = restart;
    window.restartAll = restartAll;
    window.rebuildArrs = rebuildArrs;
    window.applyLogLevel = applyLogLevel;
    window.refreshLogList = refreshLogList;
    window.downloadCurrent = downloadCurrent;
    window.loadArrList = loadArrList;
} catch (e) {}
let currentArr = null; // { type: 'radarr'|'sonarr', cat, targetId }function globalSearch(q) {    if (!currentArr) return;    if (currentArr.type === "radarrAll") {        radarrAggSearch(q);    } else if (currentArr.type === "sonarrAll") {        sonarrAggSearch(q);    } else if (currentArr.type === "radarr") {        filterRadarr(currentArr.cat, currentArr.targetId, q);    } else if (currentArr.type === "sonarr") {        filterSonarr(currentArr.cat, currentArr.targetId, q);    }}function saveToken() {    const t = document.getElementById("token").value;    localStorage.setItem("token", t);}async function showTokenLocal() {    try {        const r = await fetch("/api/token");        const d = await r.json();        if (d.token) {            document.getElementById("token").value = d.token;        } else {            alert(d.error || "Not available");        }    } catch (e) {        alert("Not available");    }}function show(id) {    for (const s of document.querySelectorAll("section"))        s.style.display = "none";    const el = document.getElementById(id);    if (el) el.style.display = "block";}function activate(id) {    ["processes", "logs", "radarr", "sonarr", "config"].forEach((t) => {        const link = document.getElementById("tab-" + t);        if (link) link.classList.toggle("active", t === id);    });    show(id);}async function loadStatus() {    const [s, p, a] = await Promise.all([        fetch("/web/status", { headers: headers() })            .then((r) => r.json())            .catch((_) => ({ qbit: { alive: false }, arrs: [] })),        fetch("/web/processes", { headers: headers() })            .then((r) => r.json())            .catch((_) => ({ processes: [] })),        fetch("/web/arr", { headers: headers() })            .then((r) => r.json())            .catch((_) => ({ arr: [] })),    ]);    const qb =        s.qbit && s.qbit.alive            ? "<span class=ok>qBit OK</span>"            : "<span class=bad>qBit DOWN</span>";    const nameByCat = {};    for (const it of a.arr || []) {        nameByCat[it.category] = it.name || it.category;    }    const aliveByCat = {};    for (const proc of p.processes || []) {        if (proc.alive) aliveByCat[proc.category] = true;        if (!nameByCat[proc.category])            nameByCat[proc.category] = proc.name || proc.category;    }    const cats = new Set([        ...(s.arrs ? s.arrs.map((x) => x.category) : []),        ...Object.keys(aliveByCat),    ]);    let arrText = "";    for (const cat of cats) {        const alive =            aliveByCat[cat] ??            (s.arrs                ? s.arrs.find((x) => x.category === cat)?.alive || false                : false);        const label = nameByCat[cat] || cat;        arrText += `${label}:${alive ? "OK" : "DOWN"} `;    }    document.getElementById("status").innerHTML = qb + " | " + arrText;}async function loadProcesses() {    const r = await fetch("/web/processes", { headers: headers() });    const d = await r.json();    let html =        "<table><tr><th>Category</th><th>Name</th><th>Kind</th><th>PID</th><th>Alive</th><th>Actions</th></tr>";    for (const p of d.processes) {        html += `<tr><td>${p.category}</td><td>${p.name}</td><td>${            p.kind        }</td><td>${p.pid || ""}</td><td>${            p.alive ? "<span class=ok>yes</span>" : "<span class=bad>no</span>"        }</td><td><button onclick=restart('${p.category}','${            p.kind        }')>Restart</button></td></tr>`;    }    html += "</table>";    document.getElementById("procOut").innerHTML = html;}async function restart(category, kind) {    await fetch(`/web/processes/${category}/${kind}/restart`, {        method: "POST",        headers: headers(),    });    loadProcesses();}async function restartAll() {    await fetch("/web/processes/restart_all", {        method: "POST",        headers: headers(),    });    loadProcesses();}async function rebuildArrs() {    await fetch("/web/arr/rebuild", { method: "POST", headers: headers() });    loadProcesses();    loadArrList();}function toast(msg, type = "") {    const wrap = document.getElementById("toasts");    if (!wrap) return;    const el = document.createElement("div");    el.className = "toast " + type;    el.textContent = msg;    wrap.appendChild(el);    setTimeout(() => {        el.style.opacity = "0";    }, 2800);    setTimeout(() => {        wrap.removeChild(el);    }, 3500);}async function applyLogLevel() {    const lv = document.getElementById("logLevel").value;    const res = await fetch("/web/loglevel", {        method: "POST",        headers: headers(),        body: JSON.stringify({ level: lv }),    });    if (res.ok) {        toast("Log level set to " + lv, "success");    } else {        toast("Failed to set log level", "error");    }}async function refreshLogList() {    const r = await fetch("/web/logs", { headers: headers() });    const d = await r.json();    const sel = document.getElementById("logSelect");    if (!sel) return;    sel.innerHTML = "";    for (const f of d.files) {        const opt = document.createElement("option");        opt.value = f;        opt.textContent = f;        sel.appendChild(opt);    }    if (d.files && d.files.length) {        sel.value = d.files[0];        startLogFollow();    }}async function loadLogs() {    await refreshLogList();}async function tail(name) {    const t = localStorage.getItem("token");    const q = t ? `?token=${encodeURIComponent(t)}` : "";    const r = await fetch(`/web/logs/${name}${q}`);    const c = await r.text();    const el = document.getElementById("logTail");    if (!el) return;    el.textContent = c;    el.dataset.filename = name;    el.scrollTop = el.scrollHeight;}function downloadCurrent() {    const sel = document.getElementById("logSelect");    const name = sel && sel.value;    if (!name) return;    const t = localStorage.getItem("token");    const q = t ? `?token=${encodeURIComponent(t)}` : "";    window.location = `/web/logs/${name}/download${q}`;}let logTimer = null;function startLogFollow() {    if (logTimer) clearInterval(logTimer);    const sel = document.getElementById("logSelect");    if (!sel) return;    const run = () => {        const live = document.getElementById("logFollow");        if (live && !live.checked) return;        if (sel.value) tail(sel.value);    };    run();    logTimer = setInterval(run, 2000);}document.addEventListener("change", (e) => {    if (e.target && e.target.id === "logSelect") {        startLogFollow();    }});const radarrState = {};const sonarrState = {};const arrIndex = { radarr: {}, sonarr: {} };async function loadArrList() {    const [arrRes, procRes] = await Promise.all([        fetch("/web/arr", { headers: headers() }),        fetch("/web/processes", { headers: headers() }),    ]);    const d = await arrRes.json();    const procs = await procRes.json();    const nameByCat = {};    for (const p of procs.processes || [])        nameByCat[p.category] = p.name || p.category;    const radarrCats = [];    const sonarrCats = [];    for (const a of d.arr) {        const name = a.name || nameByCat[a.category] || a.category;        if (a.type === "radarr") { radarrCats.push(a.category); arrIndex && (arrIndex.radarr = arrIndex.radarr || {}, arrIndex.radarr[a.category] = name); }        if (a.type === "sonarr") { sonarrCats.push(a.category); arrIndex && (arrIndex.sonarr = arrIndex.sonarr || {}, arrIndex.sonarr[a.category] = name); }    }    const rnav = document.getElementById("radarrNav");    if (rnav) rnav.innerHTML = `<button class="btn" onclick="loadRadarrAllInstances(window.__radarrCats)">Load All Radarr</button>`;    const snav = document.getElementById("sonarrNav");    if (snav) snav.innerHTML = `<button class="btn" onclick="loadSonarrAllInstances(window.__sonarrCats)">Load All Sonarr</button>`;    // Store cats on window for button handlers    window.__radarrCats = radarrCats;    window.__sonarrCats = sonarrCats;}async function restartArr(cat) {    const res = await fetch(`/web/arr/${cat}/restart`, {        method: "POST",        headers: headers(),    });    if (res.ok) {        toast("Restarted " + cat, "success");    } else {        toast("Failed to restart " + cat, "error");    }}async function loadRadarr(cat, targetId) {    const ps = parseInt(        document.getElementById(`${targetId}_ps`).value || "50"    );    const q = document.getElementById(`${targetId}`).dataset.filter || "";    const page = radarrState[cat]?.page || 0;    const r = await fetch(        `/web/radarr/${cat}/movies?q=${encodeURIComponent(            q        )}&page=${page}&page_size=${ps}`,        { headers: headers() }    );    const d = await r.json();    radarrState[cat] = { page, counts: d.counts, total: d.total };    currentArr = { type: "radarr", cat, targetId };    renderRadarr(cat, targetId, d.movies, d.total, ps);}function renderRadarr(cat, targetId, items, total, ps) {    const page = radarrState[cat].page || 0;    const pages = Math.max(1, Math.ceil(total / ps));    let html = `<p>Counts: ${radarrState[cat].counts.available} / ${        radarrState[cat].counts.monitored    } — Page ${page + 1} of ${pages} (total ${total})</p>`;    html +=        "<table><tr><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>";    for (const m of items) {        html += `<tr><td>${m.title}</td><td>${m.year || ""}</td><td>${            m.monitored        }</td><td>${m.hasFile}</td></tr>`;    }    html += "</table>";    document.getElementById(targetId).innerHTML = html;}function pageRadarr(cat, targetId, delta) {    radarrState[cat] = radarrState[cat] || { page: 0 };    const ps = parseInt(        document.getElementById(`${targetId}_ps`).value || "50"    );    const total = radarrState[cat].total || 0;    const maxPage = Math.max(0, Math.ceil(total / ps) - 1);    radarrState[cat].page = Math.min(        maxPage,        Math.max(0, (radarrState[cat].page || 0) + delta)    );    loadRadarr(cat, targetId);}function filterRadarr(cat, targetId, q) {    try { radarrState[cat] = { page: 0 }; } catch(_) {}    loadRadarrAll(cat, q);}async function loadSonarr(cat, targetId) {    const ps = parseInt(        document.getElementById(`${targetId}_ps`).value || "25"    );    const q = document.getElementById(`${targetId}`).dataset.filter || "";    const page = sonarrState[cat]?.page || 0;    const r = await fetch(        `/web/sonarr/${cat}/series?q=${encodeURIComponent(            q        )}&page=${page}&page_size=${ps}`,        { headers: headers() }    );    const d = await r.json();    sonarrState[cat] = { page, counts: d.counts, total: d.total };    currentArr = { type: "sonarr", cat, targetId };    renderSonarr(cat, targetId, d.series, d.total, ps);}function renderSonarr(cat, targetId, series, total, ps) {    const page = sonarrState[cat].page || 0;    const pages = Math.max(1, Math.ceil(total / ps));    let html = `<p>Counts: ${sonarrState[cat].counts.available} / ${        sonarrState[cat].counts.monitored    } — Page ${page + 1} of ${pages} (total ${total})</p>`;    for (const s of series) {        html += `<details><summary>${s.series.title} — ${s.totals.available} / ${s.totals.monitored}</summary>`;        const seasons = Object.entries(s.seasons).sort((a, b) => a[0] - b[0]);        for (const [sn, sv] of seasons) {            html += `<details style='margin-left:12px'><summary>Season ${sn} — ${sv.available} / ${sv.monitored}</summary>`;            html +=                "<table><tr><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>";            for (const e of sv.episodes) {                html += `<tr><td>${e.episodeNumber}</td><td>${                    e.title || ""                }</td><td>${e.monitored}</td><td>${e.hasFile}</td><td>${                    e.airDateUtc || ""                }</td></tr>`;            }            html += "</table></details>";        }        html += "</details>";    }    document.getElementById(targetId).innerHTML = html;}function pageSonarr(cat, targetId, delta) {    sonarrState[cat] = sonarrState[cat] || { page: 0 };    const ps = parseInt(        document.getElementById(`${targetId}_ps`).value || "25"    );    const total = sonarrState[cat].total || 0;    const maxPage = Math.max(0, Math.ceil(total / ps) - 1);    sonarrState[cat].page = Math.min(        maxPage,        Math.max(0, (sonarrState[cat].page || 0) + delta)    );    loadSonarr(cat, targetId);}function filterSonarr(cat, targetId, q) {    try { sonarrState[cat] = { page: 0 }; } catch(_) {}    loadSonarrAll(cat, q);}async function loadConfig() {    try {        const r = await fetch("/web/config", { headers: headers() });        const d = await r.json();        document.getElementById("cfgOut").textContent = JSON.stringify(            d,            null,            2        );        if (d.Settings && typeof d.Settings.WebUIToken !== "undefined") {            document.getElementById("configToken").value =                d.Settings.WebUIToken || "";        }    } catch (e) {        try {            const r = await fetch("/api/token");            const d = await r.json();            if (d.token) {                document.getElementById("configToken").value = d.token;            }        } catch (_) {            /* ignore */        }    }}const pending = {};function addChange() {    const k = document.getElementById("cfgKey").value;    const v = document.getElementById("cfgVal").value;    try {        pending[k] = JSON.parse(v);    } catch {        pending[k] = v;    }    document.getElementById("changes").textContent = JSON.stringify(        { changes: pending },        null,        2    );}async function saveChanges() {    await fetch("/web/config", {        method: "POST",        headers: headers(),        body: JSON.stringify({ changes: pending }),    });    alert("Saved");    for (const k of Object.keys(pending)) delete pending[k];    document.getElementById("changes").textContent = "";}// default view// add modern navigation helpers and improved sectionsfunction activate(id) {    ["processes", "logs", "radarr", "sonarr", "config"].forEach((t) => {        const link = document.getElementById("tab-" + t);        if (link) link.classList.toggle("active", t === id);    });    show(id);    if (id === "config") {        renderConfigForms();    }}async function refreshLogList() {    const r = await fetch("/web/logs", { headers: headers() });    const d = await r.json();    const sel = document.getElementById("logSelect");    if (!sel) return;    sel.innerHTML = "";    for (const f of d.files) {        const opt = document.createElement("option");        opt.value = f;        opt.textContent = f;        sel.appendChild(opt);    }    if (d.files?.length) {        sel.value = d.files[0];        startLogFollow();    }}async function loadLogs() {    await refreshLogList();}async function tail(name) {    const t = localStorage.getItem("token");    const q = t ? `?token=${encodeURIComponent(t)}` : "";    const r = await fetch(`/web/logs/${name}${q}`);    const c = await r.text();    const el = document.getElementById("logTail");    if (!el) return;    el.textContent = c;    el.dataset.filename = name;    el.scrollTop = el.scrollHeight;}function downloadCurrent() {    const sel = document.getElementById("logSelect");    const name = sel && sel.value;    if (!name) return;    const t = localStorage.getItem("token");    const q = t ? `?token=${encodeURIComponent(t)}` : "";    window.location = `/web/logs/${name}/download${q}`;}document.addEventListener("change", (e) => {    if (e.target && e.target.id === "logSelect") {        startLogFollow();    }});// Config form rendererfunction inputField(label, id, value, type = "text") {    return `<div class="field"><label for="${id}">${label}</label><input id="${id}" type="${type}" value="${        value ?? ""    }"/></div>`;}function checkboxField(label, id, checked) {    return `<div class="field"><label><input id="${id}" type="checkbox" ${        checked ? "checked" : ""    }/> ${label}</label></div>`;}function selectField(label, id, value, options) {    const opts = options        .map(            (o) =>                `<option ${                    String(o) == String(value) ? "selected" : ""                }>${o}</option>`        )        .join("");    return `<div class="field"><label for="${id}">${label}</label><select id="${id}">${opts}</select></div>`;}async function renderConfigForms() {    const r = await fetch("/web/config", { headers: headers() });    const cfg = await r.json();    const root = document.getElementById("configForms");    if (!root) return;    root.innerHTML = "";    let html =        '<div class="card"><div class="card-header">Settings</div><div class="card-body">';    html += selectField(        "Console Level",        "cfg_ConsoleLevel",        cfg.Settings?.ConsoleLevel || "INFO",        ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"]    );    html += checkboxField("Logging", "cfg_Logging", !!cfg.Settings?.Logging);    html += inputField(        "Completed Download Folder",        "cfg_CompletedDownloadFolder",        cfg.Settings?.CompletedDownloadFolder    );    html += inputField("Free Space", "cfg_FreeSpace", cfg.Settings?.FreeSpace);    html += inputField(        "Free Space Folder",        "cfg_FreeSpaceFolder",        cfg.Settings?.FreeSpaceFolder    );    html += checkboxField(        "Auto Pause/Resume",        "cfg_AutoPauseResume",        !!cfg.Settings?.AutoPauseResume    );    html += inputField(        "No Internet Sleep (s)",        "cfg_NoInternetSleepTimer",        cfg.Settings?.NoInternetSleepTimer,        "number"    );    html += inputField(        "Loop Sleep (s)",        "cfg_LoopSleepTimer",        cfg.Settings?.LoopSleepTimer,        "number"    );    html += inputField(        "Search Loop Delay (s)",        "cfg_SearchLoopDelay",        cfg.Settings?.SearchLoopDelay,        "number"    );    html += inputField(        "Failed Category",        "cfg_FailedCategory",        cfg.Settings?.FailedCategory    );    html += inputField(        "Recheck Category",        "cfg_RecheckCategory",        cfg.Settings?.RecheckCategory    );    html += checkboxField("Tagless", "cfg_Tagless", !!cfg.Settings?.Tagless);    html += inputField(        "Ignore Torrents Younger Than (s)",        "cfg_IgnoreTorrentsYoungerThan",        cfg.Settings?.IgnoreTorrentsYoungerThan,        "number"    );    html += inputField(        "WebUI Host",        "cfg_WebUIHost",        cfg.Settings?.WebUIHost || "0.0.0.0"    );    html += inputField(        "WebUI Port",        "cfg_WebUIPort",        cfg.Settings?.WebUIPort || 6969,        "number"    );    html +=        inputField(            "WebUI Token",            "cfg_WebUIToken",            cfg.Settings?.WebUIToken || "",            "password"        ) +        '<label class="hint"><input type="checkbox" onchange="toggleTokenVisibility(\'cfg_WebUIToken\', this)"/> Show</label>';    html += "</div></div>";    html +=        '<div class="card" style="margin-top:12px"><div class="card-header">qBit</div><div class="card-body">';    html += checkboxField(        "Disabled",        "cfg_qBit_Disabled",        !!cfg.qBit?.Disabled    );    html += inputField("Host", "cfg_qBit_Host", cfg.qBit?.Host);    html += inputField("Port", "cfg_qBit_Port", cfg.qBit?.Port, "number");    html += inputField("UserName", "cfg_qBit_UserName", cfg.qBit?.UserName);    html +=        inputField(            "Password",            "cfg_qBit_Password",            cfg.qBit?.Password,            "password"        ) +        '<label class="hint"><input type="checkbox" onchange="toggleTokenVisibility(\'cfg_qBit_Password\', this)"/> Show</label>';    html += "</div></div>";    for (const key of Object.keys(cfg)) {        if (/(rad|son|anim)arr/i.test(key)) {            const sec = cfg[key] || {};            html += `<div class="card" style="margin-top:12px"><div class="card-header">${key}</div><div class="card-body">`;            html += checkboxField(                "Managed",                `cfg_${key}_Managed`,                !!sec.Managed            );            html += inputField("URI", `cfg_${key}_URI`, sec.URI);            html +=                inputField(                    "API Key",                    `cfg_${key}_APIKey`,                    sec.APIKey,                    "password"                ) +                `<label class="hint"><input type="checkbox" onchange="toggleTokenVisibility('cfg_${key}_APIKey', this)"/> Show</label>`;            html += inputField("Category", `cfg_${key}_Category`, sec.Category);            html += "</div></div>";        }    }    root.innerHTML = html;}async function submitConfigForms() {    const changes = {};    const get = (id) => document.getElementById(id);    changes["Settings.ConsoleLevel"] = get("cfg_ConsoleLevel").value;    changes["Settings.Logging"] = get("cfg_Logging").checked;    changes["Settings.CompletedDownloadFolder"] = get(        "cfg_CompletedDownloadFolder"    ).value;    changes["Settings.FreeSpace"] = get("cfg_FreeSpace").value;    changes["Settings.FreeSpaceFolder"] = get("cfg_FreeSpaceFolder").value;    changes["Settings.AutoPauseResume"] = get("cfg_AutoPauseResume").checked;    changes["Settings.NoInternetSleepTimer"] = Number(        get("cfg_NoInternetSleepTimer").value || 0    );    changes["Settings.LoopSleepTimer"] = Number(        get("cfg_LoopSleepTimer").value || 0    );    changes["Settings.SearchLoopDelay"] = Number(        get("cfg_SearchLoopDelay").value || 0    );    changes["Settings.FailedCategory"] = get("cfg_FailedCategory").value;    changes["Settings.RecheckCategory"] = get("cfg_RecheckCategory").value;    changes["Settings.Tagless"] = get("cfg_Tagless").checked;    changes["Settings.IgnoreTorrentsYoungerThan"] = Number(        get("cfg_IgnoreTorrentsYoungerThan").value || 0    );    changes["Settings.WebUIHost"] = get("cfg_WebUIHost").value;    changes["Settings.WebUIPort"] = Number(get("cfg_WebUIPort").value || 6969);    changes["Settings.WebUIToken"] = get("cfg_WebUIToken").value;    changes["qBit.Disabled"] = get("cfg_qBit_Disabled").checked;    changes["qBit.Host"] = get("cfg_qBit_Host").value;    changes["qBit.Port"] = Number(get("cfg_qBit_Port").value || 0);    changes["qBit.UserName"] = get("cfg_qBit_UserName").value;    changes["qBit.Password"] = get("cfg_qBit_Password").value;    const cards = document.querySelectorAll("#configForms .card .card-header");    for (const header of cards) {        const key = header.textContent.trim();        if (/(rad|son|anim)arr/i.test(key)) {            const m = (id) => document.getElementById(`cfg_${key}_${id}`);            if (m("Managed")) changes[`${key}.Managed`] = m("Managed").checked;            if (m("URI")) changes[`${key}.URI`] = m("URI").value;            if (m("APIKey")) changes[`${key}.APIKey`] = m("APIKey").value;            if (m("Category")) changes[`${key}.Category`] = m("Category").value;        }    }    await fetch("/web/config", {        method: "POST",        headers: headers(),        body: JSON.stringify({ changes }),    });    alert("Saved");}// default view – auto-load needed datadocument.addEventListener("DOMContentLoaded", async () => {    try {        await bootstrapToken();        activate("processes");        loadProcesses();        loadStatus();        await refreshLogList();        await loadArrList();    } catch (e) {        /* ignore */    }});// Load full Radarr dataset for an instance and render a single tableasync function loadRadarrAll(cat, q = "") {    currentArr = { type: "radarr", cat, targetId: "radarrContent" };    const content = document.getElementById("radarrContent");    if (!content) return;    content.innerHTML = '<span class="hint">Loading movies…</span>';    const pageSize = 500;    let page = 0;    let all = [];    while (true) {        const r = await fetch(`/web/radarr/${cat}/movies?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`, { headers: headers() });        if (!r.ok) break;        const d = await r.json();        all = all.concat(d.movies || []);        if (!d.movies || d.movies.length < pageSize) break;        page += 1;        if (page > 100) break;    }    renderRadarrAllTable(all);}function renderRadarrAllTable(items) {    const content = document.getElementById("radarrContent");    if (!content) return;    let html = '';    html += `<div class="row"><div class="col field"><input placeholder="search movies" oninput="globalSearch(this.value)"/></div></div>`;    html += "<table><tr><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>";    for (const m of items) {        html += `<tr><td>${m.title || ''}</td><td>${m.year || ''}</td><td>${m.monitored ? 'Yes' : 'No'}</td><td>${m.hasFile ? 'Yes' : 'No'}</td></tr>`;    }    html += "</table>";    content.innerHTML = html;}// Load full Sonarr dataset for an instance and render a flattened episodes tableasync function loadSonarrAll(cat, q = "") {    currentArr = { type: "sonarr", cat, targetId: "sonarrContent" };    const content = document.getElementById("sonarrContent");    if (!content) return;    content.innerHTML = '<span class="hint">Loading series…</span>';    const pageSize = 200;    let page = 0;    let allSeries = [];    while (true) {        const r = await fetch(`/web/sonarr/${cat}/series?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`, { headers: headers() });        if (!r.ok) break;        const d = await r.json();        allSeries = allSeries.concat(d.series || []);        if (!d.series || d.series.length < pageSize) break;        page += 1;        if (page > 200) break;    }    const rows = [];    for (const s of allSeries) {        const seriesTitle = s.series?.title || '';        for (const [sn, sv] of Object.entries(s.seasons || {})) {            for (const e of (sv.episodes || [])) {                rows.push({ series: seriesTitle, season: sn, ep: e.episodeNumber, title: e.title || '', monitored: !!e.monitored, hasFile: !!e.hasFile, air: e.airDateUtc || '' });            }        }    }    renderSonarrAllTable(rows);}function renderSonarrAllTable(rows) {    const content = document.getElementById("sonarrContent");    if (!content) return;    let html = '';    html += `<div class="row"><div class="col field"><input placeholder="search episodes" oninput="globalSearch(this.value)"/></div></div>`;    html += "<table><tr><th>Series</th><th>Season</th><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>";    for (const r of rows) {        html += `<tr><td>${r.series}</td><td>${r.season}</td><td>${r.ep}</td><td>${r.title}</td><td>${r.monitored ? 'Yes':'No'}</td><td>${r.hasFile ? 'Yes':'No'}</td><td>${r.air}</td></tr>`;    }    html += "</table>";    content.innerHTML = html;}// Config helpers for token visibility and savingfunction toggleTokenVisibility(inputId, cb) {    const el = document.getElementById(inputId);    if (!el) return;    el.type = cb.checked ? "text" : "password";}async function saveTokenToConfig() {    const val = document.getElementById("configToken").value;    if (!val) {        alert("Token cannot be empty");        return;    }    await fetch("/web/config", {        method: "POST",        headers: headers(),        body: JSON.stringify({ changes: { "Settings.WebUIToken": val } }),    });    alert("Token saved");    localStorage.setItem("token", val);}// Aggregated views across all instances with loading placeholders and paginationconst radarrAgg = { items: [], filtered: [], page: 0, pageSize: 50, q: "" };function radarrAggApply() {    const ql = (radarrAgg.q || "").toLowerCase();    if (!ql) radarrAgg.filtered = radarrAgg.items;    else radarrAgg.filtered = radarrAgg.items.filter(m => (m.title||'').toLowerCase().includes(ql) || (m.__instance||'').toLowerCase().includes(ql));    const totalPages = Math.max(1, Math.ceil(radarrAgg.filtered.length / radarrAgg.pageSize));    radarrAgg.page = Math.min(radarrAgg.page, totalPages - 1);}function renderRadarrAgg() {    const content = document.getElementById('radarrContent');    if (!content) return;    radarrAggApply();    const start = radarrAgg.page * radarrAgg.pageSize;    const items = radarrAgg.filtered.slice(start, start + radarrAgg.pageSize);    let html = '';    html += `<div class="row"><div class="col field"><input placeholder="search movies" value="${radarrAgg.q}" oninput="radarrAggSearch(this.value)"/></div></div>`;    html += '<table><tr><th>Instance</th><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>';    for (const m of items) {        html += `<tr><td>${m.__instance||''}</td><td>${m.title||''}</td><td>${m.year||''}</td><td>${m.monitored?'Yes':'No'}</td><td>${m.hasFile?'Yes':'No'}</td></tr>`;    }    html += '</table>';    const totalPages = Math.max(1, Math.ceil(radarrAgg.filtered.length / radarrAgg.pageSize));    html += `<div class="row" style="margin-top:8px"><div class="col">Page ${radarrAgg.page+1} of ${totalPages} (${radarrAgg.filtered.length} items)</div><div class="col" style="text-align:right"><button class="btn" onclick="radarrAggPage(-1)">Prev</button> <button class="btn" onclick="radarrAggPage(1)">Next</button></div></div>`;    content.innerHTML = html;}function radarrAggPage(d) {    const totalPages = Math.max(1, Math.ceil(radarrAgg.filtered.length / radarrAgg.pageSize));    radarrAgg.page = Math.min(totalPages-1, Math.max(0, radarrAgg.page + d));    renderRadarrAgg();}function radarrAggSearch(q) { radarrAgg.q = q||""; radarrAgg.page = 0; renderRadarrAgg(); }async function loadRadarrAllInstances(cats) {    currentArr = { type: 'radarrAll' };    const content = document.getElementById('radarrContent');    if (!content) return;    content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading Radarr…</div>';    radarrAgg.items = [];    for (const cat of (cats||[])) {        const label = (arrIndex.radarr && arrIndex.radarr[cat]) || cat;        let page = 0, pageSize = 500;        while (true) {            const r = await fetch(`/web/radarr/${cat}/movies?q=&page=${page}&page_size=${pageSize}`, { headers: headers() });            if (!r.ok) break;            const d = await r.json();            for (const m of (d.movies||[])) radarrAgg.items.push({ ...m, __instance: label });            if (!d.movies || d.movies.length < pageSize) break;            page += 1; if (page > 100) break;        }    }    radarrAgg.page = 0; radarrAgg.q = ""; renderRadarrAgg();}const sonarrAgg = { rows: [], filtered: [], page: 0, pageSize: 100, q: "" };function sonarrAggApply() {    const ql = (sonarrAgg.q || "").toLowerCase();    if (!ql) sonarrAgg.filtered = sonarrAgg.rows;    else sonarrAgg.filtered = sonarrAgg.rows.filter(r => (r.series||'').toLowerCase().includes(ql) || (r.__instance||'').toLowerCase().includes(ql) || (r.title||'').toLowerCase().includes(ql));    const totalPages = Math.max(1, Math.ceil(sonarrAgg.filtered.length / sonarrAgg.pageSize));    sonarrAgg.page = Math.min(sonarrAgg.page, totalPages - 1);}function renderSonarrAgg() {    const content = document.getElementById('sonarrContent');    if (!content) return;    sonarrAggApply();    const start = sonarrAgg.page * sonarrAgg.pageSize;    const rows = sonarrAgg.filtered.slice(start, start + sonarrAgg.pageSize);    let html = '';    html += `<div class="row"><div class="col field"><input placeholder="search episodes" value="${sonarrAgg.q}" oninput="sonarrAggSearch(this.value)"/></div></div>`;    html += '<table><tr><th>Instance</th><th>Series</th><th>Season</th><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>';    for (const r of rows) {        html += `<tr><td>${r.__instance||''}</td><td>${r.series}</td><td>${r.season}</td><td>${r.ep}</td><td>${r.title}</td><td>${r.monitored?'Yes':'No'}</td><td>${r.hasFile?'Yes':'No'}</td><td>${r.air}</td></tr>`;    }    html += '</table>';    const totalPages = Math.max(1, Math.ceil(sonarrAgg.filtered.length / sonarrAgg.pageSize));    html += `<div class="row" style="margin-top:8px"><div class="col">Page ${sonarrAgg.page+1} of ${totalPages} (${sonarrAgg.filtered.length} rows)</div><div class="col" style="text-align:right"><button class="btn" onclick="sonarrAggPage(-1)">Prev</button> <button class="btn" onclick="sonarrAggPage(1)">Next</button></div></div>`;    content.innerHTML = html;}function sonarrAggPage(d) {    const totalPages = Math.max(1, Math.ceil(sonarrAgg.filtered.length / sonarrAgg.pageSize));    sonarrAgg.page = Math.min(totalPages-1, Math.max(0, sonarrAgg.page + d));    renderSonarrAgg();}function sonarrAggSearch(q) { sonarrAgg.q = q||""; sonarrAgg.page = 0; renderSonarrAgg(); }async function loadSonarrAllInstances(cats) {    currentArr = { type: 'sonarrAll' };    const content = document.getElementById('sonarrContent');    if (!content) return;    content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading Sonarr…</div>';    sonarrAgg.rows = [];    for (const cat of (cats||[])) {        const label = (arrIndex.sonarr && arrIndex.sonarr[cat]) || cat;        let page = 0, pageSize = 200;        while (true) {            const r = await fetch(`/web/sonarr/${cat}/series?q=&page=${page}&page_size=${pageSize}`, { headers: headers() });            if (!r.ok) break;            const d = await r.json();            const series = d.series || [];            for (const s of series) {                const seriesTitle = s.series?.title || '';                for (const [sn, sv] of Object.entries(s.seasons || {})) {                    for (const e of (sv.episodes || [])) {                        sonarrAgg.rows.push({ __instance: label, series: seriesTitle, season: sn, ep: e.episodeNumber, title: e.title || '', monitored: !!e.monitored, hasFile: !!e.hasFile, air: e.airDateUtc || '' });                    }                }            }            if (!series || series.length < pageSize) break;            page += 1; if (page > 200) break;        }    }    sonarrAgg.page = 0; sonarrAgg.q = ""; renderSonarrAgg();}

// Safety shims: define any missing functions used by inline handlers
(function () {
    const H = () => ({ "Content-Type": "application/json" });
    if (typeof window.globalSearch !== "function") {
        window.globalSearch = function (q) {
            /* no-op fallback */
        };
    }
    if (typeof window.loadStatus !== "function") {
        window.loadStatus = async function () {
            const r = await fetch("/web/status", { headers: H() }).catch(
                () => null
            );
            if (!r) return;
            const d = await r.json();
            const qb =
                d.qbit && d.qbit.alive
                    ? "<span class=ok>qBit OK</span>"
                    : "<span class=bad>qBit DOWN</span>";
            let arr = "";
            for (const a of d.arrs || [])
                arr += `${a.name || a.category}:${a.alive ? "OK" : "DOWN"} `;
            const el = document.getElementById("status");
            if (el) el.innerHTML = qb + " | " + arr;
        };
    }
    if (typeof window.loadProcesses !== "function") {
        window.loadProcesses = async function () {
            const r = await fetch("/web/processes", { headers: H() });
            const d = await r.json();
            let html =
                "<table><tr><th>Category</th><th>Name</th><th>Kind</th><th>PID</th><th>Alive</th><th>Actions</th></tr>";
            for (const p of d.processes || [])
                html += `<tr><td>${p.category}</td><td>${p.name}</td><td>${
                    p.kind
                }</td><td>${p.pid || ""}</td><td>${
                    p.alive
                        ? "<span class=ok>yes</span>"
                        : "<span class=bad>no</span>"
                }</td><td><button onclick="restart('${p.category}','${
                    p.kind
                }')">Restart</button></td></tr>`;
            html += "</table>";
            const out = document.getElementById("procOut");
            if (out) out.innerHTML = html;
        };
    }
    if (typeof window.restart !== "function") {
        window.restart = async function (category, kind) {
            await fetch(`/web/processes/${category}/${kind}/restart`, {
                method: "POST",
                headers: H(),
            });
            window.loadProcesses();
        };
    }
    if (typeof window.restartAll !== "function") {
        window.restartAll = async function () {
            await fetch("/web/processes/restart_all", {
                method: "POST",
                headers: H(),
            });
            window.loadProcesses();
        };
    }
    if (typeof window.rebuildArrs !== "function") {
        window.rebuildArrs = async function () {
            await fetch("/web/arr/rebuild", { method: "POST", headers: H() });
            window.loadProcesses();
            window.loadArrList();
        };
    }
    if (typeof window.applyLogLevel !== "function") {
        window.applyLogLevel = async function () {
            const lv = document.getElementById("logLevel")?.value || "INFO";
            await fetch("/web/loglevel", {
                method: "POST",
                headers: H(),
                body: JSON.stringify({ level: lv }),
            });
        };
    }
    if (typeof window.refreshLogList !== "function") {
        window.refreshLogList = async function () {
            const r = await fetch("/web/logs", { headers: H() });
            const d = await r.json();
            const sel = document.getElementById("logSelect");
            if (!sel) return;
            sel.innerHTML = "";
            for (const f of d.files || []) {
                const o = document.createElement("option");
                o.value = f;
                o.textContent = f;
                sel.appendChild(o);
            }
            window.startLogFollow && window.startLogFollow();
        };
    }
    if (typeof window.tail !== "function") {
        window.tail = async function (name) {
            const r = await fetch(`/web/logs/${name}`);
            const c = await r.text();
            const el = document.getElementById("logTail");
            if (!el) return;
            el.textContent = c;
            el.dataset.filename = name;
            el.scrollTop = el.scrollHeight;
        };
    }
    if (typeof window.downloadCurrent !== "function") {
        window.downloadCurrent = function () {
            const sel = document.getElementById("logSelect");
            const name = sel && sel.value;
            if (!name) return;
            window.location = `/web/logs/${name}/download`;
        };
    }
    if (typeof window.startLogFollow !== "function") {
        let logTimer = null;
        window.startLogFollow = function () {
            if (logTimer) clearInterval(logTimer);
            const sel = document.getElementById("logSelect");
            if (!sel) return;
            const run = () => {
                const live = document.getElementById("logFollow");
                if (live && !live.checked) return;
                if (sel.value) window.tail(sel.value);
            };
            run();
            logTimer = setInterval(run, 2000);
        };
    }
    if (typeof window.loadArrList !== "function") {
        window.loadArrList = async function () {
            const [arrRes, procRes] = await Promise.all([
                fetch("/web/arr", { headers: H() }),
                fetch("/web/processes", { headers: H() }),
            ]);
            const d = await arrRes.json();
            const nameByCat = {};
            const procs = await procRes.json();
            for (const p of procs.processes || [])
                nameByCat[p.category] = p.name || p.category;
            const rnav = document.getElementById("radarrNav");
            const snav = document.getElementById("sonarrNav");
            if (rnav) rnav.innerHTML = "";
            if (snav) snav.innerHTML = "";
            const rbtn = document.createElement("button");
            rbtn.className = "btn";
            rbtn.textContent = "Load All Radarr";
            rbtn.onclick = () =>
                window.loadRadarrAllInstances &&
                window.loadRadarrAllInstances(
                    (d.arr || [])
                        .filter((a) => a.type === "radarr")
                        .map((a) => a.category)
                );
            rnav && rnav.appendChild(rbtn);
            const sbtn = document.createElement("button");
            sbtn.className = "btn";
            sbtn.textContent = "Load All Sonarr";
            sbtn.onclick = () =>
                window.loadSonarrAllInstances &&
                window.loadSonarrAllInstances(
                    (d.arr || [])
                        .filter((a) => a.type === "sonarr")
                        .map((a) => a.category)
                );
            snav && snav.appendChild(sbtn);
        };
    }
    if (typeof window.loadRadarrAllInstances !== "function") {
        window.loadRadarrAllInstances = async function (cats) {
            const content = document.getElementById("radarrContent");
            if (!content) return;
            content.innerHTML =
                '<div class="loading"><span class="spinner"></span> Loading Radarr…</div>';
            let items = [];
            for (const cat of cats || []) {
                let page = 0;
                const ps = 500;
                while (true) {
                    const r = await fetch(
                        `/web/radarr/${cat}/movies?q=&page=${page}&page_size=${ps}`,
                        { headers: H() }
                    );
                    if (!r.ok) break;
                    const d = await r.json();
                    for (const m of d.movies || [])
                        items.push({ ...m, __instance: cat });
                    if (!d.movies || d.movies.length < ps) break;
                    page++;
                    if (page > 50) break;
                }
            }
            window._radarrAgg = {
                items,
                q: (window._radarrAgg && window._radarrAgg.q) || "",
                page: 0,
                pageSize: 50,
                cats: cats || [],
            };
            window.currentArr = { type: "radarrAll" };
            window.renderRadarrAgg();
        };
    }
    if (typeof window.renderRadarrAgg !== "function") {
        window.renderRadarrAgg = function () {
            const st = window._radarrAgg || {
                items: [],
                q: "",
                page: 0,
                pageSize: 50,
            };
            const content = document.getElementById("radarrContent");
            if (!content) return;
            const ql = (st.q || "").toLowerCase();
            const filtered = ql
                ? st.items.filter(
                      (m) =>
                          (m.title || "").toLowerCase().includes(ql) ||
                          (m.__instance || "").toLowerCase().includes(ql)
                  )
                : st.items;
            const totalPages = Math.max(
                1,
                Math.ceil(filtered.length / st.pageSize)
            );
            st.page = Math.min(st.page, totalPages - 1);
            const start = st.page * st.pageSize;
            const pageItems = filtered.slice(start, start + st.pageSize);
            let html = "";
            html += `<div class="row"><div class="col field"><input placeholder="search movies" value="${st.q}" oninput="radarrAggSearch(this.value)"/></div></div>`;
            html +=
                "<table><tr><th>Instance</th><th>Title</th><th>Year</th><th>Monitored</th><th>Has File</th></tr>";
            for (const m of pageItems) {
                html += `<tr><td>${m.__instance || ""}</td><td>${
                    m.title || ""
                }</td><td>${m.year || ""}</td><td>${
                    m.monitored ? "Yes" : "No"
                }</td><td>${m.hasFile ? "Yes" : "No"}</td></tr>`;
            }
            html += "</table>";
            html += `<div class="row" style="margin-top:8px"><div class="col">Page ${
                st.page + 1
            } of ${totalPages} (${
                filtered.length
            } items)</div><div class="col" style="text-align:right"><button class="btn" onclick="radarrAggPage(-1)">Prev</button> <button class="btn" onclick="radarrAggPage(1)">Next</button></div></div>`;
            content.innerHTML = html;
        };
    }
    if (typeof window.radarrAggSearch !== "function") {
        window.radarrAggSearch = function (q) {
            if (!window._radarrAgg) return;
            window._radarrAgg.q = q || "";
            window._radarrAgg.page = 0;
            window.renderRadarrAgg();
        };
    }
    if (typeof window.radarrAggPage !== "function") {
        window.radarrAggPage = function (delta) {
            if (!window._radarrAgg) return;
            const st = window._radarrAgg;
            const totalPages = Math.max(
                1,
                Math.ceil(
                    (st.q
                        ? st.items.filter(
                              (m) =>
                                  (m.title || "")
                                      .toLowerCase()
                                      .includes(st.q.toLowerCase()) ||
                                  (m.__instance || "")
                                      .toLowerCase()
                                      .includes(st.q.toLowerCase())
                          )
                        : st.items
                    ).length / st.pageSize
                )
            );
            st.page = Math.min(totalPages - 1, Math.max(0, st.page + delta));
            window.renderRadarrAgg();
        };
    }
    if (typeof window.loadSonarrAllInstances !== "function") {
        window.loadSonarrAllInstances = async function (cats) {
            const content = document.getElementById("sonarrContent");
            if (!content) return;
            content.innerHTML =
                '<div class="loading"><span class="spinner"></span> Loading Sonarr…</div>';
            let rows = [];
            for (const cat of cats || []) {
                let page = 0;
                const ps = 200;
                while (true) {
                    const r = await fetch(
                        `/web/sonarr/${cat}/series?q=&page=${page}&page_size=${ps}`,
                        { headers: H() }
                    );
                    if (!r.ok) break;
                    const d = await r.json();
                    for (const s of d.series || []) {
                        const title = s.series?.title || "";
                        for (const [sn, sv] of Object.entries(
                            s.seasons || {}
                        )) {
                            for (const e of sv.episodes || []) {
                                rows.push({
                                    __instance: cat,
                                    series: title,
                                    season: sn,
                                    ep: e.episodeNumber,
                                    title: e.title || "",
                                    monitored: !!e.monitored,
                                    hasFile: !!e.hasFile,
                                    air: e.airDateUtc || "",
                                });
                            }
                        }
                    }
                    if (!d.series || d.series.length < ps) break;
                    page++;
                    if (page > 100) break;
                }
            }
            window._sonarrAgg = {
                rows,
                q: (window._sonarrAgg && window._sonarrAgg.q) || "",
                page: 0,
                pageSize: 100,
                cats: cats || [],
            };
            window.currentArr = { type: "sonarrAll" };
            window.renderSonarrAgg();
        };
    }
    if (typeof window.renderSonarrAgg !== "function") {
        window.renderSonarrAgg = function () {
            const st = window._sonarrAgg || {
                rows: [],
                q: "",
                page: 0,
                pageSize: 100,
            };
            const content = document.getElementById("sonarrContent");
            if (!content) return;
            const ql = (st.q || "").toLowerCase();
            const filtered = ql
                ? st.rows.filter(
                      (r) =>
                          (r.series || "").toLowerCase().includes(ql) ||
                          (r.__instance || "").toLowerCase().includes(ql) ||
                          (r.title || "").toLowerCase().includes(ql)
                  )
                : st.rows;
            const totalPages = Math.max(
                1,
                Math.ceil(filtered.length / st.pageSize)
            );
            st.page = Math.min(st.page, totalPages - 1);
            const start = st.page * st.pageSize;
            const pageRows = filtered.slice(start, start + st.pageSize);
            let html = "";
            html += `<div class="row"><div class="col field"><input placeholder="search episodes" value="${st.q}" oninput="sonarrAggSearch(this.value)"/></div></div>`;
            html +=
                "<table><tr><th>Instance</th><th>Series</th><th>Season</th><th>Ep</th><th>Title</th><th>Monitored</th><th>Has File</th><th>Air Date</th></tr>";
            for (const r of pageRows) {
                html += `<tr><td>${r.__instance || ""}</td><td>${
                    r.series
                }</td><td>${r.season}</td><td>${r.ep}</td><td>${
                    r.title
                }</td><td>${r.monitored ? "Yes" : "No"}</td><td>${
                    r.hasFile ? "Yes" : "No"
                }</td><td>${r.air}</td></tr>`;
            }
            html += "</table>";
            html += `<div class="row" style="margin-top:8px"><div class="col">Page ${
                st.page + 1
            } of ${totalPages} (${
                filtered.length
            } rows)</div><div class="col" style="text-align:right"><button class="btn" onclick="sonarrAggPage(-1)">Prev</button> <button class="btn" onclick="sonarrAggPage(1)">Next</button></div></div>`;
            content.innerHTML = html;
        };
    }
    if (typeof window.sonarrAggSearch !== "function") {
        window.sonarrAggSearch = function (q) {
            if (!window._sonarrAgg) return;
            window._sonarrAgg.q = q || "";
            window._sonarrAgg.page = 0;
            window.renderSonarrAgg();
        };
    }
    if (typeof window.sonarrAggPage !== "function") {
        window.sonarrAggPage = function (delta) {
            if (!window._sonarrAgg) return;
            const st = window._sonarrAgg;
            const totalPages = Math.max(
                1,
                Math.ceil(
                    (st.q
                        ? st.rows.filter(
                              (r) =>
                                  (r.series || "")
                                      .toLowerCase()
                                      .includes(st.q.toLowerCase()) ||
                                  (r.__instance || "")
                                      .toLowerCase()
                                      .includes(st.q.toLowerCase()) ||
                                  (r.title || "")
                                      .toLowerCase()
                                      .includes(st.q.toLowerCase())
                          )
                        : st.rows
                    ).length / st.pageSize
                )
            );
            st.page = Math.min(totalPages - 1, Math.max(0, st.page + delta));
            window.renderSonarrAgg();
        };
    }
})();

// Enhance left nav buttons with monitored/available counts per instance
(function () {
    const H = () => ({ "Content-Type": "application/json" });
    async function getRadarrCounts(cat) {
        try {
            const r = await fetch(
                `/web/radarr/${cat}/movies?page=0&page_size=1`,
                { headers: H() }
            );
            if (!r.ok) return null;
            const d = await r.json();
            return d && d.counts ? d.counts : null;
        } catch {
            return null;
        }
    }
    async function getSonarrCounts(cat) {
        try {
            const r = await fetch(
                `/web/sonarr/${cat}/series?page=0&page_size=1`,
                { headers: H() }
            );
            if (!r.ok) return null;
            const d = await r.json();
            return d && d.counts ? d.counts : null;
        } catch {
            return null;
        }
    }
    // Override to include counts next to each instance button
    window.loadArrList = async function () {
        const [arrRes, procRes] = await Promise.all([
            fetch("/web/arr", { headers: H() }),
            fetch("/web/processes", { headers: H() }),
        ]);
        const d = await arrRes.json();
        const procs = await procRes.json();
        const nameByCat = {};
        (procs.processes || []).forEach(
            (p) => (nameByCat[p.category] = p.name || p.category)
        );

        const rnav = document.getElementById("radarrNav");
        if (rnav) {
            rnav.innerHTML = "";
            const rcats = (d.arr || [])
                .filter((a) => a.type === "radarr")
                .map((a) => a.category);
            const allBtn = document.createElement("button");
            allBtn.className = "btn";
            allBtn.textContent = "Load All Radarr";
            allBtn.onclick = () =>
                window.loadRadarrAllInstances &&
                window.loadRadarrAllInstances(rcats);
            rnav.appendChild(allBtn);
            // Fetch counts in parallel
            const results = await Promise.all(
                rcats.map(async (cat) => ({
                    cat,
                    counts: await getRadarrCounts(cat),
                }))
            );
            for (const { cat, counts } of results) {
                const labelName = nameByCat[cat] || cat;
                const suffix = counts
                    ? ` (${counts.monitored || 0}/${counts.available || 0})`
                    : "";
                const b = document.createElement("button");
                b.className = "btn ghost";
                b.style.display = "block";
                b.style.width = "100%";
                b.style.textAlign = "left";
                b.style.margin = "4px 0";
                b.textContent = labelName + suffix;
                b.onclick = () =>
                    window.loadRadarrAll && window.loadRadarrAll(cat);
                rnav.appendChild(b);
            }
        }

        const snav = document.getElementById("sonarrNav");
        if (snav) {
            snav.innerHTML = "";
            const scats = (d.arr || [])
                .filter((a) => a.type === "sonarr")
                .map((a) => a.category);
            const allBtn = document.createElement("button");
            allBtn.className = "btn";
            allBtn.textContent = "Load All Sonarr";
            allBtn.onclick = () =>
                window.loadSonarrAllInstances &&
                window.loadSonarrAllInstances(scats);
            snav.appendChild(allBtn);
            const results = await Promise.all(
                scats.map(async (cat) => ({
                    cat,
                    counts: await getSonarrCounts(cat),
                }))
            );
            for (const { cat, counts } of results) {
                const labelName = nameByCat[cat] || cat;
                const suffix = counts
                    ? ` (${counts.monitored || 0}/${counts.available || 0})`
                    : "";
                const b = document.createElement("button");
                b.className = "btn ghost";
                b.style.display = "block";
                b.style.width = "100%";
                b.style.textAlign = "left";
                b.style.margin = "4px 0";
                b.textContent = labelName + suffix;
                b.onclick = () =>
                    window.loadSonarrAll && window.loadSonarrAll(cat);
                snav.appendChild(b);
            }
        }
    };
})();

// Lightweight 1s auto-refresh of counts without rebuilding nav
(function () {
    const H = () => ({ "Content-Type": "application/json" });
    async function getRadarrCounts(cat) {
        try {
            const r = await fetch(
                `/web/radarr/${cat}/movies?page=0&page_size=1`,
                { headers: H() }
            );
            if (!r.ok) return null;
            const d = await r.json();
            return d.counts || null;
        } catch {
            return null;
        }
    }
    async function getSonarrCounts(cat) {
        try {
            const r = await fetch(
                `/web/sonarr/${cat}/series?page=0&page_size=1`,
                { headers: H() }
            );
            if (!r.ok) return null;
            const d = await r.json();
            return d.counts || null;
        } catch {
            return null;
        }
    }
    // Override loadArrList to add data attributes for later incremental refresh
    window.loadArrList = async function () {
        const [arrRes, procRes] = await Promise.all([
            fetch("/web/arr", { headers: H() }),
            fetch("/web/processes", { headers: H() }),
        ]);
        const d = await arrRes.json();
        const procs = await procRes.json();
        const nameByCat = {};
        (procs.processes || []).forEach(
            (p) => (nameByCat[p.category] = p.name || p.category)
        );

        const rnav = document.getElementById("radarrNav");
        if (rnav) {
            rnav.innerHTML = "";
            const rcats = (d.arr || [])
                .filter((a) => a.type === "radarr")
                .map((a) => a.category);
            const allBtn = document.createElement("button");
            allBtn.className = "btn";
            allBtn.textContent = "Load All Radarr";
            allBtn.onclick = () =>
                window.loadRadarrAllInstances &&
                window.loadRadarrAllInstances(rcats);
            rnav.appendChild(allBtn);
            const results = await Promise.all(
                rcats.map(async (cat) => ({
                    cat,
                    counts: await getRadarrCounts(cat),
                }))
            );
            for (const { cat, counts } of results) {
                const labelName = nameByCat[cat] || cat;
                const suffix = counts
                    ? ` (${counts.monitored || 0}/${counts.available || 0})`
                    : "";
                const b = document.createElement("button");
                b.className = "btn ghost";
                b.style.display = "block";
                b.style.width = "100%";
                b.style.textAlign = "left";
                b.style.margin = "4px 0";
                b.textContent = labelName + suffix;
                b.onclick = () => {
                    window.currentArr = {
                        type: "radarr",
                        cat,
                        targetId: "radarrContent",
                    };
                    window.loadRadarrAll && window.loadRadarrAll(cat);
                };
                b.dataset.cat = cat;
                b.dataset.type = "radarr";
                b.dataset.label = labelName;
                rnav.appendChild(b);
            }
        }

        const snav = document.getElementById("sonarrNav");
        if (snav) {
            snav.innerHTML = "";
            const scats = (d.arr || [])
                .filter((a) => a.type === "sonarr")
                .map((a) => a.category);
            const allBtn = document.createElement("button");
            allBtn.className = "btn";
            allBtn.textContent = "Load All Sonarr";
            allBtn.onclick = () =>
                window.loadSonarrAllInstances &&
                window.loadSonarrAllInstances(scats);
            snav.appendChild(allBtn);
            const results = await Promise.all(
                scats.map(async (cat) => ({
                    cat,
                    counts: await getSonarrCounts(cat),
                }))
            );
            for (const { cat, counts } of results) {
                const labelName = nameByCat[cat] || cat;
                const suffix = counts
                    ? ` (${counts.monitored || 0}/${counts.available || 0})`
                    : "";
                const b = document.createElement("button");
                b.className = "btn ghost";
                b.style.display = "block";
                b.style.width = "100%";
                b.style.textAlign = "left";
                b.style.margin = "4px 0";
                b.textContent = labelName + suffix;
                b.onclick = () => {
                    window.currentArr = {
                        type: "sonarr",
                        cat,
                        targetId: "sonarrContent",
                    };
                    window.loadSonarrAll && window.loadSonarrAll(cat);
                };
                b.dataset.cat = cat;
                b.dataset.type = "sonarr";
                b.dataset.label = labelName;
                snav.appendChild(b);
            }
        }
        // Initial counts set; subsequent refresh uses refreshArrCounts
        window.refreshArrCounts && window.refreshArrCounts();
    };

    window.refreshArrCounts = async function () {
        const updateButtons = async (containerId, type) => {
            const c = document.getElementById(containerId);
            if (!c) return;
            const btns = Array.from(c.querySelectorAll("button")).filter(
                (b) => b.dataset && b.dataset.cat
            );
            await Promise.all(
                btns.map(async (b) => {
                    const cat = b.dataset.cat;
                    const label =
                        b.dataset.label ||
                        b.textContent.replace(/\(.*\)$/, "").trim();
                    const counts =
                        type === "radarr"
                            ? await getRadarrCounts(cat)
                            : await getSonarrCounts(cat);
                    const suffix = counts
                        ? ` (${counts.monitored || 0}/${counts.available || 0})`
                        : "";
                    b.textContent = label + suffix;
                })
            );
        };
        await updateButtons("radarrNav", "radarr");
        await updateButtons("sonarrNav", "sonarr");
    };
})();

// Override tab timers: 1s refresh and incremental count updates
(function () {
    let procTimer = null;
    let arrTimer = null;
    function clearTimers() {
        if (procTimer) {
            clearInterval(procTimer);
            procTimer = null;
        }
        if (arrTimer) {
            clearInterval(arrTimer);
            arrTimer = null;
        }
    }
    window.onTabActivated = function (id) {
        clearTimers();
        if (id === "processes") {
            if (typeof window.loadProcesses === "function")
                window.loadProcesses();
            procTimer = setInterval(() => {
                try {
                    window.loadProcesses && window.loadProcesses();
                } catch (_) {}
            }, 1000);
        } else if (id === "radarr" || id === "sonarr") {
            if (typeof window.loadArrList === "function") window.loadArrList();
            arrTimer = setInterval(() => {
                try {
                    window.refreshArrCounts && window.refreshArrCounts();
                    // also refresh the active table data without losing search/page
                    if (typeof window.refreshActiveArrTable === "function")
                        window.refreshActiveArrTable();
                } catch (_) {}
            }, 1000);
        }
    };
    document.addEventListener("DOMContentLoaded", function () {
        try {
            // Always auto-refresh the toolbar status every 1s
            try {
                window.loadStatus && window.loadStatus();
            } catch (_) {}
            setInterval(() => {
                try {
                    window.loadStatus && window.loadStatus();
                } catch (_) {}
            }, 1000);
            // Determine active tab if not set
            if (!window.__activeTab) {
                var active = document.querySelector(".nav a.active");
                window.__activeTab = active
                    ? (active.id || "tab-processes").replace("tab-", "")
                    : "processes";
            }
            window.onTabActivated(window.__activeTab);
        } catch (_) {}
    });
})();

// Add instance helper for Config: creates a new card with fields
(function () {
    if (typeof window.addArrInstance !== "function") {
        window.addArrInstance = function (type) {
            const root = document.getElementById("configForms");
            if (!root) return;
            const t = String(type || "").toLowerCase();
            const prefix = t.charAt(0).toUpperCase() + t.slice(1);
            let idx = 1;
            let key = `${prefix}-${idx}`;
            while (document.getElementById(`cfg_${key}_URI`)) {
                idx++;
                key = `${prefix}-${idx}`;
            }
            const defCat = t === "radarr" || t === "sonarr" ? t : "qbitrr";
            const html = [
                `<div class="card" style="margin-top:12px"><div class="card-header">${key}</div><div class="card-body">`,
                `<div class="field"><label><input id="cfg_${key}_Managed" type="checkbox" checked/> Managed</label></div>`,
                `<div class="field"><label for="cfg_${key}_URI">URI</label><input id="cfg_${key}_URI" type="text" placeholder="http://host:port"/></div>`,
                `<div class="field"><label for="cfg_${key}_APIKey">API Key</label><input id="cfg_${key}_APIKey" type="password" placeholder="apikey"/></div>`,
                `<div class="field"><label for="cfg_${key}_Category">Category</label><input id="cfg_${key}_Category" type="text" value="${defCat}"/></div>`,
                `</div></div>`,
            ].join("");
            root.insertAdjacentHTML("beforeend", html);
        };
    }
})();

// Fallback Config render/save if missing
(function () {
    const H = () => ({ "Content-Type": "application/json" });
    if (typeof window.renderConfigForms !== "function") {
        window.renderConfigForms = async function () {
            const r = await fetch("/web/config", { headers: H() });
            const cfg = await r.json();
            const root = document.getElementById("configForms");
            if (!root) return;
            let html =
                '<div class="card"><div class="card-header">Settings</div><div class="card-body">';
            function input(label, id, val, type) {
                return `<div class="field"><label for="${id}">${label}</label><input id="${id}" type="${
                    type || "text"
                }" value="${val ?? ""}"></div>`;
            }
            function checkbox(label, id, checked) {
                return `<div class="field"><label><input id="${id}" type="checkbox" ${
                    checked ? "checked" : ""
                }/> ${label}</label></div>`;
            }
            function select(label, id, val, opts) {
                const o = opts
                    .map(
                        (x) =>
                            `<option ${
                                String(x) == String(val) ? "selected" : ""
                            }>${x}</option>`
                    )
                    .join("");
                return `<div class="field"><label for="${id}">${label}</label><select id="${id}">${o}</select></div>`;
            }
            html += select(
                "Console Level",
                "cfg_ConsoleLevel",
                cfg.Settings?.ConsoleLevel || "INFO",
                [
                    "CRITICAL",
                    "ERROR",
                    "WARNING",
                    "NOTICE",
                    "INFO",
                    "DEBUG",
                    "TRACE",
                ]
            );
            html += checkbox("Logging", "cfg_Logging", !!cfg.Settings?.Logging);
            html += input(
                "Completed Download Folder",
                "cfg_CompletedDownloadFolder",
                cfg.Settings?.CompletedDownloadFolder
            );
            html += input(
                "Free Space",
                "cfg_FreeSpace",
                cfg.Settings?.FreeSpace
            );
            html += input(
                "Free Space Folder",
                "cfg_FreeSpaceFolder",
                cfg.Settings?.FreeSpaceFolder
            );
            html += checkbox(
                "Auto Pause/Resume",
                "cfg_AutoPauseResume",
                !!cfg.Settings?.AutoPauseResume
            );
            html += input(
                "No Internet Sleep (s)",
                "cfg_NoInternetSleepTimer",
                cfg.Settings?.NoInternetSleepTimer,
                "number"
            );
            html += input(
                "Loop Sleep (s)",
                "cfg_LoopSleepTimer",
                cfg.Settings?.LoopSleepTimer,
                "number"
            );
            html += input(
                "Search Loop Delay (s)",
                "cfg_SearchLoopDelay",
                cfg.Settings?.SearchLoopDelay,
                "number"
            );
            html += input(
                "Failed Category",
                "cfg_FailedCategory",
                cfg.Settings?.FailedCategory
            );
            html += input(
                "Recheck Category",
                "cfg_RecheckCategory",
                cfg.Settings?.RecheckCategory
            );
            html += checkbox("Tagless", "cfg_Tagless", !!cfg.Settings?.Tagless);
            html += input(
                "Ignore Torrents Younger Than",
                "cfg_IgnoreTorrentsYoungerThan",
                cfg.Settings?.IgnoreTorrentsYoungerThan,
                "number"
            );
            html += input(
                "WebUI Host",
                "cfg_WebUIHost",
                cfg.Settings?.WebUIHost
            );
            html += input(
                "WebUI Port",
                "cfg_WebUIPort",
                cfg.Settings?.WebUIPort,
                "number"
            );
            html += input(
                "WebUI Token",
                "cfg_WebUIToken",
                cfg.Settings?.WebUIToken
            );
            html += "</div></div>";
            html +=
                '<div class="card" style="margin-top:12px"><div class="card-header">qBit</div><div class="card-body">';
            html += checkbox(
                "Disabled",
                "cfg_qBit_Disabled",
                !!cfg.qBit?.Disabled
            );
            html += input("Host", "cfg_qBit_Host", cfg.qBit?.Host);
            html += input("Port", "cfg_qBit_Port", cfg.qBit?.Port, "number");
            html += input("UserName", "cfg_qBit_UserName", cfg.qBit?.UserName);
            html += input(
                "Password",
                "cfg_qBit_Password",
                cfg.qBit?.Password,
                "password"
            );
            html += "</div></div>";
            // Arr sections
            for (const key of Object.keys(cfg || {})) {
                if (/(rad|son|anim)arr/i.test(key)) {
                    const sec = cfg[key] || {};
                    html += `<div class="card" style="margin-top:12px"><div class="card-header">${key}</div><div class="card-body">`;
                    html += checkbox(
                        "Managed",
                        `cfg_${key}_Managed`,
                        !!sec.Managed
                    );
                    html += input("URI", `cfg_${key}_URI`, sec.URI);
                    html += input(
                        "API Key",
                        `cfg_${key}_APIKey`,
                        sec.APIKey,
                        "password"
                    );
                    html += input(
                        "Category",
                        `cfg_${key}_Category`,
                        sec.Category
                    );
                    // EntrySearch
                    html +=
                        '<div class="hint" style="margin-top:8px">EntrySearch</div>';
                    html += checkbox(
                        "Search Missing",
                        `cfg_${key}_EntrySearch_SearchMissing`,
                        !!(sec.EntrySearch && sec.EntrySearch.SearchMissing)
                    );
                    html += checkbox(
                        "Do Upgrade Search",
                        `cfg_${key}_EntrySearch_DoUpgradeSearch`,
                        !!(sec.EntrySearch && sec.EntrySearch.DoUpgradeSearch)
                    );
                    html += checkbox(
                        "Quality Unmet Search",
                        `cfg_${key}_EntrySearch_QualityUnmetSearch`,
                        !!(
                            sec.EntrySearch &&
                            sec.EntrySearch.QualityUnmetSearch
                        )
                    );
                    html += checkbox(
                        "Custom Format Unmet Search",
                        `cfg_${key}_EntrySearch_CustomFormatUnmetSearch`,
                        !!(
                            sec.EntrySearch &&
                            sec.EntrySearch.CustomFormatUnmetSearch
                        )
                    );
                    html += checkbox(
                        "Force Minimum Custom Format",
                        `cfg_${key}_EntrySearch_ForceMinimumCustomFormat`,
                        !!(
                            sec.EntrySearch &&
                            sec.EntrySearch.ForceMinimumCustomFormat
                        )
                    );
                    html += input(
                        "Search Limit",
                        `cfg_${key}_EntrySearch_SearchLimit`,
                        sec.EntrySearch && sec.EntrySearch.SearchLimit,
                        "number"
                    );
                    html += checkbox(
                        "Prioritize Today's Releases",
                        `cfg_${key}_EntrySearch_PrioritizeTodaysReleases`,
                        !!(
                            sec.EntrySearch &&
                            sec.EntrySearch.PrioritizeTodaysReleases
                        )
                    );
                    // Torrent
                    html +=
                        '<div class="hint" style="margin-top:8px">Torrent</div>';
                    html += input(
                        "Ignore Torrents Younger Than (s)",
                        `cfg_${key}_Torrent_IgnoreTorrentsYoungerThan`,
                        sec.Torrent && sec.Torrent.IgnoreTorrentsYoungerThan,
                        "number"
                    );
                    html += input(
                        "Maximum ETA (s)",
                        `cfg_${key}_Torrent_MaximumETA`,
                        sec.Torrent && sec.Torrent.MaximumETA,
                        "number"
                    );
                    html += input(
                        "Maximum Deletable Percentage",
                        `cfg_${key}_Torrent_MaximumDeletablePercentage`,
                        sec.Torrent && sec.Torrent.MaximumDeletablePercentage,
                        "number"
                    );
                    html += checkbox(
                        "Do Not Remove Slow",
                        `cfg_${key}_Torrent_DoNotRemoveSlow`,
                        !!(sec.Torrent && sec.Torrent.DoNotRemoveSlow)
                    );
                    html += input(
                        "Stalled Delay (min)",
                        `cfg_${key}_Torrent_StalledDelay`,
                        sec.Torrent && sec.Torrent.StalledDelay,
                        "number"
                    );
                    html += checkbox(
                        "Re-Search Stalled",
                        `cfg_${key}_Torrent_ReSearchStalled`,
                        !!(sec.Torrent && sec.Torrent.ReSearchStalled)
                    );
                    html += input(
                        "File Extension Allowlist (comma)",
                        `cfg_${key}_Torrent_FileExtensionAllowlist`,
                        (
                            (sec.Torrent &&
                                sec.Torrent.FileExtensionAllowlist) ||
                            []
                        ).join(",")
                    );
                    // SeedingMode
                    html +=
                        '<div class="hint" style="margin-top:8px">Seeding Mode</div>';
                    html += input(
                        "Max Upload Ratio",
                        `cfg_${key}_SeedingMode_MaxUploadRatio`,
                        sec.Torrent &&
                            sec.Torrent.SeedingMode &&
                            sec.Torrent.SeedingMode.MaxUploadRatio,
                        "number"
                    );
                    html += input(
                        "Max Seeding Time (s)",
                        `cfg_${key}_SeedingMode_MaxSeedingTime`,
                        sec.Torrent &&
                            sec.Torrent.SeedingMode &&
                            sec.Torrent.SeedingMode.MaxSeedingTime,
                        "number"
                    );
                    html += input(
                        "Remove Torrent (policy)",
                        `cfg_${key}_SeedingMode_RemoveTorrent`,
                        sec.Torrent &&
                            sec.Torrent.SeedingMode &&
                            sec.Torrent.SeedingMode.RemoveTorrent,
                        "number"
                    );
                    html += "</div></div>";
                }
            }
            root.innerHTML = html;
        };
    }
    if (typeof window.submitConfigForms !== "function") {
        window.submitConfigForms = async function () {
            const get = (id) => document.getElementById(id);
            const changes = {};
            if (get("cfg_ConsoleLevel"))
                changes["Settings.ConsoleLevel"] =
                    get("cfg_ConsoleLevel").value;
            if (get("cfg_Logging"))
                changes["Settings.Logging"] = get("cfg_Logging").checked;
            if (get("cfg_CompletedDownloadFolder"))
                changes["Settings.CompletedDownloadFolder"] = get(
                    "cfg_CompletedDownloadFolder"
                ).value;
            if (get("cfg_FreeSpace"))
                changes["Settings.FreeSpace"] = get("cfg_FreeSpace").value;
            if (get("cfg_FreeSpaceFolder"))
                changes["Settings.FreeSpaceFolder"] = get(
                    "cfg_FreeSpaceFolder"
                ).value;
            if (get("cfg_AutoPauseResume"))
                changes["Settings.AutoPauseResume"] = get(
                    "cfg_AutoPauseResume"
                ).checked;
            if (get("cfg_NoInternetSleepTimer"))
                changes["Settings.NoInternetSleepTimer"] = Number(
                    get("cfg_NoInternetSleepTimer").value || 0
                );
            if (get("cfg_LoopSleepTimer"))
                changes["Settings.LoopSleepTimer"] = Number(
                    get("cfg_LoopSleepTimer").value || 0
                );
            if (get("cfg_SearchLoopDelay"))
                changes["Settings.SearchLoopDelay"] = Number(
                    get("cfg_SearchLoopDelay").value || 0
                );
            if (get("cfg_FailedCategory"))
                changes["Settings.FailedCategory"] =
                    get("cfg_FailedCategory").value;
            if (get("cfg_RecheckCategory"))
                changes["Settings.RecheckCategory"] = get(
                    "cfg_RecheckCategory"
                ).value;
            if (get("cfg_Tagless"))
                changes["Settings.Tagless"] = get("cfg_Tagless").checked;
            if (get("cfg_IgnoreTorrentsYoungerThan"))
                changes["Settings.IgnoreTorrentsYoungerThan"] = Number(
                    get("cfg_IgnoreTorrentsYoungerThan").value || 0
                );
            if (get("cfg_WebUIHost"))
                changes["Settings.WebUIHost"] = get("cfg_WebUIHost").value;
            if (get("cfg_WebUIPort"))
                changes["Settings.WebUIPort"] = Number(
                    get("cfg_WebUIPort").value || 6969
                );
            if (get("cfg_WebUIToken"))
                changes["Settings.WebUIToken"] = get("cfg_WebUIToken").value;
            if (get("cfg_qBit_Disabled"))
                changes["qBit.Disabled"] = get("cfg_qBit_Disabled").checked;
            if (get("cfg_qBit_Host"))
                changes["qBit.Host"] = get("cfg_qBit_Host").value;
            if (get("cfg_qBit_Port"))
                changes["qBit.Port"] = Number(get("cfg_qBit_Port").value || 0);
            if (get("cfg_qBit_UserName"))
                changes["qBit.UserName"] = get("cfg_qBit_UserName").value;
            if (get("cfg_qBit_Password"))
                changes["qBit.Password"] = get("cfg_qBit_Password").value;
            const headers = H();
            // Dynamic arr cards
            const cards = document.querySelectorAll(
                "#configForms .card .card-header"
            );
            for (const header of cards) {
                const key = header.textContent.trim();
                if (/(rad|son|anim)arr/i.test(key)) {
                    const m = (id) =>
                        document.getElementById(`cfg_${key}_${id}`);
                    if (m("Managed"))
                        changes[`${key}.Managed`] = m("Managed").checked;
                    if (m("URI")) changes[`${key}.URI`] = m("URI").value;
                    if (m("APIKey"))
                        changes[`${key}.APIKey`] = m("APIKey").value;
                    if (m("Category"))
                        changes[`${key}.Category`] = m("Category").value;
                    // EntrySearch mappings
                    if (m("EntrySearch_SearchMissing"))
                        changes[`${key}.EntrySearch.SearchMissing`] = m(
                            "EntrySearch_SearchMissing"
                        ).checked;
                    if (m("EntrySearch_DoUpgradeSearch"))
                        changes[`${key}.EntrySearch.DoUpgradeSearch`] = m(
                            "EntrySearch_DoUpgradeSearch"
                        ).checked;
                    if (m("EntrySearch_QualityUnmetSearch"))
                        changes[`${key}.EntrySearch.QualityUnmetSearch`] = m(
                            "EntrySearch_QualityUnmetSearch"
                        ).checked;
                    if (m("EntrySearch_CustomFormatUnmetSearch"))
                        changes[`${key}.EntrySearch.CustomFormatUnmetSearch`] =
                            m("EntrySearch_CustomFormatUnmetSearch").checked;
                    if (m("EntrySearch_ForceMinimumCustomFormat"))
                        changes[`${key}.EntrySearch.ForceMinimumCustomFormat`] =
                            m("EntrySearch_ForceMinimumCustomFormat").checked;
                    if (m("EntrySearch_SearchLimit"))
                        changes[`${key}.EntrySearch.SearchLimit`] = Number(
                            m("EntrySearch_SearchLimit").value || 0
                        );
                    if (m("EntrySearch_PrioritizeTodaysReleases"))
                        changes[`${key}.EntrySearch.PrioritizeTodaysReleases`] =
                            m("EntrySearch_PrioritizeTodaysReleases").checked;
                    // Torrent mappings
                    if (m("Torrent_IgnoreTorrentsYoungerThan"))
                        changes[`${key}.Torrent.IgnoreTorrentsYoungerThan`] =
                            Number(
                                m("Torrent_IgnoreTorrentsYoungerThan").value ||
                                    0
                            );
                    if (m("Torrent_MaximumETA"))
                        changes[`${key}.Torrent.MaximumETA`] = Number(
                            m("Torrent_MaximumETA").value || 0
                        );
                    if (m("Torrent_MaximumDeletablePercentage"))
                        changes[`${key}.Torrent.MaximumDeletablePercentage`] =
                            Number(
                                m("Torrent_MaximumDeletablePercentage").value ||
                                    0
                            );
                    if (m("Torrent_DoNotRemoveSlow"))
                        changes[`${key}.Torrent.DoNotRemoveSlow`] = m(
                            "Torrent_DoNotRemoveSlow"
                        ).checked;
                    if (m("Torrent_StalledDelay"))
                        changes[`${key}.Torrent.StalledDelay`] = Number(
                            m("Torrent_StalledDelay").value || 0
                        );
                    if (m("Torrent_ReSearchStalled"))
                        changes[`${key}.Torrent.ReSearchStalled`] = m(
                            "Torrent_ReSearchStalled"
                        ).checked;
                    if (m("Torrent_FileExtensionAllowlist"))
                        changes[`${key}.Torrent.FileExtensionAllowlist`] = m(
                            "Torrent_FileExtensionAllowlist"
                        )
                            .value.split(",")
                            .map((s) => s.trim())
                            .filter(Boolean);
                    // SeedingMode mappings
                    if (m("SeedingMode_MaxUploadRatio"))
                        changes[`${key}.Torrent.SeedingMode.MaxUploadRatio`] =
                            Number(m("SeedingMode_MaxUploadRatio").value || 0);
                    if (m("SeedingMode_MaxSeedingTime"))
                        changes[`${key}.Torrent.SeedingMode.MaxSeedingTime`] =
                            Number(m("SeedingMode_MaxSeedingTime").value || 0);
                    if (m("SeedingMode_RemoveTorrent"))
                        changes[`${key}.Torrent.SeedingMode.RemoveTorrent`] =
                            Number(m("SeedingMode_RemoveTorrent").value || 0);
                }
            }
            await fetch("/web/config", {
                method: "POST",
                headers,
                body: JSON.stringify({ changes }),
            });
            alert("Saved");
        };
    }
})();

// Overrides: per-instance buttons + unified search routing
(function () {
    // Unified search routing across aggregated and single-instance views
    window.globalSearch = function (q) {
        try {
            if (!window.currentArr) return;
            const t = window.currentArr.type;
            if (t === "radarrAll")
                return window.radarrAggSearch && window.radarrAggSearch(q);
            if (t === "sonarrAll")
                return window.sonarrAggSearch && window.sonarrAggSearch(q);
            if (t === "radarr")
                return (
                    window.loadRadarrAll &&
                    window.loadRadarrAll(window.currentArr.cat, q)
                );
            if (t === "sonarr")
                return (
                    window.loadSonarrAll &&
                    window.loadSonarrAll(window.currentArr.cat, q)
                );
        } catch (e) {
            /* ignore */
        }
    };

    // Build left nav with a 'Load All' plus one button per instance
    window.loadArrList = async function () {
        const H = () => ({ "Content-Type": "application/json" });
        const [arrRes, procRes] = await Promise.all([
            fetch("/web/arr", { headers: H() }),
            fetch("/web/processes", { headers: H() }),
        ]);
        const d = await arrRes.json();
        const procs = await procRes.json();
        const nameByCat = {};
        for (const p of procs.processes || [])
            nameByCat[p.category] = p.name || p.category;

        const rnav = document.getElementById("radarrNav");
        if (rnav) {
            rnav.innerHTML = "";
            const rcats = (d.arr || [])
                .filter((a) => a.type === "radarr")
                .map((a) => a.category);
            const allBtn = document.createElement("button");
            allBtn.className = "btn";
            allBtn.textContent = "Load All Radarr";
            allBtn.onclick = () =>
                window.loadRadarrAllInstances &&
                window.loadRadarrAllInstances(rcats);
            rnav.appendChild(allBtn);
            for (const cat of rcats) {
                const b = document.createElement("button");
                b.className = "btn ghost";
                b.style.display = "block";
                b.style.width = "100%";
                b.style.textAlign = "left";
                b.style.margin = "4px 0";
                b.textContent = nameByCat[cat] || cat;
                b.onclick = () =>
                    window.loadRadarrAll && window.loadRadarrAll(cat);
                rnav.appendChild(b);
            }
        }

        const snav = document.getElementById("sonarrNav");
        if (snav) {
            snav.innerHTML = "";
            const scats = (d.arr || [])
                .filter((a) => a.type === "sonarr")
                .map((a) => a.category);
            const allBtn = document.createElement("button");
            allBtn.className = "btn";
            allBtn.textContent = "Load All Sonarr";
            allBtn.onclick = () =>
                window.loadSonarrAllInstances &&
                window.loadSonarrAllInstances(scats);
            snav.appendChild(allBtn);
            for (const cat of scats) {
                const b = document.createElement("button");
                b.className = "btn ghost";
                b.style.display = "block";
                b.style.width = "100%";
                b.style.textAlign = "left";
                b.style.margin = "4px 0";
                b.textContent = nameByCat[cat] || cat;
                b.onclick = () =>
                    window.loadSonarrAll && window.loadSonarrAll(cat);
                snav.appendChild(b);
            }
        }
    };
})();

// Auto-refresh timers for Processes and ARR counts
(function () {
    let procTimer = null;
    let arrTimer = null;
    function clearTimers() {
        if (procTimer) {
            clearInterval(procTimer);
            procTimer = null;
        }
        if (arrTimer) {
            clearInterval(arrTimer);
            arrTimer = null;
        }
    }
    window.onTabActivated = function (id) {
        clearTimers();
        if (id === "processes") {
            // initial load and start 5s refresh
            if (typeof window.loadProcesses === "function")
                window.loadProcesses();
            procTimer = setInterval(() => {
                try {
                    window.loadProcesses && window.loadProcesses();
                } catch (_) {}
            }, 5000);
        } else if (id === "radarr" || id === "sonarr") {
            // initial nav build and start 5s refresh for counts
            if (typeof window.loadArrList === "function") window.loadArrList();
            arrTimer = setInterval(() => {
                try {
                    window.loadArrList && window.loadArrList();
                } catch (_) {}
            }, 5000);
        }
    };
    // If page initially lands on processes (default), kick off timers
    document.addEventListener("DOMContentLoaded", function () {
        try {
            if (window.__activeTab) {
                window.onTabActivated(window.__activeTab);
            }
        } catch (_) {}
    });
})();

// Periodic data refresh for active ARR tables (1s)
(function () {
    const H = () => ({ "Content-Type": "application/json" });
    async function fetchRadarrCatsItems(cats) {
        let items = [];
        for (const cat of cats || []) {
            let page = 0;
            const ps = 500;
            while (true) {
                const r = await fetch(
                    `/web/radarr/${cat}/movies?q=&page=${page}&page_size=${ps}`,
                    { headers: H() }
                );
                if (!r.ok) break;
                const d = await r.json();
                for (const m of d.movies || [])
                    items.push({ ...m, __instance: cat });
                if (!d.movies || d.movies.length < ps) break;
                page++;
                if (page > 20) break;
            }
        }
        return items;
    }
    async function fetchSonarrCatsRows(cats) {
        let rows = [];
        for (const cat of cats || []) {
            let page = 0;
            const ps = 200;
            while (true) {
                const r = await fetch(
                    `/web/sonarr/${cat}/series?q=&page=${page}&page_size=${ps}`,
                    { headers: H() }
                );
                if (!r.ok) break;
                const d = await r.json();
                for (const s of d.series || []) {
                    const title = s.series?.title || "";
                    for (const [sn, sv] of Object.entries(s.seasons || {})) {
                        for (const e of sv.episodes || []) {
                            rows.push({
                                __instance: cat,
                                series: title,
                                season: sn,
                                ep: e.episodeNumber,
                                title: e.title || "",
                                monitored: !!e.monitored,
                                hasFile: !!e.hasFile,
                                air: e.airDateUtc || "",
                            });
                        }
                    }
                }
                if (!d.series || d.series.length < ps) break;
                page++;
                if (page > 50) break;
            }
        }
        return rows;
    }
    async function refreshActiveArrTable() {
        try {
            if (!window.currentArr) return;
            const t = window.currentArr.type;
            if (t === "radarrAll" && window._radarrAgg) {
                const keepQ = window._radarrAgg.q || "";
                const keepPage = window._radarrAgg.page || 0;
                const cats = window._radarrAgg.cats || [];
                const items = await fetchRadarrCatsItems(cats);
                window._radarrAgg.items = items;
                window._radarrAgg.q = keepQ;
                window._radarrAgg.page = keepPage;
                window.renderRadarrAgg && window.renderRadarrAgg();
            } else if (t === "sonarrAll" && window._sonarrAgg) {
                const keepQ = window._sonarrAgg.q || "";
                const keepPage = window._sonarrAgg.page || 0;
                const cats = window._sonarrAgg.cats || [];
                const rows = await fetchSonarrCatsRows(cats);
                window._sonarrAgg.rows = rows;
                window._sonarrAgg.q = keepQ;
                window._sonarrAgg.page = keepPage;
                window.renderSonarrAgg && window.renderSonarrAgg();
            } else if (t === "radarr" && window.loadRadarrAll) {
                const qEl = document.querySelector(
                    '#radarrContent input[type="text"]'
                );
                const q = qEl ? qEl.value : "";
                window.loadRadarrAll(window.currentArr.cat, q);
            } else if (t === "sonarr" && window.loadSonarrAll) {
                const qEl = document.querySelector(
                    '#sonarrContent input[type="text"]'
                );
                const q = qEl ? qEl.value : "";
                window.loadSonarrAll(window.currentArr.cat, q);
            }
        } catch (_) {}
    }
    // Hook into existing onTabActivated refresh loop
    let dataTimer = null;
    const prevOnTabActivated = window.onTabActivated;
    window.onTabActivated = function (id) {
        try {
            if (typeof prevOnTabActivated === "function")
                prevOnTabActivated(id);
        } catch (_) {}
        if (dataTimer) {
            clearInterval(dataTimer);
            dataTimer = null;
        }
        if (id === "radarr" || id === "sonarr") {
            dataTimer = setInterval(refreshActiveArrTable, 1000);
        }
    };
})();
