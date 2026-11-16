"""
InstALLer Review & Configuration Dialog
Diálogo de confirmación que permite revisar y ajustar el nombre, ejecutable,
ícono y destino antes de proceder con la instalación.
"""

from pathlib import Path
from typing import Optional, Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

from installer.models import AppPackageAnalysis, CandidateBinary
from installer.ui.binary_dialog import BinarySelectionDialog


class ReviewDialog(Gtk.Window):
    """Diálogo modal para confirmar o ajustar los parámetros de instalación."""

    def __init__(
        self,
        parent: Gtk.Window,
        analysis: AppPackageAnalysis,
        initial_is_system: bool = False,
        on_install_confirmed_cb: Optional[Callable[[str, CandidateBinary, bool, Optional[str]], None]] = None
    ):
        super().__init__(transient_for=parent, modal=True, title="Confirmar Instalación")
        self.set_default_size(540, 520)
        self.analysis = analysis
        self.is_system = initial_is_system
        self.selected_binary = analysis.selected_binary
        self.custom_icon_path = analysis.icon_path
        self.on_install_confirmed_cb = on_install_confirmed_cb

        self._build_ui()

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # HeaderBar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)

        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect("clicked", self._on_cancel)
        header.pack_start(cancel_btn)

        install_btn = Gtk.Button(label="Instalar App")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", self._on_install_click)
        header.pack_end(install_btn)

        main_box.append(header)

        # Scrolled container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(24)
        content.set_margin_end(24)

        # Aviso de Chrome Sandbox si aplica
        if self.analysis.has_chrome_sandbox:
            sandbox_banner = Adw.Banner()
            sandbox_banner.set_title(
                "Aplicación Electron / Chromium detectada: Se solicitarán permisos elevados con pkexec "
                "para configurar de forma segura el 'chrome-sandbox' (root:root chmod 4755)."
            )
            sandbox_banner.set_revealed(True)
            content.append(sandbox_banner)

        # Card de Identidad (Ícono y Nombre)
        id_group = Adw.PreferencesGroup()
        id_group.set_title("Identidad de la Aplicación")
        id_group.set_description(f"Peso detectado: {self.analysis.total_size_formatted}")

        # Fila Nombre
        self.name_entry_row = Adw.EntryRow()
        self.name_entry_row.set_title("Nombre de la aplicación")
        self.name_entry_row.set_text(self.analysis.app_name)
        id_group.add(self.name_entry_row)

        # Fila Ícono
        self.icon_row = Adw.ActionRow()
        self.icon_row.set_title("Ícono detectado")
        
        self.icon_image = Gtk.Image()
        self.icon_image.set_pixel_size(48)
        self._update_icon_preview()
        self.icon_row.add_prefix(self.icon_image)

        change_icon_btn = Gtk.Button(label="Cambiar...")
        change_icon_btn.set_valign(Gtk.Align.CENTER)
        change_icon_btn.connect("clicked", self._on_change_icon)
        self.icon_row.add_suffix(change_icon_btn)
        id_group.add(self.icon_row)

        content.append(id_group)

        # Card de Ejecutable
        exec_group = Adw.PreferencesGroup()
        exec_group.set_title("Ejecutable Principal")

        self.exec_row = Adw.ActionRow()
        self._update_exec_row_text()

        if len(self.analysis.candidates) > 1:
            change_exec_btn = Gtk.Button(label="Cambiar...")
            change_exec_btn.set_valign(Gtk.Align.CENTER)
            change_exec_btn.connect("clicked", self._on_change_exec)
            self.exec_row.add_suffix(change_exec_btn)

        exec_group.add(self.exec_row)
        content.append(exec_group)

        # Card de Ubicación de Instalación
        dest_group = Adw.PreferencesGroup()
        dest_group.set_title("Ubicación de Instalación")

        # Fila Local
        self.local_row = Adw.ActionRow()
        self.local_row.set_title("Directorio Personal (Recomendado)")
        self.local_row.set_subtitle("~/.local/share/installer/apps/ — No requiere contraseña de root")
        self.check_local = Gtk.CheckButton()
        self.local_row.add_prefix(self.check_local)
        self.local_row.set_activatable_widget(self.check_local)
        dest_group.add(self.local_row)

        # Fila Sistema
        self.system_row = Adw.ActionRow()
        self.system_row.set_title("Todo el Sistema")
        self.system_row.set_subtitle("/opt/ — Disponible para todos los usuarios (requiere pkexec)")
        self.check_system = Gtk.CheckButton()
        self.check_system.set_group(self.check_local)
        self.system_row.add_prefix(self.check_system)
        self.system_row.set_activatable_widget(self.check_system)
        dest_group.add(self.system_row)

        if self.is_system:
            self.check_system.set_active(True)
        else:
            self.check_local.set_active(True)

        self.check_system.connect("toggled", self._on_dest_toggled)

        content.append(dest_group)

        scrolled.set_child(content)
        main_box.append(scrolled)

    def _update_icon_preview(self) -> None:
        if self.custom_icon_path and Path(self.custom_icon_path).exists():
            self.icon_image.set_from_file(self.custom_icon_path)
            self.icon_row.set_subtitle(Path(self.custom_icon_path).name)
        else:
            self.icon_image.set_from_icon_name("application-x-executable")
            self.icon_row.set_subtitle("Ícono genérico predeterminado")

    def _update_exec_row_text(self) -> None:
        if self.selected_binary:
            self.exec_row.set_title(self.selected_binary.name)
            badge = "ELF" if self.selected_binary.is_elf else "Script"
            self.exec_row.set_subtitle(f"{self.selected_binary.rel_path} ({badge})")
        else:
            self.exec_row.set_title("Ningún binario seleccionado")
            self.exec_row.set_subtitle("Advertencia: No se detectaron ejecutables automáticos")

    def _on_change_exec(self, btn: Gtk.Button) -> None:
        def on_selected(bin_chosen: CandidateBinary):
            self.selected_binary = bin_chosen
            self._update_exec_row_text()

        dialog = BinarySelectionDialog(
            parent=self,
            candidates=self.analysis.candidates,
            selected_binary=self.selected_binary,
            on_selected_cb=on_selected
        )
        dialog.present()

    def _on_change_icon(self, btn: Gtk.Button) -> None:
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Seleccionar ícono para la aplicación")
        
        filter_icon = Gtk.FileFilter()
        filter_icon.set_name("Imágenes de ícono (*.png, *.svg, *.ico)")
        for ext in ("*.png", "*.svg", "*.ico"):
            filter_icon.add_pattern(ext)
        
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_icon)
        file_dialog.set_filters(filters)

        def on_icon_picked(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if gfile:
                    self.custom_icon_path = gfile.get_path()
                    self._update_icon_preview()
            except Exception:
                pass

        file_dialog.open(self, None, on_icon_picked)

    def _on_dest_toggled(self, check: Gtk.CheckButton) -> None:
        self.is_system = check.get_active()

    def _on_cancel(self, btn: Gtk.Button) -> None:
        self.analysis.clean_temp()
        self.close()

    def _on_install_click(self, btn: Gtk.Button) -> None:
        final_name = self.name_entry_row.get_text().strip() or self.analysis.app_name
        is_sys = self.check_system.get_active()

        if not self.selected_binary:
            return

        if self.on_install_confirmed_cb:
            self.on_install_confirmed_cb(
                final_name,
                self.selected_binary,
                is_sys,
                self.custom_icon_path
            )
        self.close()
