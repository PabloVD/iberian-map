/* Mapa interactivo de yacimientos de la cultura ibérica.
   Lee data/yacimientos.geojson (pre-generado por el pipeline de Python). */

const TYPE_COLORS = {
  poblado:    "#a0522d",
  necrópolis: "#6a4c93",
  santuario:  "#1b7a5a",
  cueva:      "#c9820a",
  yacimiento: "#4a6fa5",
};
const typeColor = (t) => TYPE_COLORS[t] || TYPE_COLORS.yacimiento;

const map = L.map("map", { zoomControl: true }).setView([39.6, -2.2], 6);
L.control.scale({ imperial: false }).addTo(map);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

const cluster = L.markerClusterGroup({
  maxClusterRadius: 45,
  spiderfyOnMaxZoom: true,
});
map.addLayer(cluster);

const activeTypes = new Set(Object.keys(TYPE_COLORS));
let allFeatures = [];
let markers = []; // { marker, feature }

function makeIcon(tipo) {
  return L.divIcon({
    className: "",
    html: `<div class="pin" style="background:${typeColor(tipo)}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 16],
  });
}

function hoverHtml(p) {
  const img = p.imagen
    ? `<img src="${p.imagen}" alt="" loading="lazy" onerror="this.remove()">`
    : "";
  return `${img}<div class="hc-body">
      <div class="hc-name">${escapeHtml(p.nombre)}</div>
      <div class="hc-type">${escapeHtml(p.tipo)}</div>
    </div>`;
}

function panelHtml(p) {
  const links = [];
  if (p.url_oficial)
    links.push(`<a href="${p.url_oficial}" target="_blank" rel="noopener">Web oficial</a>`);
  if (p.url_wikipedia)
    links.push(`<a href="${p.url_wikipedia}" target="_blank" rel="noopener">Wikipedia</a>`);

  let gallery = "";
  if (p.imagenes && p.imagenes.length) {
    const figs = p.imagenes.map((im) => `
      <figure>
        <a href="${im.descripcion_pagina || im.url}" target="_blank" rel="noopener">
          <img src="${im.thumb || im.url}" alt="${escapeHtml(im.titulo || "")}" loading="lazy" onerror="this.closest('figure').remove()">
        </a>
        <figcaption>${escapeHtml(im.autor || "")} · ${escapeHtml(im.licencia || "")}</figcaption>
      </figure>`).join("");
    gallery = `<div class="gallery">${figs}</div>`;
  } else if (p.imagen) {
    gallery = `<div class="gallery"><figure><img src="${p.imagen}" alt="" loading="lazy" onerror="this.closest('figure').remove()"></figure></div>`;
  }

  return `
    <h2>${escapeHtml(p.nombre)}</h2>
    <div class="p-type" style="color:${typeColor(p.tipo)}">${escapeHtml(p.tipo)}</div>
    ${p.epoca ? `<div class="p-epoca">${escapeHtml(p.epoca)}</div>` : ""}
    ${p.descripcion ? `<p class="p-desc">${escapeHtml(p.descripcion)}</p>` : ""}
    ${links.length ? `<div class="p-links">${links.join("")}</div>` : ""}
    ${gallery}
    <div class="p-source">Fuente de datos: ${escapeHtml(p.fuente || "—")}. Textos e imágenes bajo sus licencias en Wikipedia/Wikimedia Commons.</div>
  `;
}

const panel = document.getElementById("panel");
const panelContent = document.getElementById("panel-content");
document.getElementById("panel-close").onclick = () => panel.classList.add("hidden");

function openPanel(feature) {
  panelContent.innerHTML = panelHtml(feature.properties);
  panel.classList.remove("hidden");
}

function buildMarkers() {
  markers = allFeatures.map((f) => {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.marker([lat, lon], { icon: makeIcon(f.properties.tipo) });
    m.bindTooltip(hoverHtml(f.properties), {
      direction: "top",
      offset: [0, -12],
      className: "hover-card",
      opacity: 1,
    });
    m.on("click", () => openPanel(f));
    return { marker: m, feature: f };
  });
}

function applyFilters() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  cluster.clearLayers();
  let shown = 0;
  for (const { marker, feature } of markers) {
    const p = feature.properties;
    const okType = activeTypes.has(p.tipo);
    const okText = !q || p.nombre.toLowerCase().includes(q);
    if (okType && okText) { cluster.addLayer(marker); shown++; }
  }
  document.getElementById("count").textContent = `${shown} yacimientos`;
}

function buildFilters() {
  const box = document.getElementById("filters");
  const counts = {};
  allFeatures.forEach((f) => (counts[f.properties.tipo] = (counts[f.properties.tipo] || 0) + 1));
  Object.keys(TYPE_COLORS).forEach((t) => {
    if (!counts[t]) return;
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.borderColor = typeColor(t);
    chip.innerHTML = `<span class="dot" style="background:${typeColor(t)}"></span>${t} (${counts[t]})`;
    chip.onclick = () => {
      if (activeTypes.has(t)) { activeTypes.delete(t); chip.classList.add("off"); }
      else { activeTypes.add(t); chip.classList.remove("off"); }
      applyFilters();
    };
    box.appendChild(chip);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

fetch("data/yacimientos.geojson")
  .then((r) => r.json())
  .then((geo) => {
    allFeatures = geo.features;
    buildMarkers();
    buildFilters();
    applyFilters();
    document.getElementById("search").addEventListener("input", applyFilters);
  })
  .catch((err) => {
    document.getElementById("count").textContent = "Error cargando datos";
    console.error(err);
  });
