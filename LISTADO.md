# Ficha de listado — Datos PE MCP

Metadatos para publicar este servidor en Glama, MCP.so, MCP Market y MCPize.
Copia y pega; no hay que reescribir nada.

## Identidad

| Campo | Valor |
|---|---|
| Nombre | Datos PE MCP |
| Slug | `datos-pe-mcp` |
| Título | Datos PE MCP — BCRP, contrataciones y normas del Perú |
| Versión | 0.3.0 |
| Categoría | Government Data |
| Etiquetas | `peru`, `bcrp`, `exchange-rate`, `procurement`, `legal`, `open-data`, `government`, `spanish` |
| Icono | `logo.png` (512×512) o `logo.svg` |
| Licencia del servicio | Uso comercial bajo token |
| Contacto | Ivan Medina Soto — `ivanuxs@gmail.com` — Perú |

## Descripción corta (≤160 caracteres)

> Datos públicos del Perú para agentes: tipo de cambio del BCRP, contrataciones del Estado y normas de El Peruano. Sin claves, sin parsear PDF.

English:

> Peruvian public data for agents: BCRP exchange rates, state procurement and official gazette norms. No keys, no PDF parsing.

## Descripción larga

> Tres fuentes oficiales del Perú, detrás de una sola interfaz. Del Banco Central de
> Reserva se obtienen el tipo de cambio SBS venta y cualquier serie estadística por su
> código. Del Organismo Especializado para las Contrataciones Públicas, los procesos de
> contratación abiertos: listado de los últimos, búsqueda por texto y detalle completo
> por identificador OCID. Del Diario Oficial El Peruano, la búsqueda de normas por
> materia y fecha, y el texto de cada norma.
>
> El Peruano no publica una API de datos: aquí la búsqueda se hace sobre el buscador
> oficial y el texto se devuelve limpio, sin navegador ni extracción manual de HTML.
> Los datos de contrataciones llegan en el estándar de Contrataciones Abiertas, listos
> para citar con su OCID.
>
> Pensado para agentes que responden preguntas sobre el Perú: cuánto está el dólar,
> quién ganó una licitación, qué dice una norma publicada esta semana.

English:

> Three official Peruvian sources behind one interface. From the Central Reserve Bank:
> the SBS selling exchange rate and any statistical series by code. From the public
> procurement agency: open contracting processes, latest listings, text search and full
> detail by OCID. From the official gazette El Peruano: search norms by subject and
> date, and read the full text of each one.
>
> El Peruano publishes no data API: search runs against the official search page and
> text is returned clean, with no browser and no manual HTML extraction. Procurement
> data arrives in the Open Contracting standard, ready to cite by OCID.
>
> Built for agents answering questions about Peru: what the dollar costs, who won a
> tender, what a norm published this week actually says.

## Conexión

| Campo | Valor |
|---|---|
| Endpoint | `https://datos-pe.hlquantlabs.trade/mcp` |
| Transporte | Streamable HTTP, con respuestas SSE |
| Autenticación | Cabecera `Authorization: Bearer <token>` |
| Sin token | `401`, no se ejecuta nada |

```json
{
  "mcpServers": {
    "datos-pe": {
      "type": "http",
      "url": "https://datos-pe.hlquantlabs.trade/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

## Herramientas (8)

| Herramienta | Parámetros | Fuente |
|---|---|---|
| `estado` | — | — |
| `tipo_cambio` | `desde`, `hasta` | BCRP, serie `PD04640PD` |
| `serie_bcrp` | `codigo`*, `desde`, `hasta` | BCRP |
| `contrataciones_ultimas` | `pagina` | OECE |
| `contrataciones_buscar` | `consulta`*, `paginas` | OECE |
| `contratacion_detalle` | `ocid`* | OECE |
| `norma_buscar` | `consulta`*, `desde`, `hasta`, `start` | El Peruano |
| `norma_detalle` | `id_o_url`* | El Peruano |

`*` obligatorio.

## Ejemplos de uso

- «¿A cuánto cerró el dólar ayer según el BCRP?»
- «Dame el tipo de cambio de todo septiembre y calcula el promedio.»
- «¿Qué licitaciones publicó el OECE esta semana?»
- «Busca contrataciones de "oxígeno medicinal" y dime el monto de la primera.»
- «¿Qué normas se publicaron sobre minería en octubre?»
- «Resume esta norma del Diario Oficial El Peruano.»

## Límites y atribución

- **BCRP:** series oficiales; el tipo de cambio es SBS venta, en soles por dólar. Las
  fechas van en formato `YYYY-MM-DD` y el rango máximo por consulta es de diez años.
- **OECE:** datos en el estándar Contrataciones Abiertas, con licencia **CC BY 4.0**.
  Se devuelven 20 registros por página; el filtrado por texto se hace página a página,
  porque la API no expone búsqueda.
- **El Peruano:** contenido del Diario Oficial El Peruano, con atribución. El buscador
  oficial limita a 10.000 resultados y el texto devuelto se recorta a 20.000
  caracteres, con aviso cuando ocurre.
- Caché de una hora en BCRP y El Peruano, diez minutos en OECE.
- No se inventan datos: si la fuente no responde, la herramienta devuelve el error.

## Verificación

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://datos-pe.hlquantlabs.trade/mcp   # 401

curl -s -X POST https://datos-pe.hlquantlabs.trade/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"prueba","version":"1"}}}'
```
