#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor MCP de datos públicos del Perú.

Fase 1: series del BCRP (`tipo_cambio` y `serie_bcrp`). Escucha solo en
`127.0.0.1`; la puerta pública es el proxy con token.

Uso:
    ./.venv/bin/python servidor.py
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from fuentes.bcrp import ErrorFuente
from fuentes.bcrp import serie as _serie_bcrp
from fuentes.bcrp import tipo_cambio as _tipo_cambio

RAIZ = Path(__file__).resolve().parent
ENV = RAIZ / ".env"

VERSION = "0.1.0"


def cargar_env(ruta: Path = ENV) -> dict:
    """Lee el `.env` sin dependencias externas."""
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


ENV_DATOS = cargar_env()
PUERTO = int(ENV_DATOS.get("MCP_INTERNO_PUERTO", "8950"))

SERVIDOR = MCPServer(
    name="datos-pe",
    title="Datos públicos del Perú",
    description="Series del BCRP y, más adelante, contrataciones y normas.",
    version=VERSION,
)


@SERVIDOR.tool()
def estado() -> dict:
    """Devuelve el estado del servicio de datos del Perú."""
    return {
        "servicio": "datos-pe",
        "version": VERSION,
        "estado": "ok",
        "fuentes": ["BCRP"],
    }


@SERVIDOR.tool()
async def tipo_cambio(desde: str = "", hasta: str = "") -> dict:
    """Consulta el tipo de cambio SBS venta (soles por dólar) en el BCRP.

    Args:
        desde: Fecha inicial YYYY-MM-DD; por defecto, hace 30 días.
        hasta: Fecha final YYYY-MM-DD; por defecto, hoy.
    """
    try:
        return await _tipo_cambio(desde, hasta)
    except ErrorFuente as error:
        raise ValueError(str(error)) from error


@SERVIDOR.tool()
async def serie_bcrp(codigo: str, desde: str = "", hasta: str = "") -> dict:
    """Consulta cualquier serie del BCRP por su código.

    Args:
        codigo: Código de la serie, por ejemplo `PD04640PD`.
        desde: Fecha inicial YYYY-MM-DD; por defecto, hace 30 días.
        hasta: Fecha final YYYY-MM-DD; por defecto, hoy.
    """
    try:
        return await _serie_bcrp(codigo, desde, hasta)
    except ErrorFuente as error:
        raise ValueError(str(error)) from error


def main() -> None:
    """Arranca el transporte Streamable HTTP en loopback."""
    SERVIDOR.run(transport="streamable-http", host="127.0.0.1", port=PUERTO)


if __name__ == "__main__":
    main()
