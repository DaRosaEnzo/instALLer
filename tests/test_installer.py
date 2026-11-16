"""
InstALLer Automated Test Suite
Pruebas integrales de extracción, detección de binarios, íconos,
chrome-sandbox, registro y desinstalador.
"""

import os
import sys
import shutil
import tarfile
import zipfile
import tempfile
import unittest
from pathlib import Path

# Agregar directorio raíz al PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from installer.constants import REGISTRY_FILE, LOCAL_APPS_DIR, LOCAL_APPLICATIONS_DIR
from installer.models import CandidateBinary, InstalledApp
from installer.extractor import extract_archive, prepare_source_package, normalize_extracted_folder
from installer.detector import (
    is_elf_executable,
    is_shell_script,
    find_candidate_binaries,
    find_best_icon,
    detect_chrome_sandbox,
    infer_app_metadata,
    analyze_package,
)
from installer.registry import RegistryManager
from installer.installer import AppInstaller


class TestInstALLerBackend(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory(prefix="installer-test-")
        self.test_path = Path(self.test_dir.name)

        # Configurar registro aislado para tests
        self.custom_reg_file = self.test_path / "registry.json"
        self.registry = RegistryManager(self.custom_reg_file)

    def tearDown(self):
        try:
            self.test_dir.cleanup()
        except Exception:
            pass

    def test_infer_metadata(self):
        name, app_id, ver = infer_app_metadata("obsidian-1.5.8-linux-x64.tar.gz")
        self.assertIn("Obsidian", name)
        self.assertEqual(ver, "1.5.8")
        self.assertEqual(app_id, "obsidian")

        name2, app_id2, ver2 = infer_app_metadata("Blender_v4.2.0_linux.tar.xz")
        self.assertIn("Blender", name2)
        self.assertEqual(ver2, "4.2.0")

    def test_tar_and_zip_extraction(self):
        # Crear estructura simulada de app
        app_source = self.test_path / "mock-source"
        app_source.mkdir()
        (app_source / "myapp").write_text("#!/bin/bash\necho 'hello'")
        os.chmod(app_source / "myapp", 0o755)
        (app_source / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x80\x00\x00\x00\x80\x08\x06\x00\x00\x00")

        # 1. Probar tar.gz
        tar_path = self.test_path / "mockapp-1.0.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(app_source, arcname="mockapp-1.0")

        dest_tar = self.test_path / "extract-tar"
        extracted_tar = extract_archive(tar_path, dest_tar)
        self.assertTrue((extracted_tar / "myapp").exists())
        self.assertTrue((extracted_tar / "icon.png").exists())

        # 2. Probar zip
        zip_path = self.test_path / "mockapp-1.0.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for item in app_source.iterdir():
                zf.write(item, arcname=f"mockapp-1.0/{item.name}")

        dest_zip = self.test_path / "extract-zip"
        extracted_zip = extract_archive(zip_path, dest_zip)
        self.assertTrue((extracted_zip / "myapp").exists())
        self.assertTrue((extracted_zip / "icon.png").exists())

    def test_detection_of_electron_and_binaries(self):
        app_dir = self.test_path / "electron-app"
        app_dir.mkdir()

        # Binario principal (script simulado)
        main_bin = app_dir / "my-electron-app"
        main_bin.write_text("#!/bin/bash\nexec electron .")
        main_bin.chmod(0o755)

        # chrome-sandbox
        sandbox = app_dir / "chrome-sandbox"
        sandbox.write_text("binary-mock")
        sandbox.chmod(0o755)

        # Archivo .bin de datos (debe ser ignorado)
        data_bin = app_dir / "snapshot_blob.bin"
        data_bin.write_bytes(b"blob data")

        # Archivo .so (debe ser ignorado)
        lib_so = app_dir / "libffmpeg.so"
        lib_so.write_bytes(b"mock library")

        # Ícono SVG
        icon_file = app_dir / "app.svg"
        icon_file.write_text("<svg></svg>")

        # Análisis
        analysis = analyze_package(app_dir, "my-electron-app-1.0.0.tar.gz")

        self.assertTrue(analysis.has_chrome_sandbox)
        self.assertIsNotNone(analysis.selected_binary)
        self.assertEqual(analysis.selected_binary.name, "my-electron-app")

        # Asegurar que snapshot_blob.bin y libffmpeg.so NO están entre los candidatos
        cand_names = [c.name for c in analysis.candidates]
        self.assertNotIn("snapshot_blob.bin", cand_names)
        self.assertNotIn("libffmpeg.so", cand_names)
        self.assertNotIn("chrome-sandbox", cand_names)

        # Ícono
        self.assertEqual(Path(analysis.icon_path).name, "app.svg")

    def test_registry_and_uninstall(self):
        app_id = "test-app"
        fake_install_dir = self.test_path / "installed_app"
        fake_install_dir.mkdir()
        fake_exec = fake_install_dir / "run.sh"
        fake_exec.write_text("#!/bin/sh\n")

        fake_desktop = self.test_path / "test-app.desktop"
        fake_desktop.write_text("[Desktop Entry]\nName=Test\n")

        app = InstalledApp(
            id=app_id,
            name="Test App",
            version="1.0",
            install_path=str(fake_install_dir),
            exec_path=str(fake_exec),
            icon_path=None,
            desktop_file=str(fake_desktop),
            installed_at="2026-11-16T12:00:00",
            is_system=False,
            size_bytes=100,
            size_formatted="100 B",
            has_chrome_sandbox=False
        )

        # Registrar
        self.registry.register_app(app)
        apps = self.registry.list_apps()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].id, app_id)

        # Desinstalar
        success, msg = self.registry.uninstall_app(app_id)
        self.assertTrue(success)
        self.assertFalse(fake_install_dir.exists())
        self.assertFalse(fake_desktop.exists())
        self.assertEqual(len(self.registry.list_apps()), 0)


if __name__ == "__main__":
    unittest.main()
