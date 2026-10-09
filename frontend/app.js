// BreatheBuddy dashboard logic (Leaflet + fetch).
// window.BB_CONFIG is optional — supplied by amplify-config.js on AWS.
const CFG = window.BB_CONFIG || { apiBase: "", cognito: null };
const API = (p) => `${CFG.apiBase}${p}`;

const AQI_COLORS = [
  [50, "#2ecc71"],   // good
  [100, "#a3d977"],  // satisfactory
  [200, "#f5c542"],  // moderate
  [300, "#ff7a45"],  // poor
  [400, "#b1409a"],  // very poor
  [Infinity, "#7a1030"] // severe
];

function aqiColor(aqi) {
  for (const [max, c] of AQI_COLORS) if (aqi <= max) return c;
  return "#7a1030";
}

let map, gridLayer, stationLayer, schoolLayer, routeLayer;
let schools = [];

function initMap() {
  map = L.map("map", { preferCanvas: true, zoomControl: true })
    .setView([28.61, 77.19], 11);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 19
  }).addTo(map);
  gridLayer = L.layerGroup().addTo(map);
  stationLayer = L.layerGroup().addTo(map);
  schoolLayer = L.layerGroup().addTo(map);
  routeLayer = L.layerGroup().addTo(map);
  renderLegend();
}

function renderLegend() {
  const scale = [
    ["Good (0-50)", "#2ecc71"], ["Satisfactory (51-100)", "#a3d977"],
    ["Moderate (101-200)", "#f5c542"], ["Poor (201-300)", "#ff7a45"],
    ["Very poor (301-400)", "#b1409a"], ["Severe (400+)", "#7a1030"]
  ];
  document.getElementById("legend").innerHTML = scale.map(
    ([t, c]) => `<div class="item"><span class="sw" style="background:${c}"></span>${t}</div>`
  ).join("");
}

function drawGrid(cells) {
  gridLayer.clearLayers();
  for (const c of cells) {
    const d = 0.0025; // ~500 m box
    L.rectangle([[c.lat - d / 2, c.lon - d / 2], [c.lat + d / 2, c.lon + d / 2]], {
      color: "transparent", weight: 0, fillColor: aqiColor(c.aqi_now), fillOpacity: 0.5,
      interactive: false
    }).addTo(gridLayer);
  }
}

async function loadGrid() {
  const cells = await (await fetch(API("/grid"))).json();
  drawGrid(cells);
}

async function loadStations() {
  const stations = await (await fetch(API("/stations"))).json();
  stationLayer.clearLayers();
  for (const s of stations) {
    L.circleMarker([s.lat, s.lon], {
      radius: 6, color: "#fff", weight: 1.5, fillColor: aqiColor(s.aqi), fillOpacity: 1
    }).bindPopup(`<b>${s.station_id}</b><br>AQI ${s.aqi}<br>PM2.5 ${s.pm25}`).addTo(stationLayer);
  }
}

async function loadSchools() {
  schools = await (await fetch(API("/schools"))).json();
  const sel = document.getElementById("school-select");
  sel.innerHTML = schools.map(s => `<option value="${s.school_id}">${s.name}</option>`).join("");
  schoolLayer.clearLayers();
  for (const s of schools) {
    L.marker([s.lat, s.lon]).bindPopup(
      `<b>${s.name}</b><br>${s.students} students`).addTo(schoolLayer)
      .on("click", () => loadSchoolCard(s.school_id));
  }
  sel.onchange = () => loadSchoolCard(sel.value);
  if (schools.length) loadSchoolCard(schools[0].school_id);
}

async function loadSchoolCard(id) {
  const card = await (await fetch(API(`/school/${id}/today`))).json();
  const chips = (list, cls) => list.map(a => `<span class="chip ${cls}">${a.replace(/_/g, " ")}</span>`).join("");
  const el = document.getElementById("school-card");
  el.innerHTML = `
    <div><span class="aqi-big" style="color:${aqiColor(card.aqi_now)}">${card.aqi_now}</span>
      <span class="badge" style="background:${aqiColor(card.aqi_now)};color:#08121f">${card.status}</span></div>
    <div style="font-weight:600;margin:6px 0">${card.headline}</div>
    <div style="color:var(--muted);font-size:11px">Peak next 6h: ${card.aqi_peak} · clean-index ${card.clean_index}</div>
    <div style="font-size:11px;margin-top:8px;color:var(--muted)">Allowed</div>
    <div class="chips">${chips(card.allowed, "ok") || "<span class='chip no'>none</span>"}</div>
    <div style="font-size:11px;margin-top:8px;color:var(--muted)">Blocked by Cedar</div>
    <div class="chips">${chips(card.blocked, "no") || "<span class='chip ok'>none</span>"}</div>
    <div style="font-size:11px;color:var(--muted);margin-top:8px">
      ${card.decisions.hold_outdoor_assembly.reason}</div>
    <div class="indoor">
      <h3>Indoor air advisory (indoor est. AQI ${card.indoor_aqi_estimate})</h3>
      <ul>${(card.indoor_advisory || []).map(t => `<li>${t}</li>`).join("")}</ul>
    </div>`;
}

