"""Construye galerías de imágenes desde Wikimedia Commons (licencia libre).

Para cada yacimiento reúne imágenes de tres fuentes y las deduplica:
  1. Las imágenes del propio artículo de Wikipedia (REST `media-list`, es y ca).
     Así aparecen las fotos que ve el lector (p. ej. la Dama de Elche en La Alcúdia).
  2. La imagen de cabecera (`imagen_principal`).
  3. Los archivos de la categoría de Commons (P373).
Luego pide a Commons los metadatos (miniatura, autor, licencia) para atribuir.

Entrada:  data/sources/wikidata.json
Salida:   data/sources/commons_images.json  ->  {qid: [ {..imagen..}, ... ]}
"""
import json
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from common import api_get, rest_json, chunked

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "data", "sources", "wikidata.json")
OUT = os.path.join(ROOT, "data", "sources", "commons_images.json")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_IMAGES = 10
IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")

# Nombres de archivo que casi nunca son fotos del yacimiento.
JUNK = re.compile(
    r"(flag|coat|escudo|bandera|location.?map|locator|relief.?map|topographic|"
    r"logo|wikidata|commons-logo|map_of|mapa.?de|blank|icon|símbolo|simbolo|"
    r"star_of|red_pog|blue_pog)",
    re.IGNORECASE,
)

# Si una imagen aparece en al menos estos yacimientos distintos, se considera
# ilustrativa/de plantilla (no específica del sitio) y se retira de todos.
SHARED_IMAGE_THRESHOLD = 3


def canon_file(title):
    """Normaliza 'Archivo:X' / 'File:X' -> 'File:X' (namespace canónico)."""
    if ":" in title:
        title = title.split(":", 1)[1]
    return "File:" + title.replace("_", " ").strip()


def filename_from_url(url):
    """Extrae el nombre de archivo de una URL de upload.wikimedia."""
    if not url or "upload.wikimedia.org" not in url:
        return None
    path = urllib.parse.urlparse(url).path
    if "/thumb/" in path:
        # .../thumb/a/ab/Nombre.jpg/700px-Nombre.jpg  -> Nombre.jpg
        seg = path.split("/thumb/", 1)[1].split("/")
        name = seg[2] if len(seg) >= 3 else seg[-1]
    else:
        name = path.rsplit("/", 1)[-1]
    return urllib.parse.unquote(name)


def article_images(wiki, title):
    """Nombres de archivo de imagen usados en un artículo (en orden)."""
    if not title:
        return []
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    data = rest_json(f"https://{wiki}.wikipedia.org/api/rest_v1/page/media-list/{t}")
    if not data:
        return []
    files = []
    for it in data.get("items", []):
        if it.get("type") == "image" and it.get("title"):
            files.append(canon_file(it["title"]))
    return files


def category_files(cat):
    """Archivos de imagen de una categoría de Commons."""
    data = api_get(COMMONS_API, {
        "action": "query", "generator": "categorymembers",
        "gcmtitle": f"Category:{cat}", "gcmtype": "file", "gcmlimit": "30",
        "prop": "info",
    })
    return [pg["title"] for pg in data.get("query", {}).get("pages", {}).values()]


def _meta(extmeta, key):
    v = (extmeta or {}).get(key, {}).get("value", "")
    v = re.sub("<[^>]+>", " ", v)          # quita HTML
    return " ".join(v.split()).strip()      # normaliza espacios


def _caption(em):
    """Descripción original del archivo en Commons (ImageDescription), recortada."""
    c = _meta(em, "ImageDescription")
    return (c[:297] + "…") if len(c) > 300 else c


def imageinfo(file_titles):
    """Metadatos (thumb, url, autor, licencia) para una lista de 'File:...'."""
    info = {}
    for batch in chunked(file_titles, 40):
        data = api_get(COMMONS_API, {
            "action": "query", "titles": "|".join(batch),
            "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
            "iiurlwidth": "500",
        })
        q = data.get("query", {})
        alias = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for pg in q.get("pages", {}).values():
            title = pg.get("title", "")
            ii = pg.get("imageinfo")
            if not ii or not ii[0].get("mime", "").startswith("image/"):
                continue
            i0, em = ii[0], ii[0].get("extmetadata", {})
            rec = {
                "titulo": title.replace("File:", ""),
                "thumb": i0.get("thumburl"),
                "url": i0.get("url"),
                "autor": _meta(em, "Artist") or "Desconocido",
                "licencia": _meta(em, "LicenseShortName") or "ver Commons",
                "caption": _caption(em),
                "descripcion_pagina": i0.get("descriptionurl"),
            }
            info[title] = rec
            if title in alias:
                info[alias[title]] = rec
    return info


def gallery_for(s):
    """(qid, [imágenes]) para un yacimiento, o None."""
    candidates = []
    candidates += article_images("es", s.get("es_title"))
    candidates += article_images("ca", s.get("ca_title"))
    fn = filename_from_url(s.get("imagen_principal"))
    if fn:
        candidates.append(canon_file(fn))
    if s.get("commons_cat"):
        candidates += category_files(s["commons_cat"])

    seen, ordered = set(), []
    for f in candidates:
        key = f.lower()
        if key in seen:
            continue
        seen.add(key)
        if not f.lower().endswith(IMG_EXT) or JUNK.search(f):
            continue
        ordered.append(f)
        if len(ordered) >= MAX_IMAGES:
            break
    if not ordered:
        return None
    info = imageinfo(ordered)
    imgs = [info[f] for f in ordered if f in info and info[f].get("thumb")]
    return (s["qid"], imgs) if imgs else None


def main():
    sites = json.load(open(IN, encoding="utf-8"))
    gallery = {}
    done = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for res in ex.map(gallery_for, sites):
            done += 1
            if res:
                gallery[res[0]] = res[1]
            if done % 50 == 0:
                print(f"  {done}/{len(sites)} procesados...", flush=True)

    # Retirar imágenes ilustrativas/de plantilla (aparecen en muchos yacimientos).
    from collections import Counter
    freq = Counter(im["titulo"] for ims in gallery.values() for im in ims)
    shared = {t for t, c in freq.items() if c >= SHARED_IMAGE_THRESHOLD}
    if shared:
        print(f"Imágenes compartidas retiradas (>= {SHARED_IMAGE_THRESHOLD} sitios): {len(shared)}")
        for t in sorted(shared):
            print(f"   - {t} ({freq[t]} sitios)")
        for qid in list(gallery):
            gallery[qid] = [im for im in gallery[qid] if im["titulo"] not in shared]
            if not gallery[qid]:
                del gallery[qid]

    total = sum(len(v) for v in gallery.values())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(gallery, f, ensure_ascii=False, indent=2)
    print(f"Guardadas {total} imágenes de {len(gallery)} yacimientos en {OUT}")


if __name__ == "__main__":
    main()
