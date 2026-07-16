"""Recopila yacimientos de la cultura ibérica desde Wikipedia + Wikidata.

Orientado a QID y bilingüe (es/ca):
  1. Descubre QIDs recorriendo categorías semilla de yacimientos íberos en
     Wikipedia es y ca, más los que declaran cultura íbera (P2596) en Wikidata.
  2. wbgetentities: labels/descriptions (es/ca/en), sitelinks (eswiki/cawiki) y
     claims (P625 coords, P18 imagen, P373 categoría Commons, P856 web oficial,
     P31 instance-of).
  3. Con los títulos de sitelink obtiene, de cada Wikipedia (es y ca por
     separado): coordenadas (respaldo), imagen de cabecera y resumen (intro).
  4. Enlaces oficiales: si no hay P856, elige un enlace externo fiable del
     artículo (lista negra + allowlist de dominios).

Salida: data/sources/wikidata.json  (registros bilingües con p31)
"""
import json
import os

from common import api_get, sparql, chunked

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sources", "wikidata.json")

SEED_CATEGORIES = {
    "es": ["Categoría:Yacimientos íberos"],
    "ca": ["Categoria:Jaciments arqueològics ibers",
           "Categoria:Poblacions ibèriques de Catalunya"],
}

IBERIAN_CULTURE_QIDS = ["Q190992", "Q13048864"]
MAX_DEPTH = 4

# --- Selección de enlace oficial desde los enlaces externos de Wikipedia ---
LINK_BLOCKLIST = (
    "youtube.", "youtu.be", "google.", "books.google", "archive.org",
    "web.archive", "geohack", "wmflabs", "toolforge", "pleiades.stoa",
    "imperium.ahlfeldt", "doi.org", "jstor", "researchgate", "academia.edu",
    "dialnet", "worldcat", "facebook.", "twitter.", "x.com", "instagram.",
    "flickr.", "wikipedia.org", "wikimedia.org", "wikidata.org", "gutenberg",
    # prensa y repositorios académicos/gazetteers (no son "sitio oficial")
    "elpais", "lavanguardia", "elmundo", "elperiodico", "abc.es", "20minutos",
    "eldiario", "perseus.tufts", "penelope.uchicago", "revistas.", "blog.",
    "geonames", "dbpedia", "vias.org",
)
LINK_ALLOWLIST = (
    ".gob.es", "gva.es", "gencat", "generalitat", "juntadeandalucia", ".junta",
    "diputacion", "diputacio", "ayuntamiento", "ajuntament", "patrimonio",
    "cultura", "museo", "museu", "turismo", "turisme", ".edu", "universidad",
    "universitat", "csic", ".ua.es", "arqueolog", "iberos", "ibers",
)


def api_url(wiki):
    return f"https://{wiki}.wikipedia.org/w/api.php"


def norm_title(t):
    return (t or "").replace("_", " ").strip()


def collect_category_titles(wiki, seeds):
    """Títulos de artículo recorriendo recursivamente las categorías."""
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
            data = api_get(url, params)
            for m in data.get("query", {}).get("categorymembers", []):
                if m["ns"] == 14:
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
    """Mapea títulos -> QID de Wikidata (pageprops wikibase_item)."""
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
    """Por título: coordenadas, imagen de cabecera y resumen (intro)."""
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
        # mapea posibles redirecciones/normalizaciones al título pedido
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
    """Primer enlace externo fiable del artículo (o None)."""
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


def sparql_culture_qids():
    values = " ".join(f"wd:{q}" for q in IBERIAN_CULTURE_QIDS)
    q = f"""SELECT DISTINCT ?s WHERE {{
      VALUES ?c {{ {values} }} ?s wdt:P2596 ?c ; wdt:P625 ?coord . }}"""
    return [b["s"]["value"].rsplit("/", 1)[-1] for b in sparql(q)]


def commons_image_url(filename):
    import hashlib
    import urllib.parse
    name = filename.replace(" ", "_")
    md5 = hashlib.md5(name.encode("utf-8")).hexdigest()
    return (f"https://upload.wikimedia.org/wikipedia/commons/"
            f"{md5[0]}/{md5[:2]}/{urllib.parse.quote(name)}")


