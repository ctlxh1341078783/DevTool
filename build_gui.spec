# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包：一键发布工具"""
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

a = Analysis(
    [str(PROJECT_ROOT / "publish_tool.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "version.json"), "."),
        (str(PROJECT_ROOT / "projects.json"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "test", "matplotlib", "PIL",
              "frida", "frida_tools", "uiautomator2", "transformers",
              "sentence_transformers", "text2vec", "tokenizers",
              "openpyxl", "huggingface_hub"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="一键发布工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    [],
    name="一键发布工具",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
