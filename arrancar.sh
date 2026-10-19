#!/usr/bin/env bash
# Levanta el servidor MCP de datos del Perú (interno, 127.0.0.1) y el proxy con token.
# Uso: ./arrancar.sh        (Ctrl+C para todo)
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
    echo "✘ Falta el .env. Créalo desde la plantilla y dale permisos 600:"
    echo "    cp .env.example .env && chmod 600 .env"
    exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
    echo "✘ Falta el entorno: no existe .venv/bin/python."
    echo "    python3 -m venv --without-pip .venv    # y luego get-pip.py"
    echo "    .venv/bin/pip install -r requirements.txt"
    exit 1
fi

INTERNO=$(grep -E '^MCP_INTERNO_PUERTO=' .env | cut -d= -f2 | tr -d ' \r')
INTERNO=${INTERNO:-8950}

if (echo > "/dev/tcp/127.0.0.1/${INTERNO}") 2>/dev/null; then
    echo "✘ El puerto ${INTERNO} ya está ocupado: quedó otro MCP vivo."
    echo "    ./parar.sh   y vuelve a intentarlo."
    exit 1
fi

echo "· Arrancando el MCP de datos del Perú en 127.0.0.1:${INTERNO}…"
./.venv/bin/python servidor.py >> logs/mcp_salida.txt 2>&1 &
PID_MCP=$!

limpiar() {
    echo
    echo "· Cerrando el MCP (pid ${PID_MCP})…"
    kill "$PID_MCP" 2>/dev/null || true
}
trap limpiar EXIT
trap 'exit 130' INT TERM

LISTO=0
for _ in $(seq 1 40); do
    if (echo > "/dev/tcp/127.0.0.1/${INTERNO}") 2>/dev/null; then
        echo "✔ MCP interno escuchando."
        LISTO=1
        break
    fi
    sleep 0.5
done
if [[ "$LISTO" -ne 1 ]]; then
    echo "✘ El MCP no abrió el puerto ${INTERNO} en 20 s. Mira logs/mcp_salida.txt."
    exit 1
fi

echo "· Arrancando el proxy con token…"
./.venv/bin/python proxy.py &
PID_PROXY=$!
wait "$PID_PROXY"
