// BreatheBuddy dashboard logic (Leaflet + fetch).
// window.BB_CONFIG is optional; supplied by amplify-config.js on AWS.
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

// --- i18n (English + Hindi) ------------------------------------------------
const I18N = {
  en: {
    run_cycle: "Run 15-min cycle", sign_in: "Sign in (Cognito)",
    for_who: "For <b>school admins</b> &amp; <b>vulnerable commuters</b>",
    steps: "<b>1</b> Run cycle <i>&rarr;</i> <b>2</b> Pick a school <i>&rarr;</i> "
      + "<b>3</b> Compare routes <i>&rarr;</i> <b>4</b> Ask the agent",
    air_line: "500 m hyperlocal AQI &middot; 6-hour nowcast &middot; Cedar school rules",
    today_school: "Today at your school", vuln_alerts: "Vulnerable alerts",
    forecast: "Forecast", from_label: "From (lat,lon)", to_label: "To (lat,lon)",
    compare: "Compare routes", pick: "Pick on map", near_me: "Near me", clear: "Clear",
    ask_title: "Ask BreatheBuddy", ask_hint: "Strands agent + Cedar policy",
    eng_auto: "Auto (Strands SDK if configured)", eng_simple: "Deterministic (offline)",
    ask_btn: "Ask agent", sub_title: "Subscribe (vulnerable)",
    kind_rider: "Rider", kind_asthma: "Asthma patient", kind_child: "School child",
    kind_elderly: "Elderly", sub_btn: "Subscribe",
    ph_name: "Name", ph_phone: "Phone (+91…)", ph_email: "Email", now: "Now"
  },
  hi: {
    run_cycle: "15-मिनट चक्र चलाएँ", sign_in: "साइन इन (Cognito)",
    for_who: "<b>स्कूल एडमिन</b> और <b>संवेदनशील यात्रियों</b> के लिए",
    steps: "<b>1</b> चक्र चलाएँ <i>&rarr;</i> <b>2</b> स्कूल चुनें <i>&rarr;</i> "
      + "<b>3</b> रास्ते तुलना करें <i>&rarr;</i> <b>4</b> एजेंट से पूछें",
    air_line: "500 मी हाइपरलोकल AQI &middot; 6-घंटे पूर्वानुमान &middot; Cedar स्कूल नियम",
    today_school: "आज आपके स्कूल में", vuln_alerts: "संवेदनशील अलर्ट",
    forecast: "पूर्वानुमान", from_label: "से (lat,lon)", to_label: "तक (lat,lon)",
    compare: "रास्ते तुलना करें", pick: "नक्शे पर चुनें", near_me: "मेरे पास",
    clear: "साफ़ करें",
    ask_title: "BreatheBuddy से पूछें", ask_hint: "Strands एजेंट + Cedar नीति",
    eng_auto: "ऑटो (Strands SDK सेट हो तो)", eng_simple: "नियतात्मक (ऑफ़लाइन)",
    ask_btn: "एजेंट से पूछें", sub_title: "सब्सक्राइब (संवेदनशील)",
    kind_rider: "राइडर", kind_asthma: "अस्थमा रोगी", kind_child: "स्कूली बच्चा",
    kind_elderly: "बुज़ुर्ग", sub_btn: "सब्सक्राइब करें",
    ph_name: "नाम", ph_phone: "फ़ोन (+91…)", ph_email: "ईमेल", now: "अभी"
  }
};

let LANG = (typeof localStorage !== "undefined" && localStorage.getItem("bb_lang")) || "en";
if (!I18N[LANG]) LANG = "en";

function t(key) {
  return (I18N[LANG] && I18N[LANG][key]) || I18N.en[key] || key;
}

function applyLang() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-html]").forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
  setForecast(FC_IDX);   // refresh the dynamic "Now / +Nh" label
}

function setLang(lang) {
  LANG = I18N[lang] ? lang : "en";
  try { localStorage.setItem("bb_lang", LANG); } catch (e) { /* private mode */ }
  applyLang();
}

