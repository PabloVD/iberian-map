"""Recopila yacimientos de la cultura ibérica desde Wikipedia + Wikidata.

Estrategia (validada):
  1. Recorre recursivamente categorías semilla de yacimientos íberos en varias
     Wikipedias (es, ca) -> lista de artículos.
  2. Por cada artículo obtiene, vía API de Wikipedia: coordenadas, imagen de
     cabecera, resumen (intro) y el QID de Wikidata asociado.
  3. Añade sitios que en Wikidata declaran cultura (P2596) = íberos / cultura
     ibérica aunque no estén en las categorías.
  4. Enriquece cada QID desde Wikidata: coordenadas (fallback), imagen (P18),
     categoría de Commons (P373), web oficial (P856), instance-of (P31).

Salida: data/sources/wikidata.json
"""
import json
import os
import re

from common import api_get, sparql, chunked

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sources", "wikidata.json")

# Categorías raíz por wiki. Se recorren en profundidad; las que no existan se
# ignoran silenciosamente. Añadir más aquí amplía la cobertura.
SEED_CATEGORIES = {
    "es": [
        "Categoría:Yacimientos íberos",
    ],
    "ca": [
        "Categoria:Jaciments arqueològics ibers",
        "Categoria:Poblacions ibèriques de Catalunya",
    ],
}

# QIDs de "cultura" que consideramos íberos.
IBERIAN_CULTURE_QIDS = ["Q190992", "Q13048864"]

MAX_DEPTH = 4

# Inferencia de tipo por palabras clave (multilingüe).
TYPE_KEYWORDS = [
    ("necrópolis", ["necrópolis", "necropoli", "necrópoli", "necropolis"]),
    ("santuario", ["santuario", "santuari", "sanctuary", "templo"]),
    ("cueva", ["cueva", "cova", "abrigo", "gruta"]),
    ("poblado", ["poblado", "poblat", "oppidum", "ciudad", "ciutat", "castro",
                  "asentamiento", "asentament", "yacimiento", "jaciment"]),
]


def api_url(wiki):
    return f"https://{wiki}.wikipedia.org/w/api.php"


def collect_category_pages(wiki, seeds):
    """Devuelve {pageid: title} recorriendo recursivamente las categorías."""
    url = api_url(wiki)
    seen_cat = set()
    pages = {}

    def walk(cat, depth):
        if cat in seen_cat or depth > MAX_DEPTH:
            return
        seen_cat.add(cat)
        cont = {}
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmlimit": "500",
                "cmtype": "page|subcat",
            }
            params.update(cont)
            data = api_get(url, params)
            for m in data.get("query", {}).get("categorymembers", []):
                if m["ns"] == 14:  # subcategoría
                    walk(m["title"], depth + 1)
                elif m["ns"] == 0:  # artículo
                    pages[m["pageid"]] = m["title"]
            if "continue" in data:
                cont = data["continue"]
            else:
                break

    for seed in seeds:
        walk(seed, 0)
    return pages


def fetch_page_details(wiki, titles):
    """Coordenadas, imagen, resumen y QID para una lista de títulos."""
    url = api_url(wiki)
    out = {}
    for batch in chunked(titles, 20):
        params = {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "coordinates|pageimages|extracts|pageprops",
            "coprop": "type|name",
            "colimit": "max",
            "piprop": "original|thumbnail",
            "pithumbsize": "600",
            "exintro": "1",
            "explaintext": "1",
            "exsentences": "3",
            "ppprop": "wikibase_item",
            "redirects": "1",
        }
        data = api_get(url, params)
        for pg in data.get("query", {}).get("pages", {}).values():
            title = pg.get("title")
            rec = {
                "wiki": wiki,
                "title": title,
                "qid": pg.get("pageprops", {}).get("wikibase_item"),
                "extract": (pg.get("extract") or "").strip(),
                "url": f"https://{wiki}.wikipedia.org/wiki/{title.replace(' ', '_')}",
            }
            coords = pg.get("coordinates")
            if coords:
                rec["lat"] = coords[0]["lat"]
                rec["lon"] = coords[0]["lon"]
            img = pg.get("original") or pg.get("thumbnail")
            if img:
                rec["imagen_principal"] = img["source"]
            out[title] = rec
    return out


def wikidata_entities(qids):
    """wbgetentities para claims/labels/descriptions/sitelinks (lotes de 50)."""
    url = "https://www.wikidata.org/w/api.php"
    entities = {}
    for batch in chunked(sorted(set(qids)), 50):
        data = api_get(url, {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "claims|labels|descriptions|sitelinks",
            "languages": "es|ca|en",
        })
        entities.update(data.get("entities", {}))
    return entities


def _claim_value(entity, prop):
    claims = entity.get("claims", {}).get(prop, [])
    vals = []
    for c in claims:
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        vals.append(snak["datavalue"]["value"])
    return vals


