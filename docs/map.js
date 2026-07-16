/* Mapa interactivo de yacimientos de la cultura ibérica.
   Lee data/yacimientos.geojson (pre-generado por el pipeline de Python).
   Bilingüe es/ca con selector; lightbox para las imágenes. */

const TYPE_COLORS = {
  "poblado":       "#a0522d",
  "ciudad":        "#b5651d",
  "necrópolis":    "#6a4c93",
  "santuario":     "#1b7a5a",
  "cueva":         "#c9820a",
  "fortificación": "#8a1c2b",
  "yacimiento":    "#4a6fa5",
};
const typeColor = (t) => TYPE_COLORS[t] || TYPE_COLORS.yacimiento;

const TYPE_LABELS = {
  es: { "poblado": "poblado", "ciudad": "ciudad", "necrópolis": "necrópolis",
        "santuario": "santuario", "cueva": "cueva",
        "fortificación": "fortificación", "yacimiento": "yacimiento" },
  ca: { "poblado": "poblat", "ciudad": "ciutat", "necrópolis": "necròpolis",
        "santuario": "santuari", "cueva": "cova",
        "fortificación": "fortificació", "yacimiento": "jaciment" },
};

const I18N = {
  es: {
    title: "Yacimientos de la cultura ibérica",
    search: "Buscar yacimiento…",
    count: (n) => `${n} yacimientos`,
    wiki: "Wikipedia", oficial: "Web oficial",
    source: "Fuente de datos", noDesc: "Sin descripción disponible.",
    licenseNote: "Imágenes de Wikimedia Commons bajo sus respectivas licencias.",
  },
  ca: {
    title: "Jaciments de la cultura ibèrica",
    search: "Cerca jaciment…",
    count: (n) => `${n} jaciments`,
    wiki: "Viquipèdia", oficial: "Web oficial",
    source: "Font de dades", noDesc: "Sense descripció disponible.",
    licenseNote: "Imatges de Wikimedia Commons sota les seves llicències.",
  },
};

let lang = (navigator.language || "es").toLowerCase().startsWith("ca") ? "ca" : "es";
const t = () => I18N[lang];
const typeLabel = (tipo) => TYPE_LABELS[lang][tipo] || tipo;

// Accesores bilingües con respaldo al otro idioma.
const pick = (p, base) =>
  lang === "ca" ? (p[base + "_ca"] || p[base + "_es"]) : (p[base + "_es"] || p[base + "_ca"]);
const name = (p) => pick(p, "nombre") || "—";
const desc = (p) => pick(p, "descripcion") || "";
const wikiUrl = (p) => pick(p, "url_wikipedia");

const map = L.map("map", { zoomControl: true }).setView([39.6, -2.2], 6);
L.control.scale({ imperial: false }).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "&copy; OpenStreetMap",
}).addTo(map);

const cluster = L.markerClusterGroup({ maxClusterRadius: 45, spiderfyOnMaxZoom: true });
map.addLayer(cluster);

const activeTypes = new Set(Object.keys(TYPE_COLORS));
let allFeatures = [];
let markers = [];
let currentFeature = null;

function makeIcon(tipo) {
  return L.divIcon({
    className: "",
    html: `<div class="pin" style="background:${typeColor(tipo)}"></div>`,
    iconSize: [16, 16], iconAnchor: [8, 16],
  });
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function hoverHtml(p) {
  const img = p.imagen
    ? `<img src="${p.imagen}" alt="" loading="lazy" onerror="this.remove()">` : "";
  return `${img}<div class="hc-body">
      <div class="hc-name">${escapeHtml(name(p))}</div>
      <div class="hc-type">${escapeHtml(typeLabel(p.tipo))}</div>
    </div>`;
}

/* ---------- Lightbox ---------- */
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCap = document.getElementById("lb-cap");
function openLightbox(im) {
  lbImg.src = im.url || im.thumb;
  lbImg.alt = im.titulo || "";
  lbCap.innerHTML = `${escapeHtml(im.autor)} · ${escapeHtml(im.licencia)}` +
    (im.descripcion_pagina
      ? ` · <a href="${im.descripcion_pagina}" target="_blank" rel="noopener">Commons</a>` : "");
  lightbox.classList.remove("hidden");
}
function closeLightbox() { lightbox.classList.add("hidden"); lbImg.src = ""; }
lightbox.addEventListener("click", (e) => { if (e.target !== lbImg) closeLightbox(); });
document.querySelector(".lb-close").onclick = closeLightbox;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeLightbox(); });

