/**
 * dashboard.js
 * ============
 * Connects to the SSE stream (/stream) and updates the dashboard in real time.
 * Falls back to polling /api/latest every 5 seconds if SSE is not supported.
 *
 * Also loads /api/history on startup to populate the trend charts.
 *
 * Dependencies: none (vanilla JS, no frameworks).
 */

"use strict";

// ── Helpers ──────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

function riskClass(level) {
  const map = {
    NORMAL: "risk-normal", LOW: "risk-low",
    WATCH:  "risk-watch",
    HIGH:   "risk-high",
  };
  return map[level] || "";
}

function bannerClass(level) {
  const map = { NORMAL: "banner--normal", LOW: "banner--normal", WATCH: "banner--watch", HIGH: "banner--high" };
  return map[level] || "";
}

function chipBorderColor(level) {
  const map = {
    NORMAL: "rgba(34,197,94,0.3)", LOW: "rgba(34,197,94,0.3)",
    WATCH:  "rgba(245,158,11,0.4)",
    HIGH:   "rgba(239,68,68,0.5)",
  };
  return map[level] || "";
}

function formatTs(epoch) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleTimeString();
}

function fmt1(v) { return (v !== undefined && v !== null) ? Number(v).toFixed(1) : "—"; }
function fmt0(v) { return (v !== undefined && v !== null) ? Math.round(v) : "—"; }

// ── Chart setup (lightweight canvas sparklines) ───────────────────────────────

const CHART_LEN = 30;   // Keep last 30 data points
const charts = {};

function initChart(canvasId, color) {
  const canvas = $(canvasId);
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  const state = { data: [], color, canvas, ctx };

  // Set canvas size explicitly
  canvas.width  = canvas.parentElement.clientWidth - 32;
  canvas.height = 80;

  charts[canvasId] = state;
  return state;
}

function pushChart(canvasId, value) {
  const state = charts[canvasId];
  if (!state) return;
  state.data.push(value);
  if (state.data.length > CHART_LEN) state.data.shift();
  drawChart(state);
}

function drawChart(state) {
  const { data, color, canvas, ctx } = state;
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  if (data.length < 2) return;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const toX = i => (i / (CHART_LEN - 1)) * W;
  const toY = v => H - ((v - min) / range) * (H - 10) - 5;

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, color + "66");
  grad.addColorStop(1, color + "00");

  ctx.beginPath();
  ctx.moveTo(toX(0), toY(data[0]));
  for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
  ctx.lineTo(toX(data.length - 1), H);
  ctx.lineTo(toX(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(data[0]));
  for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.stroke();

  // Latest value label
  const last = data[data.length - 1];
  ctx.fillStyle = color;
  ctx.font = "bold 12px 'JetBrains Mono', monospace";
  ctx.textAlign = "right";
  ctx.fillText(last.toFixed(1), W - 4, 14);
}

// ── Dashboard update ──────────────────────────────────────────────────────────

let _prevOverall = null;

function applyUpdate(data) {
  const latest = data.latest || {};
  const risk   = data.risk   || {};

  // Vitals
  $("val-hr").textContent    = fmt0(latest.heart_rate);
  $("val-spo2").textContent  = fmt1(latest.spo2);
  $("val-btemp").textContent = fmt1(latest.body_temperature);
  $("val-rtemp").textContent = fmt1(latest.room_temperature);
  $("val-hum").textContent   = fmt1(latest.humidity);

  $("stat-device").textContent = latest.device_id || "—";

  // Baseline sub-labels (from /api/baseline – loaded separately)
  if (window._baseline) {
    const bl = window._baseline;
    $("sub-hr").textContent   = `Baseline ${fmt0(bl.heart_rate)} bpm`;
    $("sub-spo2").textContent = `Baseline ${fmt1(bl.spo2)} %`;
    $("sub-btemp").textContent = `Baseline ${fmt1(bl.body_temperature)} °C`;
  }

  // Last update
  $("last-update").textContent = "Updated " + (latest.timestamp
    ? new Date(latest.timestamp).toLocaleTimeString()
    : new Date().toLocaleTimeString());

  // Overall banner
  const overall = risk.overall_status || "NORMAL";
  const banner = $("overall-banner");
  banner.className = "card card--full risk-banner " + bannerClass(overall);
  $("overall-status").textContent = overall;
  $("overall-status").className = "risk-banner-value " + riskClass(overall);

  // Risk chips
  function setChip(chipId, valId, level) {
    const el = $(valId);
    if (!el) return;
    el.textContent = level || "—";
    el.className = "risk-chip-value " + riskClass(level);
    const chip = $(chipId);
    if (chip) chip.style.borderColor = chipBorderColor(level);
  }
  setChip("chip-heat",  "val-heat",  risk.heat_risk);
  setChip("chip-vital", "val-vital", risk.vital_risk);
  setChip("chip-resp",  "val-resp",  risk.respiratory_risk);

  // Recommendation
  $("recommendation").textContent = risk.recommendation || "No recommendation available.";

  // Reasons
  const ul = $("reasons-list");
  ul.innerHTML = "";
  (risk.reasons || []).forEach(r => {
    const li = document.createElement("li");
    li.textContent = r;
    ul.appendChild(li);
  });

  // Charts
  if (latest.heart_rate)       pushChart("chart-hr",    latest.heart_rate);
  if (latest.spo2)             pushChart("chart-spo2",  latest.spo2);
  if (latest.body_temperature) pushChart("chart-btemp", latest.body_temperature);

  // Alert toast
  if (overall !== _prevOverall && _prevOverall !== null) {
    showToast(overall, risk.recommendation || "");
  }
  _prevOverall = overall;
}

function applyStatus(data) {
  $("stat-total").textContent    = data.total_readings    ?? "—";
  $("stat-rejected").textContent = data.total_rejected    ?? "—";

  const dot = $("connection-dot");
  dot.className = data.has_data ? "dot dot--connected" : "dot dot--connecting";
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(level, message) {
  const toast = $("alert-toast");
  const icons = { NORMAL: "✅", WATCH: "⚠️", HIGH: "🚨" };
  toast.textContent = `${icons[level] || "ℹ️"} ${level}: ${message.slice(0, 120)}…`;
  toast.className = `alert-toast show toast--${level.toLowerCase()}`;
  setTimeout(() => { toast.className = "alert-toast hidden"; }, 8000);
}

// ── SSE / polling ─────────────────────────────────────────────────────────────

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
      // Refresh status
      fetchStatus();
      fetchBaseline();
    } catch (e) { console.warn("SSE parse error", e); }
  };

  es.onerror = () => {
    console.warn("SSE error – falling back to polling");
    es.close();
    startPolling();
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
    .catch(e => console.warn("Fetch error", e));
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
        if (r.heart_rate)       pushChart("chart-hr",    r.heart_rate);
        if (r.spo2)             pushChart("chart-spo2",  r.spo2);
        if (r.body_temperature) pushChart("chart-btemp", r.body_temperature);
      });
    })
    .catch(() => {});
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initChart("chart-hr",    "#3b82f6");   // blue
  initChart("chart-spo2",  "#22c55e");   // green
  initChart("chart-btemp", "#f59e0b");   // amber

  loadHistory();
  fetchStatus();
  fetchBaseline();

  if (typeof EventSource !== "undefined") {
    startSSE();
  } else {
    startPolling();
  }
});