def sparql_culture_qids():
    """QIDs de yacimientos con P2596 = cultura íbera y con coordenadas."""
    values = " ".join(f"wd:{q}" for q in IBERIAN_CULTURE_QIDS)
    q = f"""
    SELECT DISTINCT ?s WHERE {{
      VALUES ?c {{ {values} }}
      ?s wdt:P2596 ?c ; wdt:P625 ?coord .
    }}
    """
    return [b["s"]["value"].rsplit("/", 1)[-1] for b in sparql(q)]


def infer_type(*texts):
    blob = " ".join(t for t in texts if t).lower()
    for tipo, kws in TYPE_KEYWORDS:
        if any(k in blob for k in kws):
            return tipo
    return "yacimiento"


def commons_image_url(filename):
    """URL directa a un archivo de Commons a partir de su nombre."""
    import hashlib
    import urllib.parse
    name = filename.replace(" ", "_")
    md5 = hashlib.md5(name.encode("utf-8")).hexdigest()
    enc = urllib.parse.quote(name)
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[:2]}/{enc}"


def main():
    # 1-2. Categorías -> artículos -> detalles, por wiki.
    by_qid = {}
    for wiki, seeds in SEED_CATEGORIES.items():
        pages = collect_category_pages(wiki, seeds)
        print(f"[{wiki}] artículos en categorías: {len(pages)}")
        details = fetch_page_details(wiki, list(pages.values()))
        for rec in details.values():
            qid = rec.get("qid")
            if not qid:
                continue
            # Preferimos el registro con coordenadas; si empatan, es > ca.
            prev = by_qid.get(qid)
            if prev is None:
                by_qid[qid] = rec
            else:
                if "lat" not in prev and "lat" in rec:
                    by_qid[qid] = rec
                # completa campos que falten
                for k, v in rec.items():
                    by_qid.setdefault(qid, prev).setdefault(k, v)

    print(f"QIDs únicos desde categorías: {len(by_qid)}")

    # 3. Sitios por cultura (P2596) que no estuvieran ya.
    culture_qids = sparql_culture_qids()
    print(f"QIDs por P2596 (cultura íbera): {len(culture_qids)}")
    for qid in culture_qids:
        by_qid.setdefault(qid, {"qid": qid})

    # 4. Enriquecer todos los QIDs desde Wikidata.
    entities = wikidata_entities(by_qid.keys())
    for qid, rec in by_qid.items():
        ent = entities.get(qid)
        if not ent:
            continue
        labels = ent.get("labels", {})
        descs = ent.get("descriptions", {})
        rec.setdefault("nombre", (labels.get("es") or labels.get("ca")
                                  or labels.get("en") or {}).get("value"))
        rec["descripcion_wd"] = (descs.get("es") or descs.get("ca")
                                 or descs.get("en") or {}).get("value", "")

        # Coordenadas (fallback a Wikidata).
        if "lat" not in rec:
            coords = _claim_value(ent, "P625")
            if coords:
                rec["lat"] = coords[0]["latitude"]
                rec["lon"] = coords[0]["longitude"]

        # Imagen P18 (fallback).
        if "imagen_principal" not in rec:
            imgs = _claim_value(ent, "P18")
            if imgs:
                rec["imagen_principal"] = commons_image_url(imgs[0])

        # Categoría de Commons (para la galería).
        p373 = _claim_value(ent, "P373")
        if p373:
            rec["commons_cat"] = p373[0]

        # Web oficial.
        p856 = _claim_value(ent, "P856")
        if p856:
            rec["url_oficial"] = p856[0]

        # instance-of para trazabilidad.
        rec["p31"] = [v["id"] for v in _claim_value(ent, "P31")]

    # Filtrar sin coordenadas y componer registros finales.
    sites = []
    dropped = 0
    for qid, rec in by_qid.items():
        if "lat" not in rec or "lon" not in rec:
            dropped += 1
            continue
        nombre = rec.get("nombre") or rec.get("title") or qid
        sites.append({
            "qid": qid,
            "nombre": nombre,
            "lat": rec["lat"],
            "lon": rec["lon"],
            "tipo": infer_type(nombre, rec.get("extract"), rec.get("descripcion_wd")),
            "descripcion": rec.get("extract") or rec.get("descripcion_wd", ""),
            "imagen_principal": rec.get("imagen_principal"),
            "commons_cat": rec.get("commons_cat"),
            "url_wikipedia": rec.get("url"),
            "url_oficial": rec.get("url_oficial"),
            "fuente": "wikidata",
        })

    sites.sort(key=lambda s: s["nombre"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)
    print(f"\nGuardados {len(sites)} yacimientos en {OUT} "
          f"(descartados {dropped} sin coordenadas).")


if __name__ == "__main__":
    main()
