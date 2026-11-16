"""
InstALLer Installer
Lógica de instalación, permisos elevados (pkexec), creación de lanzadores .desktop
y actualización de aplicaciones portables.
"""

import os
import shutil
import stat
import subprocess
import datetime
from pathlib import Path
from typing import Tuple, Optional, Callable

from installer.constants import (
    LOCAL_APPS_DIR,
    SYSTEM_APPS_DIR,
    LOCAL_APPLICATIONS_DIR,
    APP_NAME as INSTALLER_NAME,
)
from installer.models import AppPackageAnalysis, CandidateBinary, InstalledApp
from installer.registry import RegistryManager
from installer.detector import calculate_total_size, format_bytes


class InstallationError(Exception):
    """Error durante el proceso de instalación."""
    pass


class AppInstaller:
    """Gestiona la instalación de aplicaciones locales y en el sistema (/opt)."""

    def __init__(self, registry_manager: Optional[RegistryManager] = None):
        self.registry = registry_manager or RegistryManager()

    def install(
        self,
        analysis: AppPackageAnalysis,
        target_name: Optional[str] = None,
        target_binary: Optional[CandidateBinary] = None,
        is_system: bool = False,
        custom_icon_path: Optional[str] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None
    ) -> InstalledApp:
        """
        Ejecuta la instalación completa:
        1. Copia o mueve la carpeta a ~/.local/share/installer/apps/<id> o /opt/<id>.
        2. Configura chrome-sandbox (root:root 4755) con pkexec si aplica.
        3. Otorga permisos de ejecución (+x) al binario principal.
        4. Configura el ícono.
        5. Crea el lanzador .desktop y actualiza la base de datos de Ubuntu.
        6. Guarda la aplicación en el registro.
        """
        app_name = (target_name or analysis.app_name).strip()
        binary = target_binary or analysis.selected_binary

        if not binary:
            raise InstallationError("No se ha seleccionado ningún archivo ejecutable principal para la aplicación.")

        app_id = analysis.app_id
        src_root = Path(analysis.root_dir).resolve()

        if progress_cb:
            progress_cb(0.1, "Preparando directorio de destino...")

        # Determinar directorio destino
        if is_system:
            dest_dir = SYSTEM_APPS_DIR / app_id
        else:
            LOCAL_APPS_DIR.mkdir(parents=True, exist_ok=True)
            dest_dir = LOCAL_APPS_DIR / app_id

        # Transferencia de archivos
        if progress_cb:
            progress_cb(0.3, f"Instalando archivos en {dest_dir}...")

        if is_system:
            # Para /opt se requiere pkexec
            self._install_to_opt(src_root, dest_dir)
        else:
            # Para directorio local del usuario
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_root, dest_dir, symlinks=True)

        # Ubicar binario final y dar permisos +x
        dest_binary_path = dest_dir / binary.rel_path
        if progress_cb:
            progress_cb(0.6, "Configurando permisos de ejecución...")

        self._set_executable_permissions(dest_binary_path, is_system)

        # Configurar sandbox de Electron / Chromium si existe
        if analysis.has_chrome_sandbox and analysis.chrome_sandbox_path:
            rel_sandbox = Path(analysis.chrome_sandbox_path).relative_to(src_root)
            dest_sandbox = dest_dir / rel_sandbox
            if dest_sandbox.exists():
                if progress_cb:
                    progress_cb(0.7, "Configurando permisos de seguridad (chrome-sandbox)...")
                self._configure_chrome_sandbox(dest_sandbox)

        # Determinar ícono final
        if progress_cb:
            progress_cb(0.8, "Generando lanzador .desktop...")

        final_icon_path = None
        chosen_icon = custom_icon_path or analysis.icon_path
        if chosen_icon:
            try:
                rel_icon = Path(chosen_icon).relative_to(src_root)
                dest_icon = dest_dir / rel_icon
                if dest_icon.exists():
                    final_icon_path = str(dest_icon)
                else:
                    final_icon_path = chosen_icon
            except ValueError:
                final_icon_path = chosen_icon

        # Si aún no tiene ícono, buscar o usar genérico
        if not final_icon_path:
            final_icon_path = "application-x-executable"

        # Crear lanzador .desktop
        desktop_file_path = self._create_desktop_entry(
            app_id=app_id,
            app_name=app_name,
            exec_path=str(dest_binary_path),
            icon_path=final_icon_path,
            comment=f"Aplicación portable instalada mediante {INSTALLER_NAME}",
        )

        # Actualizar base de datos de escritorio
        self._update_desktop_database()

        # Calcular tamaño final
        size_bytes = calculate_total_size(dest_dir)
        size_fmt = format_bytes(size_bytes)

        installed_app = InstalledApp(
            id=app_id,
            name=app_name,
            version=analysis.version,
            install_path=str(dest_dir),
            exec_path=str(dest_binary_path),
            icon_path=final_icon_path,
            desktop_file=str(desktop_file_path),
            installed_at=datetime.datetime.now().isoformat(),
            is_system=is_system,
            size_bytes=size_bytes,
            size_formatted=size_fmt,
            has_chrome_sandbox=analysis.has_chrome_sandbox,
        )

        # Registrar en JSON
        self.registry.register_app(installed_app)

        if progress_cb:
            progress_cb(1.0, "¡Instalación completada!")

        return installed_app

    def update(
        self,
        app_id: str,
        new_analysis: AppPackageAnalysis,
        progress_cb: Optional[Callable[[float, str], None]] = None
    ) -> InstalledApp:
        """
        Actualiza una aplicación existente manteniendo sus metadatos y reemplazando los binarios.
        """
        existing = self.registry.get_app(app_id)
        if not existing:
            raise InstallationError(f"No se encontró la aplicación '{app_id}' registrada para actualizar.")

        # Reusar nombre e instalación previos
        return self.install(
            analysis=new_analysis,
            target_name=existing.name,
            target_binary=new_analysis.selected_binary,
            is_system=existing.is_system,
            progress_cb=progress_cb,
        )

    def _install_to_opt(self, src: Path, dest: Path) -> None:
        """Instala la carpeta en /opt utilizando pkexec de forma segura."""
        if not shutil.which("pkexec"):
            raise InstallationError("No se encontró 'pkexec' en el sistema para solicitar permisos de administrador.")

        # Se crea un comando bash para limpiar destino anterior y copiar nuevo
        bash_cmd = f"rm -rf '{dest}' && cp -r '{src}' '{dest}' && chown -R root:root '{dest}' && chmod -R u+rwX,go+rX '{dest}'"
        res = subprocess.run(["pkexec", "sh", "-c", bash_cmd], capture_output=True, text=True)
        if res.returncode != 0:
            err = res.stderr.strip() or "Autorización cancelada por el usuario"
            raise InstallationError(f"Error al instalar en /opt: {err}")

    def _set_executable_permissions(self, binary_path: Path, is_system: bool) -> None:
        """Otorga permisos de ejecución al binario principal."""
        if not binary_path.exists():
            return

        if is_system:
            subprocess.run(["pkexec", "chmod", "+x", str(binary_path)], check=False)
        else:
            try:
                current_mode = binary_path.stat().st_mode
                binary_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError as e:
                raise InstallationError(f"No se pudieron asignar permisos de ejecución a {binary_path}: {e}")

    def _configure_chrome_sandbox(self, sandbox_path: Path) -> None:
        """
        Configura los permisos obligatorios de chrome-sandbox (root:root y 4755 SUID)
        solicitando elevación de privilegios gráfica con pkexec.
        """
        if not sandbox_path.exists():
            return

        if not shutil.which("pkexec"):
            print("[InstALLer] Advertencia: 'pkexec' no está disponible para configurar SUID en chrome-sandbox.")
            return

        bash_cmd = f"chown root:root '{sandbox_path}' && chmod 4755 '{sandbox_path}'"
        res = subprocess.run(["pkexec", "sh", "-c", bash_cmd], capture_output=True, text=True)
        if res.returncode != 0:
            err = res.stderr.strip() or "Autorización cancelada"
            # No abortamos la instalación completa pero dejamos constancia
            print(f"[InstALLer] Advertencia: No se pudo configurar permisos SUID en chrome-sandbox: {err}")

    def _create_desktop_entry(
        self,
        app_id: str,
        app_name: str,
        exec_path: str,
        icon_path: str,
        comment: str
    ) -> Path:
        """Genera un archivo .desktop válido en ~/.local/share/applications/."""
        LOCAL_APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
        desktop_filename = f"installer-{app_id}.desktop"
        desktop_path = LOCAL_APPLICATIONS_DIR / desktop_filename

        content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_name}
Comment={comment}
Exec="{exec_path}" %U
Icon={icon_path}
Terminal=false
Categories=Utility;Application;
StartupNotify=true
StartupWMClass={app_id}
X-InstALLer-Managed=true
"""
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Permisos de lectura/ejecución
        try:
            desktop_path.chmod(0o755)
        except OSError:
            pass

        return desktop_path

    def _update_desktop_database(self) -> None:
        """Actualiza la base de datos de lanzadores de escritorio de Ubuntu."""
        try:
            subprocess.run(
                ["update-desktop-database", str(LOCAL_APPLICATIONS_DIR)],
                capture_output=True,
                check=False
            )
        except Exception:
            pass
