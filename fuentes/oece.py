#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente de Contrataciones Abiertas de la OECE (OCDS 1.1).

API pública:
`https://contratacionesabiertas.oece.gob.pe/api/v1/records?page=N`
`https://contratacionesabiertas.oece.gob.pe/api/v1/record/{ocid}`

La API no ofrece filtros en el servidor: solo paginación de 20 registros. La
búsqueda se hace localmente sobre las páginas consultadas, con caché.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from datetime import datetime, timezone

import aiohttp

BASE = "https://contratacionesabiertas.oece.gob.pe/api/v1"
FUENTE = "OECE – Contrataciones Abiertas (OCDS 1.1)"
LICENCIA = "CC BY 4.0"
TTL = 600.0
MAX_PAGINAS = 10
OCID_RE = re.compile(r"^[A-Za-z0-9._-]{5,120}$")
CACHE: dict[str, tuple[float, dict]] = {}


class ErrorFuente(ValueError):
    """La consulta a la OECE no es válida o falló."""


def _normalizar(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter)).lower()


def _entero(valor, nombre: str, minimo: int, maximo: int) -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ErrorFuente(f"{nombre} debe ser un número entero.") from error
    if not minimo <= numero <= maximo:
        raise ErrorFuente(f"{nombre} debe estar entre {minimo} y {maximo}.")
    return numero


async def _get_json(url: str) -> dict:
    ahora = time.time()
    if url in CACHE and ahora - CACHE[url][0] < TTL:
        return CACHE[url][1]
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=25)
        ) as sesion:
            async with sesion.get(url, headers={
                    "Accept": "application/json",
                    "User-Agent": "mcp-datos-pe/0.2 (+https://datos-pe.hlquantlabs.trade)"}) as respuesta:
                if respuesta.status == 404:
                    raise ErrorFuente("No se encontró el registro solicitado.")
                if respuesta.status != 200:
                    raise ErrorFuente(f"OECE respondió HTTP {respuesta.status}.")
                datos = await respuesta.json(content_type=None)
    except ErrorFuente:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        raise ErrorFuente(
            f"No se pudo consultar la OECE: {type(error).__name__}.") from error
    except json.JSONDecodeError as error:
        raise ErrorFuente("La OECE devolvió una respuesta no válida.") from error
    if not isinstance(datos, dict):
        raise ErrorFuente("La OECE devolvió una respuesta inesperada.")
    if len(CACHE) > 200:
        CACHE.clear()
    CACHE[url] = (ahora, datos)
    return datos


def _resumen(registro: dict) -> dict:
    compiled = registro.get("compiledRelease") or {}
    tender = compiled.get("tender") or {}
    buyer = compiled.get("buyer") or {}
    valor = tender.get("value") or {}
    return {
        "ocid": registro.get("ocid", ""),
        "titulo": tender.get("title", ""),
        "descripcion": (tender.get("description") or "")[:300],
        "estado": tender.get("status", ""),
        "fecha": compiled.get("date") or tender.get("datePublished", ""),
        "comprador": buyer.get("name", ""),
        "monto": valor.get("amount"),
        "moneda": valor.get("currency", ""),
        "metodo": tender.get("procurementMethodDetails")
                  or tender.get("procurementMethod", ""),
        "categoria": tender.get("mainProcurementCategory", ""),
    }


def _texto_busqueda(registro: dict) -> str:
    compiled = registro.get("compiledRelease") or {}
    tender = compiled.get("tender") or {}
    partes = [
        registro.get("ocid", ""),
        tender.get("title", ""),
        tender.get("description", ""),
        (compiled.get("buyer") or {}).get("name", ""),
        tender.get("procurementMethodDetails", ""),
        tender.get("mainProcurementCategory", ""),
    ]
    for item in tender.get("items") or []:
        partes.append(item.get("description", ""))
    for parte in compiled.get("parties") or []:
        partes.append(parte.get("name", ""))
    return _normalizar(" ".join(str(parte) for parte in partes if parte))


