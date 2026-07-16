# Pendientes (ideas para más adelante)

## Integrar la "Llista dels 360 poblats ibèrics de Catalunya"

Fuente: <https://ibers.cat/ibers_cat_llista_360_poblats_ibers_nov14.xls>
(David Folch Flórez, nov. 2014). Copia guardada en
`data/sources/ibers_cat_360_poblats_nov14.xls`.

**Contenido:** 387 poblados ibéricos de Catalunya con columnas *Nom*, *Municipi*
y *Comentaris*. **No trae coordenadas.**

**Análisis (jul. 2026):**
- 246 municipios distintos.
- ~94 ya están en el mapa (coinciden por nombre).
- ~293 serían nuevos → casi cuadruplicaría la cobertura catalana.

**Por qué está aparcado:** al no haber coordenadas, no se pueden situar con
precisión. Opciones consideradas para retomarlo:
1. **Aproximado por municipio** (recomendado): centro del municipio (coords de
   Wikidata), con marcador/estilo distinto, etiqueta "ubicación aproximada" y un
   filtro para mostrarlos/ocultarlos. Honesto sobre la precisión.
2. **Solo validar**: usar el archivo para cruzar/enriquecer los existentes, sin
   añadir los que no tienen coordenadas.
3. **Geocodificar por nombre+municipio** (Nominatim): algunos saldrían precisos,
   pero muchos nombres son genéricos ("El Castell", "La Palomera") y darían error
   o ubicación equivocada.

Si se retoma con la opción 1: parsear el XLS (usar LibreOffice `--convert-to csv`
o instalar `xlrd`; ojo con la codificación cp1252/UTF-8), resolver el centroide
de cada municipio vía SPARQL de Wikidata, y añadir un flag `precision:
"aproximada"` a esas features + un filtro en el frontend.

## Otras ideas

- **Inventari del Patrimoni Arqueològic de Catalunya** (Generalitat,
  `invarque.cultura.gencat.cat`): fuente georreferenciada con miles de
  yacimientos; filtrando por cultura ibérica ampliaría mucho la cobertura con
  coordenadas reales (vía "portales oficiales").
- **Cronología/época** por yacimiento (ahora casi siempre vacía): se podría sacar
  de Wikidata (P571 inicio, P576 fin, o "período" P2348).
- Reducir el cajón genérico **"yacimiento"** (57) afinando el mapeo de P31.
