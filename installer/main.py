"""
InstALLer Main Entry Point
Punto de entrada de la aplicación Libadwaita / GTK4.
"""

import sys
import os
from pathlib import Path

# Asegurar que el paquete sea importable sin importar la ruta de ejecución
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from installer.constants import APP_ID, APP_NAME
from installer.ui.window import InstALLerWindow


class InstALLerApplication(Adw.Application):
    """Aplicación principal InstALLer."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = InstALLerWindow(self)
        self.window.present()

    def do_open(self, files, n_files, hint):
        """Maneja la apertura directa de archivos pasados por línea de comandos o doble clic."""
        self.do_activate()
        if n_files > 0 and self.window:
            first_path = files[0].get_path()
            if first_path:
                GLib.idle_add(lambda: self.window.install_view.process_source(first_path))


def main():
    """Función de arranque de InstALLer."""
    app = InstALLerApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
