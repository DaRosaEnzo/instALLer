"""
InstALLer Installed Apps View
Pestaña 'Apps Instaladas' con listado, buscador, lanzamiento rápido,
desinstalación limpia con un clic y actualización de versión.
"""

import os
import threading
import subprocess
from pathlib import Path
from typing import Optional, Callable, List
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from installer.constants import SUPPORTED_ARCHIVE_EXTENSIONS
from installer.models import InstalledApp, AppPackageAnalysis
from installer.registry import RegistryManager
from installer.core import AppInstaller
from installer.extractor import prepare_source_package
from installer.detector import analyze_package


class AppRow(Adw.ActionRow):
    """Fila que representa una aplicación instalada en el sistema."""

    def __init__(
        self,
        app: InstalledApp,
        on_launch_cb: Callable[[InstalledApp], None],
        on_update_cb: Callable[[InstalledApp], None],
        on_uninstall_cb: Callable[[InstalledApp], None],
    ):
        super().__init__()
        self.app = app
        self.on_launch_cb = on_launch_cb
        self.on_update_cb = on_update_cb
        self.on_uninstall_cb = on_uninstall_cb

        self._build_ui()

    def _build_ui(self) -> None:
        self.set_title(self.app.name)

        # Ubicación y badge de sistema o local
        sys_tag = "Sistema (/opt)" if self.app.is_system else "Usuario (~/.local)"
        self.set_subtitle(f"{self.app.install_path}\nPeso: {self.app.size_formatted} • {sys_tag}")

        # Ícono de la aplicación
        self.icon_image = Gtk.Image()
        self.icon_image.set_pixel_size(48)
        self.icon_image.set_margin_start(4)
        self.icon_image.set_margin_end(8)
        self._load_icon()
        self.add_prefix(self.icon_image)

        # Botones de acción en sufijo
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_valign(Gtk.Align.CENTER)

        # Botón Lanzar
        launch_btn = Gtk.Button()
        launch_btn.set_icon_name("media-playback-start-symbolic")
        launch_btn.set_tooltip_text(f"Ejecutar {self.app.name}")
        launch_btn.add_css_class("flat")
        launch_btn.connect("clicked", lambda b: self.on_launch_cb(self.app))
        btn_box.append(launch_btn)

        # Botón Actualizar
        update_btn = Gtk.Button()
        update_btn.set_icon_name("view-refresh-symbolic")
        update_btn.set_tooltip_text("Actualizar con nueva versión (.tar.gz / .zip / carpeta)")
        update_btn.add_css_class("flat")
        update_btn.connect("clicked", lambda b: self.on_update_cb(self.app))
        btn_box.append(update_btn)

        # Botón Desinstalar
        uninstall_btn = Gtk.Button()
        uninstall_btn.set_icon_name("user-trash-symbolic")
        uninstall_btn.set_tooltip_text("Desinstalar completamente")
        uninstall_btn.add_css_class("flat")
        uninstall_btn.add_css_class("destructive-action")
        uninstall_btn.connect("clicked", lambda b: self.on_uninstall_cb(self.app))
        btn_box.append(uninstall_btn)

        self.add_suffix(btn_box)

    def _load_icon(self) -> None:
        if self.app.icon_path and Path(self.app.icon_path).exists():
            self.icon_image.set_from_file(self.app.icon_path)
        else:
            self.icon_image.set_from_icon_name("application-x-executable")


