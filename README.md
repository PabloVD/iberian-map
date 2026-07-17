# Mapa interactivo de la Iberia prerromana

Web estática con un mapa de los yacimientos de la **Iberia prerromana (Edad del
Hierro)** en la península ibérica (más los íberos del sur de Francia y los
enclaves fenicio-púnicos de las Baleares, p. ej. Ibiza). Al pasar
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

### Red de seguridad ante cambios

Cambiar el descubrimiento o los filtros puede tirar sin querer sitios
importantes. Para evitarlo, `build_geojson.py` hace dos comprobaciones en cada
ejecución:
- **Anclas** (`scripts/anchor_sites.txt`): lista de yacimientos que DEBEN estar
  (por QID o nombre). Si falta alguno, avisa (`⚠️ faltan N yacimientos ANCLA`).
- **Diff con el build anterior** (el commiteado en git): muestra qué yacimientos
  aparecen y cuáles **desaparecen** respecto a la última versión.

Si algo importante desaparece, se recupera añadiéndolo a `curated_sites.csv` o
ajustando el registro/filtros.

Los datos se **pre-generan** con un pipeline en Python a partir de Wikipedia,
Wikidata y Wikimedia Commons (más un CSV curado) y se guardan en un GeoJSON. La
web solo lee ese fichero, así que se puede publicar en **GitHub Pages** sin backend.

## Estructura

