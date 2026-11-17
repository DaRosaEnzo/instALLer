"""
InstALLer Install View
Vista principal de instalación con zona amplia de Drag & Drop, selección tradicional
de archivos y retroalimentación interactiva del progreso.
"""

import threading
from pathlib import Path
from typing import Optional, Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Gio, GLib

from installer.constants import SUPPORTED_ARCHIVE_EXTENSIONS
from installer.models import AppPackageAnalysis, CandidateBinary, InstalledApp
from installer.extractor import prepare_source_package, ExtractionError
from installer.detector import analyze_package
from installer.core import AppInstaller, InstallationError
from installer.ui.review_dialog import ReviewDialog


class InstallView(Gtk.Box):
    """Pestaña 'Instalar' con Drag & Drop y selector de archivos."""

    def __init__(
        self,
        installer: AppInstaller,
        on_app_installed_cb: Optional[Callable[[InstalledApp], None]] = None,
        show_toast_cb: Optional[Callable[[str], None]] = None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.installer = installer
        self.on_app_installed_cb = on_app_installed_cb
        self.show_toast_cb = show_toast_cb
        self.current_analysis: Optional[AppPackageAnalysis] = None

        self._build_ui()
        self._setup_drop_target()

    def _build_ui(self) -> None:
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(32)
        self.set_margin_end(32)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.FILL)

        # Contenedor central tipo tarjeta
        self.drop_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.drop_card.add_css_class("drop-card")
        self.drop_card.set_vexpand(True)
        self.drop_card.set_hexpand(True)

        # Ícono central
        self.drop_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        self.drop_icon.set_pixel_size(72)
        self.drop_icon.add_css_class("accent")
        self.drop_card.append(self.drop_icon)

        # Título principal
        self.title_label = Gtk.Label(label="Arrastrá y soltá tu aplicación acá")
        self.title_label.add_css_class("title-1")
        self.drop_card.append(self.title_label)

        # Subtítulo explicativo
        self.subtitle_label = Gtk.Label(
            label="Acepta archivos .tar.gz, .tar.xz, .zip o carpetas extraídas",
            wrap=True
        )
        self.subtitle_label.add_css_class("dim-label")
        self.drop_card.append(self.subtitle_label)

        # Separador visual sutil
        sep_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        sep_box.set_halign(Gtk.Align.CENTER)
        or_label = Gtk.Label(label="o elegí desde tu equipo:")
        or_label.add_css_class("dim-label")
        sep_box.append(or_label)
        self.drop_card.append(sep_box)

        # Botones de selección tradicional
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.pick_file_btn = Gtk.Button(label="Seleccionar archivo...")
        self.pick_file_btn.add_css_class("pill")
        self.pick_file_btn.add_css_class("suggested-action")
        self.pick_file_btn.connect("clicked", self._on_pick_file_clicked)
        btn_box.append(self.pick_file_btn)

        self.pick_folder_btn = Gtk.Button(label="Seleccionar carpeta...")
        self.pick_folder_btn.add_css_class("pill")
        self.pick_folder_btn.connect("clicked", self._on_pick_folder_clicked)
        btn_box.append(self.pick_folder_btn)

        self.drop_card.append(btn_box)

        # Contenedor de progreso (oculto por defecto)
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.progress_box.set_margin_top(16)
        self.progress_box.set_visible(False)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        self.progress_box.append(self.spinner)

        self.status_label = Gtk.Label(label="Procesando aplicación...")
        self.status_label.add_css_class("caption")
        self.progress_box.append(self.status_label)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_hexpand(True)
        self.progress_box.append(self.progress_bar)

        self.drop_card.append(self.progress_box)
        self.append(self.drop_card)

    def _setup_drop_target(self) -> None:
        """Configura el controlador de Drag and Drop en la tarjeta."""
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.set_gtypes([Gdk.FileList, Gio.File])

        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)
        drop_target.connect("drop", self._on_drop)

        self.drop_card.add_controller(drop_target)

    def _on_drag_enter(self, target: Gtk.DropTarget, x: float, y: float) -> Gdk.DragAction:
        self.drop_card.add_css_class("drop-active")
        self.drop_icon.set_from_icon_name("folder-download-symbolic")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, target: Gtk.DropTarget) -> None:
        self.drop_card.remove_css_class("drop-active")

    def _on_drop(self, target: Gtk.DropTarget, value, x: float, y: float) -> bool:
        self.drop_card.remove_css_class("drop-active")

        file_path = None
        if isinstance(value, Gdk.FileList):
            files = value.get_files()
            if files:
                file_path = files[0].get_path()
        elif isinstance(value, Gio.File):
            file_path = value.get_path()

        if file_path:
            self.process_source(file_path)
            return True
        return False

    def _on_pick_file_clicked(self, btn: Gtk.Button) -> None:
        """Abre el diálogo para seleccionar un archivo comprimido."""
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Seleccionar paquete portable")

        archive_filter = Gtk.FileFilter()
        archive_filter.set_name("Archivos comprimidos (.tar.gz, .tar.xz, .zip)")
        for ext in SUPPORTED_ARCHIVE_EXTENSIONS:
            archive_filter.add_pattern(f"*{ext}")

        all_filter = Gtk.FileFilter()
        all_filter.set_name("Todos los archivos")
        all_filter.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(archive_filter)
        filters.append(all_filter)
        file_dialog.set_filters(filters)

        root_win = self.get_root()
        file_dialog.open(root_win, None, self._on_file_selected)

    def _on_file_selected(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            gfile = dialog.open_finish(result)
            if gfile:
                path = gfile.get_path()
                if path:
                    self.process_source(path)
        except Exception:
            pass

    def _on_pick_folder_clicked(self, btn: Gtk.Button) -> None:
        """Abre el diálogo para seleccionar una carpeta extraída."""
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Seleccionar carpeta de la aplicación")
        root_win = self.get_root()
        file_dialog.select_folder(root_win, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            gfile = dialog.select_folder_finish(result)
            if gfile:
                path = gfile.get_path()
                if path:
                    self.process_source(path)
        except Exception:
            pass

    def set_loading(self, active: bool, status: str = "", fraction: float = 0.0) -> None:
        """Actualiza el estado visual de carga y barra de progreso."""
        self.progress_box.set_visible(active)
        self.pick_file_btn.set_sensitive(not active)
        self.pick_folder_btn.set_sensitive(not active)
        if active:
            self.spinner.start()
            self.status_label.set_text(status)
            self.progress_bar.set_fraction(fraction)
        else:
            self.spinner.stop()

    def process_source(self, source_path_str: str) -> None:
        """
        Inicia la preparación y análisis del paquete en un hilo secundario
        para garantizar que la interfaz se mantenga 100% fluida.
        """
        self.set_loading(True, "Iniciando análisis...", 0.05)

        def worker():
            def progress_cb(fraction: float, message: str):
                GLib.idle_add(lambda: self.set_loading(True, message, fraction))

            try:
                root_dir, temp_dir = prepare_source_package(source_path_str, progress_cb)
                GLib.idle_add(lambda: self.set_loading(True, "Detectando ejecutables e íconos...", 0.85))
                analysis = analyze_package(root_dir, source_path_str, temp_dir)

                GLib.idle_add(lambda: self._on_analysis_complete(analysis))
            except Exception as e:
                err_msg = str(e)
                GLib.idle_add(lambda: self._on_analysis_failed(err_msg))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_analysis_complete(self, analysis: AppPackageAnalysis) -> None:
        self.set_loading(False)
        self.current_analysis = analysis

        if not analysis.candidates:
            if self.show_toast_cb:
                self.show_toast_cb("No se encontraron archivos ejecutables en el paquete seleccionado.")
            analysis.clean_temp()
            return

        # Abrir diálogo de revisión y confirmación
        root_win = self.get_root()
        review_dialog = ReviewDialog(
            parent=root_win,
            analysis=analysis,
            initial_is_system=False,
            on_install_confirmed_cb=self._execute_installation
        )
        review_dialog.present()

    def _on_analysis_failed(self, error_message: str) -> None:
        self.set_loading(False)
        if self.show_toast_cb:
            self.show_toast_cb(f"Error: {error_message}")

    def _execute_installation(
        self,
        final_name: str,
        target_binary: CandidateBinary,
        is_system: bool,
        custom_icon_path: Optional[str]
    ) -> None:
        """Ejecuta la instalación en segundo plano."""
        if not self.current_analysis:
            return

        analysis = self.current_analysis
        self.set_loading(True, "Instalando aplicación...", 0.3)

        def worker():
            def progress_cb(fraction: float, message: str):
                GLib.idle_add(lambda: self.set_loading(True, message, fraction))

            try:
                installed_app = self.installer.install(
                    analysis=analysis,
                    target_name=final_name,
                    target_binary=target_binary,
                    is_system=is_system,
                    custom_icon_path=custom_icon_path,
                    progress_cb=progress_cb
                )
                GLib.idle_add(lambda: self._on_install_success(installed_app))
            except Exception as e:
                err_msg = str(e)
                GLib.idle_add(lambda: self._on_install_failed(err_msg))
            finally:
                analysis.clean_temp()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_install_success(self, app: InstalledApp) -> None:
        self.set_loading(False)
        if self.show_toast_cb:
            self.show_toast_cb(f"¡'{app.name}' se instaló exitosamente!")
        if self.on_app_installed_cb:
            self.on_app_installed_cb(app)

    def _on_install_failed(self, error_msg: str) -> None:
        self.set_loading(False)
        if self.show_toast_cb:
            self.show_toast_cb(f"Error en la instalación: {error_msg}")