def main():
    # 1. Descubrimiento de QIDs.
    qids = set()
    for wiki, seeds in SEED_CATEGORIES.items():
        titles = collect_category_titles(wiki, seeds)
        found = titles_to_qids(wiki, titles)
        print(f"[{wiki}] artículos en categorías: {len(titles)} -> QIDs: {len(found)}")
        qids |= found
    culture = sparql_culture_qids()
    print(f"QIDs por P2596: {len(culture)}")
    qids |= set(culture)
    print(f"QIDs totales: {len(qids)}")

    # 2. Entidades de Wikidata.
    entities = wikidata_entities(qids)

    # 3. Detalles por idioma a partir de los sitelinks.
    es_titles, ca_titles = {}, {}   # qid -> título
    for qid, ent in entities.items():
        sl = ent.get("sitelinks", {})
        if "eswiki" in sl:
            es_titles[qid] = norm_title(sl["eswiki"]["title"])
        if "cawiki" in sl:
            ca_titles[qid] = norm_title(sl["cawiki"]["title"])
    es_det = fetch_details("es", set(es_titles.values()))
    ca_det = fetch_details("ca", set(ca_titles.values()))
    print(f"Detalles: es={len(es_titles)} ca={len(ca_titles)} artículos")

    # 4. Componer registros bilingües.
    sites, dropped = [], 0
    need_link = 0
    for qid, ent in entities.items():
        det_es = es_det.get(es_titles.get(qid, ""), {})
        det_ca = ca_det.get(ca_titles.get(qid, ""), {})

        # Coordenadas: Wikidata (P625) preferente, respaldo Wikipedia.
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

        # Imagen de cabecera: cabecera es > ca > P18.
        imagen = det_es.get("imagen_principal") or det_ca.get("imagen_principal")
        if not imagen:
            p18 = _claim_value(ent, "P18")
            if p18:
                imagen = commons_image_url(p18[0])

        # Web oficial: P856, o enlace externo fiable del artículo.
        url_oficial = None
        p856 = _claim_value(ent, "P856")
        if p856:
            url_oficial = p856[0]
        else:
            need_link += 1
            url_oficial = (fetch_extlink("es", es_titles.get(qid))
                           or fetch_extlink("ca", ca_titles.get(qid)))

        nombre_es = _label(ent, "es")
        nombre_ca = _label(ent, "ca")
        nombre = nombre_es or nombre_ca or _label(ent, "en") or qid
        commons_cat = None
        p373 = _claim_value(ent, "P373")
        if p373:
            commons_cat = p373[0]

        sites.append({
            "qid": qid,
            "nombre": nombre,
            "nombre_es": nombre_es,
            "nombre_ca": nombre_ca,
            "descripcion_es": det_es.get("extract") or _desc(ent, "es") or "",
            "descripcion_ca": det_ca.get("extract") or _desc(ent, "ca") or "",
            "lat": lat,
            "lon": lon,
            "imagen_principal": imagen,
            "commons_cat": commons_cat,
            "p31": [v["id"] for v in _claim_value(ent, "P31")],
            "es_title": es_titles.get(qid),
            "ca_title": ca_titles.get(qid),
            "url_wikipedia_es": (f"https://es.wikipedia.org/wiki/{es_titles[qid].replace(' ', '_')}"
                                 if qid in es_titles else None),
            "url_wikipedia_ca": (f"https://ca.wikipedia.org/wiki/{ca_titles[qid].replace(' ', '_')}"
                                 if qid in ca_titles else None),
            "url_oficial": url_oficial,
            "fuente": "wikidata",
        })

    sites.sort(key=lambda s: s["nombre"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)
    con_link = sum(1 for s in sites if s["url_oficial"])
    print(f"\nGuardados {len(sites)} yacimientos en {OUT} "
          f"(descartados {dropped} sin coordenadas).")
    print(f"Enlaces oficiales: {con_link}/{len(sites)} "
          f"(se buscó extlink en {need_link} sin P856).")


if __name__ == "__main__":
    main()
