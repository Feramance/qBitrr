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
    document.getElementById(id).style.display = "block";
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
async function applyLogLevel() {
    const lv = document.getElementById("logLevel").value;
    await fetch("/api/loglevel", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ level: lv }),
    });
    alert("Log level set to " + lv);
}

async function loadLogs() {
    const r = await fetch("/api/logs", { headers: headers() });
    const d = await r.json();
    let html = "";
    for (const f of d.files) {
        html += `<button onclick=tail('${f}')>${f}</button> `;
    }
    document.getElementById("logFiles").innerHTML = html;
}
async function tail(name) {
    const t = localStorage.getItem("token");
    const q = t ? `?token=${encodeURIComponent(t)}` : "";
    const r = await fetch(`/api/logs/${name}${q}`);
    const c = await r.text();
    document.getElementById("logTail").textContent = c;
    document.getElementById("logTail").dataset.filename = name;
}
function downloadCurrent() {
    const name = document.getElementById("logTail").dataset.filename;
    if (!name) return;
    const t = localStorage.getItem("token");
    const q = t ? `?token=${encodeURIComponent(t)}` : "";
    window.location = `/api/logs/${name}/download${q}`;
}

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
    await fetch(`/api/arr/${cat}/restart`, {
        method: "POST",
        headers: headers(),
    });
    alert("Restarted " + cat);
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
show("processes");
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
