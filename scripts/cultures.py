"""Registro de civilizaciones prerromanas de la península ibérica (Edad del Hierro).

Cada civilización agrupa sus pueblos (p. ej. "íberos" engloba edetanos,
contestanos, ilergetes…). Se usa para:
  - descubrir yacimientos (categorías de Wikipedia por idioma + P2596 de Wikidata),
  - etiquetar cada yacimiento con su civilización (para el marcador en el mapa).

La asignación de civilización a un yacimiento sigue esta prioridad cuando hay
solapamiento (p. ej. tartésico/fenicio). Además, el valor de P2596 (cultura) en
Wikidata, si mapea a una civilización, manda sobre la categoría.
"""

# Orden = prioridad al asignar civilización en caso de solapamiento (primero gana).
CIVILIZATIONS = [
    {
        "civ": "tartesico",
        "label_es": "Tartésico", "label_ca": "Tartèssic",
        "shape": "star",
        "culture_qids": ["Q320416"],            # Tartessos
        "categories": {
            "es": ["Categoría:Tartesos", "Categoría:Cultura tartésica"],
        },
    },
    {
        "civ": "griego",
        "label_es": "Griego", "label_ca": "Grec",
        "shape": "triangle",
        "culture_qids": ["Q828047"],            # colonización griega
        "categories": {
            "es": ["Categoría:Antiguas colonias griegas en España"],
            "ca": ["Categoria:Colònies gregues de la Mediterrània occidental"],
        },
    },
    {
        "civ": "fenicio-punico",
        "label_es": "Fenicio-púnico", "label_ca": "Fenici-púnic",
        "shape": "diamond",
        "culture_qids": ["Q1048468", "Q4383747"],   # fenicios / púnicos
        "categories": {
            "es": ["Categoría:Colonización fenicia en España Antigua",
                   "Categoría:Colonias fenicias"],
        },
    },
    {
        "civ": "vascones",
        "label_es": "Vascones", "label_ca": "Vascons",
        "shape": "pentagon",
        "culture_qids": ["Q1246837"],
        "categories": {
            "es": ["Categoría:Vascones"],
        },
    },
    {
        "civ": "celtibero",
        "label_es": "Celtíbero", "label_ca": "Celtiber",
        "shape": "square",
        "culture_qids": ["Q5011445"],
        "categories": {
            "es": ["Categoría:Celtíberos", "Categoría:Poblaciones de Celtiberia"],
        },
    },
    {
        "civ": "celtas",
        "label_es": "Celtas / atlánticos", "label_ca": "Celtes / atlàntics",
        "shape": "hexagon",
        # lusitanos, vetones, vacceos, galaicos, cultura castreña, celtas
        "culture_qids": ["Q837549", "Q924779", "Q2310278", "Q1007723",
                         "Q1049966", "Q35966", "Q16320185"],
        "categories": {
            "es": ["Categoría:Castros de España", "Categoría:Vetones",
                   "Categoría:Vacceos"],
            "gl": ["Categoría:Cultura castrexa", "Categoría:Castros de Galicia"],
            "pt": ["Categoria:Castros de Portugal", "Categoria:Castros da Galécia"],
        },
    },
    {
        "civ": "iberos",
        "label_es": "Íberos", "label_ca": "Ibers",
        "shape": "circle",
        "culture_qids": ["Q190992", "Q13048864"],
        "categories": {
            "es": ["Categoría:Yacimientos íberos"],
            "ca": ["Categoria:Jaciments arqueològics ibers",
                   "Categoria:Poblacions ibèriques de Catalunya"],
        },
    },
]

# Prioridad al asignar civilización cuando un sitio aparece en categorías de
# varias culturas. Las culturas específicas y bien acotadas van primero; las
# categorías AMPLIAS que sobre-capturan (colonización fenicia mundial, "Castros
# de España") van al final, para que un yacimiento íbero que además caiga en
# ellas se quede como íbero. P2596 y CIV_OVERRIDES siguen mandando por encima.
CIV_PRIORITY = ["tartesico", "griego", "vascones", "celtibero", "iberos",
                "fenicio-punico", "celtas"]
CIV_ORDER = [c["civ"] for c in CIVILIZATIONS]

# P2596 (cultura de Wikidata) -> civilización.
QID_TO_CIV = {q: c["civ"] for c in CIVILIZATIONS for q in c["culture_qids"]}

# Asignación manual de civilización por QID (máxima prioridad). Útil para casos
# tartésico/fenicio que Wikipedia mezcla bajo "colonización fenicia".
CIV_OVERRIDES = {
    "Q2060316": "tartesico",   # Cancho Roano
    "Q1605142": "tartesico",   # El Carambolo
}


def civ_priority(civ):
    return CIV_PRIORITY.index(civ) if civ in CIV_PRIORITY else len(CIV_PRIORITY)


def pick_primary(civs):
    """De un conjunto de civilizaciones candidatas, la de mayor prioridad."""
    return min(civs, key=civ_priority) if civs else "iberos"
