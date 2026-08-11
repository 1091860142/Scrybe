# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 + 无控制台。"""
from PyInstaller.utils.hooks import collect_all

# PyAV 内置 FFmpeg 解码库；dashscope 含动态导入，均整体收集
av_datas, av_binaries, av_hidden = collect_all("av")
ds_datas, ds_binaries, ds_hidden = collect_all("dashscope")

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=av_binaries + ds_binaries,
    datas=av_datas + ds_datas,
    hiddenimports=["requests", "websocket"] + av_hidden + ds_hidden,
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtMultimedia",
        "PySide6.QtPdf",
        "tkinter",
        "matplotlib",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Scrybe",
    debug=False,
    strip=False,
    upx=False,  # UPX 会增加杀软误报，且可能破坏 Qt DLL
    console=False,  # 窗口程序
    disable_windowed_traceback=False,
)
