# PyInstaller build of the macOS app: one .app, no Python needed on the machine.
#   uv run pyinstaller askbase.spec --noconfirm
#
# Qt modules that are not used are dropped on purpose. Qt Virtual Keyboard in
# particular is GPL-only and must not ship inside an MIT-licensed application.

datas = [
    ("askbase/fonts", "askbase/fonts"),
    ("askbase/icon.svg", "askbase"),
    ("../src/nl2sql_app/safety.py", "nl2sql_app"),
]
hiddenimports = ["sqlglot", "sqlglot.dialects", "nl2sql_app", "nl2sql_app.safety"]

a = Analysis(
    ["askbase/__main__.py"],
    pathex=[".", "../src"],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest", "numpy", "PIL",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL",
    ],
    noarchive=False,
)
QT_UNUSED = ("QtQuick", "QtQml", "QtVirtualKeyboard", "QtPdf", "QtOpenGL",
             "platforminputcontexts", "qtvirtualkeyboard", "Qt3D", "QtMultimedia",
             "QtWebEngine", "QtCharts", "QtDataVisualization")
a.binaries = [b for b in a.binaries if not any(q in b[0] for q in QT_UNUSED)]
a.datas = [d for d in a.datas if not any(q in d[0] for q in QT_UNUSED)]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Askbase", console=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Askbase")
app = BUNDLE(
    coll,
    name="Askbase.app",
    icon="askbase/icon.icns",
    bundle_identifier="tech.besk.askbase",
    version="0.1.0",
    info_plist={
        "CFBundleName": "Askbase",
        "CFBundleDisplayName": "Askbase",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "13.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSDesktopFolderUsageDescription": "Чтобы открыть базу данных, которую вы выберете.",
        "NSDocumentsFolderUsageDescription": "Чтобы открыть базу данных, которую вы выберете.",
        "NSDownloadsFolderUsageDescription": "Чтобы открыть базу данных, которую вы выберете.",
    },
)