class AppsView(Gtk.Box):
    """Pestaña con la lista de aplicaciones instaladas y controles de gestión."""

    def __init__(
        self,
        registry: RegistryManager,
        installer: AppInstaller,
        show_toast_cb: Optional[Callable[[str], None]] = None,
        switch_to_install_cb: Optional[Callable[[], None]] = None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.registry = registry
        self.installer = installer
        self.show_toast_cb = show_toast_cb
        self.switch_to_install_cb = switch_to_install_cb
        self.apps: List[InstalledApp] = []

        self._build_ui()
        self.reload_apps()

    def _build_ui(self) -> None:
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(24)
        self.set_margin_end(24)

        # Barra superior con buscador
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Buscar entre las apps instaladas...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        top_bar.append(self.search_entry)

        refresh_list_btn = Gtk.Button()
        refresh_list_btn.set_icon_name("view-refresh-symbolic")
        refresh_list_btn.set_tooltip_text("Recargar lista")
        refresh_list_btn.connect("clicked", lambda b: self.reload_apps())
        top_bar.append(refresh_list_btn)

        self.append(top_bar)

        # Contenedor con Stack para alternar entre lista y estado vacío
        self.view_stack = Gtk.Stack()
        self.view_stack.set_vexpand(True)
        self.view_stack.set_hexpand(True)

        # 1. Página de Estado Vacío
        self.empty_page = Adw.StatusPage()
        self.empty_page.set_icon_name("application-x-executable-symbolic")
        self.empty_page.set_title("No hay aplicaciones instaladas")
        self.empty_page.set_description(
            "Arrastrá un archivo comprimido (.tar.gz, .zip) en la pestaña 'Instalar' para comenzar."
        )
        if self.switch_to_install_cb:
            go_install_btn = Gtk.Button(label="Ir a Instalar")
            go_install_btn.add_css_class("pill")
            go_install_btn.add_css_class("suggested-action")
            go_install_btn.set_halign(Gtk.Align.CENTER)
            go_install_btn.connect("clicked", lambda b: self.switch_to_install_cb())
            self.empty_page.set_child(go_install_btn)

        self.view_stack.add_named(self.empty_page, "empty")

        # 2. Lista de Aplicaciones
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.list_box = Gtk.ListBox()
        self.list_box.add_css_class("boxed-list")
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_container.append(self.list_box)

        scrolled.set_child(list_container)
        self.view_stack.add_named(scrolled, "list")

        self.append(self.view_stack)

    def reload_apps(self) -> None:
        """Carga las aplicaciones desde el registro JSON y actualiza la lista."""
        self.apps = self.registry.list_apps()
        self._filter_and_display()

    def _filter_and_display(self) -> None:
        # Limpiar lista actual
        while True:
            first = self.list_box.get_first_child()
            if not first:
                break
            self.list_box.remove(first)

        query = self.search_entry.get_text().strip().lower()
        matched_apps = [
            app for app in self.apps
            if not query or query in app.name.lower() or query in app.id.lower() or query in app.install_path.lower()
        ]

        if not self.apps:
            self.empty_page.set_title("No hay aplicaciones instaladas")
            self.empty_page.set_description(
                "Arrastrá un archivo comprimido (.tar.gz, .zip) en la pestaña 'Instalar' para comenzar."
            )
            self.view_stack.set_visible_child_name("empty")
            return

        if not matched_apps:
            self.empty_page.set_title("No se encontraron coincidencias")
            self.empty_page.set_description(f"No hay apps que coincidan con '{query}'.")
            self.view_stack.set_visible_child_name("empty")
            return

        for app in matched_apps:
            row = AppRow(
                app=app,
                on_launch_cb=self._on_launch_app,
                on_update_cb=self._on_update_app,
                on_uninstall_cb=self._on_uninstall_app,
            )
            self.list_box.append(row)

        self.view_stack.set_visible_child_name("list")

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._filter_and_display()

    def _on_launch_app(self, app: InstalledApp) -> None:
        """Ejecuta la aplicación en segundo plano."""
        exec_path = Path(app.exec_path)
        if not exec_path.exists():
            if self.show_toast_cb:
                self.show_toast_cb(f"Error: No se encontró el ejecutable en {exec_path}")
            return

        try:
            subprocess.Popen([str(exec_path)], start_new_session=True)
            if self.show_toast_cb:
                self.show_toast_cb(f"Iniciando {app.name}...")
        except Exception as e:
            if self.show_toast_cb:
                self.show_toast_cb(f"Error al ejecutar: {e}")

    def _on_uninstall_app(self, app: InstalledApp) -> None:
        """Muestra confirmación antes de desinstalar."""
        root_win = self.get_root()

        dialog = Adw.AlertDialog.new(
            f"¿Desinstalar {app.name}?",
            f"Esta acción borrará de forma permanente los archivos en '{app.install_path}' y removerá el acceso directo del menú."
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("uninstall", "Desinstalar")
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dlg, response):
            if response == "uninstall":
                success, msg = self.registry.uninstall_app(app.id)
                self.reload_apps()
                if self.show_toast_cb:
                    self.show_toast_cb(msg)

        dialog.choose(root_win, None, on_response)

    def _on_update_app(self, app: InstalledApp) -> None:
        """Abre el selector de archivos para actualizar la app seleccionada."""
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title(f"Seleccionar actualización para {app.name}")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("Archivos soportados (.tar.gz, .tar.xz, .zip, carpetas)")
        for ext in SUPPORTED_ARCHIVE_EXTENSIONS:
            filter_all.add_pattern(f"*{ext}")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_all)
        file_dialog.set_filters(filters)

        root_win = self.get_root()

        def on_file_picked(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if gfile:
                    path = gfile.get_path()
                    if path:
                        self._perform_update(app, path)
            except Exception:
                pass

        file_dialog.open(root_win, None, on_file_picked)

    def _perform_update(self, app: InstalledApp, new_source_path: str) -> None:
        """Procesa y aplica la actualización en segundo plano."""
        if self.show_toast_cb:
            self.show_toast_cb(f"Actualizando {app.name}...")

        def worker():
            try:
                root_dir, temp_dir = prepare_source_package(new_source_path)
                analysis = analyze_package(root_dir, new_source_path, temp_dir)
                analysis.app_id = app.id  # Mantener mismo ID

                updated_app = self.installer.update(app.id, analysis)
                analysis.clean_temp()

                GLib.idle_add(lambda: self._on_update_finished(updated_app, None))
            except Exception as e:
                GLib.idle_add(lambda: self._on_update_finished(None, str(e)))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_update_finished(self, updated_app: Optional[InstalledApp], error_msg: Optional[str]) -> None:
        self.reload_apps()
        if error_msg:
            if self.show_toast_cb:
                self.show_toast_cb(f"Error al actualizar: {error_msg}")
        elif updated_app:
            if self.show_toast_cb:
                self.show_toast_cb(f"¡{updated_app.name} fue actualizado exitosamente!")
