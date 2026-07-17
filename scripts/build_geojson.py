"""Fusiona todas las fuentes en un único GeoJSON (bilingüe) que consume la web.

Entradas:
  data/sources/wikidata.json         (yacimientos Wikipedia/Wikidata, bilingüe)
  data/sources/commons_images.json   (galerías por QID)
  scripts/curated_sites.csv          (añadidos manuales)
  scripts/exclude_qids.txt           (QIDs a descartar a mano, opcional)

Salida:
  docs/data/yacimientos.geojson      (FeatureCollection de puntos)

- Filtra falsos positivos por P31 (lista negra).
- Clasifica el tipo por P31 (con respaldo por palabras clave).
- Deduplica por nombre normalizado + cercanía de coordenadas.
"""
import csv
import json
import math
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WD = os.path.join(ROOT, "data", "sources", "wikidata.json")
IMGS = os.path.join(ROOT, "data", "sources", "commons_images.json")
CSV_FILE = os.path.join(HERE, "curated_sites.csv")
EXCLUDE_FILE = os.path.join(HERE, "exclude_qids.txt")
ANCHOR_FILE = os.path.join(HERE, "anchor_sites.txt")
OUT = os.path.join(ROOT, "docs", "data", "yacimientos.geojson")

DEDUP_METERS = 600
SAME_POINT_METERS = 50


def in_scope(lat, lon):
    """Península ibérica + íberos del sur de Francia + islas Baleares.
    (Se excluyen Canarias y el norte de África por latitud/longitud.)"""
    return 35.5 <= lat <= 44.0 and -9.8 <= lon <= 4.5

# --- Filtro de falsos positivos por P31 (Wikidata "instance of") ---
# Se descarta un yacimiento solo si TODOS sus P31 están en esta lista negra
# (así se conservan sitios reales tipados como "castillo", p. ej. Giribaile).
# Solo tipos INEQUÍVOCAMENTE no-arqueológicos. Se evitan a propósito montaña,
# colina, área protegida o "entidad singular de población", porque Wikidata suele
# tipar ahí el accidente geográfico y no la arqueología, y arrastraría sitios
# reales (Villaricos, Puig de la Nau, Tossal de la Cala, El Molón…). Lo dudoso se
# gestiona a mano en exclude_qids.txt.
BLOCKLIST_TYPES = {
    "Q16970", "Q317557", "Q56750657",             # iglesia / iglesia parroquial / ermita
    "Q33506",                                       # museo
    "Q2624046", "Q46831",                           # sierra / cordillera (rangos montañosos)
    "Q2074737", "Q123754112", "Q532",              # municipio(s) / pueblo
    "Q3257686", "Q11939023",                        # localidad / núcleo de población
}

# --- Clasificación de tipo por P31 (prioridad de arriba a abajo) ---
TYPE_BY_P31 = [
    ("necrópolis",    {"Q200141", "Q173387", "Q56055312"}),
    ("santuario",     {"Q29553"}),
    ("cueva",         {"Q35509", "Q11269813"}),
    ("poblado",       {"Q100268926", "Q192601", "Q486972", "Q22674925", "Q350895"}),
    ("ciudad",        {"Q15661340", "Q2202509", "Q213468", "Q918230", "Q756780",
                       "Q133442", "Q2974842", "Q515"}),
    ("fortificación", {"Q23413", "Q57346", "Q81917", "Q12518"}),
    ("yacimiento",    {"Q839954", "Q1291195", "Q48794661", "Q3363945", "Q21752084"}),
]

# Respaldo por palabras clave (multilingüe) cuando P31 no basta.
TYPE_KEYWORDS = [
    ("necrópolis",   ["necrópolis", "necropoli", "necrópoli", "necropolis"]),
    ("santuario",    ["santuario", "santuari", "templo", "temple"]),
    ("cueva",        ["cueva", "cova", "abrigo", "gruta"]),
    ("fortificación", ["castillo", "castell", "muralla", "torre", "fortaleza", "fortalesa"]),
    ("ciudad",       ["ciudad", "ciutat", "municipium", "colonia", "urbs"]),
    ("poblado",      ["poblado", "poblat", "oppidum", "castro", "asentamiento",
                      "asentament", "poblament"]),
]