/* ---------- Panel lateral ---------- */
const panel = document.getElementById("panel");
const panelContent = document.getElementById("panel-content");
document.getElementById("panel-close").onclick = () => {
  panel.classList.add("hidden"); currentFeature = null;
};

function panelHtml(p) {
  const links = [];
  if (p.url_oficial)
    links.push(`<a href="${p.url_oficial}" target="_blank" rel="noopener">${t().oficial}</a>`);
  const w = wikiUrl(p);
  if (w) links.push(`<a href="${w}" target="_blank" rel="noopener">${t().wiki}</a>`);

  let gallery = "";
  const imgs = p.imagenes || [];
  if (imgs.length) {
    const figs = imgs.map((im, i) => `
      <figure data-idx="${i}">
        <img src="${im.thumb || im.url}" alt="${escapeHtml(im.titulo)}" loading="lazy"
             onerror="this.closest('figure').remove()">
        <figcaption>${escapeHtml(im.autor)} · ${escapeHtml(im.licencia)}</figcaption>
      </figure>`).join("");
    gallery = `<div class="gallery">${figs}</div>`;
  }

  const d = desc(p);
  return `
    <h2>${escapeHtml(name(p))}</h2>
    <div class="p-type" style="color:${typeColor(p.tipo)}">${escapeHtml(typeLabel(p.tipo))}</div>
    ${p.epoca ? `<div class="p-epoca">${escapeHtml(p.epoca)}</div>` : ""}
    <p class="p-desc">${escapeHtml(d) || t().noDesc}</p>
    ${links.length ? `<div class="p-links">${links.join("")}</div>` : ""}
    ${gallery}
    <div class="p-source">${t().source}: ${escapeHtml(p.fuente || "—")}. ${t().licenseNote}</div>
  `;
}

function openPanel(feature) {
  currentFeature = feature;
  panelContent.innerHTML = panelHtml(feature.properties);
  // Enlazar clics de la galería al lightbox.
  panelContent.querySelectorAll(".gallery figure").forEach((fig) => {
    fig.querySelector("img").onclick = () =>
      openLightbox(feature.properties.imagenes[+fig.dataset.idx]);
  });
  panel.classList.remove("hidden");
}

/* ---------- Marcadores y filtros ---------- */
function buildMarkers() {
  markers = allFeatures.map((f) => {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.marker([lat, lon], { icon: makeIcon(f.properties.tipo) });
    m.bindTooltip(hoverHtml(f.properties),
      { direction: "top", offset: [0, -12], className: "hover-card", opacity: 1 });
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
    const okText = !q || name(p).toLowerCase().includes(q) ||
                   (p.nombre_es || "").toLowerCase().includes(q) ||
                   (p.nombre_ca || "").toLowerCase().includes(q);
    if (okType && okText) { cluster.addLayer(marker); shown++; }
  }
  document.getElementById("count").textContent = t().count(shown);
}

function buildFilters() {
  const box = document.getElementById("filters");
  box.innerHTML = "";
  const counts = {};
  allFeatures.forEach((f) => (counts[f.properties.tipo] = (counts[f.properties.tipo] || 0) + 1));
  Object.keys(TYPE_COLORS).forEach((tp) => {
    if (!counts[tp]) return;
    const chip = document.createElement("span");
    chip.className = "chip" + (activeTypes.has(tp) ? "" : " off");
    chip.style.borderColor = typeColor(tp);
    chip.innerHTML = `<span class="dot" style="background:${typeColor(tp)}"></span>${typeLabel(tp)} (${counts[tp]})`;
    chip.onclick = () => {
      if (activeTypes.has(tp)) { activeTypes.delete(tp); chip.classList.add("off"); }
      else { activeTypes.add(tp); chip.classList.remove("off"); }
      applyFilters();
    };
    box.appendChild(chip);
  });
}

/* ---------- Idioma ---------- */
function applyStaticText() {
  document.documentElement.lang = lang;
  document.getElementById("title").textContent = t().title;
  document.getElementById("search").placeholder = t().search;
  document.querySelectorAll("#lang button").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === lang));
}

function setLang(l) {
  if (l === lang) return;
  lang = l;
  applyStaticText();
  buildMarkers();
  buildFilters();
  applyFilters();
  if (currentFeature) openPanel(currentFeature);
}
document.querySelectorAll("#lang button").forEach((b) =>
  (b.onclick = () => setLang(b.dataset.lang)));

/* ---------- Carga ---------- */
applyStaticText();
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
    document.getElementById("count").textContent = "Error";
    console.error(err);
  });