let map, gridLayer, stationLayer, schoolLayer, routeLayer, pickLayer, meLayer;
let schools = [];
let gridCells = [];
let FC_IDX = 0;          // 0 = "Now", 1..6 = forecast hour offset
let PICK_MODE = false;   // when true, map clicks set route start/end
let PICK_POINTS = [];
let MAP_READY = false;

function initMap() {
  if (!window.L) throw new Error("Leaflet not loaded");
  map = L.map("map", { preferCanvas: true, zoomControl: true })
    .setView([28.61, 77.19], 11);
  // Map imagery is cached locally (frontend/vendor/tiles, see
  // scripts/fetch_tiles.py) so the map works offline. maxNativeZoom lets
  // Leaflet upscale the cached z13 tiles for deeper zooms; any uncached tile
  // falls back to the live keyless Esri "Dark Gray" server when online.
  const tiles = L.tileLayer("vendor/tiles/{z}/{x}/{y}.jpg", {
    attribution: "&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
    minZoom: 9, maxZoom: 18, maxNativeZoom: 13
  }).addTo(map);
  tiles.on("tileerror", (e) => {
    if (!e.tile || e.tile.dataset.remote) return;
    e.tile.dataset.remote = "1";
    e.tile.src = "https://server.arcgisonline.com/ArcGIS/rest/services/"
      + `Canvas/World_Dark_Gray_Base/MapServer/tile/${e.coords.z}/${e.coords.y}/${e.coords.x}`;
  });
  gridLayer = L.layerGroup().addTo(map);
  stationLayer = L.layerGroup().addTo(map);
  schoolLayer = L.layerGroup().addTo(map);
  routeLayer = L.layerGroup().addTo(map);
  pickLayer = L.layerGroup().addTo(map);
  meLayer = L.layerGroup().addTo(map);
  map.on("click", onMapClick);
  renderLegend();
  MAP_READY = true;
}

// Wait for Leaflet (local vendor file, or the CDN fallback) to appear.
function ensureLeaflet(timeoutMs = 6000) {
  if (window.L) return Promise.resolve(true);
  return new Promise((resolve) => {
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (window.L) { clearInterval(iv); resolve(true); }
      else if (Date.now() - t0 > timeoutMs) { clearInterval(iv); resolve(false); }
    }, 100);
  });
}

