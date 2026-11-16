"""
InstALLer Binary Selection Dialog
Diálogo para elegir el ejecutable principal en caso de múltiples candidatos o ambigüedad.
"""

from typing import List, Optional, Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango

from installer.models import CandidateBinary
from installer.detector import format_bytes


class BinarySelectionDialog(Gtk.Window):
    """Ventana modal para que el usuario seleccione el ejecutable deseado."""

    def __init__(
        self,
        parent: Gtk.Window,
        candidates: List[CandidateBinary],
        selected_binary: Optional[CandidateBinary],
        on_selected_cb: Callable[[CandidateBinary], None]
    ):
        super().__init__(transient_for=parent, modal=True, title="Seleccionar Ejecutable Principal")
        self.set_default_size(520, 420)
        self.candidates = candidates
        self.selected_binary = selected_binary or (candidates[0] if candidates else None)
        self.on_selected_cb = on_selected_cb
        self._radio_group = None

        self._build_ui()

    def _build_ui(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # HeaderBar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)

        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_btn)

        confirm_btn = Gtk.Button(label="Seleccionar")
        confirm_btn.add_css_class("suggested-action")
        confirm_btn.connect("clicked", self._on_confirm)
        header.pack_end(confirm_btn)

        main_box.append(header)

        # Contenido
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # Descripción
        info_label = Gtk.Label(
            label="Se encontraron varios ejecutables en el paquete. Seleccioná cuál debe abrir la aplicación al hacer clic en el menú:",
            wrap=True,
            xalign=0
        )
        info_label.add_css_class("dim-label")
        content_box.append(info_label)

        # Lista de candidatos dentro de un ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        list_box = Gtk.ListBox()
        list_box.add_css_class("boxed-list")
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        first_check = None
        self.radio_buttons = []

        for idx, candidate in enumerate(self.candidates):
            row = Adw.ActionRow()
            row.set_title(candidate.name)
            
            # Subtítulo con ruta relativa y tamaño
            size_str = format_bytes(candidate.file_size)
            badge_type = "ELF" if candidate.is_elf else "Script"
            is_rec = " • (Recomendado)" if idx == 0 else ""
            row.set_subtitle(f"{candidate.rel_path} • {badge_type} • {size_str}{is_rec}")

            check = Gtk.CheckButton()
            if first_check is None:
                first_check = check
            else:
                check.set_group(first_check)

            if self.selected_binary and candidate.full_path == self.selected_binary.full_path:
                check.set_active(True)
            elif idx == 0 and not self.selected_binary:
                check.set_active(True)

            check.connect("toggled", self._on_radio_toggled, candidate)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            list_box.append(row)
            self.radio_buttons.append((check, candidate))

        scrolled.set_child(list_box)
        content_box.append(scrolled)
        main_box.append(content_box)

    def _on_radio_toggled(self, check: Gtk.CheckButton, candidate: CandidateBinary) -> None:
        if check.get_active():
            self.selected_binary = candidate

    def _on_confirm(self, btn: Gtk.Button) -> None:
        if self.selected_binary and self.on_selected_cb:
            self.on_selected_cb(self.selected_binary)
        self.close()
