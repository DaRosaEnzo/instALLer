#!/usr/bin/env bash
# ==============================================================================
# InstALLer - Instalador Universal para Distribuciones Linux
# Detecta automáticamente la distribución (Ubuntu, Debian, Fedora, Arch, openSUSE, etc.)
# e instala las dependencias correspondientes con el gestor nativo.
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # Sin color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}          InstALLer - Instalador Universal Linux        ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Comprobar permisos de administrador para instalar paquetes
SUDO_CMD=""
if [ "$EUID" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO_CMD="sudo"
    else
        echo -e "${RED}[ERROR] Se requieren permisos de administrador (sudo) para instalar dependencias.${NC}"
        exit 1
    fi
fi

# 2. Detección automática del sistema operativo mediante /etc/os-release
DISTRO_ID="unknown"
DISTRO_NAME="Linux Genérico"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-}"
    DISTRO_NAME="${PRETTY_NAME:-$NAME}"
fi

echo -e "\n${CYAN}🔍 Sistema detectado: ${DISTRO_NAME} (${DISTRO_ID})${NC}"

# 3. Instalación de dependencias según el gestor del sistema
echo -e "\n${YELLOW}[1/4] Verificando e instalando dependencias nativas...${NC}"

installed_deps=false

# Familia Debian / Ubuntu / Mint / Pop!_OS / Zorin / elementary
if command -v apt-get >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}apt${NC}..."
    $SUDO_CMD apt-get update -qq || true
    $SUDO_CMD apt-get install -y --no-install-recommends \
        python3 \
        python3-gi \
        gir1.2-gtk-4.0 \
        gir1.2-adw-1 \
        gir1.2-gdkpixbuf-2.0 \
        desktop-file-utils \
        tar \
        xz-utils \
        unzip \
        pkexec
    installed_deps=true

# Familia Fedora / RHEL / Rocky / AlmaLinux / CentOS
elif command -v dnf >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}dnf${NC}..."
    $SUDO_CMD dnf install -y \
        python3 \
        python3-gobject \
        gtk4 \
        libadwaita \
        desktop-file-utils \
        tar \
        xz \
        unzip \
        polkit
    installed_deps=true

# Familia Arch Linux / Manjaro / EndeavourOS / Garuda
elif command -v pacman >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}pacman${NC}..."
    $SUDO_CMD pacman -S --noconfirm --needed \
        python \
        python-gobject \
        gtk4 \
        libadwaita \
        desktop-file-utils \
        tar \
        xz \
        unzip \
        polkit
    installed_deps=true

# Familia openSUSE (Tumbleweed / Leap)
elif command -v zypper >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}zypper${NC}..."
    $SUDO_CMD zypper --non-interactive install \
        python3 \
        python3-gobject \
        typelib-Gtk-4_0 \
        typelib-Adw-1 \
        desktop-file-utils \
        tar \
        xz \
        unzip \
        polkit
    installed_deps=true

# Solus
elif command -v eopkg >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}eopkg${NC}..."
    $SUDO_CMD eopkg install -y \
        python3 \
        python-gobject \
        libgtk-4 \
        libadwaita \
        desktop-file-utils \
        tar \
        xz \
        unzip \
        polkit
    installed_deps=true

# Void Linux
elif command -v xbps-install >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}xbps${NC}..."
    $SUDO_CMD xbps-install -Sy \
        python3 \
        python3-gobject \
        gtk4 \
        libadwaita \
        desktop-file-utils \
        tar \
        xz \
        unzip \
        polkit
    installed_deps=true

# Alpine Linux
elif command -v apk >/dev/null 2>&1; then
    echo -e "📦 Utilizando gestor ${BLUE}apk${NC}..."
    $SUDO_CMD apk add --no-cache \
        python3 \
        py3-gobject3 \
        gtk4.0 \
        libadwaita \
        desktop-file-utils \
        tar \
        xz \
        unzip \
        polkit
    installed_deps=true
fi

if [ "$installed_deps" = true ]; then
    echo -e "${GREEN}✓ Dependencias del sistema configuradas correctamente.${NC}"
else
    echo -e "${YELLOW}⚠️ No se pudo determinar el gestor de paquetes automáticamente.${NC}"
    echo -e "Asegurate de tener instalados: Python 3, PyGObject, GTK4, Libadwaita y pkexec."
fi

# 4. Directorios de instalación del sistema
INSTALL_DIR="/opt/installer"
BIN_LINK="/usr/local/bin/installer"
ICON_DIR_SVG="/usr/share/icons/hicolor/scalable/apps"
ICON_DIR_PNG="/usr/share/icons/hicolor/128x128/apps"
APPLICATIONS_DIR="/usr/share/applications"

echo -e "\n${YELLOW}[2/4] Copiando archivos de la aplicación a ${INSTALL_DIR}...${NC}"
$SUDO_CMD mkdir -p "${INSTALL_DIR}"
$SUDO_CMD cp -r "${SCRIPT_DIR}/installer" "${INSTALL_DIR}/"
$SUDO_CMD cp -r "${SCRIPT_DIR}/assets" "${INSTALL_DIR}/"
$SUDO_CMD cp -r "${SCRIPT_DIR}/data" "${INSTALL_DIR}/"

# Crear wrapper ejecutable en /usr/local/bin
echo -e "\n${YELLOW}[3/4] Creando comando de sistema 'installer'...${NC}"
$SUDO_CMD tee "${BIN_LINK}" > /dev/null << 'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/opt/installer:${PYTHONPATH}"
exec /usr/bin/python3 /opt/installer/installer/main.py "$@"
EOF

$SUDO_CMD chmod +x "${BIN_LINK}"

# 5. Instalar íconos y lanzador .desktop
echo -e "\n${YELLOW}[4/4] Registrando íconos y lanzador en el menú del sistema...${NC}"

# Íconos
$SUDO_CMD mkdir -p "${ICON_DIR_SVG}" "${ICON_DIR_PNG}"
if [ -f "${SCRIPT_DIR}/assets/installer.svg" ]; then
    $SUDO_CMD cp "${SCRIPT_DIR}/assets/installer.svg" "${ICON_DIR_SVG}/installer.svg"
fi
if [ -f "${SCRIPT_DIR}/assets/installer.png" ]; then
    $SUDO_CMD cp "${SCRIPT_DIR}/assets/installer.png" "${ICON_DIR_PNG}/installer.png"
fi

# Lanzador .desktop
$SUDO_CMD mkdir -p "${APPLICATIONS_DIR}"
$SUDO_CMD cp "${SCRIPT_DIR}/data/io.github.installer.InstALLer.desktop" "${APPLICATIONS_DIR}/installer.desktop"
$SUDO_CMD chmod 644 "${APPLICATIONS_DIR}/installer.desktop"

# Actualizar bases de datos de escritorio e íconos si están disponibles
if command -v update-desktop-database >/dev/null 2>&1; then
    $SUDO_CMD update-desktop-database "${APPLICATIONS_DIR}" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    $SUDO_CMD gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN} ¡InstALLer se ha instalado exitosamente en ${DISTRO_NAME}! ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "Ya podés iniciar InstALLer desde el menú de aplicaciones de tu sistema"
echo -e "o ejecutando el comando '${BLUE}installer${NC}' en tu terminal.\n"
