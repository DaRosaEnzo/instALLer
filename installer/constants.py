"""
InstALLer Constants
Constantes globales y rutas predeterminadas de la aplicación.
"""

from pathlib import Path
import os

APP_ID = "io.github.installer.InstALLer"
APP_NAME = "InstALLer"
APP_VERSION = "1.0.0"
APP_COMMENT = "Instalador y gestor visual de aplicaciones portables para Linux"

# Directorios de usuario (compatible con ejecución normal y Snap clásico)
_real_home_str = os.environ.get("SNAP_REAL_HOME") or os.environ.get("HOME")
USER_HOME = Path(_real_home_str).resolve() if _real_home_str else Path.home()

CONFIG_DIR = USER_HOME / ".config" / "installer"
REGISTRY_FILE = CONFIG_DIR / "registry.json"

LOCAL_APPS_DIR = USER_HOME / ".local" / "share" / "installer" / "apps"
SYSTEM_APPS_DIR = Path("/opt")

LOCAL_APPLICATIONS_DIR = USER_HOME / ".local" / "share" / "applications"
LOCAL_ICONS_DIR = USER_HOME / ".local" / "share" / "icons" / "hicolor"

TEMP_PREFIX = "installer-extract-"

# Extensiones de archivo comprimido soportadas
SUPPORTED_ARCHIVE_EXTENSIONS = (
    ".tar.gz",
    ".tgz",
    ".tar.xz",
    ".txz",
    ".tar.bz2",
    ".tbz2",
    ".zip",
    ".tar",
)

# Extensiones de imagen para íconos
ICON_EXTENSIONS = (".svg", ".png", ".ico")

# Binarios y archivos internos a ignorar durante la detección del ejecutable principal
IGNORED_BINARY_NAMES = {
    # Sandbox y utilidades internas de Chromium/Electron
    "chrome-sandbox",
    "chrome_sandbox",
    "chrome_crashpad_handler",
    "crashpad_handler",
    "nacl_helper",
    "nacl_helper_bootstrap",
    # Desinstaladores y actualizadores internos
    "uninstall",
    "uninstaller",
    "uninstall.sh",
    "unins000.exe",
    "updater",
    "updater.sh",
    "update.sh",
    "disable-usb-device-prompt",
    # Scripts o utilidades del sistema
    "xdg-open",
    "xdg-mime",
    "xdg-settings",
}

# Prefijos y sufijos de bibliotecas y datos a ignorar
IGNORED_EXTENSIONS = (
    ".so",
    ".so.",
    ".a",
    ".o",
    ".bin",
    ".dat",
    ".pak",
    ".asar",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".txt",
    ".md",
    ".html",
    ".js",
    ".css",
    ".png",
    ".svg",
    ".ico",
    ".jpg",
    ".jpeg",
    ".gif",
    ".wav",
    ".mp3",
    ".ogg",
)
