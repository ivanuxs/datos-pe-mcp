#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba de las herramientas de El Peruano.

Uso:
    .venv/bin/python pruebas/prueba_elperuano.py
"""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"
PROTOCOLO = "2025-06-18"
CLIENTE = {"name": "prueba-elperuano", "version": "1.0"}
DISPOSITIVO = "NL/2565770-1"

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
            comprobar("norma_buscar" in nombres, "tools/list incluye norma_buscar")
            comprobar("norma_detalle" in nombres, "tools/list incluye norma_detalle")

        async def llamar(nombre: str, argumentos: dict, ident: int) -> dict:
            async with http.post(endpoint, headers=cabeceras, json={
                    "jsonrpc": "2.0", "id": ident, "method": "tools/call",
                    "params": {"name": nombre, "arguments": argumentos}}) as respuesta:
                return await leer_jsonrpc(respuesta)

        print("== norma_buscar ==")
        datos = await llamar("norma_buscar", {"consulta": "mineria", "start": 0}, 10)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "norma_buscar no devuelve isError")
        resultados = resultado.get("resultados") or []
        comprobar(bool(resultados), "devuelve resultados")
        primero = resultados[0] if resultados else {}
        comprobar(bool(primero.get("id")), "el primer resultado tiene id")
        comprobar(bool(primero.get("titulo")), "el primer resultado tiene título")
        comprobar(str(primero.get("url", "")).startswith("https://busquedas.elperuano.pe/"),
                  "el primer resultado tiene URL")
        comprobar((resultado.get("total_aproximado") or 0) > 0,
                  f"informa el total aproximado ({resultado.get('total_aproximado')})")
        comprobar(resultado.get("fuente") == "Diario Oficial El Peruano",
                  "incluye la fuente")

        print(f"== norma_detalle {DISPOSITIVO} ==")
        datos = await llamar("norma_detalle", {"id_o_url": DISPOSITIVO}, 11)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "norma_detalle no devuelve isError")
        comprobar(bool(resultado.get("titulo")), "incluye el título")
        comprobar(bool(resultado.get("tipo_norma")), "incluye el tipo de norma")
        comprobar(bool(resultado.get("numero")), "incluye el número")
        comprobar(resultado.get("fecha") == "2026-10-16",
                  f"incluye la fecha ({resultado.get('fecha')})")
        comprobar(len(resultado.get("texto", "")) > 500,
                  f"incluye el texto ({len(resultado.get('texto', ''))} caracteres)")

        print("== errores ==")
        datos = await llamar("norma_buscar", {"consulta": "a"}, 12)
        resultado = datos.get("result") or {}
        comprobar(bool(resultado.get("isError")) or bool(datos.get("error")),
                  "rechaza una consulta demasiado corta")

        datos = await llamar("norma_detalle", {"id_o_url": "x"}, 13)
        resultado = datos.get("result") or {}
        comprobar(bool(resultado.get("isError")) or bool(datos.get("error")),
                  "rechaza una ruta inválida")

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
