/**
 * dashboard.js
 * ============
 * Connects to the SSE stream (/stream) and updates the dashboard in real time.
 * Falls back to polling /api/latest every 5 seconds if SSE is not supported.
 *
 * Also loads /api/history on startup to populate the trend charts.
 *
 * Dependencies: icons.js (must be loaded before this script).
 */

"use strict";

// ── Helpers ───────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

function riskClass(level) {
  const map = {
    NORMAL: "risk-normal",
    LOW:    "risk-low",
    WATCH:  "risk-watch",
    HIGH:   "risk-high",
  };
  return map[level] || "";
}

function bannerClass(level) {
  const map = {
    NORMAL: "banner--normal",
    LOW:    "banner--normal",
    WATCH:  "banner--watch",
    HIGH:   "banner--high",
  };
  return map[level] || "";
}

function chipClass(level) {
  const map = {
    NORMAL: "chip--normal",
    LOW:    "chip--normal",
    WATCH:  "chip--watch",
    HIGH:   "chip--high",
  };
  return map[level] || "";
}

function formatTs(epoch) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleTimeString();
}

function fmt1(v) { return (v !== undefined && v !== null) ? Number(v).toFixed(1) : "—"; }
function fmt0(v) { return (v !== undefined && v !== null) ? Math.round(v) : "—"; }

// ── Icon Injection ────────────────────────────────────────────────────────────

function injectIcons() {
  // Header logo
  ICONS.inject($("header-logo-icon"), "waveform");

  // Last update clock
  ICONS.inject($("last-update-icon"), "clock");

  // Metric icons
  ICONS.inject($("icon-hr"),    "heart");
  ICONS.inject($("icon-spo2"),  "lungs");
  ICONS.inject($("icon-btemp"), "thermometer");
  ICONS.inject($("icon-bp"),    "waveform");
  ICONS.inject($("icon-rtemp"), "thermometer");
  ICONS.inject($("icon-hum"),   "droplet");

  // Card title icons
  ICONS.inject($("icon-env-title"),    "signal");
  ICONS.inject($("icon-risk-title"),   "warning");
  ICONS.inject($("icon-stats-title"),  "chip");
  ICONS.inject($("icon-rec-title"),    "shield");
  ICONS.inject($("icon-trends-title"), "waveform");

  // Risk chip icons
  ICONS.inject($("icon-chip-heat"),  "flame");
  ICONS.inject($("icon-chip-vital"), "heart");
  ICONS.inject($("icon-chip-resp"),  "lungs");

  // Stat row icons
  ICONS.inject($("icon-stat-total"),    "signal");
  ICONS.inject($("icon-stat-rejected"), "warning");
  ICONS.inject($("icon-stat-device"),   "chip");

  // Recommendation icon
  ICONS.inject($("rec-icon"), "shield");

  // Banner icon (default)
  ICONS.inject($("banner-icon"), "shield");

  // Toast close button
  ICONS.inject($("toast-close-icon"), "close");
}

// ── Chart setup (lightweight canvas sparklines) ───────────────────────────────

const CHART_LEN      = 30;   // Main trend chart data points
const MINI_CHART_LEN = 20;   // Mini sparkline inside metric card

const charts = {};

function initChart(canvasId, color, isMini = false) {
  const canvas = $(canvasId);
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  const len = isMini ? MINI_CHART_LEN : CHART_LEN;
  const state = { data: [], color, canvas, ctx, isMini, len };

  canvas.width  = canvas.parentElement.clientWidth - (isMini ? 0 : 32);
  canvas.height = isMini ? 40 : 120;

  charts[canvasId] = state;
  return state;
}

function pushChart(canvasId, value) {
  const state = charts[canvasId];
  if (!state || value === undefined || value === null) return;
  const v = Number(value);
  if (isNaN(v)) return;
  state.data.push(v);
  if (state.data.length > state.len) state.data.shift();
  drawChart(state);

  // Update live value badge on trend charts
  const liveId = canvasId.replace("chart-", "live-").replace("chart-mini-", "live-");
  const liveEl = $(liveId);
  if (liveEl) {
    liveEl.classList.add("has-data");
  }
}

