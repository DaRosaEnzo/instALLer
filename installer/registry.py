"""
InstALLer Registry & Uninstaller
Gestión del registro liviano (~/.config/installer/registry.json) y desinstalación limpia.
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from installer.constants import REGISTRY_FILE, CONFIG_DIR, LOCAL_APPLICATIONS_DIR
from installer.models import InstalledApp


class RegistryManager:
    """Administra el registro JSON y las operaciones de desinstalación de InstALLer."""

    def __init__(self, registry_path: Path = REGISTRY_FILE):
        self.registry_path = Path(registry_path)
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._write_raw({"version": 1, "apps": {}})

    def _read_raw(self) -> dict:
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": 1, "apps": {}}

    def _write_raw(self, data: dict) -> None:
        temp_file = self.registry_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.registry_path)

    def list_apps(self) -> List[InstalledApp]:
        """Devuelve la lista de aplicaciones instaladas ordenadas alfabéticamente."""
        data = self._read_raw()
        apps_dict = data.get("apps", {})
        apps = []
        for app_id, app_data in apps_dict.items():
            try:
                apps.append(InstalledApp.from_dict(app_data))
            except Exception:
                continue
        apps.sort(key=lambda a: a.name.lower())
        return apps

    def get_app(self, app_id: str) -> Optional[InstalledApp]:
        """Obtiene una aplicación por su ID."""
        data = self._read_raw()
        app_data = data.get("apps", {}).get(app_id)
        if app_data:
            return InstalledApp.from_dict(app_data)
        return None

    def register_app(self, app: InstalledApp) -> None:
        """Guarda o actualiza una aplicación en el registro."""
        data = self._read_raw()
        if "apps" not in data:
            data["apps"] = {}
        data["apps"][app.id] = app.to_dict()
        self._write_raw(data)

    def unregister_app(self, app_id: str) -> None:
        """Elimina una aplicación del registro sin alterar el sistema de archivos."""
        data = self._read_raw()
        if "apps" in data and app_id in data["apps"]:
            del data["apps"][app_id]
            self._write_raw(data)

    def uninstall_app(self, app_id: str) -> Tuple[bool, str]:
        """
        Desinstala una aplicación por completo:
        - Elimina el directorio de instalación (/opt/... mediante pkexec o ~/.local/share/installer/apps/...).
        - Elimina el lanzador .desktop en ~/.local/share/applications/.
        - Actualiza la base de datos de escritorio.
        - Elimina la entrada del registro JSON.
        """
        app = self.get_app(app_id)
        if not app:
            return False, f"La aplicación con ID '{app_id}' no está registrada."

        errors = []
        install_path = Path(app.install_path)

        # 1. Borrar directorio de la app
        if install_path.exists():
            if app.is_system or str(install_path).startswith("/opt"):
                # Requiere permisos de root mediante pkexec
                if not shutil.which("pkexec"):
                    return False, "No se encontró 'pkexec' en el sistema para solicitar permisos de administrador."
                cmd = ["pkexec", "rm", "-rf", str(install_path)]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    err = res.stderr.strip() or "Permiso denegado por el usuario"
                    return False, f"Error al eliminar la carpeta del sistema ({install_path}): {err}"
            else:
                try:
                    shutil.rmtree(install_path)
                except Exception as e:
                    errors.append(f"No se pudo eliminar {install_path}: {e}")

        # 2. Borrar lanzador .desktop
        desktop_file = Path(app.desktop_file)
        if desktop_file.exists():
            try:
                desktop_file.unlink()
            except Exception as e:
                errors.append(f"No se pudo eliminar el lanzador {desktop_file}: {e}")

        # 3. Actualizar base de datos de escritorio de Ubuntu
        try:
            subprocess.run(
                ["update-desktop-database", str(LOCAL_APPLICATIONS_DIR)],
                capture_output=True,
                check=False
            )
        except Exception:
            pass

        # 4. Remover del registro
        self.unregister_app(app_id)

        if errors:
            return True, f"Aplicación desinstalada con advertencias: {'; '.join(errors)}"
        return True, f"'{app.name}' ha sido desinstalada exitosamente sin dejar residuos."
