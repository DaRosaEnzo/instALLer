# 📦 InstALLer

**InstALLer** es una aplicación de escritorio nativa para Ubuntu / Linux diseñada para actuar como un instalador y gestor visual de *"arrastrar y soltar"* (Drag & Drop) para aplicaciones portables distribuidas en archivos comprimidos (`.tar.gz`, `.tar.xz`, `.zip`, `.tar.bz2`) o carpetas sueltas.

Desarrollada con **Python**, **GTK4** y **Libadwaita**, InstALLer prioriza la eficiencia, respuesta instantánea y bajo consumo de memoria RAM (ideal para equipos con 8 GB de RAM o recursos limitados), integrándose perfectamente con el diseño moderno de Ubuntu y GNOME.

---

## ✨ Características Principales

### 1. Interfaz Gráfica Moderna y Minimalista (Libadwaita)
- **Pestaña "Instalar"**:
  - Zona amplia de **Drag & Drop** con respuesta visual interactiva.
  - Botones tradicionales para **"Seleccionar archivo..."** o **"Seleccionar carpeta..."**.
  - Opciones de destino: **Directorio personal** (`~/.local/share/installer/apps/`) o **Sistema** (`/opt/`).
  - Barra de progreso y spinner sin congelar la interfaz gracias a ejecución multihilo con `GLib.idle_add`.
- **Pestaña "Apps Instaladas"**:
  - Catálogo de todas las aplicaciones gestionadas con su nombre, ícono de alta resolución, ruta y peso formateado en disco.
  - **Lanzador directo**: ejecutá cualquier app instalada con un solo clic.
  - **Actualizar**: pisá una versión vieja con un nuevo archivo comprimido manteniendo su lanzador y configuración.
  - **Desinstalar**: eliminación limpia en un clic de la carpeta de la app y su acceso directo `.desktop`, sin dejar residuos.

### 2. Detección Inteligente y Automática (Backend)
- **Descompresión segura y normalización**: Descomprime archivos `.tar.gz`, `.tgz`, `.tar.xz`, `.txz`, `.zip`, `.tar.bz2` con protección contra *Zip Slip* / *Path Traversal* y normalización de carpetas anidadas.
- **Análisis de ejecutables (ELF y Shell)**:
  - Inspecciona binarios ejecutables reales mediante encabezados ELF (`ET_EXEC` y `ET_DYN` con `PT_INTERP`).
  - **Ignora automáticamente**: bibliotecas compartidas (`*.so*`, `lib*.so`), archivos de datos (`snapshot_blob.bin`, `v8_context_snapshot.bin`, etc.), crashpad handlers, desinstaladores (`uninstall*`) y scripts internos.
  - Si hay ambigüedad o múltiples opciones, presenta un diálogo ordenado con la opción recomendada.
- **Compatibilidad con Electron y Chromium**:
  - Detecta la presencia de `chrome-sandbox`.
  - Configura automáticamente sus permisos SUID requeridos (`root:root` y `chmod 4755`) mediante un diálogo gráfico seguro de `pkexec` (sin hardcodear contraseñas).
- **Asignación automática del mejor ícono**:
  - Escanea la carpeta buscando archivos `.svg`, `.png` o `.ico`.
  - Prioriza archivos vectoriales escalables (`.svg`) y analiza las dimensiones de archivos `.png` seleccionando las versiones de mayor resolución (512x512, 256x256).
- **Integración con el Menú de Ubuntu**:
  - Crea lanzadores `.desktop` estándar en `~/.local/share/applications/`.
  - Ejecuta de inmediato `update-desktop-database` para que la app aparezca al instante en el menú de aplicaciones / Dash de Ubuntu.
- **Registro Liviano en JSON**:
  - Almacena el historial y rutas exactas en `~/.config/installer/registry.json`.

---

## 📂 Estructura del Proyecto

```text
installer/
├── installer/
│   ├── __init__.py           # Inicializador del paquete
│   ├── constants.py          # Rutas, extensiones y nombres ignorados
│   ├── models.py             # Modelos de datos (AppPackageAnalysis, InstalledApp, etc.)
│   ├── extractor.py          # Descompresión segura y restauración de permisos
│   ├── detector.py           # Detección de binarios ELF/Scripts, chrome-sandbox e íconos
│   ├── installer.py          # Lógica de instalación, permisos pkexec y lanzadores .desktop
│   ├── registry.py           # Registro en JSON y desinstalador limpio
│   ├── main.py               # Punto de entrada Adw.Application
│   └── ui/
│       ├── __init__.py
│       ├── window.py         # Ventana principal Adw.ApplicationWindow
│       ├── install_view.py   # Vista de Drag & Drop y selector de archivos
│       ├── apps_view.py      # Vista de gestión de apps instaladas
│       ├── review_dialog.py  # Diálogo de confirmación de metadatos previo a instalar
│       └── binary_dialog.py  # Diálogo para seleccionar ejecutable en caso de ambigüedad
├── assets/
│   ├── installer.svg           # Ícono vectorial oficial de InstALLer
│   ├── installer.png           # Ícono en alta resolución (128x128)
│   └── style.css             # Estilos CSS de Adwaita para la zona de arrastre
├── data/
│   └── io.github.installer.InstALLer.desktop  # Lanzador de escritorio para InstALLer
├── tests/
│   └── test_installer.py       # Suite automatizada de pruebas unitarias
├── install.sh                # Script de instalación automática de dependencias y sistema
├── run.sh                    # Script para ejecutar InstALLer directamente en desarrollo
└── README.md                 # Documentación completa
```

---

## 🚀 Instalación en Ubuntu

Para instalar las dependencias necesarias y registrar InstALLer en tu sistema:

```bash
cd installer
chmod +x install.sh
./install.sh
```

El instalador:
1. Instalará los paquetes requeridos mediante `apt`: `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `desktop-file-utils`, `tar`, `xz-utils`, `unzip`, `pkexec`.
2. Instalará InstALLer en `/opt/installer` y creará el comando `/usr/local/bin/installer`.
3. Instalará el ícono del sistema y el archivo `.desktop` para que puedas abrirlo directamente desde el menú de aplicaciones de Ubuntu.

---

## 💻 Ejecución directa (sin instalar)

Si preferís probarlo directamente desde el código fuente sin modificar el sistema:

```bash
cd installer
chmod +x run.sh
./run.sh
```

También podés pasarle directamente la ruta a un archivo comprimido o carpeta:

```bash
./run.sh /ruta/a/mi-app-portable.tar.gz
```

---

## 🧪 Ejecución de Pruebas Automatizadas

InstALLer incluye una suite de pruebas para verificar la descompresión, la detección de binarios, la detección de Electron y la desinstalación limpia:

```bash
python3 installer/tests/test_installer.py
```

---

## 📋 Requisitos del Sistema

- **Sistema Operativo**: Ubuntu 22.04 LTS o superior (o cualquier distribución Linux con GTK4 y Libadwaita).
- **Python**: 3.10 o superior.
- **Bibliotecas**:
  - `python3-gi`
  - `gir1.2-gtk-4.0`
  - `gir1.2-adw-1`
  - `pkexec`
