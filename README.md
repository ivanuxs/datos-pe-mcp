# Datos PE MCP

Peruvian public data for AI agents behind one interface: BCRP exchange rates and
statistical series, state procurement in the Open Contracting standard, and norms from
the official gazette El Peruano — which publishes no data API, so the search page is
parsed and the text is returned clean.

**Español:** datos públicos del Perú para agentes. Tipo de cambio y series del BCRP,
contrataciones del Estado (OECE) y normas del Diario Oficial El Peruano. El Peruano no
tiene API de datos: aquí se busca en su buscador oficial y se devuelve el texto limpio.

## Connect

| | |
|---|---|
| Endpoint | `https://datos-pe.hlquantlabs.trade/mcp` |
| Transport | Streamable HTTP (SSE responses) |
| Auth | `Authorization: Bearer <token>` — without it, `401` |

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

## Tools

| Tool | Parameters | Source |
|---|---|---|
| `estado` | — | — |
| `tipo_cambio` | `desde`, `hasta` | BCRP series `PD04640PD` (SBS selling rate) |
| `serie_bcrp` | `codigo`*, `desde`, `hasta` | BCRP |
| `contrataciones_ultimas` | `pagina` | OECE |
| `contrataciones_buscar` | `consulta`*, `paginas` | OECE |
| `contratacion_detalle` | `ocid`* | OECE |
| `norma_buscar` | `consulta`*, `desde`, `hasta`, `start` | El Peruano |
| `norma_detalle` | `id_o_url`* | El Peruano |

`*` required.

## Notes and attribution

- **BCRP** — official series. Dates use `YYYY-MM-DD`; up to ten years per query.
- **OECE** — Open Contracting Data Standard, licensed **CC BY 4.0**. Twenty records per
  page; text filtering walks page by page because the API exposes no search.
- **El Peruano** — official gazette content, attributed. Its search caps at 10,000
  results; returned text is trimmed to 20,000 characters with a notice when that
  happens.
- Cache: one hour for BCRP and El Peruano, ten minutes for OECE.
- If a source fails, the tool reports the error. Nothing is invented.

## Docs

- [`LISTADO.md`](LISTADO.md) — listing metadata for MCP directories (ES/EN), tools,
  sources and a `curl` check.
- [`LEEME.md`](LEEME.md) — operating notes in Spanish: proxy, ports, systemd, nginx.

## License

MIT. See [LICENSE](LICENSE). The hosted service is sold separately under a token.

## Contact

`soporte@hlquantlabs.trade`
