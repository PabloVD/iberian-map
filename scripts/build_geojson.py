"""Fusiona todas las fuentes en un único GeoJSON que consume la web.

Entradas:
  data/sources/wikidata.json         (yacimientos Wikipedia/Wikidata)
  data/sources/commons_images.json   (galerías por QID)
  scripts/curated_sites.csv          (añadidos manuales)

Salida:
  data/yacimientos.geojson           (FeatureCollection de puntos)

Deduplica por nombre normalizado + cercanía de coordenadas.
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
# El GeoJSON final se sirve desde docs/ (lo que publica GitHub Pages).
OUT = os.path.join(ROOT, "docs", "data", "yacimientos.geojson")

DEDUP_METERS = 600  # dos puntos más cercanos que esto y con nombre afín = mismo sitio


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


def load_curated():
    rows = []
    if not os.path.exists(CSV_FILE):
        return rows
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(l for l in f if not l.lstrip().startswith("#"))
        for r in reader:
            if not r.get("nombre") or not r.get("lat"):
                continue
            rows.append({
                "qid": None,
                "nombre": r["nombre"].strip(),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "tipo": (r.get("tipo") or "yacimiento").strip() or "yacimiento",
                "epoca": (r.get("epoca") or "").strip(),
                "descripcion": (r.get("descripcion") or "").strip(),
                "url_wikipedia": (r.get("url_info") or "").strip() or None,
                "url_oficial": None,
                "imagen_principal": (r.get("url_imagen") or "").strip() or None,
                "commons_cat": None,
                "fuente": "curado",
            })
    return rows


def find_duplicate(site, existing):
    n = normalize(site["nombre"])
    for e in existing:
        d = haversine((site["lat"], site["lon"]), (e["lat"], e["lon"]))
        if d <= DEDUP_METERS:
            en = normalize(e["nombre"])
            if n and en and (n in en or en in n or n == en):
                return e
            if d <= 120:  # prácticamente el mismo punto
                return e
    return None


def main():
    wikidata = json.load(open(WD, encoding="utf-8"))
    galleries = json.load(open(IMGS, encoding="utf-8"))
    curated = load_curated()

    merged = list(wikidata)
    added = 0
    for c in curated:
        dup = find_duplicate(c, merged)
        if dup:
            # el CSV rellena huecos y puede aportar época.
            for k in ("epoca", "descripcion", "url_oficial", "imagen_principal"):
                if c.get(k) and not dup.get(k):
                    dup[k] = c[k]
            dup["fuente"] = dup.get("fuente", "") + "+curado"
        else:
            merged.append(c)
            added += 1

    features = []
    for s in merged:
        imgs = galleries.get(s.get("qid"), []) if s.get("qid") else []
        imagen = s.get("imagen_principal") or (imgs[0]["thumb"] if imgs else None)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(s["lon"], 6),
                                                           round(s["lat"], 6)]},
            "properties": {
                "nombre": s["nombre"],
                "tipo": s.get("tipo", "yacimiento"),
                "epoca": s.get("epoca", ""),
                "descripcion": s.get("descripcion", ""),
                "imagen": imagen,
                "imagenes": imgs,
                "url_wikipedia": s.get("url_wikipedia"),
                "url_oficial": s.get("url_oficial"),
                "fuente": s.get("fuente", ""),
            },
        })

    features.sort(key=lambda f: f["properties"]["nombre"])
    fc = {"type": "FeatureCollection",
          "metadata": {"count": len(features),
                       "descripcion": "Yacimientos de la cultura ibérica"},
          "features": features}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=1)

    con_img = sum(1 for f in features if f["properties"]["imagen"])
    print(f"GeoJSON con {len(features)} yacimientos ({added} añadidos del CSV, "
          f"{con_img} con imagen) -> {OUT}")


if __name__ == "__main__":
    main()
