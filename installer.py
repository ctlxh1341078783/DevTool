"""
一键发布工具 — 安装程序（Windows / macOS）
双击运行，选择安装路径，自动复制文件、创建快捷方式、注册卸载信息
"""
import sys
import os
import json
import shutil
import subprocess
import threading
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

IS_FROZEN = getattr(sys, 'frozen', False)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

APP_NAME = "一键发布工具"
EXE_NAME = "一键发布工具.exe" if IS_WIN else "一键发布工具"
UNINST_NAME = "一键发布工具卸载程序.exe" if IS_WIN else "一键发布工具卸载程序"

def get_bundled_app_dir() -> Path:
    if IS_FROZEN:
        return Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    app_dir = base / "dist" / APP_NAME
    if not app_dir.exists():
        alt = base / APP_NAME
        if alt.exists():
            return alt
    return app_dir

def get_default_install_path() -> Path:
    if IS_WIN:
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if is_admin:
            return Path(f"C:/Program Files/{APP_NAME}")
        else:
            local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            return Path(local) / "Programs" / APP_NAME
    elif IS_MAC:
        return Path(f"/Applications/{APP_NAME}")
    else:
        return Path.home() / "Applications" / APP_NAME

def load_version() -> dict:
    try:
        vp = Path(__file__).parent / "version.json"
        if not vp.exists() and IS_FROZEN:
            vp = Path(sys._MEIPASS) / "version.json"
        if vp.exists():
            return json.loads(vp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"version": "1.0.0", "build_date": "", "build_number": 1}