```
scripts/
  common.py           utilidades de acceso a APIs
  fetch_wikidata.py   categorías de Wikipedia (es/ca) + P2596 -> data/sources/wikidata.json
  enrich_commons.py   galerías de imágenes con licencia -> data/sources/commons_images.json
  cultures.py         registro de civilizaciones (categorías, QIDs, prioridad)
  curated_sites.csv   yacimientos a mano (los que NO están en Wikidata)
  include_qids.txt    QIDs de Wikidata a incluir a la fuerza (no salen por categoría)
  exclude_qids.txt    QIDs a descartar a mano
  anchor_sites.txt    yacimientos que DEBEN estar (red de seguridad)
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

### Parches manuales (se re-aplican en cada fetch)

Tres ficheros de configuración corrigen lo que el descubrimiento automático no
acierta; al ser declarativos, **los parches no se pierden al regenerar**:
- `include_qids.txt` — yacimientos que existen en Wikidata (con coordenadas) pero
  no salen por categoría (p. ej. **Rode**, **Akra Leuke**, **Asta Regia**). Se
  indican por QID + civilización y se enriquecen igual que el resto. Se marcan con
  `fuente = "wikidata+incluido"`.
- `exclude_qids.txt` — quita falsos positivos o entradas equivocadas (p. ej. la
  Ciutadella renacentista de Roses).
- `curated_sites.csv` — yacimientos que **no** están en Wikidata o sin coordenadas
  (p. ej. **Gadir/Gades**); datos escritos a mano.

`anchor_sites.txt` vigila que los yacimientos importantes no desaparezcan tras un
cambio (ver "Red de seguridad").

#### Yacimientos con datos introducidos a mano (y su fuente)

Estos se añadieron manualmente en `curated_sites.csv` (coordenadas, época y
descripción escritas a mano); la fuente de la información es:

| Yacimiento | Civilización | Fuente |
|---|---|---|
| La Alcúdia d'Elx | íberos | [Wikipedia: La Alcudia](https://es.wikipedia.org/wiki/La_Alcudia) |
| Contrebia Leukade | celtíbero | [Wikipedia: Contrebia Leukade](https://es.wikipedia.org/wiki/Contrebia_Leukade) |
| Gebut | íberos | [Llista de poblacions ibèriques de Catalunya (ca.wikipedia)](https://ca.wikipedia.org/wiki/Llista_de_poblacions_ib%C3%A8riques_de_Catalunya) |
| Turó de Montgat | íberos | [Llista de poblacions ibèriques de Catalunya (ca.wikipedia)](https://ca.wikipedia.org/wiki/Llista_de_poblacions_ib%C3%A8riques_de_Catalunya) |
| Cástulo | íberos | [Wikipedia: Cástulo](https://es.wikipedia.org/wiki/Cástulo) |
| Cancho Roano | tartésico | [Wikipedia: Cancho Roano](https://es.wikipedia.org/wiki/Cancho_Roano) |
| Iruña-Veleia | vascones | [Wikipedia: Iruña-Veleia](https://es.wikipedia.org/wiki/Iruña-Veleia) |
| Gadir (Gades) | fenicio-púnico | [Wikipedia: Gadir](https://es.wikipedia.org/wiki/Gadir) — coordenadas aproximadas (casco antiguo de Cádiz) |

Los sitios de `include_qids.txt` (Rode, Akra Leuke, Asta Regia, Lucentum) **no**
se listan aquí porque sus datos vienen íntegros de Wikidata/Wikipedia, no a mano.

Para **ampliar la cobertura** desde Wikipedia, añade categorías semilla en
`SEED_CATEGORIES` dentro de `fetch_wikidata.py`.

## Ver en local

```bash
cd docs
python3 -m http.server 8777
# abre http://localhost:8777
```

## Publicar en GitHub Pages

Publicado desde la rama `main`, carpeta `/docs`:
<https://pablovd.github.io/iberian-map/>. Para regenerarlo, ejecuta el pipeline
y haz push; Pages se actualiza solo.

## Fuentes

Los datos se obtienen por API de:
- [Wikidata](https://www.wikidata.org) (coordenadas, cultura, fechas, imagen, web oficial).
- [Wikimedia Commons](https://commons.wikimedia.org) (imágenes de licencia libre).
- [OpenStreetMap](https://www.openstreetmap.org) (mapa base).

**Categorías de Wikipedia** recorridas para descubrir yacimientos (registro en
`scripts/cultures.py`):
- Íberos: [Yacimientos íberos](https://es.wikipedia.org/wiki/Categoría:Yacimientos_íberos),
  [Poblaciones iberas](https://es.wikipedia.org/wiki/Categoría:Poblaciones_iberas),
  [Jaciments arqueològics ibers](https://ca.wikipedia.org/wiki/Categoria:Jaciments_arqueològics_ibers),
  [Poblacions ibèriques](https://ca.wikipedia.org/wiki/Categoria:Poblacions_ibèriques)
  (incluye [de Catalunya](https://ca.wikipedia.org/wiki/Categoria:Poblacions_ibèriques_de_Catalunya)
  y [del País Valencià](https://ca.wikipedia.org/wiki/Categoria:Poblacions_ibèriques_del_País_Valencià)),
  [Jaciments arqueològics ibers del País Valencià](https://ca.wikipedia.org/wiki/Categoria:Jaciments_arqueològics_ibers_del_País_Valencià).
- Celtíberos: [Celtíberos](https://es.wikipedia.org/wiki/Categoría:Celtíberos),
  [Poblaciones de Celtiberia](https://es.wikipedia.org/wiki/Categoría:Poblaciones_de_Celtiberia),
  [Yacimientos celtíberos de Aragón](https://es.wikipedia.org/wiki/Categoría:Yacimientos_celtíberos_de_Aragón).
- Fenicio-púnico: [Colonización fenicia en España Antigua](https://es.wikipedia.org/wiki/Categoría:Colonización_fenicia_en_España_Antigua),
  [Colonias fenicias](https://es.wikipedia.org/wiki/Categoría:Colonias_fenicias).
- Griego: [Antiguas colonias griegas en España](https://es.wikipedia.org/wiki/Categoría:Antiguas_colonias_griegas_en_España).
- Vascones: [Vascones](https://es.wikipedia.org/wiki/Categoría:Vascones).
- Celtas / atlánticos: [Castros de España](https://es.wikipedia.org/wiki/Categoría:Castros_de_España),
  [Cultura castrexa](https://gl.wikipedia.org/wiki/Categoría:Cultura_castrexa),
  [Castros de Galicia](https://gl.wikipedia.org/wiki/Categoría:Castros_de_Galicia),
  [Castros de Portugal](https://pt.wikipedia.org/wiki/Categoria:Castros_de_Portugal),
  [Castros da Galécia](https://pt.wikipedia.org/wiki/Categoria:Castros_da_Galécia).

También se recorren las **subcategorías** de las anteriores (por provincias, etc.).

**Páginas generales de Wikipedia** de referencia:
[Cultura ibérica](https://es.wikipedia.org/wiki/Cultura_ibérica),
[Íberos](https://es.wikipedia.org/wiki/Íberos),
[Celtíberos](https://es.wikipedia.org/wiki/Celtíberos),
[Tartessos](https://es.wikipedia.org/wiki/Tartessos),
[Fenicios](https://es.wikipedia.org/wiki/Fenicia),
[Colonización griega](https://es.wikipedia.org/wiki/Colonización_griega),
[Vascones](https://es.wikipedia.org/wiki/Vascones),
[Lusitanos](https://es.wikipedia.org/wiki/Lusitanos),
[Cultura castreña](https://es.wikipedia.org/wiki/Cultura_castreña).

Listas curadas usadas como complemento:
[Llista de poblacions ibèriques de Catalunya](https://ca.wikipedia.org/wiki/Llista_de_poblacions_ibèriques_de_Catalunya)
y la [llista de 360 poblats ibers](https://ibers.cat/ibers_cat_llista_360_poblats_ibers_nov14.xls)
de David Folch (ver `TODO.md`).

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
