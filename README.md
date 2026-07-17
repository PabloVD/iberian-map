# Mapa interactivo de la Iberia prerromana

Web estática con un mapa de los yacimientos de la **Iberia prerromana (Edad del
Hierro)** en la península ibérica (más los íberos del sur de Francia). Al pasar
el cursor sobre cada punto aparece una ficha con foto e información; al hacer clic
se abre un panel con descripción, galería de imágenes (con lightbox) y enlaces.

Características:
- **Civilizaciones por forma de marcador**: íberos, celtíberos, fenicio-púnico,
  griego, tartésico, vascones y celtas/atlánticos (castros). El **color** indica
  el tipo de yacimiento.
- **Filtro por siglos** (deslizador) además de por civilización y tipo.
- **Bilingüe es/ca** con selector; idioma inicial según el navegador.
- Tipos clasificados por **P31** de Wikidata (poblado, ciudad, necrópolis,
  santuario, cueva, fortificación, yacimiento) y filtro de falsos positivos.
- Galería que combina las imágenes del **artículo** de Wikipedia, la imagen
  principal y la **categoría de Commons**; clic para ampliar (lightbox).
- **Enlaces oficiales** extraídos de forma selectiva (inventarios de patrimonio,
  museos, etc.).

Cada civilización se descubre por sus categorías de Wikipedia (varios idiomas) y
por la cultura declarada en Wikidata (P2596); el registro está en
`scripts/cultures.py`.

Los datos se **pre-generan** con un pipeline en Python a partir de Wikipedia,
Wikidata y Wikimedia Commons (más un CSV curado) y se guardan en un GeoJSON. La
web solo lee ese fichero, así que se puede publicar en **GitHub Pages** sin backend.

## Estructura

```
scripts/
  common.py           utilidades de acceso a APIs
  fetch_wikidata.py   categorías de Wikipedia (es/ca) + P2596 -> data/sources/wikidata.json
  enrich_commons.py   galerías de imágenes con licencia -> data/sources/commons_images.json
  curated_sites.csv   yacimientos añadidos a mano (parte "híbrida")
  build_geojson.py    fusiona todo -> docs/data/yacimientos.geojson
docs/                 sitio estático que publica GitHub Pages
  index.html  style.css  map.js  data/yacimientos.geojson
```

## Regenerar los datos

```bash
pip install -r requirements.txt
cd scripts
python3 fetch_wikidata.py     # ~1-2 min
python3 enrich_commons.py     # ~2-3 min
python3 build_geojson.py
```

Para **añadir yacimientos** que falten o mejorar los existentes, edita
`scripts/curated_sites.csv` y vuelve a ejecutar `build_geojson.py`. Los duplicados
con Wikidata se fusionan por cercanía de coordenadas + nombre.

Para **ampliar la cobertura** desde Wikipedia, añade categorías semilla en
`SEED_CATEGORIES` dentro de `fetch_wikidata.py`.

## Ver en local

```bash
cd docs
python3 -m http.server 8777
# abre http://localhost:8777
```

## Publicar en GitHub Pages

Sube el repo a GitHub y en *Settings → Pages* elige la rama y la carpeta `/docs`.

## Licencias y atribución

- **Wikidata**: dominio público (CC0).
- **Wikimedia Commons**: imágenes con licencias libres; se muestran autor y
  licencia en la galería. Solo se usan imágenes de Commons — no se redistribuyen
  fotos de webs de museos o portales oficiales (a esos solo se enlaza).
- **Textos** de descripción provenientes de Wikipedia: CC BY-SA; cada ficha
  enlaza al artículo de origen.
- **Mapa base**: © OpenStreetMap contributors.

Añadir imágenes propias al CSV (`url_imagen`) solo si tienes derechos o son de
licencia libre.
