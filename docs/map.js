/* Mapa interactivo de la Iberia prerromana (Edad del Hierro).
   Marcador = forma por civilización; color = tipo de yacimiento.
   Bilingüe es/ca, filtro por siglos, lightbox con navegación. */

/* ---------- Civilizaciones (forma del marcador) ---------- */
const CIVS = [
  { civ: "iberos",         es: "Íberos",              ca: "Ibers",              shape: "circle" },
  { civ: "celtibero",      es: "Celtíbero",           ca: "Celtiber",           shape: "square" },
  { civ: "fenicio-punico", es: "Fenicio-púnico",      ca: "Fenici-púnic",       shape: "diamond" },
  { civ: "griego",         es: "Griego",              ca: "Grec",               shape: "triangle" },
  { civ: "tartesico",      es: "Tartésico",           ca: "Tartèssic",          shape: "star" },
  { civ: "vascones",       es: "Vascones",            ca: "Vascons",            shape: "pentagon" },
  { civ: "celtas",         es: "Celtas / atlánticos", ca: "Celtes / atlàntics", shape: "hexagon" },
];
const CIV_BY_ID = Object.fromEntries(CIVS.map((c) => [c.civ, c]));
const civLabel = (id) => (CIV_BY_ID[id] ? CIV_BY_ID[id][lang] : id);

