#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente del buscador del Diario Oficial El Peruano.

No hay API JSON: se consulta el buscador y se parsea el HTML con BeautifulSoup.
Se cachea una hora y se atribuye siempre la fuente.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

import aiohttp
from bs4 import BeautifulSoup

BASE = "https://busquedas.elperuano.pe"
FUENTE = "Diario Oficial El Peruano"
LICENCIA = "Contenido oficial; citar la fuente"
TTL = 3600.0
CACHE: dict[str, tuple[float, str]] = {}
RUTA_DISPOSITIVO = re.compile(r"^/dispositivo/([A-Za-z]{2})/([A-Za-z0-9._-]+)$")
MESES_LARGOS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


class ErrorFuente(ValueError):
    """La consulta a El Peruano no es válida o falló."""


def _fecha_compacta(valor: str) -> str:
    try:
        return datetime.strptime(valor.strip(), "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError as error:
        raise ErrorFuente("Fecha no válida; usa el formato YYYY-MM-DD.") from error


def _fecha_iso(texto: str) -> str:
    coincidencia = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", texto or "")
    if coincidencia:
        dia, mes, anio = coincidencia.groups()
        return f"{anio}-{int(mes):02d}-{int(dia):02d}"
    coincidencia = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", (texto or "").lower())
    if coincidencia:
        dia, mes, anio = coincidencia.groups()
        numero_mes = MESES_LARGOS.get(mes)
        if numero_mes:
            return f"{anio}-{numero_mes:02d}-{int(dia):02d}"
    return ""


async def _get_html(url: str) -> str:
    ahora = time.time()
    if url in CACHE and ahora - CACHE[url][0] < TTL:
        return CACHE[url][1]
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=25)
        ) as sesion:
            async with sesion.get(url, headers={
                    "User-Agent": "mcp-datos-pe/0.3 (+https://datos-pe.hlquantlabs.trade)",
                    "Accept": "text/html,application/xhtml+xml"}) as respuesta:
                if respuesta.status != 200:
                    raise ErrorFuente(f"El Peruano respondió HTTP {respuesta.status}.")
                html = await respuesta.text()
    except ErrorFuente:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        raise ErrorFuente(
            f"No se pudo consultar El Peruano: {type(error).__name__}.") from error
    if len(CACHE) > 200:
        CACHE.clear()
    CACHE[url] = (ahora, html)
    return html


def _parsear_resultados(html: str, start: int) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    resultados = []
    vistos = set()

    for tarjeta in soup.select("div.rounded-xl.border"):
        enlace = tarjeta.select_one('a[href^="/dispositivo/"]')
        if not enlace:
            continue
        ruta = enlace.get("href", "")
        if ruta in vistos or not RUTA_DISPOSITIVO.fullmatch(ruta):
            continue
        vistos.add(ruta)

        entidad = tarjeta.select_one("p.text-primary")
        parrafos = tarjeta.select("p.text-muted-foreground")
        sumilla = tarjeta.select_one("a.text-xs.text-foreground")
        spans = tarjeta.find_all("span")
        identificador = spans[-2].get_text(" ", strip=True) if len(spans) >= 2 else ""
        fecha_texto = spans[-1].get_text(" ", strip=True) if spans else ""

        resultados.append({
            "id": identificador,
            "titulo": sumilla.get_text(" ", strip=True) if sumilla else "",
            "entidad": entidad.get_text(" ", strip=True) if entidad else "",
            "tipo": parrafos[0].get_text(" ", strip=True) if parrafos else "",
            "numero": parrafos[1].get_text(" ", strip=True) if len(parrafos) > 1 else "",
            "fecha": _fecha_iso(fecha_texto),
            "url": BASE + ruta,
        })

    coincidencia_total = re.search(r'totalHits\\?",\s*(\d+)', html)
    total = int(coincidencia_total.group(1)) if coincidencia_total else None
    coincidencia_pagina = re.search(r'paginatedBy\\?",\s*(\d+)', html)
    por_pagina = int(coincidencia_pagina.group(1)) if coincidencia_pagina else 20
    hay_siguiente = bool(total and start + por_pagina < min(total, 10000))
    return {
        "resultados": resultados,
        "total_aproximado": total,
        "por_pagina": por_pagina,
        "hay_siguiente": hay_siguiente,
        "siguiente_start": start + por_pagina if hay_siguiente else None,
    }


def _parsear_detalle(html: str, ruta: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    story = soup.find("div", class_="story")
    if not story:
        raise ErrorFuente("No se encontró el texto de la norma.")

    titulo = story.find("h1")
    encabezados = story.find_all("h2")
    parrafos = story.find_all("p", class_="cuerpo")
    fecha = ""
    for parrafo in parrafos:
        fecha = _fecha_iso(parrafo.get_text(" ", strip=True))
        if fecha:
            break

    texto = "\n".join(parrafo.get_text(" ", strip=True) for parrafo in parrafos)
    recortado = len(texto) > 20000
    coincidencia = RUTA_DISPOSITIVO.fullmatch(ruta)
    return {
        "id": coincidencia.group(2) if coincidencia else "",
        "tipo_publicacion": coincidencia.group(1) if coincidencia else "",
        "titulo": titulo.get_text(" ", strip=True) if titulo else "",
        "tipo_norma": encabezados[0].get_text(" ", strip=True) if encabezados else "",
        "numero": encabezados[1].get_text(" ", strip=True) if len(encabezados) > 1 else "",
        "fecha": fecha,
        "texto": texto[:20000],
        "texto_recortado": recortado,
    }


async def buscar(consulta: str, desde: str = "", hasta: str = "", start: int = 0) -> dict:
    """Busca normas por texto, con fechas opcionales."""
    consulta = (consulta or "").strip()
    if not 2 <= len(consulta) <= 100:
        raise ErrorFuente("La consulta debe tener entre 2 y 100 caracteres.")
    try:
        start = int(start)
    except (TypeError, ValueError) as error:
        raise ErrorFuente("El desplazamiento debe ser un número entero.") from error
    if not 0 <= start <= 10000:
        raise ErrorFuente("El desplazamiento debe estar entre 0 y 10.000.")

    parametros = {"query": consulta, "start": start}
    if desde:
        parametros["fechaIni"] = _fecha_compacta(desde)
    if hasta:
        parametros["fechaFin"] = _fecha_compacta(hasta)

    url = f"{BASE}/?{urlencode(parametros)}"
    html = await _get_html(url)
    datos = _parsear_resultados(html, start)
    return {
        "consulta": consulta,
        "desde": desde,
        "hasta": hasta,
        "start": start,
        **datos,
        "fuente": FUENTE,
        "licencia": LICENCIA,
        "url": url,
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def detalle(id_o_url: str) -> dict:
    """Devuelve el texto de una norma por su ruta o su URL completa."""
    valor = (id_o_url or "").strip()
    if valor.startswith(BASE):
        ruta = urlsplit(valor).path
    elif valor.startswith("/dispositivo/"):
        ruta = valor
    else:
        # Acepta también NL/2565770-1
        ruta = "/dispositivo/" + valor.lstrip("/")

    if not RUTA_DISPOSITIVO.fullmatch(ruta):
        raise ErrorFuente("Ruta de dispositivo no válida.")

    url = BASE + ruta
    html = await _get_html(url)
    datos = _parsear_detalle(html, ruta)
    return {
        **datos,
        "fuente": FUENTE,
        "licencia": LICENCIA,
        "url": url,
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
