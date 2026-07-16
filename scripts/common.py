"""Utilidades compartidas por los scripts del pipeline de datos.

Todo el acceso a datos se hace por APIs públicas (Wikipedia, Wikidata,
Wikimedia Commons), no por scraping de HTML. Ver README para el detalle de
licencias.
"""
import time
import requests

# Wikimedia pide un User-Agent identificable con forma de contacto.
UA = "iberos-map/0.1 (https://github.com/PabloVD; pablo@embodiedaifoundation.org)"
HEADERS = {"User-Agent": UA}

_session = requests.Session()
_session.headers.update(HEADERS)


def api_get(url, params, retries=3, pause=0.2):
    """GET a un endpoint de API que devuelve JSON, con reintentos simples."""
    params = dict(params)
    params.setdefault("format", "json")
    last_exc = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=60)
            r.raise_for_status()
            time.sleep(pause)
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"API falló tras {retries} intentos: {url}\n{last_exc}")


def rest_json(url, retries=2, pause=0.15):
    """GET a una URL REST que devuelve JSON (p. ej. la REST API de Wikipedia).

    Devuelve None si falla (p. ej. 404 cuando el artículo no existe)."""
    for attempt in range(retries):
        try:
            r = _session.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            time.sleep(pause)
            return r.json()
        except Exception:  # noqa: BLE001
            time.sleep(0.5 + attempt)
    return None


def sparql(query, retries=3):
    """Consulta al Wikidata Query Service, devuelve la lista de bindings."""
    url = "https://query.wikidata.org/sparql"
    for attempt in range(retries):
        try:
            r = _session.get(
                url,
                params={"query": query, "format": "json"},
                headers={"Accept": "application/sparql-results+json"},
                timeout=120,
            )
            r.raise_for_status()
            time.sleep(0.3)
            return r.json()["results"]["bindings"]
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2 + 2 * attempt)
    raise RuntimeError(f"SPARQL falló: {last_exc}")


def chunked(seq, size):
    """Trocea una lista en bloques de tamaño `size` (para APIs con límite 50)."""
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
