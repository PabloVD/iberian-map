"""Recopila yacimientos de la Iberia prerromana (Edad del Hierro) desde
Wikipedia + Wikidata, etiquetados por civilización y con estimación de época.

Por cada civilización del registro (scripts/cultures.py):
  1. Descubre QIDs recorriendo sus categorías semilla de Wikipedia (varios
     idiomas) y los sitios que declaran su cultura (P2596) en Wikidata.
  2. Etiqueta cada yacimiento con su civilización (P2596 manda; si no, la
     categoría; con prioridad en caso de solapamiento).
Luego, para todos los QIDs:
  3. wbgetentities: labels/descripciones (es/ca/en), sitelinks, claims
     (P625 coords, P18 imagen, P373 Commons, P856 web, P31 tipo, P2596 cultura,
     P571/P576/P580/P582 fechas).
  4. Detalles por idioma (coords de respaldo, imagen de cabecera, resumen).
  5. Época: siglos inicio/fin desde fechas de Wikidata o del texto del resumen.
  6. Enlace oficial fiable desde los enlaces externos.

Salida: data/sources/wikidata.json
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from common import api_get, sparql, chunked
from cultures import CIVILIZATIONS, QID_TO_CIV, CIV_OVERRIDES, pick_primary

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "sources", "wikidata.json")
INCLUDE_FILE = os.path.join(HERE, "include_qids.txt")
MAX_DEPTH = 3

# Solo se recursa en subcategorías cuyo nombre parece de yacimientos/cultura
# (allowlist). Evita divagar por categorías de localidad/historia/geografía
# (p. ej. la categoría "Ampurias" o "Rosas (Gerona)" con páginas del municipio).
SUBCAT_RECURSE = re.compile(
    r"(yacimient|jaciment|poblad|poblat|poblac|castro|castre|castra|castrex|"
    r"col[oò]ni|necr[oó]poli|oppid|[ií]ber|ib[eè]r|celt[ií]ber|vascon|baskoi|"
    r"lusitan|veton|vacce|galaic|tart[eé]s|fenici|p[uú]nic|greg|griega|grec)",
    re.IGNORECASE,
)

LINK_BLOCKLIST = (
    "youtube.", "youtu.be", "google.", "books.google", "archive.org",
    "web.archive", "geohack", "wmflabs", "toolforge", "pleiades.stoa",
    "imperium.ahlfeldt", "doi.org", "jstor", "researchgate", "academia.edu",
    "dialnet", "worldcat", "facebook.", "twitter.", "x.com", "instagram.",
    "flickr.", "wikipedia.org", "wikimedia.org", "wikidata.org", "gutenberg",
    "elpais", "lavanguardia", "elmundo", "elperiodico", "abc.es", "20minutos",
    "eldiario", "perseus.tufts", "penelope.uchicago", "revistas.", "blog.",
    "geonames", "dbpedia", "vias.org",
)
LINK_ALLOWLIST = (
    ".gob.es", "gva.es", "gencat", "generalitat", "juntadeandalucia", ".junta",
    "diputacion", "diputacio", "ayuntamiento", "ajuntament", "patrimonio",
    "cultura", "museo", "museu", "turismo", "turisme", ".edu", "universidad",
    "universitat", "csic", ".ua.es", "arqueolog", "iberos", "ibers",
    "patrimoniocultural", "cultura.gob", "dgpc", "monumentos",
)

ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def load_include():
    """Items de Wikidata a incluir a la fuerza (no salen por categoría).
    Formato por línea: 'QID civ' (civ opcional). Devuelve {qid: civ|None}."""
    out = {}
    if os.path.exists(INCLUDE_FILE):
        for line in open(INCLUDE_FILE, encoding="utf-8"):
            line = line.split("#", 1)[0].split()
            if line:
                out[line[0]] = line[1] if len(line) > 1 else None
    return out


def api_url(wiki):
    return f"https://{wiki}.wikipedia.org/w/api.php"


def norm_title(t):
    return (t or "").replace("_", " ").strip()


def roman_to_int(s):
    s = s.lower()
    total, prev = 0, 0
    for ch in reversed(s):
        if ch not in ROMAN:
            return None
        v = ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


def year_to_century(y):
    """Año (negativo = a.C.) -> siglo con signo (negativo = a.C.)."""
    if y < 0:
        return -(((-y) - 1) // 100 + 1)
    return (y - 1) // 100 + 1


def century_label(ini, fin):
    def one(c):
        return f"s. {_roman(abs(c))} {'a.C.' if c < 0 else 'd.C.'}"
    if ini is None:
        return ""
    return one(ini) if ini == fin else f"{one(ini)} – {one(fin)}"


def _roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
            (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
            (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, r in vals:
        while n >= v:
            out += r
            n -= v
    return out


# "siglo V a. C.", "segle IV aC", "siglos V-III a. C.", "s. II d. C."
_CENT_RE = re.compile(
    r"s(?:iglo|egle|\.)\s*([ivxlcdm]+)\s*(?:[-–aliy]{1,3}\s*([ivxlcdm]+))?\s*"
    r"(a\.?\s*c\.?|d\.?\s*c\.?|abans de crist|before)",
    re.IGNORECASE,
)


def centuries_from_text(text):
    """Extrae (siglo_inicio, siglo_fin) del texto, o (None, None)."""
    best = None
    for m in _CENT_RE.finditer(text or ""):
        r1 = roman_to_int(m.group(1))
        r2 = roman_to_int(m.group(2)) if m.group(2) else None
        era = m.group(3).lower().replace(" ", "").replace(".", "")
        bc = era.startswith("ac") or "abans" in era or "before" in era
        sign = -1 if bc else 1
        c1 = sign * r1 if r1 else None
        c2 = sign * r2 if r2 else c1
        if c1 is None:
            continue
        ini, fin = min(c1, c2), max(c1, c2)
        if best is None:
            best = (ini, fin)
        else:
            best = (min(best[0], ini), max(best[1], fin))
    return best or (None, None)


def collect_category_titles(wiki, seeds):
    url = api_url(wiki)
    seen_cat, titles = set(), set()

    def walk(cat, depth):
        if cat in seen_cat or depth > MAX_DEPTH:
            return
        seen_cat.add(cat)
        cont = {}
        while True:
            params = {"action": "query", "list": "categorymembers",
                      "cmtitle": cat, "cmlimit": "500", "cmtype": "page|subcat"}
            params.update(cont)
            try:
                data = api_get(url, params)
            except Exception:  # noqa: BLE001
                return
            for m in data.get("query", {}).get("categorymembers", []):
                if m["ns"] == 14:
                    sub = m["title"].split(":", 1)[-1]
                    if SUBCAT_RECURSE.search(sub):
                        walk(m["title"], depth + 1)
                elif m["ns"] == 0:
                    titles.add(m["title"])
            if "continue" in data:
                cont = data["continue"]
            else:
                break

    for seed in seeds:
        walk(seed, 0)
    return titles


def titles_to_qids(wiki, titles):
    url = api_url(wiki)
    qids = set()
    for batch in chunked(list(titles), 50):
        data = api_get(url, {"action": "query", "titles": "|".join(batch),
                             "prop": "pageprops", "ppprop": "wikibase_item",
                             "redirects": "1"})
        for pg in data.get("query", {}).get("pages", {}).values():
            q = pg.get("pageprops", {}).get("wikibase_item")
            if q:
                qids.add(q)
    return qids


def fetch_details(wiki, titles):
    url = api_url(wiki)
    out = {}
    for batch in chunked([t for t in titles if t], 20):
        data = api_get(url, {
            "action": "query", "titles": "|".join(batch),
            "prop": "coordinates|pageimages|extracts",
            "coprop": "type|name", "colimit": "max",
            "piprop": "original|thumbnail", "pithumbsize": "700",
            "exintro": "1", "explaintext": "1", "exsentences": "4",
            "redirects": "1",
        })
        q = data.get("query", {})
        alias = {}
        for r in q.get("redirects", []) + q.get("normalized", []):
            alias[norm_title(r["to"])] = norm_title(r["from"])
        for pg in q.get("pages", {}).values():
            t = norm_title(pg.get("title"))
            rec = {"extract": (pg.get("extract") or "").strip()}
            coords = pg.get("coordinates")
            if coords:
                rec["lat"], rec["lon"] = coords[0]["lat"], coords[0]["lon"]
            img = pg.get("original") or pg.get("thumbnail")
            if img:
                rec["imagen_principal"] = img["source"]
            out[t] = rec
            if t in alias:
                out[alias[t]] = rec
    return out


def fetch_extlink(wiki, title):
    if not title:
        return None
    data = api_get(api_url(wiki), {"action": "query", "titles": title,
                                   "prop": "extlinks", "ellimit": "max",
                                   "redirects": "1"})
    for pg in data.get("query", {}).get("pages", {}).values():
        for e in pg.get("extlinks", []):
            u = e.get("*", "")
            low = u.lower()
            if any(b in low for b in LINK_BLOCKLIST):
                continue
            if any(a in low for a in LINK_ALLOWLIST):
                return u
    return None


def wikidata_entities(qids):
    url = "https://www.wikidata.org/w/api.php"
    entities = {}
    for batch in chunked(sorted(set(qids)), 50):
        data = api_get(url, {"action": "wbgetentities", "ids": "|".join(batch),
                             "props": "claims|labels|descriptions|sitelinks",
                             "languages": "es|ca|en"})
        entities.update(data.get("entities", {}))
    return entities


def _claim_value(entity, prop):
    vals = []
    for c in entity.get("claims", {}).get(prop, []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            vals.append(snak["datavalue"]["value"])
    return vals


def _label(entity, lang):
    v = entity.get("labels", {}).get(lang)
    return v["value"] if v else None


def _desc(entity, lang):
    v = entity.get("descriptions", {}).get(lang)
    return v["value"] if v else None


def _year_from_time(v):
    try:
        m = re.match(r"([+-]\d+)", v.get("time", ""))
        return int(m.group(1)) if m else None
    except Exception:  # noqa: BLE001
        return None


def epoca_from_entity(ent, det_es, det_ca):
    """(siglo_inicio, siglo_fin, etiqueta). Fechas de Wikidata o del texto."""
    starts = _claim_value(ent, "P571") + _claim_value(ent, "P580")
    ends = _claim_value(ent, "P576") + _claim_value(ent, "P582")
    sy = [year_to_century(y) for y in map(_year_from_time, starts) if y is not None]
    ey = [year_to_century(y) for y in map(_year_from_time, ends) if y is not None]
    if sy or ey:
        ini = min(sy) if sy else min(ey)
        fin = max(ey) if ey else max(sy)
        return ini, fin, century_label(ini, fin)
    ini, fin = centuries_from_text(det_es.get("extract") or det_ca.get("extract"))
    return ini, fin, century_label(ini, fin)


def sparql_culture_qids():
    """{qid: civ} para sitios con P2596 = cultura conocida (en ES/PT/AND/FR)."""
    culture_qids = sorted(QID_TO_CIV)
    vals = " ".join(f"wd:{q}" for q in culture_qids)
    q = f"""SELECT DISTINCT ?s ?c WHERE {{
      VALUES ?c {{ {vals} }}
      VALUES ?country {{ wd:Q29 wd:Q45 wd:Q142 wd:Q228 }}
      ?s wdt:P2596 ?c ; wdt:P625 ?coord ; wdt:P17 ?country .
    }}"""
    out = {}
    for b in sparql(q):
        qid = b["s"]["value"].rsplit("/", 1)[-1]
        civ = QID_TO_CIV[b["c"]["value"].rsplit("/", 1)[-1]]
        out.setdefault(qid, set()).add(civ)
    return out


def commons_image_url(filename):
    import hashlib
    import urllib.parse
    name = filename.replace(" ", "_")
    md5 = hashlib.md5(name.encode("utf-8")).hexdigest()
    return (f"https://upload.wikimedia.org/wikipedia/commons/"
            f"{md5[0]}/{md5[:2]}/{urllib.parse.quote(name)}")


def main():
    # 1-2. Descubrimiento por civilización -> {qid: set(civ)}.
    qid_civs = {}
    for c in CIVILIZATIONS:
        civ = c["civ"]
        found = set()
        for wiki, seeds in c.get("categories", {}).items():
            titles = collect_category_titles(wiki, seeds)
            if titles:
                found |= titles_to_qids(wiki, titles)
        for qid in found:
            qid_civs.setdefault(qid, set()).add(civ)
        print(f"[{civ:15s}] categorías -> {len(found)} QIDs")

    culture_map = sparql_culture_qids()
    for qid, civs in culture_map.items():
        qid_civs.setdefault(qid, set()).update(civs)

    # Inclusiones manuales (items que no salen por categoría).
    include = load_include()
    include_civ = {q: c for q, c in include.items() if c}
    for qid, civ in include.items():
        s = qid_civs.setdefault(qid, set())
        if civ:
            s.add(civ)
    print(f"P2596 aporta {len(culture_map)} QIDs. Incluidos a mano: {len(include)}. "
          f"Total QIDs: {len(qid_civs)}")

    # 3. Entidades de Wikidata.
    entities = wikidata_entities(qid_civs.keys())

    # sitelinks -> títulos por idioma.
    es_titles, ca_titles = {}, {}
    for qid, ent in entities.items():
        sl = ent.get("sitelinks", {})
        if "eswiki" in sl:
            es_titles[qid] = norm_title(sl["eswiki"]["title"])
        if "cawiki" in sl:
            ca_titles[qid] = norm_title(sl["cawiki"]["title"])
    es_det = fetch_details("es", set(es_titles.values()))
    ca_det = fetch_details("ca", set(ca_titles.values()))

    # Enlaces oficiales en paralelo (para los que no tienen P856): es el paso caro.
    def resolve_link(qid):
        return qid, (fetch_extlink("es", es_titles.get(qid))
                     or fetch_extlink("ca", ca_titles.get(qid)))
    need = [qid for qid, ent in entities.items()
            if not _claim_value(ent, "P856") and (qid in es_titles or qid in ca_titles)]
    link_map = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for qid, url in ex.map(resolve_link, need):
            link_map[qid] = url
    print(f"Enlaces externos buscados en paralelo: {len(need)}")

    sites, dropped = [], 0
    for qid, ent in entities.items():
        det_es = es_det.get(es_titles.get(qid, ""), {})
        det_ca = ca_det.get(ca_titles.get(qid, ""), {})

        coords = _claim_value(ent, "P625")
        if coords:
            lat, lon = coords[0]["latitude"], coords[0]["longitude"]
        elif "lat" in det_es:
            lat, lon = det_es["lat"], det_es["lon"]
        elif "lat" in det_ca:
            lat, lon = det_ca["lat"], det_ca["lon"]
        else:
            dropped += 1
            continue

        # Civilización: override manual > P2596 > categorías (con prioridad).
        p2596 = [v["id"] for v in _claim_value(ent, "P2596")]
        civ_from_culture = {QID_TO_CIV[q] for q in p2596 if q in QID_TO_CIV}
        if qid in CIV_OVERRIDES:
            civ = CIV_OVERRIDES[qid]
        elif qid in include_civ:
            civ = include_civ[qid]
        else:
            civ = pick_primary(civ_from_culture or qid_civs.get(qid, set()))

        imagen = det_es.get("imagen_principal") or det_ca.get("imagen_principal")
        if not imagen:
            p18 = _claim_value(ent, "P18")
            if p18:
                imagen = commons_image_url(p18[0])

        p856 = _claim_value(ent, "P856")
        url_oficial = p856[0] if p856 else link_map.get(qid)

        ini, fin, epoca = epoca_from_entity(ent, det_es, det_ca)
        nombre_es = _label(ent, "es")
        nombre_ca = _label(ent, "ca")
        nombre = nombre_es or nombre_ca or _label(ent, "en") or qid
        p373 = _claim_value(ent, "P373")

        sites.append({
            "qid": qid,
            "nombre": nombre, "nombre_es": nombre_es, "nombre_ca": nombre_ca,
            "descripcion_es": det_es.get("extract") or _desc(ent, "es") or "",
            "descripcion_ca": det_ca.get("extract") or _desc(ent, "ca") or "",
            "lat": lat, "lon": lon,
            "civ": civ,
            "siglo_inicio": ini, "siglo_fin": fin, "epoca": epoca,
            "imagen_principal": imagen,
            "commons_cat": p373[0] if p373 else None,
            "p31": [v["id"] for v in _claim_value(ent, "P31")],
            "es_title": es_titles.get(qid), "ca_title": ca_titles.get(qid),
            "url_wikipedia_es": (f"https://es.wikipedia.org/wiki/{es_titles[qid].replace(' ', '_')}"
                                 if qid in es_titles else None),
            "url_wikipedia_ca": (f"https://ca.wikipedia.org/wiki/{ca_titles[qid].replace(' ', '_')}"
                                 if qid in ca_titles else None),
            "url_oficial": url_oficial,
            "fuente": "wikidata+incluido" if qid in include else "wikidata",
        })

    sites.sort(key=lambda s: s["nombre"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)

    from collections import Counter
    civc = Counter(s["civ"] for s in sites)
    con_ep = sum(1 for s in sites if s["siglo_inicio"] is not None)
    print(f"\nGuardados {len(sites)} yacimientos (descartados {dropped} sin coords).")
    print("Por civilización:", dict(civc))
    print(f"Con época estimada: {con_ep}/{len(sites)} | "
          f"con enlace oficial: {sum(1 for s in sites if s['url_oficial'])}")


if __name__ == "__main__":
    main()
