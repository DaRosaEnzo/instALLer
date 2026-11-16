"""
InstALLer Data Models
Modelos de datos para el análisis de paquetes, ejecutables e instalaciones.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import datetime


@dataclass
class CandidateBinary:
    """Representa un ejecutable potencial encontrado dentro de la app."""
    name: str
    rel_path: str
    full_path: str
    is_elf: bool
    is_script: bool
    score: int = 0
    file_size: int = 0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppPackageAnalysis:
    """Resultado del análisis previo a la instalación de un paquete portable."""
    source_path: str
    root_dir: str
    app_name: str
    app_id: str
    version: str = "1.0.0"
    temp_dir_obj: Any = None
    candidates: List[CandidateBinary] = field(default_factory=list)
    selected_binary: Optional[CandidateBinary] = None
    icon_path: Optional[str] = None
    has_chrome_sandbox: bool = False
    chrome_sandbox_path: Optional[str] = None
    total_size_bytes: int = 0
    total_size_formatted: str = "0 B"

    def clean_temp(self) -> None:
        """Limpia el directorio temporal si existe."""
        if self.temp_dir_obj:
            try:
                self.temp_dir_obj.cleanup()
            except Exception:
                pass
            self.temp_dir_obj = None


@dataclass
class InstalledApp:
    """Representa una aplicación instalada y gestionada por InstALLer."""
    id: str
    name: str
    version: str
    install_path: str
    exec_path: str
    icon_path: Optional[str]
    desktop_file: str
    installed_at: str
    is_system: bool = False
    size_bytes: int = 0
    size_formatted: str = "0 B"
    has_chrome_sandbox: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstalledApp":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Desconocido"),
            version=data.get("version", "1.0.0"),
            install_path=data.get("install_path", ""),
            exec_path=data.get("exec_path", ""),
            icon_path=data.get("icon_path"),
            desktop_file=data.get("desktop_file", ""),
            installed_at=data.get("installed_at", datetime.datetime.now().isoformat()),
            is_system=bool(data.get("is_system", False)),
            size_bytes=int(data.get("size_bytes", 0)),
            size_formatted=data.get("size_formatted", "0 B"),
            has_chrome_sandbox=bool(data.get("has_chrome_sandbox", False)),
        )
