/* Mapa interactivo de la Iberia prerromana (Edad del Hierro).
   Marcador: COLOR = civilización; ICONO (FontAwesome) = tipo de yacimiento.
   Bilingüe es/ca, filtro por siglos (rango doble), lightbox con navegación. */

/* Poner a true para reagrupar marcadores al alejar el zoom (clustering).
   No expuesto en la UI: es una preferencia solo de código. */
const ENABLE_CLUSTER = false;

/* ---------- Civilizaciones (COLOR del marcador) ---------- */
const CIVS = [
  { civ: "iberos",         es: "Íberos",              ca: "Ibers",              color: "#D55E00" },
  { civ: "celtibero",      es: "Celtíbero",           ca: "Celtiber",           color: "#0072B2" },
  { civ: "fenicio-punico", es: "Fenicio-púnico",      ca: "Fenici-púnic",       color: "#CC79A7" },
  { civ: "griego",         es: "Griego",              ca: "Grec",               color: "#009E73" },
  { civ: "tartesico",      es: "Tartésico",           ca: "Tartèssic",          color: "#E69F00" },
  { civ: "vascones",       es: "Vascones",            ca: "Vascons",            color: "#56B4E9" },
  { civ: "celtas",         es: "Celtas / atlánticos", ca: "Celtes / atlàntics", color: "#444444" },
];
const CIV_BY_ID = Object.fromEntries(CIVS.map((c) => [c.civ, c]));
const civLabel = (id) => (CIV_BY_ID[id] ? CIV_BY_ID[id][lang] : id);
const civColor = (id) => (CIV_BY_ID[id] ? CIV_BY_ID[id].color : "#444444");

/* ---------- Tipos (ICONO FontAwesome) ---------- */
const TYPE_ICONS = {
  "poblado": "fa-house", "ciudad": "fa-city", "necrópolis": "fa-monument",
  "santuario": "fa-place-of-worship", "cueva": "fa-mountain",
  "fortificación": "fa-chess-rook", "yacimiento": "fa-landmark",
};
const typeIcon = (t) => TYPE_ICONS[t] || "fa-location-dot";
const TYPE_ORDER = Object.keys(TYPE_ICONS);
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
const layer = ENABLE_CLUSTER
  ? L.markerClusterGroup({ maxClusterRadius: 45, spiderfyOnMaxZoom: true })
  : L.layerGroup();
map.addLayer(layer);

const activeCivs = new Set(CIVS.map((c) => c.civ));
const activeTypes = new Set(TYPE_ORDER);
let epMin = -9, epMax = 1, includeUndated = true;
let allFeatures = [];
let markers = [];
let currentFeature = null;

function makeIcon(p) {
  return L.divIcon({
    className: "civ-marker",
    html: `<div class="pin" style="background:${civColor(p.civ)}">
             <i class="fa-solid ${typeIcon(p.tipo)}"></i></div>`,
    iconSize: [26, 26], iconAnchor: [13, 13],
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
  const badge = `<span class="civ-badge"><span class="dot" style="background:${civColor(p.civ)}"></span>${escapeHtml(civLabel(p.civ))}</span>`;
  const tipo = `<span class="p-type"><i class="fa-solid ${typeIcon(p.tipo)}"></i> ${escapeHtml(typeLabel(p.tipo))}</span>`;
  return `
    <h2>${escapeHtml(name(p))}</h2>
    <div class="p-meta">${badge}${tipo}</div>
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
  layer.clearLayers();
  let shown = 0;
  for (const { marker, feature } of markers) {
    const p = feature.properties;
    const ok = activeCivs.has(p.civ) && activeTypes.has(p.tipo) && inEpoch(p) &&
      (!q || name(p).toLowerCase().includes(q) ||
       (p.nombre_es || "").toLowerCase().includes(q) || (p.nombre_ca || "").toLowerCase().includes(q));
    if (ok) { layer.addLayer(marker); shown++; }
  }
  document.getElementById("count").textContent = t().count(shown);
}

function buildFilters() {
  const count = (key) => {
    const c = {}; allFeatures.forEach((f) => (c[f.properties[key]] = (c[f.properties[key]] || 0) + 1)); return c;
  };
  const cc = count("civ"), civBox = document.getElementById("filters-civ");
  civBox.innerHTML = "";
  CIVS.forEach((c) => {
    if (!cc[c.civ]) return;
    const chip = document.createElement("span");
    chip.className = "chip" + (activeCivs.has(c.civ) ? "" : " off");
    chip.innerHTML = `<span class="dot" style="background:${c.color}"></span>${civLabel(c.civ)} (${cc[c.civ]})`;
    chip.onclick = () => toggle(activeCivs, c.civ, chip);
    civBox.appendChild(chip);
  });
  const tc = count("tipo"), tipoBox = document.getElementById("filters-tipo");
  tipoBox.innerHTML = "";
  TYPE_ORDER.forEach((tp) => {
    if (!tc[tp]) return;
    const chip = document.createElement("span");
    chip.className = "chip" + (activeTypes.has(tp) ? "" : " off");
    chip.innerHTML = `<i class="fa-solid ${typeIcon(tp)}"></i> ${typeLabel(tp)} (${tc[tp]})`;
    chip.onclick = () => toggle(activeTypes, tp, chip);
    tipoBox.appendChild(chip);
  });
}
function toggle(set, key, chip) {
  if (set.has(key)) { set.delete(key); chip.classList.add("off"); }
  else { set.add(key); chip.classList.remove("off"); }
  applyFilters();
}

/* ---------- Rango doble de siglos ---------- */
const epMinI = document.getElementById("epoca-min");
const epMaxI = document.getElementById("epoca-max");
const rangeFill = document.getElementById("range-fill");
const EP_LO = -9, EP_HI = 1;
function updateEpoch() {
  epMin = +epMinI.value; epMax = +epMaxI.value;
  if (epMin > epMax) { [epMin, epMax] = [epMax, epMin]; }
  const span = EP_HI - EP_LO;
  const l = ((epMin - EP_LO) / span) * 100, r = ((epMax - EP_LO) / span) * 100;
  rangeFill.style.left = l + "%";
  rangeFill.style.width = (r - l) + "%";
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
  const open = !document.getElementById("controls-body").classList.contains("hidden");
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
