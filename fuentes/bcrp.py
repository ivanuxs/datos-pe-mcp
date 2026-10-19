#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente de la API de series estadísticas del BCRP.

La API es pública, no requiere clave y devuelve JSON:
`https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/{desde}/{hasta}`

Las fechas van en formato `YYYY-MM-DD`. La serie `PD04640PD` es el tipo de cambio
SBS venta (soles por dólar).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta, timezone

import aiohttp

BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
SERIE_TIPO_CAMBIO = "PD04640PD"
CODIGO_RE = re.compile(r"^[A-Za-z0-9]{4,20}$")
MAX_DIAS = 3660
TTL = 3600.0
CACHE: dict[tuple[str, str, str], tuple[float, dict]] = {}

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


class ErrorFuente(ValueError):
    """La consulta a la fuente no es válida o falló."""


def _fecha(valor: str, defecto: date) -> date:
    if not valor:
        return defecto
    try:
        return datetime.strptime(valor.strip(), "%Y-%m-%d").date()
    except ValueError as error:
        raise ErrorFuente("Fecha no válida; usa el formato YYYY-MM-DD.") from error


def _periodo_iso(nombre: str) -> str:
    """Convierte `01.Oct.26` al formato ISO. Si no puede, deja el original."""
    partes = nombre.strip().split(".")
    if len(partes) == 3:
        dia, mes, anio = partes
        numero = MESES.get(mes.lower())
        if numero:
            try:
                anio_numero = int(anio)
                anio_numero += 2000 if anio_numero < 100 else 0
                return date(anio_numero, numero, int(dia)).isoformat()
            except ValueError:
                pass
    return nombre


def _valor(texto: str):
    texto = (texto or "").strip()
    if not texto or texto.lower() in {"n/d", "nd", "-", "—"}:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


async def _consultar(codigo: str, desde: str, hasta: str) -> dict:
    codigo = (codigo or "").strip().upper()
    if not CODIGO_RE.fullmatch(codigo):
        raise ErrorFuente("Código de serie no válido.")

    hoy = datetime.now(timezone.utc).date()
    inicio = _fecha(desde, hoy - timedelta(days=30))
    fin = _fecha(hasta, hoy)
    if inicio > fin:
        raise ErrorFuente("La fecha inicial no puede ser posterior a la final.")
    if (fin - inicio).days > MAX_DIAS:
        raise ErrorFuente("El rango máximo es de 10 años.")

    clave = (codigo, inicio.isoformat(), fin.isoformat())
    ahora = time.time()
    if clave in CACHE and ahora - CACHE[clave][0] < TTL:
        return CACHE[clave][1]

    url = f"{BASE}/{codigo}/json/{inicio.isoformat()}/{fin.isoformat()}"
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        ) as sesion:
            async with sesion.get(url, headers={
                    "User-Agent": "mcp-datos-pe/0.1",
                    "Accept": "application/json"}) as respuesta:
                if respuesta.status != 200:
                    raise ErrorFuente(f"BCRP respondió HTTP {respuesta.status}.")
                datos = await respuesta.json(content_type=None)
    except ErrorFuente:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        raise ErrorFuente(
            f"No se pudo consultar el BCRP: {type(error).__name__}.") from error
    except json.JSONDecodeError as error:
        raise ErrorFuente("El BCRP devolvió una respuesta no válida.") from error

    if not isinstance(datos, dict) or "periods" not in datos:
        raise ErrorFuente("El BCRP devolvió una respuesta inesperada.")

    config = datos.get("config") or {}
    series = config.get("series") or []
    periodos = []
    for periodo in datos.get("periods", []):
        valores = periodo.get("values") or []
        periodos.append({
            "fecha": _periodo_iso(periodo.get("name", "")),
            "valores": [_valor(valor) for valor in valores],
        })

    resultado = {
        "codigo": codigo,
        "titulo": config.get("title", ""),
        "series": [
            {"nombre": serie.get("name", ""), "decimales": serie.get("dec", "")}
            for serie in series
        ],
        "desde": inicio.isoformat(),
        "hasta": fin.isoformat(),
        "datos": periodos,
        "fuente": "Banco Central de Reserva del Perú (BCRP)",
        "url": url,
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if len(CACHE) > 200:
        CACHE.clear()
    CACHE[clave] = (ahora, resultado)
    return resultado


async def tipo_cambio(desde: str = "", hasta: str = "") -> dict:
    """Tipo de cambio SBS venta (soles por dólar)."""
    resultado = await _consultar(SERIE_TIPO_CAMBIO, desde, hasta)
    datos = [
        {"fecha": periodo["fecha"],
         "valor": periodo["valores"][0] if periodo["valores"] else None}
        for periodo in resultado["datos"]
    ]
    return {
        "serie": SERIE_TIPO_CAMBIO,
        "titulo": resultado["titulo"],
        "descripcion": resultado["series"][0]["nombre"] if resultado["series"] else "",
        "desde": resultado["desde"],
        "hasta": resultado["hasta"],
        "datos": datos,
        "fuente": resultado["fuente"],
        "url": resultado["url"],
        "consultado": resultado["consultado"],
        "nota": "Soles por dólar estadounidense (venta)." if datos
                else "Sin datos en el rango solicitado.",
    }


async def serie(codigo: str, desde: str = "", hasta: str = "") -> dict:
    """Cualquier serie del BCRP, por código."""
    return await _consultar(codigo, desde, hasta)