function showMapNotice(msg) {
  const el = document.getElementById("map");
  if (el) el.innerHTML = `<div class="map-notice">${msg}</div>`;
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

// AQI shown at the current forecast offset (0 = now).
function aqiAt(c) {
  if (FC_IDX > 0 && Array.isArray(c.aqi_forecast) && c.aqi_forecast[FC_IDX - 1] != null) {
    return c.aqi_forecast[FC_IDX - 1];
  }
  return c.aqi_now;
}

function drawGrid(cells) {
  if (!MAP_READY) return;
  gridLayer.clearLayers();
  if (!cells.length) return;
  // Derive the true cell size from the grid instead of assuming a fixed
  // degree box (500 m is ~0.0045° lat, ~0.005° lon at Delhi's latitude).
  const lats = [...new Set(cells.map(c => c.lat))].sort((a, b) => a - b);
  const lons = [...new Set(cells.map(c => c.lon))].sort((a, b) => a - b);
  const dLat = lats.length > 1 ? Math.abs(lats[1] - lats[0]) : 0.0045;
  const dLon = lons.length > 1 ? Math.abs(lons[1] - lons[0]) : 0.005;
  for (const c of cells) {
    L.rectangle([
      [c.lat - dLat / 2, c.lon - dLon / 2],
      [c.lat + dLat / 2, c.lon + dLon / 2]
    ], {
      color: "transparent", weight: 0, fillColor: aqiColor(aqiAt(c)), fillOpacity: 0.5,
      interactive: false
    }).addTo(gridLayer);
  }
}

async function loadGrid() {
  gridCells = await (await fetch(API("/grid"))).json();
  if (!Array.isArray(gridCells)) gridCells = [];
  drawGrid(gridCells);
}

// Forecast time slider: 0 = Now, n = +n hours.
function setForecast(idx) {
  FC_IDX = Math.max(0, Math.min(6, Number(idx) || 0));
  const label = document.getElementById("fc-label");
  if (label) label.textContent = FC_IDX === 0 ? t("now") : `+${FC_IDX}h`;
  drawGrid(gridCells);
}

function togglePickMode(force) {
  PICK_MODE = force === undefined ? !PICK_MODE : !!force;
  if (PICK_MODE) PICK_POINTS = [];
  const btn = document.getElementById("btn-pick");
  if (btn) btn.classList.toggle("active", PICK_MODE);
  if (PICK_MODE) showPickHint("Click the map to set the start point…");
}

function showPickHint(msg) {
  const el = document.getElementById("route-result");
  if (el) { el.style.display = "block"; el.innerHTML = `<span class="hint">${msg}</span>`; }
}

function onMapClick(e) {
  if (!PICK_MODE) return;
  const { lat, lng } = e.latlng;
  const val = `${lat.toFixed(4)},${lng.toFixed(4)}`;
  PICK_POINTS.push(e.latlng);
  if (pickLayer) {
    L.marker(e.latlng, {
      icon: L.divIcon({ className: "pick-pin", html: "📍", iconSize: [24, 24] })
    }).addTo(pickLayer);
  }
  if (PICK_POINTS.length === 1) {
    document.getElementById("from").value = val;
    showPickHint("Now click the end point…");
  } else {
    document.getElementById("to").value = val;
    togglePickMode(false);
    compareRoutes();
  }
}

function clearRoute() {
  if (routeLayer) routeLayer.clearLayers();
  if (pickLayer) pickLayer.clearLayers();
  PICK_POINTS = [];
  togglePickMode(false);
  const el = document.getElementById("route-result");
  if (el) { el.style.display = "none"; el.innerHTML = ""; }
}

// "Near me": use the browser's location to show local AQI and start routes here.
function locateMe() {
  const el = document.getElementById("route-result");
  const show = (html) => { if (el) { el.style.display = "block"; el.innerHTML = html; } };
  if (!navigator.geolocation) {
    show(`<span class="err">Geolocation is not supported by this browser.</span>`);
    return;
  }
  show(`<span class="hint">Locating…</span>`);
  navigator.geolocation.getCurrentPosition(async (pos) => {
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    const val = `${lat.toFixed(4)},${lon.toFixed(4)}`;
    document.getElementById("from").value = val;
    try {
      const nc = await (await fetch(API(`/aqi?lat=${lat}&lon=${lon}`))).json();
      if (nc.error) { show(`<span class="err">${nc.error}</span>`); return; }
      if (MAP_READY && meLayer) {
        meLayer.clearLayers();
        L.circleMarker([lat, lon], {
          radius: 8, color: "#fff", weight: 2, fillColor: aqiColor(nc.aqi_now), fillOpacity: 1
        }).bindPopup(`<b>You are here</b><br>AQI ${nc.aqi_now}<br>${nc.category || ""}`)
          .addTo(meLayer).openPopup();
        map.setView([lat, lon], 13);
      }
      show(`<b>Your location</b> - AQI ${nc.aqi_now} (${nc.category || ""})<br>
        <span class="hint">Start point set. Now pick a destination and compare routes.</span>`);
    } catch (e) {
      show(`<span class="err">Could not load local AQI - is the server running?</span>`);
    }
  }, (err) => {
    show(`<span class="err">Location unavailable (${err.message}).</span>`);
  }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 });
}

async function loadStations() {
  const stations = await (await fetch(API("/stations"))).json();
  if (!MAP_READY || !Array.isArray(stations)) return;
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
  if (!Array.isArray(schools)) { sel.innerHTML = ""; return; }
  sel.innerHTML = schools.map(s => `<option value="${s.school_id}">${s.name}</option>`).join("");
  if (MAP_READY) {
    schoolLayer.clearLayers();
    for (const s of schools) {
      L.marker([s.lat, s.lon]).bindPopup(
        `<b>${s.name}</b><br>${s.students} students`).addTo(schoolLayer)
        .on("click", () => loadSchoolCard(s.school_id));
    }
  }
  sel.onchange = () => loadSchoolCard(sel.value);
  if (schools.length) loadSchoolCard(schools[0].school_id);
}

