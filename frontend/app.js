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
    ph_name: "Name", ph_phone: "Phone (+91…)", ph_email: "Email", now: "Now",
    bm_dark: "Dark", bm_streets: "Streets", bm_sat: "Satellite", bm_terrain: "Terrain",
    route_title: "Route comparison", winner: "winner", fastest: "Fastest", cleanest: "Cleanest",
    no_route: "No route found. Use from=lat,lon&to=lat,lon",
    no_alerts: "No alerts yet.", err_server: "Network error - is the server running?",
    thinking: "Thinking…", rl_running: "Running…", sub_running: "Subscribing…",
    engine: "engine", school_allowed: "Allowed", school_blocked: "Blocked by Cedar",
    school_peak: "Peak next 6h", indoor_title: "Indoor air advisory (indoor est. AQI {aqi})",
    pick_start: "Click the map to set the start point…", pick_end: "Now click the end point…",
    locating: "Locating…", your_location: "Your location",
    start_point_set: "Start point set. Now pick a destination and compare routes.",
    stubble: "Stubble-burning spike",
    wind: "Smoke drifting {from} → {to} · grid AQI elevated downwind",
    geo_unsupported: "Geolocation is not supported by this browser.",
    geo_unavailable: "Location unavailable",
    sub_done: "Subscribed {name} ({kind}) - alert threshold AQI {threshold}.",
    leg_good: "Good (0-50)", leg_sat: "Satisfactory (51-100)", leg_mod: "Moderate (101-200)",
    leg_poor: "Poor (201-300)", leg_vpoor: "Very poor (301-400)", leg_sev: "Severe (400+)"
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
    ph_name: "नाम", ph_phone: "फ़ोन (+91…)", ph_email: "ईमेल", now: "अभी",
    bm_dark: "डार्क", bm_streets: "सड़कें", bm_sat: "सैटेलाइट", bm_terrain: "भू-आकृति",
    route_title: "रास्तों की तुलना", winner: "विजेता", fastest: "सबसे तेज़", cleanest: "सबसे साफ़",
    no_route: "कोई रास्ता नहीं मिला। from=lat,lon और to=lat,lon दें",
    no_alerts: "अभी कोई अलर्ट नहीं।", err_server: "नेटवर्क त्रुटि - क्या सर्वर चल रहा है?",
    thinking: "सोच रहा है…", rl_running: "चल रहा है…", sub_running: "सब्सक्राइब हो रहा है…",
    engine: "इंजन", school_allowed: "अनुमत", school_blocked: "Cedar द्वारा अवरुद्ध",
    school_peak: "अगले 6 घंटे का शिखर", indoor_title: "इनडोर वायु सलाह (अनुमानित इनडोर AQI {aqi})",
    pick_start: "प्रारंभ बिंदु के लिए नक्शे पर क्लिक करें…", pick_end: "अब अंत बिंदु पर क्लिक करें…",
    locating: "स्थान ढूँढ रहे हैं…", your_location: "आपका स्थान",
    start_point_set: "प्रारंभ बिंदु सेट। अब गंतव्य चुनें और रास्ते तुलना करें।",
    stubble: "पराली जलने का उछाल",
    wind: "धुआँ {from} → {to} बह रहा · नीचे की ओर ग्रिड AQI बढ़ा",
    geo_unsupported: "यह ब्राउज़र जियोलोकेशन का समर्थन नहीं करता।",
    geo_unavailable: "स्थान उपलब्ध नहीं",
    sub_done: "{name} सब्सक्राइब हुआ ({kind}) - अलर्ट थ्रेशोल्ड AQI {threshold}।",
    leg_good: "अच्छा (0-50)", leg_sat: "संतोषजनक (51-100)", leg_mod: "मध्यम (101-200)",
    leg_poor: "खराब (201-300)", leg_vpoor: "बहुत खराब (301-400)", leg_sev: "गंभीर (400+)"
  }
};