function windArrow(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round(((deg % 360) / 45)) % 8];
}

async function loadEvents() {
  const events = await (await fetch(API("/events"))).json();
  const el = document.getElementById("event-banner");
  if (!events.length) { el.style.display = "none"; return; }
  el.style.display = "block";
  el.innerHTML = events.map(e => {
    const from = windArrow(e.wind_dir_deg || 0);
    const to = windArrow((e.wind_dir_deg || 0) + 180);
    return `<b>Stubble-burning spike</b><br>${e.label}<br>
      <span class="wind">Smoke drifting ${from} &rarr; ${to} &middot; grid AQI elevated downwind</span>`;
  }).join("<hr>");
}

async function loadAlerts() {
  const alerts = await (await fetch(API("/alerts"))).json();
  const el = document.getElementById("alerts");
  el.innerHTML = alerts.length
    ? alerts.map(a => `<div class="alert"><b>${a.kind}</b><br>${a.message}</div>`).join("")
    : "No alerts yet.";
}

function drawRoute(res) {
  routeLayer.clearLayers();
  const style = (mode, color) => ({
    color, weight: 5, opacity: 0.9,
    dashArray: mode === "fastest" ? "8 6" : null
  });
  L.polyline(res.fastest.geometry, style("fastest", "#4aa8ff")).addTo(routeLayer)
    .bindTooltip("Fastest");
  L.polyline(res.cleanest.geometry, style("cleanest", "#35d29e")).addTo(routeLayer)
    .bindTooltip("Cleanest");
  const f = res.fastest, c = res.cleanest;
  const row = (m, r) => `<tr><td>${m}</td><td>${(r.distance_m / 1000).toFixed(1)} km</td>
      <td>AQI ${r.avg_aqi}</td><td>clean ${r.clean_index}</td><td>${r.duration_min} min</td></tr>`;
  const el = document.getElementById("route-result");
  el.style.display = "block";
  el.innerHTML = `<b>Route comparison</b> — winner: <span class="win">${res.winner}</span><br>
    <table>${row("Fastest", f)}${row("Cleanest", c)}</table>
    <div style="margin-top:6px;color:var(--muted)">${res.note}</div>`;
}

async function compareRoutes() {
  const from = document.getElementById("from").value.trim();
  const to = document.getElementById("to").value.trim();
  const res = await (await fetch(
    API(`/route?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`))).json();
  drawRoute(res);
}

async function askAgent() {
  const question = document.getElementById("question").value;
  const out = document.getElementById("agent-out");
  out.textContent = "Thinking…";
  const res = await (await fetch(API("/agent"), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question })
  })).json();
  out.innerHTML = `<b>${res.answer}</b>\n\n` +
    (res.steps || []).map(s => "• " + s).join("\n") +
    `\n\n(engine: ${res.engine})`;
  loadAlerts();
}

async function runCycle() {
  const btn = document.getElementById("btn-cycle");
  btn.textContent = "Running…";
  await fetch(API("/cycle"), { method: "POST" });
  btn.textContent = "Run 15-min cycle";
  await Promise.all([loadGrid(), loadStations(), loadAlerts(), loadEvents()]);
  await loadSchoolCard(document.getElementById("school-select").value);
}

async function submitSubscribe(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  const res = await (await fetch(API("/subscribe"), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
  })).json();
  document.getElementById("sub-out").textContent =
    `Subscribed ${res.name} (${res.kind}) — alert threshold AQI ${res.threshold_aqi}.`;
}

function initAuth() {
  const btn = document.getElementById("btn-auth");
  if (!CFG.cognito) {
    btn.onclick = () => alert("Cognito is configured only in the AWS deployment "
      + "(see infra/ + frontend/amplify-config.js).");
    return;
  }
  btn.onclick = () => { window.location.href = CFG.cognito.hostedUi; };
}

window.addEventListener("DOMContentLoaded", async () => {
  initMap();
  initAuth();
  document.getElementById("btn-route").onclick = compareRoutes;
  document.getElementById("btn-ask").onclick = askAgent;
  document.getElementById("btn-cycle").onclick = runCycle;
  document.getElementById("subscribe-form").onsubmit = submitSubscribe;
  await Promise.all([loadGrid(), loadStations(), loadSchools(), loadAlerts(), loadEvents()]);
});
