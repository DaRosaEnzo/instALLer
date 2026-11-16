"""
InstALLer Detector
Análisis inteligente de la estructura de archivos de la aplicación:
- Detección de binario ejecutable principal (descartando .so, .bin de datos, helpers).
- Detección de chrome-sandbox (Electron / Chromium).
- Búsqueda del mejor ícono (.svg, .png de mayor resolución, .ico).
- Estimación del nombre, versión y peso total.
"""

import os
import re
import stat
import struct
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from installer.constants import (
    IGNORED_BINARY_NAMES,
    IGNORED_EXTENSIONS,
    ICON_EXTENSIONS,
)
from installer.models import CandidateBinary, AppPackageAnalysis


def is_elf_executable(filepath: Path) -> bool:
    """
    Verifica si un archivo es un ejecutable ELF de Linux (ET_EXEC o PIE ET_DYN con PT_INTERP),
    distinguiéndolo de bibliotecas dinámicas compartidas (.so).
    """
    try:
        if not filepath.is_file() or filepath.is_symlink():
            return False

        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != b"\x7fELF":
                return False

            f.seek(16)
            e_type_bytes = f.read(2)
            if len(e_type_bytes) < 2:
                return False
            e_type = struct.unpack("<H", e_type_bytes)[0]

            # 2 = ET_EXEC (binario ejecutable directo)
            if e_type == 2:
                return True

            # Si es 3 = ET_DYN (muchos ejecutables modernos en Linux se compilan como PIE ET_DYN).
            # Para distinguirlos de un simple .so, inspeccionamos si tiene encabezado de programa PT_INTERP (tipo 3).
            if e_type == 3:
                f.seek(0)
                header = f.read(64)
                if len(header) < 58:
                    return False

                ei_class = header[4]  # 1 = 32-bit, 2 = 64-bit
                if ei_class == 2:  # 64-bit
                    e_phoff = struct.unpack("<Q", header[32:40])[0]
                    e_phentsize = struct.unpack("<H", header[54:56])[0]
                    e_phnum = struct.unpack("<H", header[56:58])[0]
                elif ei_class == 1:  # 32-bit
                    e_phoff = struct.unpack("<I", header[28:32])[0]
                    e_phentsize = struct.unpack("<H", header[42:44])[0]
                    e_phnum = struct.unpack("<H", header[44:46])[0]
                else:
                    return False

                f.seek(e_phoff)
                for _ in range(min(e_phnum, 128)):
                    ph = f.read(e_phentsize)
                    if len(ph) < 4:
                        break
                    p_type = struct.unpack("<I", ph[:4])[0]
                    if p_type == 3:  # PT_INTERP encontrado -> ejecutable que requiere intérprete dinámico
                        return True
            return False
    except Exception:
        return False


def is_shell_script(filepath: Path) -> bool:
    """Verifica si el archivo es un script de shell ejecutable."""
    try:
        if not filepath.is_file() or filepath.is_symlink():
            return False

        with open(filepath, "rb") as f:
            first_line = f.readline(128)
            if first_line.startswith(b"#!"):
                text = first_line.decode("utf-8", errors="ignore").lower()
                return any(shell in text for shell in ("sh", "bash", "python", "perl", "dash"))
        return False
    except Exception:
        return False


def get_png_dimensions(path: Path) -> Tuple[int, int]:
    """Obtiene el ancho y alto de un PNG sin requerir dependencias externas."""
    try:
        with open(path, "rb") as f:
            header = f.read(24)
            if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
                width, height = struct.unpack(">II", header[16:24])
                return width, height
    except Exception:
        pass
    return 0, 0