class InstallerWindow:
    def __init__(self):
        self.root = tk.Tk()
        ver = load_version().get("version", "1.0.0")
        self.root.title(f"{APP_NAME} v{ver} — 安装程序")
        self.root.geometry("540x400")
        self.root.resizable(False, False)
        self._installing = False
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#4e6ef2", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=APP_NAME, font=("微软雅黑", 16, "bold"),
                 fg="white", bg="#4e6ef2").pack(pady=12)

        body = tk.Frame(self.root, padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="安装路径：", font=("微软雅黑", 11)).pack(anchor=tk.W)
        path_frame = tk.Frame(body)
        path_frame.pack(fill=tk.X, pady=(5, 15))
        self.path_var = tk.StringVar(value=str(get_default_install_path()))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, font=("微软雅黑", 10))
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="浏览...", command=self._browse, width=8).pack(side=tk.LEFT, padx=(6, 0))

        ver = load_version()
        info = f"版本: v{ver.get('version', '?')}  |  构建日期: {ver.get('build_date', '?')}"
        tk.Label(body, text=info, font=("微软雅黑", 9), fg="#888").pack(anchor=tk.W)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(body, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(15, 5))

        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(body, textvariable=self.status_var, font=("微软雅黑", 10)).pack(anchor=tk.W)

        btn_frame = tk.Frame(body)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        self.install_btn = tk.Button(btn_frame, text="开始安装", command=self._start_install,
                                     bg="#4e6ef2", fg="white", font=("微软雅黑", 11, "bold"),
                                     relief=tk.FLAT, cursor="hand2", padx=25, pady=6)
        self.install_btn.pack(side=tk.LEFT)
        self.launch_var = tk.BooleanVar(value=True)
        tk.Checkbutton(btn_frame, text="安装完成后启动程序", variable=self.launch_var,
                       font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=15)
        tk.Button(btn_frame, text="取消", command=self.root.destroy,
                  font=("微软雅黑", 10), padx=15).pack(side=tk.RIGHT)

    def _browse(self):
        d = filedialog.askdirectory(title="选择安装目录", initialdir=self.path_var.get())
        if d:
            self.path_var.set(d)

    def _start_install(self):
        if self._installing:
            return
        target = Path(self.path_var.get().strip())
        if not str(target):
            messagebox.showerror("错误", "请选择安装路径")
            return
        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            messagebox.showerror("权限不足", f"无法创建目录:\n{target}\n\n请以管理员身份运行或选择其他路径")
            return

        self._installing = True
        self.install_btn.config(state=tk.DISABLED, text="安装中...")
        t = threading.Thread(target=self._do_install, args=(target,), daemon=True)
        t.start()
        self._poll(t)

    def _do_install(self, target: Path):
        self._report(5, "正在准备...")
        source = get_bundled_app_dir()
        if not source.exists():
            self._report_error(f"未找到安装源目录:\n{source}")
            return

        files = []
        for f in source.rglob("*"):
            if f.is_file():
                files.append(f)
        total = len(files)

        self._report(10, f"正在安装 ({total} 个文件)...")

        for i, src in enumerate(files):
            try:
                rel = src.relative_to(source)
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
            except Exception as e:
                self._report_error(f"复制失败: {src.name}\n{e}")
                return
            pct = 10 + int((i + 1) / total * 60)
            if i % 50 == 0 or pct % 10 == 0:
                self._report(pct, f"正在安装... ({i+1}/{total})")

        self._report(75, "正在创建快捷方式...")
        self._create_shortcuts(target)

        self._report(85, "正在注册卸载信息...")
        self._register_uninstall(target)

        self._report(95, "正在复制卸载程序...")
        self._copy_uninstaller(target)

        self._report(100, "安装完成！")

    def _create_shortcuts(self, target: Path):
        exe = target / EXE_NAME
        if not exe.exists():
            return
        if IS_WIN:
            self._create_desktop_shortcut_win(exe)
            self._create_start_menu_win(target, exe)
        elif IS_MAC:
            self._create_desktop_shortcut_mac(target, exe)

    def _create_desktop_shortcut_win(self, target_exe: Path):
        ps = f'''
$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "{APP_NAME}.lnk"
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = "{target_exe}"
$sc.WorkingDirectory = "{target_exe.parent}"
$sc.Description = "{APP_NAME}"
$sc.IconLocation = "{target_exe}"
$sc.Save()
'''
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                           "-Command", ps], capture_output=True, timeout=30)
        except Exception:
            pass

    def _create_start_menu_win(self, target: Path, target_exe: Path):
        try:
            programs = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        except KeyError:
            return
        group = programs / APP_NAME
        group.mkdir(parents=True, exist_ok=True)

        lnk_main = group / f"{APP_NAME}.lnk"
        ps = f'''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("{lnk_main}")
$sc.TargetPath = "{target_exe}"
$sc.WorkingDirectory = "{target_exe.parent}"
$sc.Description = "{APP_NAME}"
$sc.IconLocation = "{target_exe}"
$sc.Save()

$sc2 = $ws.CreateShortcut("{group / f'卸载{APP_NAME}.lnk'}")
$sc2.TargetPath = "{target / UNINST_NAME}"
$sc2.WorkingDirectory = "{target}"
$sc2.Description = "卸载{APP_NAME}"
$sc2.Save()
'''
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                           "-Command", ps], capture_output=True, timeout=30)
        except Exception:
            pass

    def _create_desktop_shortcut_mac(self, target: Path, target_exe: Path):
        desktop = Path.home() / "Desktop"
        shortcut = desktop / f"{APP_NAME}.command"
        content = f'''#!/bin/bash
cd "{target}"
open "{target_exe}"
'''
        try:
            shortcut.write_text(content)
            os.chmod(shortcut, 0o755)
        except Exception:
            pass

    def _register_uninstall(self, target: Path):
        if sys.platform != "win32":
            return
        import winreg
        uninstaller = target / UNINST_NAME
        ver = load_version().get("version", "1.0.0")

        values = {
            "DisplayName": APP_NAME,
            "UninstallString": str(uninstaller),
            "InstallLocation": str(target),
            "DisplayVersion": ver,
            "Publisher": "DevTool",
            "NoModify": 1,
            "NoRepair": 1,
        }
        for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                key = winreg.CreateKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}")
                for k, v in values.items():
                    reg_type = winreg.REG_DWORD if isinstance(v, int) else winreg.REG_SZ
                    winreg.SetValueEx(key, k, 0, reg_type, v)
                winreg.CloseKey(key)
                return
            except (OSError, PermissionError):
                continue

    def _copy_uninstaller(self, target: Path):
        source = get_bundled_app_dir()
        uninst = source / UNINST_NAME
        if uninst.exists():
            shutil.copy2(str(uninst), str(target / UNINST_NAME))

    def _report(self, pct: int, msg: str):
        self.root.after(0, lambda: [
            self.progress_var.set(pct),
            self.status_var.set(msg)
        ])

    def _report_error(self, msg: str):
        self.root.after(0, lambda: [
            self.status_var.set(msg),
            messagebox.showerror("安装失败", msg),
            self.install_btn.config(state=tk.NORMAL, text="重试安装"),
            setattr(self, '_installing', False)
        ])

    def _poll(self, thread):
        if thread.is_alive():
            self.root.after(200, lambda: self._poll(thread))
        else:
            self.install_btn.config(state=tk.NORMAL, text="安装完成 ✓")
            if self.launch_var.get():
                target = Path(self.path_var.get()) / EXE_NAME
                if target.exists():
                    subprocess.Popen([str(target)], cwd=str(target.parent))

    def run(self):
        self.root.mainloop()

def main():
    app = InstallerWindow()
    app.run()

if __name__ == "__main__":
    main()
