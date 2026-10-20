#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor MCP de datos públicos del Perú.

Reúne series del BCRP, contrataciones del Estado (OECE) y normas del Diario
Oficial El Peruano. Escucha solo en `127.0.0.1`; la puerta pública es el proxy
con token.

Uso:
    ./.venv/bin/python servidor.py
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from fuentes.bcrp import ErrorFuente
from fuentes.bcrp import serie as _serie_bcrp
from fuentes.bcrp import tipo_cambio as _tipo_cambio
from fuentes.oece import ErrorFuente as ErrorOece
from fuentes.oece import buscar as _buscar_contrataciones
from fuentes.oece import detalle as _detalle_contratacion
from fuentes.oece import ultimas as _ultimas_contrataciones
from fuentes.elperuano import ErrorFuente as ErrorPeruano
from fuentes.elperuano import buscar as _buscar_normas
from fuentes.elperuano import detalle as _detalle_norma

RAIZ = Path(__file__).resolve().parent
ENV = RAIZ / ".env"

VERSION = "0.3.0"


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
    description=(
        "Tipo de cambio y series del BCRP, contrataciones del Estado y normas "
        "del Diario Oficial El Peruano."
    ),
    version=VERSION,
)


@SERVIDOR.tool()
def estado() -> dict:
    """Devuelve el estado del servicio de datos del Perú."""
    return {
        "servicio": "datos-pe",
        "version": VERSION,
        "estado": "ok",
        "fuentes": ["BCRP", "OECE", "El Peruano"],
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


@SERVIDOR.tool()
async def contrataciones_ultimas(pagina: int = 1) -> dict:
    """Devuelve los últimos 20 procesos de contratación publicados.

    Args:
        pagina: Número de página, desde 1.
    """
    try:
        return await _ultimas_contrataciones(pagina)
    except ErrorOece as error:
        raise ValueError(str(error)) from error


@SERVIDOR.tool()
async def contratacion_detalle(ocid: str) -> dict:
    """Devuelve el detalle de un proceso por su OCID.

    Args:
        ocid: Identificador OCDS, por ejemplo `ocds-dgv273-seacev3-999999`.
    """
    try:
        return await _detalle_contratacion(ocid)
    except ErrorOece as error:
        raise ValueError(str(error)) from error


@SERVIDOR.tool()
async def contrataciones_buscar(consulta: str, paginas: int = 5) -> dict:
    """Busca procesos por texto en las páginas indicadas.

    La API de la OECE no filtra en el servidor: se revisan las páginas y se
    filtra localmente. Cada página trae 20 registros.

    Args:
        consulta: Texto a buscar (comprador, título, descripción u OCID).
        paginas: Cuántas páginas revisar, de 1 a 10.
    """
    try:
        return await _buscar_contrataciones(consulta, paginas)
    except ErrorOece as error:
        raise ValueError(str(error)) from error


@SERVIDOR.tool()
async def norma_buscar(consulta: str, desde: str = "", hasta: str = "",
                       start: int = 0) -> dict:
    """Busca normas en el Diario Oficial El Peruano.

    Args:
        consulta: Texto a buscar, entre 2 y 100 caracteres.
        desde: Fecha inicial YYYY-MM-DD (opcional).
        hasta: Fecha final YYYY-MM-DD (opcional).
        start: Desplazamiento de resultados; 0 es la primera página.
    """
    try:
        return await _buscar_normas(consulta, desde, hasta, start)
    except ErrorPeruano as error:
        raise ValueError(str(error)) from error


@SERVIDOR.tool()
async def norma_detalle(id_o_url: str) -> dict:
    """Devuelve el texto de una norma por su ruta o URL.

    Args:
        id_o_url: Ruta como `NL/2565770-1` o la URL completa del dispositivo.
    """
    try:
        return await _detalle_norma(id_o_url)
    except ErrorPeruano as error:
        raise ValueError(str(error)) from error


def main() -> None:
    """Arranca el transporte Streamable HTTP en loopback."""
    SERVIDOR.run(transport="streamable-http", host="127.0.0.1", port=PUERTO)


if __name__ == "__main__":
    main()