def load_anchors():
    """Sitios que DEBEN estar en el mapa (QID o nombre), uno por línea."""
    items = []
    if os.path.exists(ANCHOR_FILE):
        for line in open(ANCHOR_FILE, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                items.append(line)
    return items


def check_anchors(features, merged):
    """Red de seguridad: avisa si un yacimiento importante ha desaparecido."""
    anchors = load_anchors()
    if not anchors:
        return []
    present_qids = {m["qid"] for m in merged if m.get("qid")}
    names_low = [((f["properties"]["nombre_es"] or "") + " " +
                  (f["properties"]["nombre_ca"] or "")).lower() for f in features]
    missing = []
    for a in anchors:
        if a[0] == "Q" and a[1:].isdigit():
            if a not in present_qids:
                missing.append(a)
        elif not any(a.lower() in n for n in names_low):
            missing.append(a)
    if missing:
        print(f"\n⚠️  ATENCIÓN: faltan {len(missing)} yacimientos ANCLA "
              f"(un cambio los ha tirado; revísalo):")
        for m in missing:
            print("   -", m)
    else:
        print(f"Anclas: {len(anchors)}/{len(anchors)} presentes ✓")
    return missing


def regression_diff(features):
    """Diff con el último GeoJSON en git: qué desaparece y qué se añade."""
    import subprocess
    try:
        raw = subprocess.run(["git", "show", "HEAD:docs/data/yacimientos.geojson"],
                             capture_output=True, text=True, cwd=ROOT).stdout
        prev = json.loads(raw)["features"]
    except Exception:  # noqa: BLE001
        return
    key = lambda f: f["properties"].get("nombre_es") or f["properties"].get("nombre_ca")
    prevn, newn = {key(f) for f in prev}, {key(f) for f in features}
    removed, added = sorted(prevn - newn), sorted(newn - prevn)
    print(f"\nRespecto al build anterior (git): +{len(added)} nuevos / "
          f"-{len(removed)} desaparecidos")
    for n in removed[:50]:
        print("   - (fuera)", n)


def load_exclude_qids():
    qids = set()
    if os.path.exists(EXCLUDE_FILE):
        with open(EXCLUDE_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    qids.add(line)
    return qids


def normalize(name):
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    stop = {"de", "del", "la", "el", "los", "las", "d", "poblado", "poblat",
            "iberico", "ibero", "ibera", "iber", "ciudad", "ciutat", "yacimiento",
            "jaciment", "arqueologico", "complejo", "necropolis"}
    toks = [t for t in name.split() if t and t not in stop]
    return " ".join(toks)


def haversine(a, b):
    (la1, lo1), (la2, lo2) = a, b
    r = 6371000
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = math.radians(la2 - la1)
    dl = math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def classify(site):
    """Tipo del yacimiento: primero por P31, luego por palabras clave."""
    p31 = set(site.get("p31") or [])
    for tipo, qids in TYPE_BY_P31:
        if p31 & qids:
            return tipo
    blob = " ".join(filter(None, [site.get("nombre"), site.get("nombre_ca"),
                                   site.get("descripcion_es"),
                                   site.get("descripcion_ca")])).lower()
    for tipo, kws in TYPE_KEYWORDS:
        if any(k in blob for k in kws):
            return tipo
    return "yacimiento"


def plausible_epoch(ini, fin):
    """Descarta siglos fuera de rango (errores de datos o siglos de excavación,
    p. ej. 's. XVIII' de cuando se descubrió). Edad del Hierro ibérica ≈ s. IX a.C.
    hasta la romanización; se admite continuidad hasta ~s. VII d.C."""
    if ini is None or fin is None:
        return None, None
    if ini < -9 or fin > 7 or fin < ini:
        return None, None
    return ini, fin


def is_false_positive(site, exclude):
    if site.get("qid") in exclude:
        return True
    p31 = site.get("p31") or []
    return bool(p31) and all(t in BLOCKLIST_TYPES for t in p31)


def load_curated():
    rows = []
    if not os.path.exists(CSV_FILE):
        return rows
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(l for l in f if not l.lstrip().startswith("#"))
        for r in reader:
            if not r.get("nombre") or not r.get("lat"):
                continue
            nombre = r["nombre"].strip()

            def _int(x):
                x = (x or "").strip()
                return int(x) if x.lstrip("-").isdigit() else None
            rows.append({
                "qid": None,
                "nombre": nombre,
                "nombre_es": nombre,
                "nombre_ca": None,
                "descripcion_es": (r.get("descripcion") or "").strip(),
                "descripcion_ca": "",
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "civ": (r.get("civ") or "iberos").strip() or "iberos",
                "tipo": (r.get("tipo") or "").strip() or None,
                "epoca": (r.get("epoca") or "").strip(),
                "siglo_inicio": _int(r.get("siglo_inicio")),
                "siglo_fin": _int(r.get("siglo_fin")),
                "url_wikipedia_es": (r.get("url_info") or "").strip() or None,
                "url_wikipedia_ca": None,
                "url_oficial": None,
                "imagen_principal": (r.get("url_imagen") or "").strip() or None,
                "commons_cat": None,
                "p31": [],
                "fuente": "curado",
            })
    return rows


def find_duplicate(site, existing):
    n = normalize(site["nombre"])
    for e in existing:
        d = haversine((site["lat"], site["lon"]), (e["lat"], e["lon"]))
        if d <= SAME_POINT_METERS:
            return e
        if d <= DEDUP_METERS:
            en = normalize(e["nombre"])
            if n and en and (n in en or en in n or n == en):
                return e
    return None


_INFO_FIELDS = ("imagen_principal", "commons_cat", "descripcion_es", "descripcion_ca",
                "qid", "url_wikipedia_es", "url_oficial", "epoca")


def _richness(rec):
    return sum(1 for f in _INFO_FIELDS if rec.get(f))


def merge_records(keep, drop):
    fuentes = set()
    for rec in (keep, drop):
        fuentes.update(p for p in rec.get("fuente", "").split("+") if p)
    for k, v in drop.items():
        if v and not keep.get(k):
            keep[k] = v
    keep["fuente"] = "+".join(sorted(fuentes))
    return keep


def main():
    wikidata = json.load(open(WD, encoding="utf-8"))
    galleries = json.load(open(IMGS, encoding="utf-8"))
    curated = load_curated()
    exclude = load_exclude_qids()

    # Filtrar falsos positivos y lo que quede fuera de la península ibérica.
    kept, dropped_fp, dropped_scope = [], 0, 0
    for s in wikidata:
        if is_false_positive(s, exclude):
            dropped_fp += 1
        elif not in_scope(s["lat"], s["lon"]):
            dropped_scope += 1
        else:
            kept.append(s)
    for w in kept:
        w.setdefault("epoca", "")

    # Deduplicado sobre toda la lista (Wikidata primero, luego CSV curado).
    combined = kept + list(curated)
    merged, fused = [], 0
    for site in combined:
        dup = find_duplicate(site, merged)
        if dup is None:
            merged.append(site)
            continue
        fused += 1
        if _richness(site) > _richness(dup):
            merge_records(site, dup)
            merged[merged.index(dup)] = site
        else:
            merge_records(dup, site)
    added = sum(1 for s in merged if s.get("fuente", "") == "curado")

    features = []
    for s in merged:
        imgs = galleries.get(s.get("qid"), []) if s.get("qid") else []
        # La imagen de hover = primera de la galería (coherente con el clic).
        imagen = (imgs[0]["thumb"] if imgs else None) or s.get("imagen_principal")
        tipo = s.get("tipo") or classify(s)
        ini, fin = plausible_epoch(s.get("siglo_inicio"), s.get("siglo_fin"))
        epoca = s.get("epoca", "") if ini is not None else ""
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(s["lon"], 6), round(s["lat"], 6)]},
            "properties": {
                "nombre_es": s.get("nombre_es") or s.get("nombre"),
                "nombre_ca": s.get("nombre_ca") or s.get("nombre_es") or s.get("nombre"),
                "civ": s.get("civ", "iberos"),
                "tipo": tipo,
                "epoca": epoca,
                "siglo_inicio": ini,
                "siglo_fin": fin,
                "descripcion_es": s.get("descripcion_es", ""),
                "descripcion_ca": s.get("descripcion_ca", ""),
                "imagen": imagen,
                "imagenes": imgs,
                "url_wikipedia_es": s.get("url_wikipedia_es"),
                "url_wikipedia_ca": s.get("url_wikipedia_ca"),
                "url_oficial": s.get("url_oficial"),
                "fuente": s.get("fuente", ""),
            },
        })

    features.sort(key=lambda f: f["properties"]["nombre_es"] or "")
    fc = {"type": "FeatureCollection",
          "metadata": {"count": len(features),
                       "descripcion": "Yacimientos de la cultura ibérica"},
          "features": features}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=1)

    con_img = sum(1 for f in features if f["properties"]["imagen"])
    con_link = sum(1 for f in features if f["properties"]["url_oficial"])
    con_ep = sum(1 for f in features if f["properties"]["siglo_inicio"] is not None)
    from collections import Counter
    tipos = Counter(f["properties"]["tipo"] for f in features)
    civs = Counter(f["properties"]["civ"] for f in features)
    print(f"GeoJSON con {len(features)} yacimientos "
          f"({dropped_fp} falsos positivos, {dropped_scope} fuera de la península, "
          f"{fused} duplicados fusionados, {added} del CSV, {con_img} con imagen, "
          f"{con_link} con enlace oficial, {con_ep} con época)")
    print("Civilizaciones:", dict(civs.most_common()))
    print("Tipos:", dict(tipos.most_common()))
    print("->", OUT)

    regression_diff(features)
    check_anchors(features, merged)


if __name__ == "__main__":
    main()
