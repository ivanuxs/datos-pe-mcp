# mcp/datos-pe

Servidor **MCP** que entrega datos públicos del Perú a agentes de IA.

- **Fase 1:** series del **BCRP**.
- **Fase 2:** contrataciones abiertas de la **OECE** (OCDS 1.1).
- **Fase 3 (actual):** normas del **Diario Oficial El Peruano**.

Proyecto hermano de `../navegador/` y `../auditoria/`, con su propio entorno, token,
registros y repositorio.

---

## Arquitectura

```
Agente
  │  Authorization: Bearer <MCP_TOKEN>
  ▼
DNS de Cloudflare  →  nginx de oficina-2 (datos-pe.hlquantlabs.trade)
  │  proxy_pass a 127.0.0.1:8951
  ▼
proxy.py (valida token, 401 si falta)
  │
  ▼
127.0.0.1:8950            ← servidor MCP (SDK oficial mcp 2.3.0)
  │
  ▼
API pública del BCRP
```

- El MCP escucha **solo** en `127.0.0.1`.
- El proxy escucha en `0.0.0.0:8951`; solo lo alcanza nginx por `127.0.0.1`.
- Todo corre inicialmente en **oficina-2**.

## Herramientas

| Herramienta | Qué devuelve |
|---|---|
| `estado` | Versión, estado y fuentes activas |
| `tipo_cambio` | Tipo de cambio SBS venta (soles por dólar) |
| `serie_bcrp` | Cualquier serie del BCRP por código |
| `contrataciones_ultimas` | Últimos 20 procesos de contratación (OECE) |
| `contratacion_detalle` | Detalle de un proceso por OCID |
| `contrataciones_buscar` | Búsqueda local sobre las páginas consultadas |
| `norma_buscar` | Busca normas en El Peruano, con fechas opcionales |
| `norma_detalle` | Texto completo de una norma por ruta o URL |

`tipo_cambio` y `serie_bcrp` aceptan `desde` y `hasta` en formato `YYYY-MM-DD`. Por
defecto consultan los últimos 30 días. El rango máximo es de 10 años.

Serie verificada:

| Código | Descripción |
|---|---|
| `PD04640PD` | Tipo de cambio – TC Sistema bancario SBS – Venta |

Las contrataciones usan la API pública de la OECE: 20 registros por página, sin filtros
en el servidor. `contrataciones_buscar` revisa hasta 10 páginas y filtra localmente.

Cada respuesta incluye `fuente`, `url` y `consultado`.

## Arrancar

Con systemd, una vez instalada la unidad:

```bash
sudo cp sistema/mcp-datos-pe.service /etc/systemd/system/mcp-datos-pe.service
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-datos-pe
sudo systemctl status mcp-datos-pe
```

A mano, para depurar:

```bash
./arrancar.sh          # Ctrl+C o ./parar.sh para cerrar
```

> Con el servicio activo, `./parar.sh` no sirve para apagarlo — systemd lo resucita a los
> 5 s. Se para con `sudo systemctl stop mcp-datos-pe`.

## Probar

```bash
./pruebas/prueba_mcp.sh                      # 401 sin token / 200 con token
.venv/bin/python pruebas/prueba_bcrp.py      # tipo_cambio y serie_bcrp
.venv/bin/python pruebas/prueba_oece.py      # contrataciones OECE
.venv/bin/python pruebas/prueba_elperuano.py # normas de El Peruano
```

## Configuración (`.env`, permisos 600)

| Clave | Para qué |
|---|---|
| `MCP_INTERNO_PUERTO` | Puerto del servidor MCP (127.0.0.1) |
| `MCP_PROXY_PUERTO` | Puerto del proxy con token (0.0.0.0) |
| `MCP_TOKEN` | Token que deben enviar los clientes |
| `MCP_TOKEN_NODIT` | Token exclusivo de Nodit; se revoca quitando su línea y reiniciando |
| `MCP_DOMINIO` | `datos-pe.hlquantlabs.trade` |
| `X402_PRECIO_USD` | Precio por llamada, para el alta en Nodit |
| `X402_RED` | `base` |

La plantilla está en `.env.example`:

```bash
cp .env.example .env && chmod 600 .env
openssl rand -hex 32        # valor para MCP_TOKEN
```

**Ningún valor del `.env` se imprime**: `proxy.py` los enmascara todos antes de registrar.

## Nginx y DNS

El registro DNS `datos-pe.hlquantlabs.trade` ya existe. Para dejar HTTPS:

```bash
sudo cp nginx/datos-pe.hlquantlabs.trade.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/datos-pe.hlquantlabs.trade.conf \
           /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d datos-pe.hlquantlabs.trade --redirect
```

## Fuentes y atribución

- **BCRP** — API pública de series estadísticas. Se atribuye al Banco Central de Reserva
  del Perú y se enlaza la URL de la consulta.
- **OECE** — Contrataciones Abiertas, OCDS 1.1, licencia CC BY 4.0 (fase 2).
- **El Peruano** — normas legales; no hay API JSON, se parsea el HTML del buscador. Se
  atribuye al Diario Oficial El Peruano y se enlaza cada dispositivo.

No se consultan datos personales ni se revenden bases de datos.

## Avisos

- `utils_logging.py` escribe **sin `\n`**: hay que normalizar los registros al leerlos.
- Cada servicio hermano tiene su propio repositorio y su propio entorno.