async function loadSchoolCard(id) {
  const el = document.getElementById("school-card");
  const card = await (await fetch(API(`/school/${id}/today`))).json();
  if (card.error || card.aqi_now === undefined) {
    el.innerHTML = `<div class="err">Could not load school: ${card.error || "unknown"}</div>`;
    return;
  }
  const chips = (list, cls) => list.map(a => `<span class="chip ${cls}">${a.replace(/_/g, " ")}</span>`).join("");
  const reason = (card.decisions && card.decisions.hold_outdoor_assembly)
    ? card.decisions.hold_outdoor_assembly.reason : "";
  el.innerHTML = `
    <div><span class="aqi-big" style="color:${aqiColor(card.aqi_now)}">${card.aqi_now}</span>
      <span class="badge" style="background:${aqiColor(card.aqi_now)};color:#08121f">${card.status}</span></div>
    <div style="font-weight:600;margin:6px 0">${card.headline}</div>
    <div style="color:var(--muted);font-size:11px">Peak next 6h: ${card.aqi_peak} · clean-index ${card.clean_index}</div>
    <div style="font-size:11px;margin-top:8px;color:var(--muted)">Allowed</div>
    <div class="chips">${chips(card.allowed, "ok") || "<span class='chip no'>none</span>"}</div>
    <div style="font-size:11px;margin-top:8px;color:var(--muted)">Blocked by Cedar</div>
    <div class="chips">${chips(card.blocked, "no") || "<span class='chip ok'>none</span>"}</div>
    <div style="font-size:11px;color:var(--muted);margin-top:8px">${reason}</div>
    <div class="indoor">
      <h3>Indoor air advisory (indoor est. AQI ${card.indoor_aqi_estimate})</h3>
      <ul>${(card.indoor_advisory || []).map(t => `<li>${t}</li>`).join("")}</ul>
    </div>`;
}

function windArrow(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const d = ((Number(deg) || 0) % 360 + 360) % 360;
  return dirs[Math.round(d / 45) % 8];
}

async function loadEvents() {
  const el = document.getElementById("event-banner");
  const events = await (await fetch(API("/events"))).json();
  if (!Array.isArray(events) || !events.length) { el.style.display = "none"; return; }
  el.style.display = "block";
  el.innerHTML = events.map(e => {
    const from = windArrow(e.wind_dir_deg || 0);
    const to = windArrow((e.wind_dir_deg || 0) + 180);
    return `<b>Stubble-burning spike</b><br>${e.label}<br>
      <span class="wind">Smoke drifting ${from} &rarr; ${to} &middot; grid AQI elevated downwind</span>`;
  }).join("<hr>");
}

async function loadAlerts() {
  const el = document.getElementById("alerts");
  const alerts = await (await fetch(API("/alerts"))).json();
  if (!Array.isArray(alerts)) { el.textContent = "No alerts yet."; return; }
  el.innerHTML = alerts.length
    ? alerts.map(a => `<div class="alert"><b>${a.kind}</b><br>${a.message}</div>`).join("")
    : "No alerts yet.";
}

function drawRoute(res) {
  if (MAP_READY) {
    routeLayer.clearLayers();
    const style = (mode, color) => ({
      color, weight: 5, opacity: 0.9,
      dashArray: mode === "fastest" ? "8 6" : null
    });
    L.polyline(res.fastest.geometry, style("fastest", "#4aa8ff")).addTo(routeLayer)
      .bindTooltip("Fastest");
    L.polyline(res.cleanest.geometry, style("cleanest", "#35d29e")).addTo(routeLayer)
      .bindTooltip("Cleanest");
  }
  const f = res.fastest, c = res.cleanest;
  const row = (m, r) => `<tr><td>${m}</td><td>${(r.distance_m / 1000).toFixed(1)} km</td>
      <td>AQI ${r.avg_aqi}</td><td>clean ${r.clean_index}</td><td>${r.duration_min} min</td></tr>`;
  const el = document.getElementById("route-result");
  el.style.display = "block";
  el.innerHTML = `<b>Route comparison</b> - winner: <span class="win">${res.winner}</span><br>
    <table>${row("Fastest", f)}${row("Cleanest", c)}</table>
    <div style="margin-top:6px;color:var(--muted)">${res.note}</div>`;
}

