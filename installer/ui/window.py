"""
InstALLer Main Application Window
Ventana principal con Libadwaita, ViewSwitcher para 'Instalar' y 'Apps Instaladas',
y notificaciones flotantes con ToastOverlay.
"""

import os
from pathlib import Path
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from installer.constants import APP_NAME, APP_COMMENT
from installer.registry import RegistryManager
from installer.core import AppInstaller
from installer.models import InstalledApp
from installer.ui.install_view import InstallView
from installer.ui.apps_view import AppsView


class InstALLerWindow(Adw.ApplicationWindow):
    """Ventana principal de la aplicación InstALLer."""

    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(760, 560)
        self.set_size_request(580, 440)

        self.registry = RegistryManager()
        self.installer = AppInstaller(self.registry)

        self._load_css()
        self._build_ui()

    def _load_css(self) -> None:
        """Carga los estilos personalizados de InstALLer."""
        snap_root = os.environ.get("SNAP")
        if snap_root and (Path(snap_root) / "assets" / "style.css").exists():
            css_file = Path(snap_root) / "assets" / "style.css"
        else:
            css_file = Path(__file__).resolve().parent.parent.parent / "assets" / "style.css"

        if css_file.exists():
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(str(css_file))
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                print(f"[InstALLer] Error al cargar CSS: {e}")

    def _build_ui(self) -> None:
        # Contenedor raíz vertical
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)

        # HeaderBar con ViewSwitcher
        self.header_bar = Adw.HeaderBar()
        self.view_stack = Adw.ViewStack()

        self.view_switcher = Adw.ViewSwitcher()
        self.view_switcher.set_stack(self.view_stack)
        self.view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.header_bar.set_title_widget(self.view_switcher)

        # Botón de menú de la app / About
        menu_btn = Gtk.Button()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Acerca de InstALLer")
        menu_btn.connect("clicked", self._on_about_clicked)
        self.header_bar.pack_end(menu_btn)

        main_box.append(self.header_bar)

        # ToastOverlay para notificaciones emergentes
        self.toast_overlay = Adw.ToastOverlay()
        main_box.append(self.toast_overlay)

        # Vistas de las pestañas
        self.install_view = InstallView(
            installer=self.installer,
            on_app_installed_cb=self._on_app_installed,
            show_toast_cb=self.show_toast,
        )

        self.apps_view = AppsView(
            registry=self.registry,
            installer=self.installer,
            show_toast_cb=self.show_toast,
            switch_to_install_cb=lambda: self.view_stack.set_visible_child_name("install")
        )

        # Agregar páginas a ViewStack
        page_install = self.view_stack.add_titled(self.install_view, "install", "Instalar")
        page_install.set_icon_name("folder-download-symbolic")

        page_apps = self.view_stack.add_titled(self.apps_view, "apps", "Apps Instaladas")
        page_apps.set_icon_name("application-x-executable-symbolic")

        self.toast_overlay.set_child(self.view_stack)

    def show_toast(self, message: str) -> None:
        """Muestra una notificación toast moderna dentro de la ventana."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(4)
        self.toast_overlay.add_toast(toast)

    def _on_app_installed(self, app: InstalledApp) -> None:
        """Callback al finalizar con éxito una instalación: refresca la lista y cambia de pestaña."""
        self.apps_view.reload_apps()
        self.view_stack.set_visible_child_name("apps")

    def _on_about_clicked(self, btn: Gtk.MenuButton) -> None:
        """Muestra el diálogo Acerca de InstALLer."""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=APP_NAME,
            application_icon="application-x-executable",
            version="1.0.0",
            developer_name="Google DeepMind Team",
            comments=APP_COMMENT,
            license_type=Gtk.License.MIT_X11,
            issue_url="https://github.com",
            website="https://github.com"
        )
        about.present()