async def ultimas(pagina: int = 1) -> dict:
    """Últimos 20 procesos publicados, por página."""
    pagina = _entero(pagina, "La página", 1, 100000)
    url = f"{BASE}/records?page={pagina}"
    datos = await _get_json(url)
    registros = datos.get("records") or []
    return {
        "pagina": pagina,
        "registros": [_resumen(registro) for registro in registros],
        "hay_siguiente": bool((datos.get("links") or {}).get("next")),
        "fuente": FUENTE,
        "licencia": LICENCIA,
        "url": url,
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def detalle(ocid: str) -> dict:
    """Detalle normalizado de un proceso por su OCID."""
    ocid = (ocid or "").strip()
    if not OCID_RE.fullmatch(ocid):
        raise ErrorFuente("OCID no válido.")

    url = f"{BASE}/record/{ocid}"
    datos = await _get_json(url)
    registros = datos.get("records") or []
    if not registros:
        raise ErrorFuente("No se encontró el registro solicitado.")
    registro = registros[0]
    compiled = registro.get("compiledRelease") or {}
    tender = compiled.get("tender") or {}

    adjudicaciones = []
    for adjudicacion in (compiled.get("awards") or [])[:20]:
        valor = adjudicacion.get("value") or {}
        adjudicaciones.append({
            "id": adjudicacion.get("id", ""),
            "estado": adjudicacion.get("status", ""),
            "fecha": adjudicacion.get("date", ""),
            "monto": valor.get("amount"),
            "moneda": valor.get("currency", ""),
            "proveedores": [
                proveedor.get("name", "")
                for proveedor in (adjudicacion.get("suppliers") or [])
                if proveedor.get("name")
            ],
        })

    contratos = []
    for contrato in (compiled.get("contracts") or [])[:20]:
        valor = contrato.get("value") or {}
        contratos.append({
            "id": contrato.get("id", ""),
            "estado": contrato.get("status", ""),
            "fecha": contrato.get("dateSigned", ""),
            "monto": valor.get("amount"),
            "moneda": valor.get("currency", ""),
            "proveedores": [
                proveedor.get("name", "")
                for proveedor in (contrato.get("suppliers") or [])
                if proveedor.get("name")
            ],
        })

    items = []
    for item in (tender.get("items") or [])[:30]:
        items.append({
            "id": item.get("id", ""),
            "descripcion": item.get("description", ""),
            "cantidad": item.get("quantity"),
            "unidad": (item.get("unit") or {}).get("name", ""),
        })

    documentos = []
    for documento in (tender.get("documents") or [])[:10]:
        documentos.append({
            "titulo": documento.get("title", ""),
            "tipo": documento.get("documentType", ""),
            "url": documento.get("url", ""),
        })

    partes = []
    for parte in (compiled.get("parties") or [])[:30]:
        partes.append({
            "nombre": parte.get("name", ""),
            "roles": parte.get("roles", []),
        })

    return {
        "resumen": _resumen(registro),
        "adjudicaciones": adjudicaciones,
        "contratos": contratos,
        "items": items,
        "documentos": documentos,
        "partes": partes,
        "fuente": FUENTE,
        "licencia": LICENCIA,
        "url": url,
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def buscar(consulta: str, paginas: int = 5) -> dict:
    """Busca localmente en las páginas indicadas (la API no filtra)."""
    consulta = (consulta or "").strip()
    if not 2 <= len(consulta) <= 100:
        raise ErrorFuente("La consulta debe tener entre 2 y 100 caracteres.")
    paginas = _entero(paginas, "El número de páginas", 1, MAX_PAGINAS)

    terminos = [termino for termino in _normalizar(consulta).split() if termino]
    if not terminos:
        raise ErrorFuente("La consulta no tiene términos útiles.")

    coincidencias = []
    revisados = 0
    for pagina in range(1, paginas + 1):
        url = f"{BASE}/records?page={pagina}"
        datos = await _get_json(url)
        for registro in datos.get("records") or []:
            revisados += 1
            texto = _texto_busqueda(registro)
            if all(termino in texto for termino in terminos):
                coincidencias.append(_resumen(registro))
                if len(coincidencias) >= 100:
                    break
        if len(coincidencias) >= 100:
            break

    return {
        "consulta": consulta,
        "paginas_consultadas": paginas,
        "registros_revisados": revisados,
        "coincidencias": coincidencias,
        "nota": "La API de la OECE no filtra en el servidor; se revisaron las "
                "páginas indicadas y se filtró localmente.",
        "fuente": FUENTE,
        "licencia": LICENCIA,
        "url": f"{BASE}/records",
        "consultado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
