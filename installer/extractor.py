"""
InstALLer Extractor
Módulo de descompresión segura y normalización de archivos y carpetas.
"""

import os
import shutil
import tarfile
import zipfile
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Callable

from installer.constants import SUPPORTED_ARCHIVE_EXTENSIONS, TEMP_PREFIX


class ExtractionError(Exception):
    """Error durante la descompresión o preparación del paquete."""
    pass


def is_archive(path: Path) -> bool:
    """Verifica si la ruta corresponde a un archivo comprimido soportado."""
    if not path.is_file():
        return False
    name_lower = path.name.lower()
    return any(name_lower.endswith(ext) for ext in SUPPORTED_ARCHIVE_EXTENSIONS)


def _safe_extract_tar(tar: tarfile.TarFile, dest_dir: Path, progress_cb: Optional[Callable[[float, str], None]] = None) -> None:
    """Extrae un tar de forma segura, protegiendo contra path traversal."""
    members = tar.getmembers()
    total = len(members)

    # Uso del filtro 'data' disponible en Python 3.12+
    has_data_filter = hasattr(tarfile, "data_filter")

    for idx, member in enumerate(members):
        if not has_data_filter:
            # Validación manual preventiva para versiones anteriores
            target_path = (dest_dir / member.name).resolve()
            if not str(target_path).startswith(str(dest_dir.resolve())):
                raise ExtractionError(f"Ruta peligrosa detectada en el archivo: {member.name}")

        if has_data_filter:
            tar.extract(member, path=dest_dir, filter="data")
        else:
            tar.extract(member, path=dest_dir)

        if progress_cb and total > 0 and idx % max(1, total // 20) == 0:
            progress_cb(float(idx) / float(total), f"Descomprimiendo: {member.name}")


def _safe_extract_zip(zip_ref: zipfile.ZipFile, dest_dir: Path, progress_cb: Optional[Callable[[float, str], None]] = None) -> None:
    """
    Extrae un archivo zip de forma segura y restaura los permisos POSIX de ejecución
    que comúnmente se pierden al descomprimir zips en Python.
    """
    infolist = zip_ref.infolist()
    total = len(infolist)
    resolved_dest = dest_dir.resolve()

    for idx, info in enumerate(infolist):
        target_path = (dest_dir / info.filename).resolve()
        # Prevenir zip slip
        if not str(target_path).startswith(str(resolved_dest)):
            raise ExtractionError(f"Ruta peligrosa detectada en el zip: {info.filename}")

        zip_ref.extract(info, path=dest_dir)

        # Restaurar permisos UNIX de ejecución (bits 16-31 de external_attr)
        if info.external_attr > 0:
            mode = info.external_attr >> 16
            if mode & 0o111 and target_path.exists() and not target_path.is_symlink():
                try:
                    os.chmod(target_path, mode)
                except OSError:
                    pass

        if progress_cb and total > 0 and idx % max(1, total // 20) == 0:
            progress_cb(float(idx) / float(total), f"Descomprimiendo: {info.filename}")


def extract_archive(
    archive_path: Path,
    dest_dir: Path,
    progress_cb: Optional[Callable[[float, str], None]] = None
) -> Path:
    """
    Descomprime un archivo en el directorio destino y retorna la raíz normalizada de la app.
    Si el archivo contenía una única carpeta contenedora, retorna esa subcarpeta.
    """
    archive_path = Path(archive_path).resolve()
    dest_dir = Path(dest_dir).resolve()

    if not archive_path.is_file():
        raise ExtractionError(f"El archivo no existe o no es válido: {archive_path}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    name_lower = archive_path.name.lower()

    try:
        if name_lower.endswith(".zip"):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                _safe_extract_zip(zip_ref, dest_dir, progress_cb)
        elif any(name_lower.endswith(ext) for ext in (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar")):
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                _safe_extract_tar(tar_ref, dest_dir, progress_cb)
        else:
            raise ExtractionError(f"Formato no soportado: {archive_path.suffix}")
    except Exception as e:
        if isinstance(e, ExtractionError):
            raise
        raise ExtractionError(f"Error al descomprimir '{archive_path.name}': {e}") from e

    if progress_cb:
        progress_cb(1.0, "Descompresión finalizada")

    return normalize_extracted_folder(dest_dir)


def normalize_extracted_folder(dest_dir: Path) -> Path:
    """
    Si el archivo contenía una única carpeta en su raíz y ningún otro archivo
    relevante, retorna dicha subcarpeta para evitar anidamientos redundantes
    (ej: /tmp/extract/blender-4.1/blender -> blender-4.1).
    """
    dest_dir = Path(dest_dir).resolve()
    items = [item for item in dest_dir.iterdir() if not item.name.startswith(".")]

    if len(items) == 1 and items[0].is_dir():
        return items[0]
    return dest_dir


def prepare_source_package(
    source_path_str: str,
    progress_cb: Optional[Callable[[float, str], None]] = None
) -> Tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    """
    Prepara la fuente para análisis:
    - Si es carpeta: la retorna tal cual (sin directorio temporal).
    - Si es archivo comprimido: crea un directorio temporal y lo descomprime.
    Retorna (app_root_dir, temp_dir_object).
    """
    source_path = Path(source_path_str).resolve()
    if not source_path.exists():
        raise ExtractionError(f"La ruta no existe: {source_path}")

    if source_path.is_dir():
        if progress_cb:
            progress_cb(1.0, "Carpeta lista para análisis")
        return source_path, None

    if is_archive(source_path):
        temp_dir = tempfile.TemporaryDirectory(prefix=TEMP_PREFIX)
        extracted_root = extract_archive(source_path, Path(temp_dir.name), progress_cb)
        return extracted_root, temp_dir

    raise ExtractionError(
        f"El elemento seleccionado no es un directorio ni un archivo comprimido válido (.tar.gz, .tar.xz, .zip)."
    )