async function compareRoutes() {
  const from = document.getElementById("from").value.trim();
  const to = document.getElementById("to").value.trim();
  const el = document.getElementById("route-result");
  el.style.display = "block";
  let res;
  try {
    res = await (await fetch(
      API(`/route?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`))).json();
  } catch (e) {
    el.innerHTML = `<span class="err">Network error - is the server running?</span>`;
    return;
  }
  if (res.error || !res.fastest) {
    el.innerHTML = `<span class="err">${res.error || "No route found. Use from=lat,lon&to=lat,lon"}</span>`;
    return;
  }
  drawRoute(res);
}

async function askAgent() {
  const question = document.getElementById("question").value;
  const engine = document.getElementById("engine") ? document.getElementById("engine").value : "auto";
  const out = document.getElementById("agent-out");
  out.textContent = "Thinking…";
  let res;
  try {
    res = await (await fetch(API("/agent"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, engine })
    })).json();
  } catch (e) {
    out.innerHTML = `<span class="err">Network error - is the server running?</span>`;
    return;
  }
  if (res.error) { out.innerHTML = `<span class="err">${res.error}</span>`; return; }
  out.innerHTML = `<b>${res.answer}</b>\n\n` +
    (res.steps || []).map(s => "• " + s).join("\n") +
    `\n\n(engine: ${res.engine})`;
  loadAlerts();
}

async function runCycle() {
  const btn = document.getElementById("btn-cycle");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Running…";
  try {
    await fetch(API("/cycle"), { method: "POST" });
  } catch (e) {
    document.getElementById("alerts").innerHTML =
      `<span class="err">Network error - is the server running?</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
  await refreshAll();
}

async function submitSubscribe(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  const out = document.getElementById("sub-out");
  out.textContent = "Subscribing…";
  let res;
  try {
    res = await (await fetch(API("/subscribe"), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
    })).json();
  } catch (err) {
    out.innerHTML = `<span class="err">Network error - is the server running?</span>`;
    return;
  }
  out.innerHTML = res.error
    ? `<span class="err">${res.error}</span>`
    : `Subscribed ${res.name} (${res.kind}) - alert threshold AQI ${res.threshold_aqi}.`;
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

function wireControls() {
  initAuth();
  const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
  bind("btn-route", compareRoutes);
  bind("btn-pick", () => togglePickMode());
  bind("btn-nearme", locateMe);
  bind("btn-clear", clearRoute);
  bind("btn-lang", () => setLang(LANG === "en" ? "hi" : "en"));
  bind("btn-ask", askAgent);
  bind("btn-cycle", runCycle);
  const slider = document.getElementById("fc-slider");
  if (slider) slider.oninput = () => setForecast(slider.value);
  const form = document.getElementById("subscribe-form");
  if (form) form.onsubmit = submitSubscribe;
}

async function refreshAll() {
  const id = document.getElementById("school-select").value;
  await Promise.allSettled([loadGrid(), loadStations(), loadAlerts(), loadEvents()]);
  if (id) await loadSchoolCard(id);
}

async function bootstrapUI() {
  // 1) Wire every button FIRST so the UI works even if the map/CDN fails.
  wireControls();
  // 2) Apply the saved language.
  applyLang();
  // 2) Bring up the map best-effort (local vendor, else CDN, else a notice).
  const ok = await ensureLeaflet();
  if (ok) {
    try { initMap(); }
    catch (e) { showMapNotice("Map failed to start - the side panels still work."); }
  } else {
    showMapNotice("Map library unavailable (offline?). The side panels still work.");
  }
  // 3) Load data; failures never disable the buttons.
  await Promise.allSettled([loadGrid(), loadStations(), loadSchools(), loadAlerts(), loadEvents()]);
}

window.addEventListener("DOMContentLoaded", bootstrapUI);
