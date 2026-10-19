#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba de las herramientas de contrataciones OECE.

Uso:
    .venv/bin/python pruebas/prueba_oece.py
"""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"
PROTOCOLO = "2025-06-18"
CLIENTE = {"name": "prueba-oece", "version": "1.0"}

FALLOS = 0


def comprobar(condicion: bool, descripcion: str) -> None:
    global FALLOS
    if condicion:
        print(f"✔ {descripcion}")
    else:
        FALLOS += 1
        print(f"✘ {descripcion}")


def cargar_env(ruta: Path = ENV) -> dict:
    datos = {}
    try:
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            datos[clave.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        pass
    return datos


async def leer_jsonrpc(respuesta: aiohttp.ClientResponse) -> dict:
    tipo = respuesta.headers.get("Content-Type", "")
    if "text/event-stream" in tipo:
        async for linea in respuesta.content:
            texto = linea.decode("utf-8", "replace").strip()
            if texto.startswith("data:"):
                return json.loads(texto[5:].strip())
        raise RuntimeError("respuesta SSE sin datos")
    return await respuesta.json()


def extraer(datos: dict) -> dict:
    resultado = datos.get("result") or {}
    estructurado = resultado.get("structuredContent")
    if isinstance(estructurado, dict):
        return estructurado
    for parte in resultado.get("content", []):
        if parte.get("type") == "text":
            try:
                return json.loads(parte.get("text", ""))
            except json.JSONDecodeError:
                continue
    return {}


async def main() -> int:
    env = cargar_env()
    token = env.get("MCP_TOKEN", "").strip()
    puerto = env.get("MCP_PROXY_PUERTO", "8951").strip() or "8951"
    if not token:
        print("✘ Falta MCP_TOKEN en el .env.")
        return 2

    endpoint = f"http://127.0.0.1:{puerto}/mcp"
    tiempo = aiohttp.ClientTimeout(total=120, sock_connect=10, sock_read=120)
    cabeceras = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    async with aiohttp.ClientSession(timeout=tiempo) as http:
        async with http.post(endpoint, headers=cabeceras, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": PROTOCOLO,
                           "capabilities": {}, "clientInfo": CLIENTE}}) as respuesta:
            sesion = respuesta.headers.get("Mcp-Session-Id")
            await leer_jsonrpc(respuesta)
        if not sesion:
            print("✘ initialize no devolvió sesión.")
            return 1
        cabeceras["Mcp-Session-Id"] = sesion
        async with http.post(endpoint, headers=cabeceras, json={
                "jsonrpc": "2.0", "method": "notifications/initialized"}) as respuesta:
            await respuesta.read()

        print("== tools/list ==")
        async with http.post(endpoint, headers=cabeceras, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) as respuesta:
            datos = await leer_jsonrpc(respuesta)
            nombres = [t.get("name") for t in (datos.get("result") or {}).get("tools", [])]
            for herramienta in ("contrataciones_ultimas", "contratacion_detalle",
                                "contrataciones_buscar"):
                comprobar(herramienta in nombres, f"tools/list incluye {herramienta}")

        async def llamar(nombre: str, argumentos: dict, ident: int) -> dict:
            async with http.post(endpoint, headers=cabeceras, json={
                    "jsonrpc": "2.0", "id": ident, "method": "tools/call",
                    "params": {"name": nombre, "arguments": argumentos}}) as respuesta:
                return await leer_jsonrpc(respuesta)

        print("== contrataciones_ultimas ==")
        datos = await llamar("contrataciones_ultimas", {"pagina": 1}, 10)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "contrataciones_ultimas no devuelve isError")
        registros = resultado.get("registros") or []
        comprobar(bool(registros), "devuelve registros")
        comprobar(len(registros) <= 20, f"devuelve como máximo 20 registros ({len(registros)})")
        primero = registros[0] if registros else {}
        comprobar(bool(primero.get("ocid")), "el primer registro tiene OCID")
        comprobar(bool(primero.get("comprador")), "el primer registro tiene comprador")
        comprobar(resultado.get("licencia") == "CC BY 4.0", "incluye la licencia CC BY 4.0")

        ocid = primero.get("ocid", "")
        print(f"== contratacion_detalle {ocid} ==")
        datos = await llamar("contratacion_detalle", {"ocid": ocid}, 11)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "contratacion_detalle no devuelve isError")
        comprobar((resultado.get("resumen") or {}).get("ocid") == ocid,
                  "el detalle corresponde al OCID")
        comprobar("adjudicaciones" in resultado, "incluye adjudicaciones")
        comprobar("contratos" in resultado, "incluye contratos")

        print("== contrataciones_buscar ==")
        datos = await llamar("contrataciones_buscar", {
            "consulta": ocid, "paginas": 1}, 12)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "contrataciones_buscar no devuelve isError")
        comprobar(bool(resultado.get("coincidencias")),
                  "encuentra el registro por su OCID")
        comprobar(resultado.get("registros_revisados", 0) > 0,
                  "informa cuántos registros revisó")

        print("== errores ==")
        datos = await llamar("contrataciones_ultimas", {"pagina": 0}, 13)
        resultado = datos.get("result") or {}
        comprobar(bool(resultado.get("isError")) or bool(datos.get("error")),
                  "rechaza una página inválida")

        datos = await llamar("contratacion_detalle", {"ocid": "x"}, 14)
        resultado = datos.get("result") or {}
        comprobar(bool(resultado.get("isError")) or bool(datos.get("error")),
                  "rechaza un OCID inválido")

    print()
    if FALLOS:
        print(f"✘ {FALLOS} comprobación(es) fallida(s).")
        return 1
    print("✔ Todas las comprobaciones pasaron.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n· Prueba cancelada.")
        sys.exit(130)