def format_bytes(size: int) -> str:
    """Formatea bytes a formato legible (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def infer_app_metadata(name_hint: str) -> Tuple[str, str, str]:
    """
    Infiere el nombre de la app, el ID normalizado y la versión a partir
    del nombre del archivo comprimido o carpeta.
    """
    clean_name = name_hint
    # Quitar extensiones comunes
    for ext in (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".zip", ".tar"):
        if clean_name.lower().endswith(ext):
            clean_name = clean_name[:-len(ext)]
            break

    # Primero quitar tags de arquitectura y plataforma
    clean_no_arch = re.sub(
        r"[-_](x86_64|amd64|x64|i386|arm64|aarch64|linux-x64|linux-arm64|linux|portable|bin|build)",
        "",
        clean_name,
        flags=re.IGNORECASE
    )

    # Detectar versión (ej: 1.2.3, 4.1.0, 2024.1)
    version_match = re.search(
        r"[-_vV]?(\d+\.\d+(?:\.\d+)?(?:[-_.](?:alpha|beta|rc|preview|patch)\d*)?)",
        clean_no_arch,
        flags=re.IGNORECASE
    )
    version = version_match.group(1) if version_match else "1.0.0"

    # Quitar número de versión del nombre
    filtered = re.sub(
        r"[-_vV]?\d+\.\d+(?:\.\d+)?(?:[-_.](?:alpha|beta|rc|preview|patch)\d*)?",
        "",
        clean_no_arch,
        flags=re.IGNORECASE
    )
    filtered = filtered.strip("-_ .")

    if not filtered:
        filtered = clean_name.strip("-_ .")

    app_name = filtered.replace("-", " ").replace("_", " ").title()
    app_id = re.sub(r"[^a-z0-9_-]", "", filtered.lower()).strip("-_")
    if not app_id:
        app_id = "portable-app"

    return app_name, app_id, version


def find_candidate_binaries(root_dir: Path, app_name_hint: str) -> List[CandidateBinary]:
    """
    Escanea el directorio para encontrar ejecutables viables y clasificarlos con un score.
    Descarta librerías (.so), archivos de datos (.bin) y utilidades secundarias.
    """
    candidates: List[CandidateBinary] = []
    root_dir = root_dir.resolve()
    name_hint_lower = app_name_hint.lower().replace(" ", "").replace("-", "").replace("_", "")

    for root, dirs, files in os.walk(root_dir):
        # Evitar carpetas ocultas o de desarrollo
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", ".git")]

        current_dir = Path(root)
        rel_dir = current_dir.relative_to(root_dir)
        depth = len(rel_dir.parts)

        for filename in files:
            name_lower = filename.lower()

            # Descartar archivos expresamente ignorados
            if name_lower in IGNORED_BINARY_NAMES:
                continue

            # Descartar extensiones de datos o librerías
            if any(name_lower.endswith(ext) or (ext in name_lower and ext.startswith(".so")) for ext in IGNORED_EXTENSIONS):
                continue

            # Descartar bibliotecas que comienzan con 'lib' y terminan en número o .so
            if name_lower.startswith("lib") and (".so" in name_lower or name_lower.endswith(".a")):
                continue

            file_path = current_dir / filename
            if file_path.is_symlink():
                continue

            is_elf = is_elf_executable(file_path)
            is_script = is_shell_script(file_path)

            if not (is_elf or is_script):
                continue

            # Cálculo del puntaje (score)
            score = 0
            file_stat = file_path.stat()
            file_size = file_stat.st_size

            # Bono por tener bit de ejecución activo
            if file_stat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                score += 20

            # Coincidencia con el nombre de la app
            clean_fn = name_lower.replace("-", "").replace("_", "").replace(".sh", "")
            if clean_fn == name_hint_lower:
                score += 100
            elif name_hint_lower in clean_fn or clean_fn in name_hint_lower:
                score += 50

            # Ubicación preferencial
            if depth == 0:
                score += 40  # Justo en la raíz
            elif depth == 1 and rel_dir.parts[0].lower() in ("bin", "usr", "app"):
                score += 35
            else:
                score -= depth * 10  # Penalización por profundidad

            # Preferir binarios ELF sobre scripts a menos que sea un wrapper
            if is_elf:
                score += 15
                desc = "Binario compilado (ELF)"
            else:
                desc = "Script ejecutable (Shell)"

            # Desempate por tamaño razonable
            if 10_000 < file_size < 500_000_000:
                score += 5

            rel_path_str = str(file_path.relative_to(root_dir))
            candidates.append(
                CandidateBinary(
                    name=filename,
                    rel_path=rel_path_str,
                    full_path=str(file_path),
                    is_elf=is_elf,
                    is_script=is_script,
                    score=score,
                    file_size=file_size,
                    description=desc,
                )
            )

    # Ordenar candidatos de mayor a menor score
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def find_best_icon(root_dir: Path, app_name_hint: str) -> Optional[str]:
    """
    Busca el mejor ícono para la aplicación dentro de la carpeta:
    - Prioriza SVG (escalable vectorial).
    - Para PNG, busca la mayor resolución (512x512 > 256x256 > 128x128).
    - Asigna bonificaciones por nombres como 'icon', 'logo' o coincidencia con la app.
    """
    root_dir = root_dir.resolve()
    name_hint_lower = app_name_hint.lower().replace(" ", "").replace("-", "").replace("_", "")

    best_icon: Optional[Path] = None
    best_score = -1

    for root, dirs, files in os.walk(root_dir):
        # Descartar directorios irrelevantes
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", ".git")]

        current_dir = Path(root)
        rel_dir = current_dir.relative_to(root_dir)
        depth = len(rel_dir.parts)

        for filename in files:
            name_lower = filename.lower()
            if not any(name_lower.endswith(ext) for ext in ICON_EXTENSIONS):
                continue

            file_path = current_dir / filename
            score = 0

            # Nombre relevante
            if any(k in name_lower for k in ("icon", "logo", "app", name_hint_lower)):
                score += 100

            # Ubicación relevante
            if depth == 0:
                score += 30
            elif any(part.lower() in ("icons", "resources", "assets", "share", "pixmaps") for part in rel_dir.parts):
                score += 40
            else:
                score -= depth * 5

            # Formato y resolución
            if name_lower.endswith(".svg"):
                score += 500  # SVG es el preferido por ser vectorial
            elif name_lower.endswith(".png"):
                w, h = get_png_dimensions(file_path)
                dim = max(w, h)
                if dim >= 256:
                    score += 300 + min(dim, 512)
                elif dim >= 128:
                    score += 200 + dim
                elif dim >= 48:
                    score += 100 + dim
                else:
                    score += dim
            elif name_lower.endswith(".ico"):
                score += 50  # ICO como último recurso

            if score > best_score:
                best_score = score
                best_icon = file_path

    return str(best_icon) if best_icon else None


def calculate_total_size(path: Path) -> int:
    """Calcula el tamaño total en bytes de un directorio o archivo."""
    total = 0
    try:
        if path.is_file():
            return path.stat().st_size
        for entry in path.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except Exception:
        pass
    return total


def detect_chrome_sandbox(root_dir: Path) -> Tuple[bool, Optional[str]]:
    """
    Detecta si existe un binario chrome-sandbox en la app (típico de Electron / Chromium).
    Retorna (has_sandbox, sandbox_path).
    """
    root_dir = root_dir.resolve()
    # Buscar primero directamente en la raíz o subdirectorios
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f in ("chrome-sandbox", "chrome_sandbox"):
                sandbox_file = Path(root) / f
                return True, str(sandbox_file)
    return False, None


def analyze_package(root_dir: Path, source_path_str: str, temp_dir_obj=None) -> AppPackageAnalysis:
    """
    Ejecuta el análisis integral del paquete portable extraído o referenciado.
    """
    source_name = Path(source_path_str).name
    app_name, app_id, version = infer_app_metadata(source_name)

    candidates = find_candidate_binaries(root_dir, app_name)
    selected = candidates[0] if candidates else None

    icon_path = find_best_icon(root_dir, app_name)
    has_sandbox, sandbox_path = detect_chrome_sandbox(root_dir)
    total_size = calculate_total_size(root_dir)

    return AppPackageAnalysis(
        source_path=source_path_str,
        root_dir=str(root_dir),
        app_name=app_name,
        app_id=app_id,
        version=version,
        temp_dir_obj=temp_dir_obj,
        candidates=candidates,
        selected_binary=selected,
        icon_path=icon_path,
        has_chrome_sandbox=has_sandbox,
        chrome_sandbox_path=sandbox_path,
        total_size_bytes=total_size,
        total_size_formatted=format_bytes(total_size),
    )
