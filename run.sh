#!/usr/bin/env bash
# Script para ejecutar InstALLer directamente desde el código fuente o paquete Snap

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detectar si se ejecuta dentro del entorno Snap o en el árbol del proyecto
if [ -n "$SNAP" ] && [ -d "$SNAP/installer" ]; then
    ROOT_DIR="$SNAP"
elif [ -d "${SCRIPT_DIR}/installer" ]; then
    ROOT_DIR="${SCRIPT_DIR}"
elif [ -d "${SCRIPT_DIR}/../installer" ]; then
    ROOT_DIR="${SCRIPT_DIR}/.."
else
    ROOT_DIR="${SCRIPT_DIR}"
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH}"
exec python3 "${ROOT_DIR}/installer/main.py" "$@"