const SHAPES = {
  circle:   '<circle cx="12" cy="12" r="9"/>',
  square:   '<rect x="4" y="4" width="16" height="16" rx="2"/>',
  triangle: '<polygon points="12,3 21,20 3,20"/>',
  diamond:  '<polygon points="12,2 22,12 12,22 2,12"/>',
  star:     '<polygon points="12,2 14.6,9.2 22,9.2 16,13.8 18.2,21 12,16.6 5.8,21 8,13.8 2,9.2 9.4,9.2"/>',
  pentagon: '<polygon points="12,2.5 21,9.5 17.6,20.5 6.4,20.5 3,9.5"/>',
  hexagon:  '<polygon points="12,2.5 20.5,7.25 20.5,16.75 12,21.5 3.5,16.75 3.5,7.25"/>',
};
function shapeSvg(shape, fill, size) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24">
    <g fill="${fill}" stroke="#fff" stroke-width="1.6" stroke-linejoin="round">${SHAPES[shape]}</g></svg>`;
}

/* ---------- Tipos (color) ---------- */
const TYPE_COLORS = {
  "poblado": "#a0522d", "ciudad": "#b5651d", "necrópolis": "#6a4c93",
  "santuario": "#1b7a5a", "cueva": "#c9820a", "fortificación": "#8a1c2b",
  "yacimiento": "#4a6fa5",
};
const typeColor = (t) => TYPE_COLORS[t] || TYPE_COLORS.yacimiento;
const TYPE_LABELS = {
  es: { "poblado": "poblado", "ciudad": "ciudad", "necrópolis": "necrópolis",
        "santuario": "santuario", "cueva": "cueva", "fortificación": "fortificación",
        "yacimiento": "yacimiento" },
  ca: { "poblado": "poblat", "ciudad": "ciutat", "necrópolis": "necròpolis",
        "santuario": "santuari", "cueva": "cova", "fortificación": "fortificació",
        "yacimiento": "jaciment" },
};
const typeLabel = (t) => TYPE_LABELS[lang][t] || t;

/* ---------- i18n ---------- */
const I18N = {
  es: {
    title: "Yacimientos de la Iberia prerromana", search: "Buscar yacimiento…",
    count: (n) => `${n} yacimientos`, wiki: "Wikipedia", oficial: "Web oficial",
    source: "Fuente de datos", noDesc: "Sin descripción disponible.",
    civ: "Civilización", tipo: "Tipo de yacimiento", epoca: "Época",
    undated: "incluir sin datar", collapse: "Ocultar filtros", expand: "Mostrar filtros",
    licenseNote: "Imágenes de Wikimedia Commons bajo sus respectivas licencias.",
  },
  ca: {
    title: "Jaciments de la Ibèria preromana", search: "Cerca jaciment…",
    count: (n) => `${n} jaciments`, wiki: "Viquipèdia", oficial: "Web oficial",
    source: "Font de dades", noDesc: "Sense descripció disponible.",
    civ: "Civilització", tipo: "Tipus de jaciment", epoca: "Època",
    undated: "incloure sense datar", collapse: "Amaga filtres", expand: "Mostra filtres",
    licenseNote: "Imatges de Wikimedia Commons sota les seves llicències.",
  },
};
let lang = (navigator.language || "es").toLowerCase().startsWith("ca") ? "ca" : "es";
const t = () => I18N[lang];

const pick = (p, base) =>
  lang === "ca" ? (p[base + "_ca"] || p[base + "_es"]) : (p[base + "_es"] || p[base + "_ca"]);
const name = (p) => pick(p, "nombre") || "—";
const desc = (p) => pick(p, "descripcion") || "";
const wikiUrl = (p) => pick(p, "url_wikipedia");

function centuryLabel(c) {
  if (c === null || c === undefined) return "";
  const r = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][Math.abs(c)] || Math.abs(c);
  return `s. ${r} ${c < 0 ? "a.C." : "d.C."}`;
}

/* ---------- Mapa ---------- */
const map = L.map("map", { zoomControl: true }).setView([39.8, -3.5], 6);
L.control.scale({ imperial: false }).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "&copy; OpenStreetMap",
}).addTo(map);
const cluster = L.markerClusterGroup({ maxClusterRadius: 45, spiderfyOnMaxZoom: true });
map.addLayer(cluster);

const activeCivs = new Set(CIVS.map((c) => c.civ));
const activeTypes = new Set(Object.keys(TYPE_COLORS));
let epMin = -9, epMax = 1, includeUndated = true;
let allFeatures = [];
let markers = [];
let currentFeature = null;

function makeIcon(p) {
  const civ = CIV_BY_ID[p.civ] || CIV_BY_ID.iberos;
  return L.divIcon({
    className: "civ-marker",
    html: shapeSvg(civ.shape, typeColor(p.tipo), 22),
    iconSize: [22, 22], iconAnchor: [11, 11],
  });
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function hoverHtml(p) {
  const img = p.imagen ? `<img src="${p.imagen}" alt="" loading="lazy" onerror="this.remove()">` : "";
  const meta = [civLabel(p.civ), typeLabel(p.tipo)].join(" · ");
  return `${img}<div class="hc-body">
      <div class="hc-name">${escapeHtml(name(p))}</div>
      <div class="hc-type">${escapeHtml(meta)}${p.epoca ? " · " + escapeHtml(p.epoca) : ""}</div>
    </div>`;
}

/* ---------- Lightbox ---------- */
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCap = document.getElementById("lb-cap");
const lbPrev = document.querySelector(".lb-prev");
const lbNext = document.querySelector(".lb-next");
let lbImages = [], lbIdx = 0;
function renderLb() {
  const im = lbImages[lbIdx];
  if (!im) return;
  lbImg.src = im.url || im.thumb;
  lbImg.alt = im.titulo || "";
  const counter = lbImages.length > 1 ? `${lbIdx + 1}/${lbImages.length} · ` : "";
  lbCap.innerHTML = counter + `${escapeHtml(im.autor)} · ${escapeHtml(im.licencia)}` +
    (im.descripcion_pagina ? ` · <a href="${im.descripcion_pagina}" target="_blank" rel="noopener">Commons</a>` : "");
  lbPrev.classList.toggle("hidden", lbImages.length < 2);
  lbNext.classList.toggle("hidden", lbImages.length < 2);
}
function openLightbox(images, idx) { lbImages = images || []; lbIdx = idx || 0; renderLb(); lightbox.classList.remove("hidden"); }
function closeLightbox() { lightbox.classList.add("hidden"); lbImg.src = ""; }
function navLb(d) { if (lbImages.length) { lbIdx = (lbIdx + d + lbImages.length) % lbImages.length; renderLb(); } }
lbPrev.onclick = (e) => { e.stopPropagation(); navLb(-1); };
lbNext.onclick = (e) => { e.stopPropagation(); navLb(1); };
lightbox.addEventListener("click", (e) => { if (e.target === lightbox) closeLightbox(); });
document.querySelector(".lb-close").onclick = closeLightbox;
document.addEventListener("keydown", (e) => {
  if (lightbox.classList.contains("hidden")) return;
  if (e.key === "Escape") closeLightbox();
  else if (e.key === "ArrowLeft") navLb(-1);
  else if (e.key === "ArrowRight") navLb(1);
});

/* ---------- Panel ---------- */
const panel = document.getElementById("panel");
const panelContent = document.getElementById("panel-content");
document.getElementById("panel-close").onclick = () => { panel.classList.add("hidden"); currentFeature = null; };

function panelHtml(p) {
  const links = [];
  if (p.url_oficial) links.push(`<a href="${p.url_oficial}" target="_blank" rel="noopener">${t().oficial}</a>`);
  const w = wikiUrl(p);
  if (w) links.push(`<a href="${w}" target="_blank" rel="noopener">${t().wiki}</a>`);
  let gallery = "";
  const imgs = p.imagenes || [];
  if (imgs.length) {
    gallery = `<div class="gallery">${imgs.map((im, i) => `
      <figure data-idx="${i}">
        <img src="${im.thumb || im.url}" alt="${escapeHtml(im.titulo)}" loading="lazy"
             onerror="this.closest('figure').remove()">
        <figcaption>${escapeHtml(im.autor)} · ${escapeHtml(im.licencia)}</figcaption>
      </figure>`).join("")}</div>`;
  }
  const civ = CIV_BY_ID[p.civ] || CIV_BY_ID.iberos;
  const badge = `<span class="civ-badge">${shapeSvg(civ.shape, "#5a4a36", 16)} ${escapeHtml(civLabel(p.civ))}</span>`;
  return `
    <h2>${escapeHtml(name(p))}</h2>
    <div class="p-meta">${badge}
      <span class="p-type" style="color:${typeColor(p.tipo)}">${escapeHtml(typeLabel(p.tipo))}</span></div>
    ${p.epoca ? `<div class="p-epoca">${escapeHtml(p.epoca)}</div>` : ""}
    <p class="p-desc">${escapeHtml(desc(p)) || t().noDesc}</p>
    ${links.length ? `<div class="p-links">${links.join("")}</div>` : ""}
    ${gallery}
    <div class="p-source">${t().source}: ${escapeHtml(p.fuente || "—")}. ${t().licenseNote}</div>`;
}
function openPanel(feature) {
  currentFeature = feature;
  panelContent.innerHTML = panelHtml(feature.properties);
  panelContent.querySelectorAll(".gallery figure").forEach((fig) => {
    fig.querySelector("img").onclick = () => openLightbox(feature.properties.imagenes, +fig.dataset.idx);
  });
  panel.classList.remove("hidden");
}

/* ---------- Marcadores y filtros ---------- */
function buildMarkers() {
  markers = allFeatures.map((f) => {
    const [lon, lat] = f.geometry.coordinates;
    const m = L.marker([lat, lon], { icon: makeIcon(f.properties) });
    m.bindTooltip(hoverHtml(f.properties), { direction: "top", offset: [0, -12], className: "hover-card", opacity: 1 });
    m.on("click", () => openPanel(f));
    return { marker: m, feature: f };
  });
}

function inEpoch(p) {
  if (p.siglo_inicio === null || p.siglo_inicio === undefined) return includeUndated;
  return p.siglo_inicio <= epMax && p.siglo_fin >= epMin;
}
function applyFilters() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  cluster.clearLayers();
  let shown = 0;
  for (const { marker, feature } of markers) {
    const p = feature.properties;
    const ok = activeCivs.has(p.civ) && activeTypes.has(p.tipo) && inEpoch(p) &&
      (!q || name(p).toLowerCase().includes(q) ||
       (p.nombre_es || "").toLowerCase().includes(q) || (p.nombre_ca || "").toLowerCase().includes(q));
    if (ok) { cluster.addLayer(marker); shown++; }
  }
  document.getElementById("count").textContent = t().count(shown);
}

function buildFilters() {
  const counts = (key) => {
    const c = {}; allFeatures.forEach((f) => (c[f.properties[key]] = (c[f.properties[key]] || 0) + 1)); return c;
  };
  // Civilizaciones (forma).
  const cc = counts("civ"), civBox = document.getElementById("filters-civ");
  civBox.innerHTML = "";
  CIVS.forEach((c) => {
    if (!cc[c.civ]) return;
    const chip = document.createElement("span");
    chip.className = "chip" + (activeCivs.has(c.civ) ? "" : " off");
    chip.innerHTML = `${shapeSvg(c.shape, "#5a4a36", 15)} ${civLabel(c.civ)} (${cc[c.civ]})`;
    chip.onclick = () => { toggle(activeCivs, c.civ, chip); };
    civBox.appendChild(chip);
  });
  // Tipos (color).
  const tc = counts("tipo"), tipoBox = document.getElementById("filters-tipo");
  tipoBox.innerHTML = "";
  Object.keys(TYPE_COLORS).forEach((tp) => {
    if (!tc[tp]) return;
    const chip = document.createElement("span");
    chip.className = "chip" + (activeTypes.has(tp) ? "" : " off");
    chip.style.borderColor = typeColor(tp);
    chip.innerHTML = `<span class="dot" style="background:${typeColor(tp)}"></span>${typeLabel(tp)} (${tc[tp]})`;
    chip.onclick = () => { toggle(activeTypes, tp, chip); };
    tipoBox.appendChild(chip);
  });
}
function toggle(set, key, chip) {
  if (set.has(key)) { set.delete(key); chip.classList.add("off"); }
  else { set.add(key); chip.classList.remove("off"); }
  applyFilters();
}

/* ---------- Deslizador de siglos ---------- */
const epMinI = document.getElementById("epoca-min");
const epMaxI = document.getElementById("epoca-max");
function updateEpoch() {
  epMin = +epMinI.value; epMax = +epMaxI.value;
  if (epMin > epMax) { [epMin, epMax] = [epMax, epMin]; }
  document.getElementById("epoca-range").textContent = `${centuryLabel(epMin)} — ${centuryLabel(epMax)}`;
  applyFilters();
}
epMinI.addEventListener("input", updateEpoch);
epMaxI.addEventListener("input", updateEpoch);
document.getElementById("epoca-undated").addEventListener("change", (e) => {
  includeUndated = e.target.checked; applyFilters();
});

/* ---------- Idioma / colapsar ---------- */
function applyStaticText() {
  document.documentElement.lang = lang;
  document.getElementById("title").textContent = t().title;
  document.getElementById("search").placeholder = t().search;
  document.getElementById("lbl-civ").textContent = t().civ;
  document.getElementById("lbl-tipo").textContent = t().tipo;
  document.getElementById("lbl-epoca").textContent = t().epoca;
  document.getElementById("lbl-undated").textContent = t().undated;
  document.querySelectorAll("#lang button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
  updateToggleLabel();
}
function updateToggleLabel() {
  const open = document.getElementById("controls-body").classList.contains("hidden") === false;
  document.getElementById("controls-toggle").textContent = open ? t().collapse : t().expand;
}
document.getElementById("controls-toggle").onclick = () => {
  document.getElementById("controls-body").classList.toggle("hidden");
  updateToggleLabel();
};
function setLang(l) {
  if (l === lang) return;
  lang = l; applyStaticText(); buildMarkers(); buildFilters();
  document.getElementById("epoca-range").textContent = `${centuryLabel(epMin)} — ${centuryLabel(epMax)}`;
  applyFilters();
  if (currentFeature) openPanel(currentFeature);
}
document.querySelectorAll("#lang button").forEach((b) => (b.onclick = () => setLang(b.dataset.lang)));

/* ---------- Carga ---------- */
applyStaticText();
updateEpoch();
fetch("data/yacimientos.geojson")
  .then((r) => r.json())
  .then((geo) => {
    allFeatures = geo.features;
    buildMarkers(); buildFilters(); applyFilters();
    document.getElementById("search").addEventListener("input", applyFilters);
  })
  .catch((err) => { document.getElementById("count").textContent = "Error"; console.error(err); });
