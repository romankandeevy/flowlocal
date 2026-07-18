# -*- mode: python ; coding: utf-8 -*-
"""Сборка FlowLocal в один .exe. Звать не напрямую, а через tools/build.py:
он выставляет FLOWLOCAL_CUDA и чистит за собой.

Два варианта:
  cpu  - работает у всех. Основной: GigaAM живёт на процессоре, и после
         переезда на onnx-asr (PLAN, этап 2) CUDA не нужна никому.
  cuda - только если поставлено колесо onnxruntime-gpu и нужен Whisper на GPU.

Модель в сборку НЕ кладём: качается при первом запуске в models/ рядом с .exe.
Класть её внутрь значило бы распаковывать сотни мегабайт во временную папку при
каждом старте.

ХВОСТ (PLAN 8.4): это onefile, а Qt под LGPLv3 запечатан внутрь - значит
перелинковать его нельзя, и §4(d) LGPL нарушен. Раздавать .exe публично до
переезда на onedir нельзя. Половину хвоста этап 7 уже убрал: pystray (тоже
LGPLv3) ушёл вместе с tkinter, трей теперь на QSystemTrayIcon.
"""

import os

import PySide6
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# CPU-сборка отличается тем, что из неё выбрасываются CUDA-библиотеки. Раньше их
# всегда тащил ctranslate2; теперь они приезжают только с onnxruntime-gpu, если
# его поставили. На машине без NVIDIA это мёртвый груз в сотни мегабайт.
CUDA = os.environ.get("FLOWLOCAL_CUDA") == "1"

datas = [
    # Без шрифтов интерфейс останется без шрифтов - буквально: theme.py
    # регистрирует их из assets/fonts через AddFontResourceExW, а в системе
    # их нет. Путь внутри сборки тот же, потому что theme._assets_dir()
    # смотрит в sys._MEIPASS.
    ("assets/fonts", "assets/fonts"),
    ("assets/FlowLocal.ico", "assets"),
    # Первый запуск делает из примера свой config.json рядом с .exe.
    ("config.example.json", "."),
    # История версий: её показывает «О программе», и показывать обязана без
    # сети - вся мысль этой страницы в том, что интернет нужен один раз.
    ("CHANGELOG.md", "."),
    # QML: PyInstaller ищет импорты в .py и про .qml не знает.
    ("qml", "qml"),
    # Тексты лицензий - требование LGPLv3 §4(a) и OFL для шрифтов: их надо
    # раздавать вместе со сборкой, а не только упоминать в README.
    ("LICENSE", "licenses"),
    ("licenses", "licenses"),
]

# Две вещи, без которых собранный .exe падает на первой же загрузке модели, а
# из исходников всё работает:
#
# 1. onnx-asr спрашивает свою же версию через importlib.metadata, а PyInstaller
#    кладёт только код, без .dist-info -> «No package metadata was found».
# 2. Внутри пакета лежат данные (preprocessors/data/fbanks.npz - банки
#    фильтров для мел-спектрограммы). PyInstaller видит только .py -> файла
#    нет, модель не поднимается.
datas += copy_metadata("onnx-asr")
datas += collect_data_files("onnx_asr")

hiddenimports = [
    # pynput выбирает бэкенд в рантайме по платформе - статический анализ его
    # не видит.
    "pynput.mouse._win32",
    "pynput.keyboard._win32",
]

binaries = [
    # Грузится через ctypes из overlay_qt._preload_qml_deps(), а не импортом -
    # PyInstaller про такую зависимость не догадается, и тень у пилюли молча
    # пропадёт. Зачем этот костыль вообще нужен - см. PLAN 3.0.
    (os.path.join(os.path.dirname(PySide6.__file__), "Qt6QuickEffects.dll"), "."),
]