let LANG = (typeof localStorage !== "undefined" && localStorage.getItem("bb_lang")) || "en";
if (!I18N[LANG]) LANG = "en";

function t(key) {
  return (I18N[LANG] && I18N[LANG][key]) || I18N.en[key] || key;
}

// Translate + fill {placeholders}: tf("wind", {from: "N", to: "S"}).
function tf(key, vars) {
  let s = t(key);
  for (const k in (vars || {})) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}

// --- colour contrast helpers ----------------------------------------------
function _hexRgb(h) {
  h = h.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function _lum(hex) {
  const [r, g, b] = _hexRgb(hex).map(v => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
// Pick dark or light text for a filled swatch of the given background colour.
function textOn(bg) { return _lum(bg) > 0.35 ? "#08121f" : "#ffffff"; }
// Lighten a very dark colour so it stays legible as text on the dark card.
function readable(hex) {
  if (_lum(hex) >= 0.30) return hex;
  const [r, g, b] = _hexRgb(hex).map(v => Math.round(v + (255 - v) * 0.65));
  return `rgb(${r},${g},${b})`;
}

// fetch JSON with a timeout and a clear error on non-2xx (spinners never hang).
async function fetchJSON(path, opts = {}, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(API(path), { ...opts, signal: ctrl.signal });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

function setErr(el, msg) { if (el) el.innerHTML = `<span class="err">${msg}</span>`; }

// Disable a button while an async action runs (prevents double submit).
async function withBusy(btn, label, fn) {
  if (!btn || btn.disabled) return fn();
  const orig = btn.textContent;
  btn.disabled = true;
  if (label) btn.textContent = label;
  try { return await fn(); }
  finally { btn.disabled = false; btn.textContent = orig; }
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
  // Dynamic regions are built in JS, so re-render them in the new language.
  const sel = document.getElementById("school-select");
  if (sel && sel.value) loadSchoolCard(sel.value);
  if (document.getElementById("alerts")) loadAlerts();
  if (document.getElementById("event-banner")) loadEvents();
  if (typeof renderLegend === "function") renderLegend();
}

let map, gridLayer, stationLayer, schoolLayer, routeLayer, pickLayer, meLayer;
let baseLayer, labelLayer;
let schools = [];
let gridCells = [];
let FC_IDX = 0;          // 0 = "Now", 1..6 = forecast hour offset
let PICK_MODE = false;   // when true, map clicks set route start/end
let PICK_POINTS = [];
let MAP_READY = false;
let currentBasemap = "dark";

// Keyless Esri basemaps. "dark" is cached in frontend/vendor/tiles so the demo
// works offline; the others are live services that make the map look richer.
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";
const MAP_ATTR = "&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors";
const BM_KEY = "bb_basemap_v2"; // remembers the user's explicit map-style pick
const BASEMAPS = {
  dark: { url: `${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
          labels: `${ESRI}/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}` },
  streets: { url: `${ESRI}/World_Street_Map/MapServer/tile/{z}/{y}/{x}` },
  satellite: { url: `${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`,
               labels: `${ESRI}/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}` },
  terrain: { url: `${ESRI}/World_Topo_Map/MapServer/tile/{z}/{y}/{x}` }
};

function makeBaseLayer(name) {
  if (name === "dark") {
    const l = L.tileLayer("vendor/tiles/{z}/{x}/{y}.jpg", {
      attribution: MAP_ATTR, minZoom: 9, maxZoom: 18, maxNativeZoom: 13
    });
    // Uncached tile -> live Esri "Dark Gray" server when online.
    l.on("tileerror", (e) => {
      if (!e.tile || e.tile.dataset.remote) return;
      e.tile.dataset.remote = "1";
      e.tile.src = `${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/${e.coords.z}/${e.coords.y}/${e.coords.x}`;
    });
    return l;
  }
  const b = BASEMAPS[name] || BASEMAPS.dark;
  return L.tileLayer(b.url, { attribution: MAP_ATTR, minZoom: 9, maxZoom: 18 });
}

function makeLabelLayer(name) {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return null;
  const b = BASEMAPS[name];
  if (!b || !b.labels) return null;
  return L.tileLayer(b.labels, { minZoom: 9, maxZoom: 18, pane: "labels" });
}

function setBasemap(name, persist) {
  if (!BASEMAPS[name]) name = "dark";
  if (baseLayer) map.removeLayer(baseLayer);
  if (labelLayer) { map.removeLayer(labelLayer); labelLayer = null; }
  baseLayer = makeBaseLayer(name).addTo(map);
  baseLayer.bringToBack();
  labelLayer = makeLabelLayer(name);
  if (labelLayer) labelLayer.addTo(map);
  currentBasemap = name;
  // Only remember an explicit pick; the auto default should stay free to change.
  if (persist !== false) {
    try { localStorage.setItem(BM_KEY, name); } catch (e) { /* private mode */ }
  }
  document.querySelectorAll("#basemaps .bm").forEach(b => {
    const on = b.dataset.bm === name;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", on);
  });
  // Redraw so cell opacity matches the new base (darker map can be more
  // transparent; a light street map needs slightly stronger cells).
  if (MAP_READY && gridCells.length) scheduleGrid();
}

function wireBasemaps() {
  const btns = document.querySelectorAll("#basemaps .bm");
  btns.forEach(b => {
    b.onclick = () => { if (!b.disabled) setBasemap(b.dataset.bm); };
  });
  const sync = () => {
    const offline = typeof navigator !== "undefined" && navigator.onLine === false;
    btns.forEach(b => {
      const remote = b.dataset.bm !== "dark";
      b.disabled = offline && remote;
      b.title = b.disabled ? "Live map needs internet - Dark works offline" : "";
    });
  };
  sync();
  window.addEventListener("online", sync);
  window.addEventListener("offline", sync);
}

function initMap() {
  if (!window.L) throw new Error("Leaflet not loaded");
  map = L.map("map", { preferCanvas: true, zoomControl: true })
    .setView([28.61, 77.19], 11);
  // A dedicated pane keeps street/place labels above the basemap but below the
  // AQI grid (overlay pane), so cells stay readable over the labels.
  map.createPane("labels");
  map.getPane("labels").style.zIndex = 350;
  map.getPane("labels").style.pointerEvents = "none";
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  // Show a real, colorful street map online so the city looks alive. Fall back
  // to the vendored dark tiles (which need no network) when offline.
  let saved = offline ? "dark" : "streets";
  try { saved = localStorage.getItem(BM_KEY) || saved; } catch (e) { /* ignore */ }
  if (offline) saved = "dark";
  setBasemap(saved, false);
  wireBasemaps();
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
  const el = document.getElementById("legend");
  if (!el) return;
  const scale = ["leg_good", "leg_sat", "leg_mod", "leg_poor", "leg_vpoor", "leg_sev"];
  el.innerHTML = scale.map((key, i) =>
    `<div class="item"><span class="sw" style="background:${AQI_COLORS[i][1]}"></span>${t(key)}</div>`
  ).join("");
}

// AQI shown at the current forecast offset (0 = now).
function aqiAt(c) {
  if (FC_IDX > 0 && Array.isArray(c.aqi_forecast) && c.aqi_forecast[FC_IDX - 1] != null) {
    return c.aqi_forecast[FC_IDX - 1];
  }
  return c.aqi_now;
}

// Cell size derived once from the last grid (500 m ~ 0.0045 lat / 0.005 lon).
let _gridDeltas = null;
let _gridRaf = null;

function drawGrid(cells) {
  if (!MAP_READY) return;
  gridLayer.clearLayers();
  if (!cells.length) return;
  if (!_gridDeltas || _gridDeltas.n !== cells.length) {
    const lats = [...new Set(cells.map(c => c.lat))].sort((a, b) => a - b);
    const lons = [...new Set(cells.map(c => c.lon))].sort((a, b) => a - b);
    _gridDeltas = {
      n: cells.length,
      dLat: lats.length > 1 ? Math.abs(lats[1] - lats[0]) : 0.0045,
      dLon: lons.length > 1 ? Math.abs(lons[1] - lons[0]) : 0.005
    };
  }
  const { dLat, dLon } = _gridDeltas;
  for (const c of cells) {
    L.rectangle([
      [c.lat - dLat / 2, c.lon - dLon / 2],
      [c.lat + dLat / 2, c.lon + dLon / 2]
    ], {
      color: "transparent", weight: 0, fillColor: aqiColor(aqiAt(c)),
      fillOpacity: currentBasemap === "dark" ? 0.5 : 0.62,
      interactive: false
    }).addTo(gridLayer);
  }
}

// Coalesce rapid redraws (slider drag, style switch) into one per frame.
function scheduleGrid() {
  if (_gridRaf) return;
  _gridRaf = requestAnimationFrame(() => { _gridRaf = null; drawGrid(gridCells); });
}

async function loadGrid() {
  try {
    const cells = await fetchJSON("/grid");
    gridCells = Array.isArray(cells) ? cells : [];
    _gridDeltas = null;
    drawGrid(gridCells);
  } catch (e) {
    gridCells = [];
    setErr(document.getElementById("legend"), t("err_server"));
  }
}

// Forecast time slider: 0 = Now, n = +n hours.
function setForecast(idx) {
  FC_IDX = Math.max(0, Math.min(6, Number(idx) || 0));
  const label = document.getElementById("fc-label");
  if (label) label.textContent = FC_IDX === 0 ? t("now") : `+${FC_IDX}h`;
  const slider = document.getElementById("fc-slider");
  if (slider) slider.setAttribute("aria-valuetext", label ? label.textContent : "");
  scheduleGrid();
}

function togglePickMode(force) {
  PICK_MODE = force === undefined ? !PICK_MODE : !!force;
  if (PICK_MODE) {
    PICK_POINTS = [];
    if (pickLayer) pickLayer.clearLayers();   // drop any stale pins from last time
  }
  const btn = document.getElementById("btn-pick");
  if (btn) { btn.classList.toggle("active", PICK_MODE); btn.setAttribute("aria-pressed", PICK_MODE); }
  if (PICK_MODE) showPickHint(t("pick_start"));
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
    showPickHint(t("pick_end"));
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
  if (!navigator.geolocation) { setErr(el, t("geo_unsupported")); return; }
  // A new origin invalidates any route drawn for the previous start point.
  if (routeLayer) routeLayer.clearLayers();
  togglePickMode(false);
  show(`<span class="hint">${t("locating")}</span>`);
  navigator.geolocation.getCurrentPosition(async (pos) => {
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    const val = `${lat.toFixed(4)},${lon.toFixed(4)}`;
    document.getElementById("from").value = val;
    try {
      const nc = await fetchJSON(`/aqi?lat=${lat}&lon=${lon}`);
      if (nc.error) { setErr(el, nc.error); return; }
      if (MAP_READY && meLayer) {
        meLayer.clearLayers();
        L.circleMarker([lat, lon], {
          radius: 8, color: "#fff", weight: 2, fillColor: aqiColor(nc.aqi_now), fillOpacity: 1
        }).bindPopup(`<b>${t("your_location")}</b><br>AQI ${nc.aqi_now}<br>${nc.category || ""}`)
          .addTo(meLayer).openPopup();
        map.setView([lat, lon], 13);
      }
      show(`<b>${t("your_location")}</b> - AQI ${nc.aqi_now} (${nc.category || ""})<br>
        <span class="hint">${t("start_point_set")}</span>`);
    } catch (e) {
      setErr(el, t("err_server"));
    }
  }, (err) => {
    setErr(el, `${t("geo_unavailable")} (${err.message}).`);
  }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 });
}

async function loadStations() {
  try {
    const stations = await fetchJSON("/stations");
    if (!MAP_READY || !Array.isArray(stations)) return;
    stationLayer.clearLayers();
    for (const s of stations) {
      L.circleMarker([s.lat, s.lon], {
        radius: 6, color: "#fff", weight: 1.5, fillColor: aqiColor(s.aqi), fillOpacity: 1
      }).bindPopup(`<b>${s.station_id}</b><br>AQI ${s.aqi}<br>PM2.5 ${s.pm25}`).addTo(stationLayer);
    }
  } catch (e) { /* stations are decorative; ignore */ }
}

async function loadSchools() {
  const sel = document.getElementById("school-select");
  try {
    schools = await fetchJSON("/schools");
  } catch (e) {
    sel.innerHTML = `<option>${t("err_server")}</option>`;
    return;
  }
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
  let card;
  try {
    card = await fetchJSON(`/school/${id}/today`);
  } catch (e) {
    setErr(el, t("err_server"));
    return;
  }
  if (card.error || card.aqi_now === undefined) {
    el.innerHTML = `<div class="err">Could not load school: ${card.error || "unknown"}</div>`;
    return;
  }
  const c = aqiColor(card.aqi_now);
  const chips = (list, cls) => list.map(a => `<span class="chip ${cls}">${a.replace(/_/g, " ")}</span>`).join("");
  const reason = (card.decisions && card.decisions.hold_outdoor_assembly)
    ? card.decisions.hold_outdoor_assembly.reason : "";
  const none = (cls) => `<span class="chip ${cls}">-</span>`;
  el.innerHTML = `
    <div><span class="aqi-big" style="color:${readable(c)}">${card.aqi_now}</span>
      <span class="badge" style="background:${c};color:${textOn(c)}">${card.status}</span></div>
    <div style="font-weight:600;margin:6px 0">${card.headline}</div>
    <div style="color:var(--muted);font-size:11px">${t("school_peak")}: ${card.aqi_peak} · clean-index ${card.clean_index}</div>
    <div style="font-size:11px;margin-top:8px;color:var(--muted)">${t("school_allowed")}</div>
    <div class="chips">${chips(card.allowed, "ok") || none("no")}</div>
    <div style="font-size:11px;margin-top:8px;color:var(--muted)">${t("school_blocked")}</div>
    <div class="chips">${chips(card.blocked, "no") || none("ok")}</div>
    <div style="font-size:11px;color:var(--muted);margin-top:8px">${reason}</div>
    <div class="indoor">
      <h3>${tf("indoor_title", { aqi: card.indoor_aqi_estimate })}</h3>
      <ul>${(card.indoor_advisory || []).map(x => `<li>${x}</li>`).join("")}</ul>
    </div>`;
}

function windArrow(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const d = ((Number(deg) || 0) % 360 + 360) % 360;
  return dirs[Math.round(d / 45) % 8];
}

async function loadEvents() {
  const el = document.getElementById("event-banner");
  let events;
  try {
    events = await fetchJSON("/events");
  } catch (e) {
    el.style.display = "none";
    return;
  }
  if (!Array.isArray(events) || !events.length) { el.style.display = "none"; return; }
  el.style.display = "block";
  el.innerHTML = events.map(e => {
    const from = windArrow(e.wind_dir_deg || 0);
    const to = windArrow((e.wind_dir_deg || 0) + 180);
    return `<b>${t("stubble")}</b><br>${e.label}<br>
      <span class="wind">${tf("wind", { from, to })}</span>`;
  }).join("<hr>");
}

async function loadAlerts() {
  const el = document.getElementById("alerts");
  let alerts;
  try {
    alerts = await fetchJSON("/alerts");
  } catch (e) {
    el.textContent = t("err_server");
    return;
  }
  if (!Array.isArray(alerts)) { el.textContent = t("no_alerts"); return; }
  el.innerHTML = alerts.length
    ? alerts.map(a => `<div class="alert"><b>${a.kind}</b><br>${a.message}</div>`).join("")
    : t("no_alerts");
}

function drawRoute(res) {
  if (MAP_READY) {
    routeLayer.clearLayers();
    const style = (mode, color) => ({
      color, weight: 5, opacity: 0.9,
      dashArray: mode === "fastest" ? "8 6" : null
    });
    L.polyline(res.fastest.geometry, style("fastest", "#4aa8ff")).addTo(routeLayer)
      .bindTooltip(t("fastest"));
    L.polyline(res.cleanest.geometry, style("cleanest", "#35d29e")).addTo(routeLayer)
      .bindTooltip(t("cleanest"));
  }
  const f = res.fastest, c = res.cleanest;
  const row = (m, r) => `<tr><td>${m}</td><td>${(r.distance_m / 1000).toFixed(1)} km</td>
      <td>AQI ${r.avg_aqi}</td><td>clean ${r.clean_index}</td><td>${r.duration_min} min</td></tr>`;
  const el = document.getElementById("route-result");
  el.style.display = "block";
  el.innerHTML = `<b>${t("route_title")}</b> - ${t("winner")}: <span class="win">${res.winner}</span><br>
    <table>${row(t("fastest"), f)}${row(t("cleanest"), c)}</table>
    <div style="margin-top:6px;color:var(--muted)">${res.note}</div>`;
}

async function compareRoutes() {
  const from = document.getElementById("from").value.trim();
  const to = document.getElementById("to").value.trim();
  const el = document.getElementById("route-result");
  el.style.display = "block";
  return withBusy(document.getElementById("btn-route"), null, async () => {
    let res;
    try {
      res = await fetchJSON(`/route?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
    } catch (e) {
      setErr(el, t("err_server"));
      return;
    }
    if (res.error || !res.fastest) { setErr(el, res.error || t("no_route")); return; }
    drawRoute(res);
  });
}

async function askAgent() {
  const question = document.getElementById("question").value;
  const engine = document.getElementById("engine") ? document.getElementById("engine").value : "auto";
  const out = document.getElementById("agent-out");
  out.textContent = t("thinking");
  await withBusy(document.getElementById("btn-ask"), null, async () => {
    let res;
    try {
      res = await fetchJSON("/agent", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, engine })
      }, 20000);
    } catch (e) {
      setErr(out, t("err_server"));
      return;
    }
    if (res.error) { setErr(out, res.error); return; }
    out.innerHTML = `<b>${res.answer}</b>\n\n` +
      (res.steps || []).map(s => "• " + s).join("\n") +
      `\n\n(${t("engine")}: ${res.engine})`;
    loadAlerts();
  });
}

async function runCycle() {
  const btn = document.getElementById("btn-cycle");
  await withBusy(btn, t("rl_running"), async () => {
    try {
      await fetchJSON("/cycle", { method: "POST" });
    } catch (e) {
      document.getElementById("alerts").innerHTML = `<span class="err">${t("err_server")}</span>`;
    }
  });
  await refreshAll();
}

async function submitSubscribe(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  const out = document.getElementById("sub-out");
  const btn = e.target.querySelector("button[type=submit], button");
  out.textContent = t("sub_running");
  await withBusy(btn, null, async () => {
    let res;
    try {
      res = await fetchJSON("/subscribe", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
      });
    } catch (err) {
      setErr(out, t("err_server"));
      return;
    }
    out.innerHTML = res.error
      ? `<span class="err">${res.error}</span>`
      : tf("sub_done", { name: res.name, kind: res.kind, threshold: res.threshold_aqi });
  });
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
