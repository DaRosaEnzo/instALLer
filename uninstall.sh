#!/usr/bin/env bash
# ==============================================================================
# InstALLer - Desinstalador del Sistema
# Remueve InstALLer, su comando de terminal, íconos y lanzador del sistema.
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}======================================================${NC}"
echo -e "${RED}             InstALLer - Desinstalador                  ${NC}"
echo -e "${RED}======================================================${NC}"

SUDO_CMD=""
if [ "$EUID" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO_CMD="sudo"
    else
        echo -e "${RED}[ERROR] Se requieren permisos de administrador (sudo) para desinstalar.${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}Eliminando archivos de InstALLer...${NC}"

# 1. Eliminar directorio de instalación
if [ -d "/opt/installer" ]; then
    $SUDO_CMD rm -rf "/opt/installer"
    echo -e "✓ Eliminado /opt/installer"
fi

# 2. Eliminar comando en /usr/local/bin
if [ -f "/usr/local/bin/installer" ]; then
    $SUDO_CMD rm -f "/usr/local/bin/installer"
    echo -e "✓ Eliminado /usr/local/bin/installer"
fi

# 3. Eliminar lanzador del menú
if [ -f "/usr/share/applications/installer.desktop" ]; then
    $SUDO_CMD rm -f "/usr/share/applications/installer.desktop"
    echo -e "✓ Eliminado lanzador de aplicaciones"
fi

# 4. Eliminar íconos
$SUDO_CMD rm -f "/usr/share/icons/hicolor/scalable/apps/installer.svg" 2>/dev/null || true
$SUDO_CMD rm -f "/usr/share/icons/hicolor/128x128/apps/installer.png" 2>/dev/null || true

# 5. Actualizar bases de datos
if command -v update-desktop-database >/dev/null 2>&1; then
    $SUDO_CMD update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    $SUDO_CMD gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN} InstALLer ha sido desinstalado de tu sistema con éxito.${NC}"
echo -e "${GREEN}======================================================${NC}\n"