excludes = [
    # Тянутся транзитивно и весят прилично, а приложению не нужны.
    "matplotlib", "scipy", "pandas", "IPython", "pytest",
    "tkinter.test", "test",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

if not CUDA:
    # Выкидываем по имени файла: хука «собери без CUDA» нет ни у ctranslate2,
    # ни у onnxruntime-gpu.
    def _is_cuda(name: str) -> bool:
        n = os.path.basename(name).lower()
        return n.startswith(("cublas", "cudnn", "cudart", "cufft", "curand",
                             "cusolver", "cusparse", "nvrtc", "nvblas"))

    a.binaries = TOC([e for e in a.binaries if not _is_cuda(e[0])])


# --- Qt: берём только то, чем пользуемся -------------------------------------
#
# PyInstaller тащит PySide6 целиком - 388 МБ и 117 библиотек, включая Qt3D,
# WebEngine и Designer. Две причины выбросить лишнее, и вторая важнее первой:
#
# 1. Размер. Ради него и затевался переезд на onnx-asr (PLAN 0.3).
# 2. Лицензия. Qt Graphs, Quick 3D, Quick Timeline, Qml Compiler, Virtual
#    Keyboard и Lottie - GPL-only (PLAN 3). Мы их не используем, но раздавали
#    бы в каждой сборке. Проще не класть.
#
# Список - то, что нужно QtQuick, плюс наше: Widgets (трей и меню), Network
# (QLocalServer для «повторный запуск открывает окно»), QuickEffects (тень
# MultiEffect у пилюли).
_QT_KEEP = {
    "qt6core", "qt6gui", "qt6network", "qt6opengl", "qt6qml", "qt6qmlmeta",
    "qt6qmlmodels", "qt6qmlworkerscript", "qt6quick", "qt6quickeffects",
    "qt6quickshapes", "qt6shadertools", "qt6svg", "qt6widgets",
}


def _drop_qt(name: str) -> bool:
    """True - выбросить. Трогаем только Qt6*.dll: остальное не наше дело."""
    base = os.path.basename(name)
    low = base.lower()
    if not low.startswith("qt6") or not low.endswith(".dll"):
        return False
    return os.path.splitext(low)[0] not in _QT_KEEP


a.binaries = TOC([e for e in a.binaries if not _drop_qt(e[0])])
# Плагины и QML-модули выброшенных модулей тоже не нужны: без своей библиотеки
# они всё равно не загрузятся, а место занимают.
_DATA_DROP = ("pyside6/qml/qtquick3d", "pyside6/qml/qtcharts", "pyside6/qml/qtgraphs",
              "pyside6/qml/qtquick/timeline", "pyside6/qml/qtwebengine",
              "pyside6/qml/qtmultimedia", "pyside6/qml/qt3d",
              "pyside6/translations", "pyside6/examples", "pyside6/designer",
              "pyside6/assistant", "pyside6/linguist")
a.datas = TOC([e for e in a.datas
               if not any(d in e[0].lower().replace("\\", "/") for d in _DATA_DROP)])

pyz = PYZ(a.pure)

# ONEDIR, а не onefile - и это не вкусовщина, а условие лицензии.
#
# Qt (PySide6) и раньше pystray идут под LGPLv3. §4(d) требует оставить
# возможность подменить библиотеку своей сборкой и перелинковать приложение. В
# onefile всё запечатано внутрь .exe и распаковывается во временную папку -
# подменить нечего, требование нарушено. Тред об этом на форуме Qt до сих пор
# Unsolved, официального ответа нет; onedir снимает вопрос целиком.
#
# Побочно onedir ещё и быстрее стартует: onefile распаковывал сотни мегабайт
# во временную папку при КАЖДОМ запуске.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,     # <- ключевое отличие onedir от onefile
    name="FlowLocal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX ломает подпись и злит антивирусы, а экономит мало
    # Окно, а не консоль: иначе при каждом запуске висит чёрный квадрат.
    # Ошибки старта при этом уходят в никуда - поэтому app.py ловит их сам и
    # показывает MessageBox, см. блок __main__ там.
    console=False,
    disable_windowed_traceback=False,
    icon="assets/FlowLocal.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FlowLocal",
)
