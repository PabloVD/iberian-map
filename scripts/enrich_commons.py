"""Construye galerías de imágenes desde Wikimedia Commons (licencia libre).

Para cada yacimiento con categoría de Commons (P373), lista algunos archivos de
imagen de esa categoría y guarda URL de miniatura, autor y licencia para poder
atribuir correctamente en la web.

Entrada:  data/sources/wikidata.json
Salida:   data/sources/commons_images.json  ->  {qid: [ {..imagen..}, ... ]}
"""
import json
import os

from common import api_get

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "data", "sources", "wikidata.json")
OUT = os.path.join(ROOT, "data", "sources", "commons_images.json")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_IMAGES = 6
IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")


def _meta(extmeta, key):
    v = (extmeta or {}).get(key, {}).get("value", "")
    # extmetadata a veces trae HTML; nos quedamos con texto plano corto.
    import re
    v = re.sub("<[^>]+>", "", v)
    return v.strip()


def category_images(cat):
    """Lista hasta MAX_IMAGES imágenes de una categoría de Commons."""
    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": f"Category:{cat}",
        "gcmtype": "file",
        "gcmlimit": str(MAX_IMAGES * 3),  # margen para filtrar no-imágenes
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "iiurlwidth": "500",
    }
    try:
        data = api_get(COMMONS_API, params)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! error en categoría {cat}: {exc}")
        return []
    pages = data.get("query", {}).get("pages", {})
    imgs = []
    for pg in pages.values():
        title = pg.get("title", "")
        if not title.lower().endswith(IMG_EXT):
            continue
        info = (pg.get("imageinfo") or [{}])[0]
        if not info.get("mime", "").startswith("image/"):
            continue
        em = info.get("extmetadata", {})
        imgs.append({
            "titulo": title.replace("File:", ""),
            "thumb": info.get("thumburl"),
            "url": info.get("url"),
            "autor": _meta(em, "Artist") or "Desconocido",
            "licencia": _meta(em, "LicenseShortName") or "ver Commons",
            "descripcion_pagina": info.get("descriptionurl"),
        })
        if len(imgs) >= MAX_IMAGES:
            break
    return imgs


def main():
    sites = json.load(open(IN, encoding="utf-8"))
    todo = [s for s in sites if s.get("commons_cat")]
    print(f"Yacimientos con categoría de Commons: {len(todo)}")
    gallery = {}
    for i, s in enumerate(todo, 1):
        imgs = category_images(s["commons_cat"])
        if imgs:
            gallery[s["qid"]] = imgs
        if i % 20 == 0:
            print(f"  {i}/{len(todo)} procesados...")
    total = sum(len(v) for v in gallery.values())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(gallery, f, ensure_ascii=False, indent=2)
    print(f"Guardadas {total} imágenes de {len(gallery)} yacimientos en {OUT}")


if __name__ == "__main__":
    main()
