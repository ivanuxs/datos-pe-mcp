# AGENTS.md — Reglas del proyecto `mcp/datos-pe`

Servidor **MCP** de datos públicos del Perú para agentes de IA. **BCRP** y **OECE**
(contrataciones) están operativos; **El Peruano** (normas) queda para la siguiente fase.

Proyecto **independiente**: no comparte código, entorno ni configuración con
`../navegador/`, `../auditoria/` ni `../../../Publicaciones/`.

---

## 0. Idioma

**Háblale siempre al usuario en español** (neutro peruano, con tuteo). También los
comentarios, los docstrings y los mensajes del código.

## 1. Plan antes de tocar

Ningún cambio se hace sin que el usuario diga **«procede»**. Primero se presenta el plan
con los pasos y una recomendación; se espera.

## 2. Claves y secretos

- Las claves viven **solo** en el `.env` (permisos `600`). Nunca en el código ni en git.
- **Todo valor del `.env` se enmascara** en los registros y en la consola: `MCP_TOKEN`,
  `MCP_TOKEN_NODIT` y cualquier otro.
- No se imprime nunca el contenido del `.env`, ni completo ni por partes.

## 3. Registros

- Se usa `utils_logging.py` (copia autónoma), no `print` sueltos.
- Escribe **sin `\n`**: todo va en una línea partida por `\r`. Para leerlo hay que normalizar.
- Los registros van en `logs/`.

## 4. El servidor no queda abierto

- El MCP escucha **solo** en `127.0.0.1:8950`.
- Lo único expuesto es el proxy en `8951`, y **exige token**: sin `Authorization: Bearer`
  correcto devuelve `401`.
- Cualquier herramienta nueva hereda esa protección.

## 5. Reinicio sin `sudo`

La unidad corre como `oficina-2` y tiene `Restart=on-failure` con `RestartSec=5`. Para
reiniciar sin contraseña se mata el proxy; `arrancar.sh` termina con código distinto de
cero, su `trap` cierra el MCP y systemd lo levanta otra vez:

```bash
pkill -TERM -f 'datos-pe/.venv/bin/python proxy.py'
```

- **No** se mata el servidor MCP a secas: el proxy quedaría vivo y el puerto ocupado.
- **No** se usa SIGKILL sobre `arrancar.sh`: no correría su `trap`.
- Tras unos segundos, comprobar `systemctl is-active mcp-datos-pe` y que `8950` y `8951`
  vuelvan a escuchar.

## 6. Alcance

- No se toca `../navegador/`, `../auditoria/` ni `../../../Publicaciones/`.
- Cada servicio hermano tiene su propio repositorio, `.env`, `.venv`, logs y token.
- No se añaden herramientas «por si acaso». Cada una se justifica y se prueba.

## 7. Fuentes y cumplimiento

- Solo fuentes públicas o con permiso expreso.
- Se respetan los términos de uso, los límites y la atribución de cada fuente.
- Toda salida debe incluir `fuente`, `url` y `consultado`.
- **No se consultan datos personales** ni se revenden bases de datos.
- Se cachea para no castigar a la fuente; el BCRP se cachea una hora.

## 8. Cuando pase a producción

- El piloto corre en `oficina-2`; luego se traslada a un servidor dedicado.
- La puerta pública es `datos-pe.hlquantlabs.trade`, con nginx delante y DNS de Cloudflare.
- El cobro irá por Nodit Agent PayGate o Cloudflare Monetization Gateway; nunca ambos a la vez.