function drawChart(state) {
  const { data, color, canvas, ctx, isMini } = state;
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  if (data.length < 2) return;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = isMini ? 4 : 12;
  const len = state.len;

  const toX = i => (i / (len - 1)) * W;
  const toY = v => H - ((v - min) / range) * (H - pad * 2) - pad;

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, color + "44");
  grad.addColorStop(1, color + "00");

  // Draw filled area
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(data[0]));
  for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
  ctx.lineTo(toX(data.length - 1), H);
  ctx.lineTo(toX(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw line
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(data[0]));
  for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
  ctx.strokeStyle = color;
  ctx.lineWidth = isMini ? 1.5 : 2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();

  // Dot at latest point
  const last = data[data.length - 1];
  const lx = toX(data.length - 1);
  const ly = toY(last);
  ctx.beginPath();
  ctx.arc(lx, ly, isMini ? 2.5 : 4, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();

  // For main charts: draw faint horizontal grid lines
  if (!isMini) {
    const steps = 3;
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    for (let s = 1; s < steps; s++) {
      const y = (H / steps) * s;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }

    // Value label for main chart
    ctx.fillStyle = color;
    ctx.font = `500 11px 'JetBrains Mono', monospace`;
    ctx.textAlign = "right";
    ctx.fillText(last.toFixed(1), W - 6, 16);
  }
}

// Handle window resize — redraw all charts
window.addEventListener("resize", () => {
  Object.values(charts).forEach(state => {
    state.canvas.width = state.canvas.parentElement.clientWidth - (state.isMini ? 0 : 32);
    drawChart(state);
  });
});

// ── Value flash animation ─────────────────────────────────────────────────────

function flashValue(el) {
  if (!el) return;
  el.classList.remove("flash-update");
  // Trigger reflow to restart animation
  void el.offsetWidth;
  el.classList.add("flash-update");
  setTimeout(() => el.classList.remove("flash-update"), 900);
}

// ── Dashboard update ──────────────────────────────────────────────────────────

let _prevOverall = null;
let _prevValues  = {};

function applyUpdate(data) {
  const latest = data.latest || {};
  const risk   = data.risk   || {};

  // ── Vitals
  setMetricValue("val-hr",    fmt0(latest.heart_rate),        "val-hr");
  setMetricValue("val-spo2",  fmt1(latest.spo2),              "val-spo2");
  setMetricValue("val-btemp", fmt1(latest.body_temperature),  "val-btemp");
  setMetricValue("val-rtemp", fmt1(latest.room_temperature),  "val-rtemp");
  setMetricValue("val-hum",   fmt1(latest.humidity),          "val-hum");
  setMetricValue("val-bp-sys", fmt0(latest.bp_sys),           "val-bp-sys");
  setMetricValue("val-bp-dia", fmt0(latest.bp_dia),           "val-bp-dia");

  // BP classification sub-label
  const bpSys = Number(latest.bp_sys || 0);
  const bpDia = Number(latest.bp_dia || 0);
  if (bpSys > 0) {
    const bpLabel = bpSys >= 140 || bpDia >= 90 ? "Stage 2 Hypertension"
                  : bpSys >= 130 || bpDia >= 80 ? "Elevated"
                  : bpSys < 90                   ? "Hypotension"
                  : "Normal";
    const subEl = $("sub-bp");
    if (subEl) subEl.textContent = `${bpLabel} · Sys / Dia`;
  }

  $("stat-device").textContent = latest.device_id || "—";

  // ── Baseline sub-labels
  if (window._baseline) {
    const bl = window._baseline;
    $("sub-hr").textContent    = `Baseline ${fmt0(bl.heart_rate)} bpm`;
    $("sub-spo2").textContent  = `Baseline ${fmt1(bl.spo2)} %`;
    $("sub-btemp").textContent = `Baseline ${fmt1(bl.body_temperature)} °C`;
  }

  // ── Last update timestamp
  const ts = latest.timestamp
    ? new Date(latest.timestamp).toLocaleTimeString()
    : new Date().toLocaleTimeString();
  $("last-update-text").textContent = `Updated ${ts}`;
  $("banner-ts").textContent = latest.timestamp
    ? new Date(latest.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "—";

  // ── Overall banner
  const overall = risk.overall_status || "NORMAL";
  const banner = $("overall-banner");
  banner.className = `card col-full risk-banner ${bannerClass(overall)}`;
  $("overall-status").textContent = overall;
  $("overall-status").className   = `risk-banner-value ${riskClass(overall)}`;
  $("banner-sub").textContent     = latest.device_id ? `Device: ${latest.device_id}` : "Live monitoring active";

  // Update banner icon to reflect status
  const bannerIconEl = $("banner-icon");
  const bannerIconKey = overall === "HIGH" ? "warning" : overall === "WATCH" ? "warning" : "shield";
  ICONS.inject(bannerIconEl, bannerIconKey);
  bannerIconEl.style.color = getComputedStyle(document.documentElement)
    .getPropertyValue(overall === "HIGH" ? "--risk-high" : overall === "WATCH" ? "--risk-watch" : "--risk-normal").trim();

  // ── Risk chips
  setChip("chip-heat",  "val-heat",  "icon-chip-heat",  "flame",  risk.heat_risk);
  setChip("chip-vital", "val-vital", "icon-chip-vital", "heart",  risk.vital_risk);
  setChip("chip-resp",  "val-resp",  "icon-chip-resp",  "lungs",  risk.respiratory_risk);

  // ── Recommendation
  $("recommendation").textContent = risk.recommendation || "No recommendation available.";
  const ul = $("reasons-list");
  ul.innerHTML = "";
  (risk.reasons || []).forEach(r => {
    const li = document.createElement("li");
    li.textContent = r;
    ul.appendChild(li);
  });

  // Update recommendation icon color
  const recIcon = $("rec-icon");
  recIcon.style.background = overall === "HIGH"
    ? "rgba(240,79,92,0.12)" : overall === "WATCH"
    ? "rgba(244,168,50,0.12)"
    : "rgba(79,142,247,0.15)";
  recIcon.style.color = overall === "HIGH"
    ? "var(--risk-high)" : overall === "WATCH"
    ? "var(--risk-watch)"
    : "var(--accent)";
  recIcon.style.borderColor = overall === "HIGH"
    ? "rgba(240,79,92,0.2)" : overall === "WATCH"
    ? "rgba(244,168,50,0.2)"
    : "rgba(79,142,247,0.2)";

  // ── Charts
  if (latest.heart_rate != null) {
    pushChart("chart-hr",      latest.heart_rate);
    pushChart("chart-mini-hr", latest.heart_rate);
    $("live-hr").textContent = `${fmt0(latest.heart_rate)} bpm`;
  }
  if (latest.spo2 != null) {
    pushChart("chart-spo2",      latest.spo2);
    pushChart("chart-mini-spo2", latest.spo2);
    $("live-spo2").textContent = `${fmt1(latest.spo2)} %`;
  }
  if (latest.body_temperature != null) {
    pushChart("chart-btemp",      latest.body_temperature);
    pushChart("chart-mini-btemp", latest.body_temperature);
    $("live-btemp").textContent = `${fmt1(latest.body_temperature)} °C`;
  }
  if (latest.bp_sys != null && latest.bp_sys > 0) {
    pushChart("chart-bp-sys",      latest.bp_sys);
    pushChart("chart-mini-bp-sys", latest.bp_sys);
    $("live-bp-sys").textContent = `${fmt0(latest.bp_sys)} mmHg`;
  }

  // ── Alert toast on status change
  if (overall !== _prevOverall && _prevOverall !== null) {
    showToast(overall, risk.recommendation || "");
  }
  _prevOverall = overall;
}

// Set metric value with flash if changed
function setMetricValue(elId, newVal, trackKey) {
  const el = $(elId);
  if (!el) return;
  if (newVal !== _prevValues[trackKey]) {
    el.textContent = newVal;
    flashValue(el);
    _prevValues[trackKey] = newVal;
  }
}

function setChip(chipId, valId, iconId, iconKey, level) {
  const valEl  = $(valId);
  const chipEl = $(chipId);
  if (!valEl || !chipEl) return;

  valEl.textContent  = level || "—";
  valEl.className    = `risk-chip-value ${riskClass(level)}`;

  // Chip border / background class
  chipEl.className = `risk-chip ${chipClass(level)}`;

  // Update icon color
  const iconEl = $(iconId);
  if (iconEl) {
    ICONS.inject(iconEl, iconKey);
  }
}

function applyStatus(data) {
  $("stat-total").textContent    = data.total_readings ?? "—";
  $("stat-rejected").textContent = data.total_rejected ?? "—";

  const dot = $("connection-dot");
  dot.className = data.has_data ? "dot dot--connected" : "dot dot--connecting";
}

// ── Toast ──────────────────────────────────────────────────────────────────────

let _toastTimer = null;

function showToast(level, message) {
  const toast    = $("alert-toast");
  const iconEl   = $("toast-icon");
  const titleEl  = $("toast-title");
  const msgEl    = $("toast-msg");

  const iconMap  = { NORMAL: "check", WATCH: "warning", HIGH: "warning" };
  const titleMap = { NORMAL: "Status Normal", WATCH: "Watch Alert", HIGH: "High Risk Alert" };

  ICONS.inject(iconEl, iconMap[level] || "shield");
  titleEl.textContent = titleMap[level] || level;
  msgEl.textContent   = message.slice(0, 160) + (message.length > 160 ? "…" : "");

  toast.className = `alert-toast show toast--${level.toLowerCase()}`;

  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(dismissToast, 9000);
}

function dismissToast() {
  $("alert-toast").className = "alert-toast";
}

// ── SSE / polling ──────────────────────────────────────────────────────────────

function startSSE() {
  const es = new EventSource("/stream");

  es.onopen = () => {
    console.log("SSE connected");
    $("connection-dot").className = "dot dot--connected";
  };

  es.onmessage = ev => {
    try {
      const data = JSON.parse(ev.data);
      if (data.event_type === "heartbeat") return;
      if (data.reading) applyUpdate(data);
      fetchStatus();
      fetchBaseline();
    } catch (e) { console.warn("SSE parse error", e); }
  };

  es.onerror = () => {
    console.warn("SSE error – falling back to polling");
    $("connection-dot").className = "dot dot--error";
    es.close();
    setTimeout(startPolling, 2000);
  };
}

function startPolling() {
  $("connection-dot").className = "dot dot--connecting";
  fetchLatest();
  setInterval(fetchLatest, 5000);
}

function fetchLatest() {
  fetch("/api/latest")
    .then(r => r.json())
    .then(data => {
      if (data.latest) applyUpdate(data);
      fetchStatus();
      fetchBaseline();
    })
    .catch(e => {
      console.warn("Fetch error", e);
      $("connection-dot").className = "dot dot--error";
    });
}

function fetchStatus() {
  fetch("/api/status")
    .then(r => r.json())
    .then(applyStatus)
    .catch(() => {});
}

function fetchBaseline() {
  fetch("/api/baseline")
    .then(r => r.json())
    .then(bl => { window._baseline = bl; })
    .catch(() => {});
}

function loadHistory() {
  fetch("/api/history")
    .then(r => r.json())
    .then(({ readings }) => {
      if (!readings || !readings.length) return;
      // Readings are newest-first; reverse for chronological display
      const sorted = [...readings].reverse();
      sorted.forEach(r => {
        if (r.heart_rate != null)       { pushChart("chart-hr",    r.heart_rate);       pushChart("chart-mini-hr",    r.heart_rate); }
        if (r.spo2 != null)             { pushChart("chart-spo2",  r.spo2);             pushChart("chart-mini-spo2",  r.spo2); }
        if (r.body_temperature != null) { pushChart("chart-btemp", r.body_temperature); pushChart("chart-mini-btemp", r.body_temperature); }
        if (r.bp_sys != null && r.bp_sys > 0) { pushChart("chart-bp-sys", r.bp_sys); pushChart("chart-mini-bp-sys", r.bp_sys); }
      });
    })
    .catch(() => {});
}

// ── Init ───────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // Inject all SVG icons
  injectIcons();

  // Wire toast close button
  $("toast-close").addEventListener("click", dismissToast);

  // Initialise trend charts
  initChart("chart-hr",    "#f04f5c");   // red
  initChart("chart-spo2",  "#4f8ef7");   // blue
  initChart("chart-btemp", "#f4a832");   // amber
  initChart("chart-bp-sys", "#a855f7");  // purple

  // Initialise mini sparklines (inside metric cards)
  initChart("chart-mini-hr",     "#f04f5c", true);
  initChart("chart-mini-spo2",   "#4f8ef7", true);
  initChart("chart-mini-btemp",  "#f4a832", true);
  initChart("chart-mini-bp-sys", "#a855f7", true);

  loadHistory();
  fetchStatus();
  fetchBaseline();

  if (typeof EventSource !== "undefined") {
    startSSE();
  } else {
    startPolling();
  }
});
