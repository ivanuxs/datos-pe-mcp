#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba de las herramientas BCRP a través del proxy.

Uso:
    .venv/bin/python pruebas/prueba_bcrp.py
"""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp

RAIZ = Path(__file__).resolve().parent.parent
ENV = RAIZ / ".env"
PROTOCOLO = "2025-06-18"
CLIENTE = {"name": "prueba-bcrp", "version": "1.0"}
DESDE = "2026-10-01"
HASTA = "2026-10-16"

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
    tiempo = aiohttp.ClientTimeout(total=60, sock_connect=10, sock_read=60)
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
            comprobar("tipo_cambio" in nombres, "tools/list incluye tipo_cambio")
            comprobar("serie_bcrp" in nombres, "tools/list incluye serie_bcrp")

        async def llamar(nombre: str, argumentos: dict, ident: int) -> dict:
            async with http.post(endpoint, headers=cabeceras, json={
                    "jsonrpc": "2.0", "id": ident, "method": "tools/call",
                    "params": {"name": nombre, "arguments": argumentos}}) as respuesta:
                return await leer_jsonrpc(respuesta)

        print("== tipo_cambio ==")
        datos = await llamar("tipo_cambio", {"desde": DESDE, "hasta": HASTA}, 10)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "tipo_cambio no devuelve isError")
        comprobar(bool(resultado.get("datos")), "tipo_cambio devuelve datos")
        primero = (resultado.get("datos") or [{}])[0]
        comprobar(str(primero.get("fecha", "")).startswith("2026-10-"),
                  f"fecha en formato ISO ({primero.get('fecha')})")
        comprobar(isinstance(primero.get("valor"), (int, float)),
                  f"valor numérico ({primero.get('valor')})")
        comprobar(resultado.get("fuente", "").startswith("Banco Central"),
                  "incluye la fuente BCRP")

        print("== serie_bcrp ==")
        datos = await llamar("serie_bcrp", {
            "codigo": "PD04640PD", "desde": DESDE, "hasta": HASTA}, 11)
        resultado = extraer(datos)
        comprobar(not (datos.get("result") or {}).get("isError"),
                  "serie_bcrp no devuelve isError")
        comprobar(resultado.get("codigo") == "PD04640PD",
                  "devuelve el código consultado")
        comprobar(bool(resultado.get("series")), "incluye la descripción de la serie")
        comprobar(bool(resultado.get("datos")), "incluye datos")

        print("== errores ==")
        datos = await llamar("serie_bcrp", {"codigo": "ZZ"}, 12)
        resultado = datos.get("result") or {}
        comprobar(bool(resultado.get("isError")) or bool(datos.get("error")),
                  "rechaza un código inválido")

        datos = await llamar("tipo_cambio", {"desde": "2026-13-01"}, 13)
        resultado = datos.get("result") or {}
        comprobar(bool(resultado.get("isError")) or bool(datos.get("error")),
                  "rechaza una fecha inválida")

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
