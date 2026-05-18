"""
一键发布工具 — 跨平台（Windows / macOS）
选择项目目录 → 输入版本号和更新内容 → 一键发布
"""
import json
import sys
import os
import shutil
import subprocess
import threading
import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APPHOME = Path(__file__).parent
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    CONFIG_FILE = Path(sys.executable).parent / "projects.json"
else:
    CONFIG_FILE = APPHOME / "projects.json"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

FONT = ("Microsoft YaHei", 9) if IS_WIN else ("PingFang SC", 11)
FONT_BOLD = ("Microsoft YaHei", 9, "bold") if IS_WIN else ("PingFang SC", 11, "bold")
FONT_TITLE = ("Microsoft YaHei", 12, "bold") if IS_WIN else ("PingFang SC", 14, "bold")
MONO = ("Consolas", 9) if IS_WIN else ("Menlo", 10)
BG = "#f0f2f5"
SURF = "#ffffff"
FG = "#1a1a2e"
ACC = "#4e6ef2"
ACC_H = "#3b5de7"
SUCC = "#2ecc71"
DANGER = "#e74c3c"
FG_M = "#666"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"projects": [], "recent_dirs": []}


def save_config(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class PublishTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("一键发布工具")
        self.root.geometry("620x780")
        self.root.configure(bg=BG)
        self.root.minsize(520, 600)

        self.config = load_config()
        self._project_dir = None
        self._version_info = {}
        self._version_file = None
        self._building = False

        self._set_app_icon()
        self._load_own_version()
        self._build_ui()

        # 自动恢复上次目录
        recent = self.config.get("recent_dirs", [])
        if recent:
            self.dir_var.set(recent[0])
            self._on_dir_changed()

    def _set_app_icon(self):
        """设置窗口图标"""
        if not IS_WIN:
            return
        try:
            ico = APPHOME / "assets" / "app_icon.ico"
            if IS_FROZEN:
                ico = Path(sys._MEIPASS) / "assets" / "app_icon.ico"
            if ico.exists():
                self.root.iconbitmap(str(ico))
        except Exception:
            pass

    def _load_own_version(self):
        """加载 DevTool 自己的版本信息"""
        try:
            vp = APPHOME / "version.json"
            if IS_FROZEN:
                vp = Path(sys._MEIPASS) / "version.json"
            if vp.exists():
                info = json.loads(vp.read_text(encoding="utf-8"))
                self.root.title(f"一键发布工具 v{info.get('version', '1.0.0')}")
        except Exception:
            pass

    # ── UI ──────────────────────────────────────────────

    def _build_ui(self):
        header = tk.Frame(self.root, bg=ACC, height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="🚀 一键发布工具", font=FONT_TITLE,
                 fg="white", bg=ACC).pack(pady=10)

        body = tk.Frame(self.root, bg=BG, padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        # ── 项目目录 ──
        tk.Label(body, text="项目目录:", bg=BG, fg=FG, font=FONT).grid(
            row=0, column=0, sticky=tk.W, pady=4)
        dir_frame = tk.Frame(body, bg=BG)
        dir_frame.grid(row=0, column=1, sticky=tk.EW, pady=4, padx=(8, 0))
        self.dir_var = tk.StringVar()
        self.dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, font=FONT)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="浏览...", command=self._browse_dir,
                   width=8).pack(side=tk.LEFT, padx=(4, 0))
        self.dir_entry.bind("<FocusOut>", lambda e: self._on_dir_changed())

        #  最近目录
        tk.Label(body, text="最近:", bg=BG, fg=FG_M, font=("Microsoft YaHei", 8) if IS_WIN else ("PingFang SC", 9)).grid(
            row=1, column=1, sticky=tk.W, pady=(0, 8))
        self._recent_frame = tk.Frame(body, bg=BG)
        self._recent_frame.grid(row=1, column=1, sticky=tk.EW, pady=(0, 8))
        self._refresh_recent_links()

        # ── 版本信息 ──
        info_frame = tk.LabelFrame(body, text="版本信息", bg=BG, fg=FG,
                                    font=FONT_BOLD, padx=12, pady=8)
        info_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 8))

        self.current_ver_var = tk.StringVar(value="请先选择项目目录")
        tk.Label(info_frame, textvariable=self.current_ver_var, bg=BG, fg=FG,
                 font=FONT).pack(anchor=tk.W)

        ver_row = tk.Frame(info_frame, bg=BG)
        ver_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(ver_row, text="新版本号:", bg=BG, fg=FG, font=FONT).pack(side=tk.LEFT)
        self.new_ver_var = tk.StringVar()
        self.new_ver_entry = ttk.Entry(ver_row, textvariable=self.new_ver_var,
                                        font=FONT, width=20)
        self.new_ver_entry.pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(ver_row, text="  留空自动建议", bg=BG, fg=FG_M,
                 font=("Microsoft YaHei", 8) if IS_WIN else ("PingFang SC", 9)).pack(side=tk.LEFT)

        # ── 更新内容 ──
        tk.Label(body, text="更新内容（一行一条，无需前缀符号）:", bg=BG, fg=FG,
                 font=FONT).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        self.changelog_text = tk.Text(body, height=6, width=50, font=FONT,
                                       relief=tk.SOLID, borderwidth=1,
                                       fg=FG, bg=SURF, padx=8, pady=6)
        self.changelog_text.grid(row=4, column=0, columnspan=2, sticky=tk.EW,
                                  pady=(0, 8))

        # ── 选项 ──
        opt_frame = tk.Frame(body, bg=BG)
        opt_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        self.auto_push_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text="自动 git commit & push", variable=self.auto_push_var,
                       bg=BG, font=FONT, activebackground=BG,
                       selectcolor=BG).pack(side=tk.LEFT)

        # ── 按钮 ──
        btn_row = tk.Frame(body, bg=BG)
        btn_row.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))

        self.publish_btn = tk.Button(btn_row, text="一键发布", command=self._publish,
                                      bg=ACC, fg="white", font=FONT_BOLD,
                                      relief=tk.FLAT, cursor="hand2", padx=28, pady=8)
        self.publish_btn.pack(side=tk.LEFT)

        self.build_only_btn = tk.Button(btn_row, text="仅构建", command=lambda: self._publish(push=False),
                                         bg="#666", fg="white", font=FONT,
                                         relief=tk.FLAT, cursor="hand2", padx=20, pady=8)
        self.build_only_btn.pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(btn_row, text="新建项目", command=self._new_project,
                  bg=SUCC, fg="white", font=FONT,
                  relief=tk.FLAT, cursor="hand2", padx=12, pady=8).pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(btn_row, text="GitHub 仓库设置", command=self._show_github_help,
                  bg="#333", fg="white", font=FONT,
                  relief=tk.FLAT, cursor="hand2", padx=12, pady=8).pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(btn_row, mode="indeterminate", length=100)

        # ── 输出日志 ──
        tk.Label(body, text="输出日志:", bg=BG, fg=FG, font=FONT).grid(
            row=7, column=0, columnspan=2, sticky=tk.W, pady=(4, 2))
        log_frame = tk.Frame(body, bg="#1e1e1e")
        log_frame.grid(row=8, column=0, columnspan=2, sticky=tk.NSEW)
        body.rowconfigure(8, weight=1)
        body.columnconfigure(1, weight=1)

        self.log_text = tk.Text(log_frame, height=10, font=MONO,
                                 bg="#1e1e1e", fg="#d4d4d4", relief=tk.FLAT,
                                 padx=10, pady=8, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.status_var = tk.StringVar(value="就绪 — 选择项目目录开始")
        tk.Label(self.root, textvariable=self.status_var, bg="#e8e8e8", fg=FG_M,
                 font=MONO, anchor=tk.W, padx=12, pady=3).pack(
            fill=tk.X, side=tk.BOTTOM)

    # ── 项目目录选择 ──────────────────────────────────

    def _browse_dir(self):
        d = filedialog.askdirectory(title="选择项目根目录（包含 version.json 的目录）")
        if d:
            self.dir_var.set(d)
            self._on_dir_changed()

    def _on_dir_changed(self, *_):
        d = self.dir_var.get().strip()
        if not d:
            return
        p = Path(d)
        if not p.exists():
            self._log(f"目录不存在: {d}", "warn")
            return

        # 查找 version.json
        vf = p / "version.json"
        if not vf.exists():
            self._log(f"未找到 version.json，请确认目录", "warn")
            self.current_ver_var.set(f"⚠  {d} 中没有 version.json")
            self._version_file = None
            return

        self._project_dir = p
        self._version_file = vf
        self._refresh_version()
        self._add_recent_dir(d)
        self._log(f"已加载项目: {p.name}", "ok")

    def _refresh_version(self):
        if not self._version_file:
            return
        try:
            self._version_info = json.loads(self._version_file.read_text(encoding="utf-8"))
            ver = self._version_info.get("version", "?")
            build = self._version_info.get("build_number", "?")
            date = self._version_info.get("build_date", "?")
            self.current_ver_var.set(f"v{ver}  |  构建 {build}  |  {date}")
            parts = ver.split(".")
            suggested = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
            self.new_ver_var.set(suggested)
        except Exception as e:
            self.current_ver_var.set(f"读取失败: {e}")

    def _add_recent_dir(self, d: str):
        recent = self.config.get("recent_dirs", [])
        if d in recent:
            recent.remove(d)
        recent.insert(0, d)
        recent = recent[:8]
        self.config["recent_dirs"] = recent
        save_config(self.config)
        self._refresh_recent_links()

    def _refresh_recent_links(self):
        for w in self._recent_frame.winfo_children():
            w.destroy()
        recent = self.config.get("recent_dirs", [])
        if not recent:
            return
        for i, d in enumerate(recent[:5]):
            name = Path(d).name
            lbl = tk.Label(self._recent_frame, text=name, fg=ACC, bg=BG,
                           font=("Microsoft YaHei", 8, "underline") if IS_WIN else ("PingFang SC", 9, "underline"),
                           cursor="hand2")
            lbl.pack(side=tk.LEFT, padx=(0, 10))
            lbl.bind("<Button-1>", lambda e, d=d: self._select_recent(d))

    def _select_recent(self, d: str):
        self.dir_var.set(d)
        self._on_dir_changed()

    # ── 日志 ─────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        colors = {"info": "#82aaff", "ok": "#c3e88d", "err": "#ff5370", "warn": "#ffcb6b"}
        tag = {"info": "  ", "ok": "✓ ", "err": "✗ ", "warn": "⚠ "}

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{tag.get(level, '  ')}{msg}\n")
        line_start = self.log_text.index("end-2l linestart")
        self.log_text.tag_add(level, line_start, "end-1l")
        self.log_text.tag_config(level, foreground=colors.get(level, colors["info"]))
        self.log_text.configure(state=tk.DISABLED)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    # ── 新建项目 ────────────────────────────────────

    def _new_project(self):
        win = tk.Toplevel(self.root, bg=SURF)
        win.title("新建项目")
        win.geometry("540x620")
        win.resizable(True, True)
        win.minsize(480, 500)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="新建项目", bg=ACC, fg="white",
                 font=FONT_TITLE).pack(fill=tk.X, pady=(0, 12))

        body = tk.Frame(win, bg=SURF, padx=20)
        body.pack(fill=tk.BOTH, expand=True)

        # 项目名称
        fields = [
            ("项目名称(中文)", "name", "我的新项目"),
            ("主程序文件", "main", "gui_main.py"),
            ("GitHub 仓库名", "repo", ""),
            ("GitHub 用户名", "user", "ctlxh1341078783"),
        ]
        vars_dict = {}

        for label, key, default in fields:
            tk.Label(body, text=f"{label}:", bg=SURF, fg=FG, font=FONT).pack(anchor=tk.W, pady=(8, 2))
            var = tk.StringVar(value=default)
            vars_dict[key] = var
            ttk.Entry(body, textvariable=var, font=FONT).pack(fill=tk.X)

        # 项目目录
        tk.Label(body, text="项目目录:", bg=SURF, fg=FG, font=FONT).pack(anchor=tk.W, pady=(8, 2))
        dir_frame = tk.Frame(body, bg=SURF)
        dir_frame.pack(fill=tk.X)
        dir_var = tk.StringVar(value="E:/新项目")
        ttk.Entry(dir_frame, textvariable=dir_var, font=FONT).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="浏览...",
                   command=lambda: dir_var.set(filedialog.askdirectory() or dir_var.get()),
                   width=8).pack(side=tk.LEFT, padx=(4, 0))

        # 说明
        tk.Label(body, text="", bg=SURF).pack()
        tk.Label(body, text="将自动创建以下文件：\n"
                 "  version.json, build_gui.spec, installer.py,\n"
                 "  uninstaller.py, build_installer.spec,\n"
                 "  build_uninstaller.spec, build_all.bat,\n"
                 "  build_all.sh, .gitignore",
                 bg=SURF, fg=FG_M, font=FONT, justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 4))

        # 日志
        log_box = tk.Text(body, height=5, font=MONO, bg="#1e1e1e", fg="#d4d4d4",
                           relief=tk.FLAT, padx=8, pady=6)
        log_box.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        def append(text):
            log_box.insert(tk.END, text)
            log_box.see(tk.END)
            win.update()

        # 按钮
        btn_row = tk.Frame(win, bg=SURF)
        btn_row.pack(fill=tk.X, padx=20, pady=(0, 12))

        def do_create():
            name = vars_dict["name"].get().strip()
            main = vars_dict["main"].get().strip()
            repo = vars_dict["repo"].get().strip()
            user = vars_dict["user"].get().strip()
            d = Path(dir_var.get().strip())

            if not name:
                messagebox.showwarning("提示", "请输入项目名称")
                return

            log_box.delete("1.0", tk.END)
            d.mkdir(parents=True, exist_ok=True)

            today = datetime.date.today().isoformat()
            safe_name = d.name

            # 1. version.json
            append("创建 version.json...\n")
            ver = {
                "version": "1.0.0", "build_date": today, "build_number": 1,
                "github_repo": f"{user}/{repo}" if repo else "",
                "changelog": ["初始版本"]
            }
            (d / "version.json").write_text(
                json.dumps(ver, ensure_ascii=False, indent=2), encoding="utf-8")
            append("  ✓ version.json\n")

            # 2. build_gui.spec
            append("创建 build_gui.spec...\n")
            spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

a = Analysis(
    [str(PROJECT_ROOT / "{main}")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "version.json"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "test", "matplotlib", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="{name}",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe, a.binaries, a.datas, [],
    name="{name}",
    debug=False, strip=False, upx=True, upx_exclude=[],
    console=False, disable_windowed_traceback=False,
)
'''
            (d / "build_gui.spec").write_text(spec_content, encoding="utf-8")
            append("  ✓ build_gui.spec\n")

            # 3. installer.py (通用模板)
            append("创建 installer.py...\n")
            installer_code = f'''"""
{name} — 安装程序（Windows / macOS）
"""
import sys, os, json, shutil, subprocess, threading, tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

IS_FROZEN = getattr(sys, 'frozen', False)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

def get_bundled_app_dir():
    if IS_FROZEN: return Path(sys._MEIPASS)
    return Path(__file__).parent / "dist" / "{name}"

def get_default_install_path():
    if IS_WIN:
        import ctypes
        try:
            if ctypes.windll.shell32.IsUserAnAdmin():
                return Path("C:/Program Files/{name}")
        except: pass
        return Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "Programs" / "{name}"
    elif IS_MAC:
        return Path("/Applications/{name}")
    return Path.home() / "Applications" / "{name}"

def get_exe_name():
    return "{name}.exe" if IS_WIN else "{name}"

def load_version():
    vp = Path(sys._MEIPASS if IS_FROZEN else __file__).parent / "version.json"
    if vp.exists(): return json.loads(vp.read_text(encoding="utf-8"))
    return {{"version": "1.0.0"}}

class Installer:
    def __init__(self):
        self.root = tk.Tk()
        ver = load_version().get("version", "1.0.0")
        self.root.title(f"{name} v{{ver}} — 安装程序")
        self.root.geometry("600x440")
        self.root.resizable(False, False)
        self._installing = False
        self._build_ui()

    def _build_ui(self):
        tk.Label(self.root, text="{name}", font=("Microsoft YaHei", 16, "bold"),
                 fg="white", bg="#667eea").pack(fill=tk.X, pady=12)
        body = tk.Frame(self.root, padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text="安装路径：", font=("Microsoft YaHei", 11)).pack(anchor=tk.W)
        pf = tk.Frame(body); pf.pack(fill=tk.X, pady=(5, 15))
        self.path_var = tk.StringVar(value=str(get_default_install_path()))
        ttk.Entry(pf, textvariable=self.path_var, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(pf, text="浏览...", command=lambda: (d := filedialog.askdirectory()) and self.path_var.set(d), width=8).pack(side=tk.LEFT, padx=(6, 0))
        self.progress = ttk.Progressbar(body, maximum=100)
        self.progress.pack(fill=tk.X, pady=(15, 5))
        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(body, textvariable=self.status_var, font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        bf = tk.Frame(body); bf.pack(fill=tk.X, pady=(15, 0))
        self.btn = tk.Button(bf, text="开始安装", command=self._start, bg="#667eea", fg="white",
                              font=("Microsoft YaHei", 11, "bold"), relief=tk.FLAT, padx=25, pady=6)
        self.btn.pack(side=tk.LEFT)
        self.launch_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bf, text="安装完成后启动程序", variable=self.launch_var, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=15)
        tk.Button(bf, text="取消", command=self.root.destroy, font=("Microsoft YaHei", 10), padx=15).pack(side=tk.RIGHT)

    def _start(self):
        target = Path(self.path_var.get().strip())
        if not str(target): return messagebox.showerror("错误", "请选择安装路径")
        try: target.mkdir(parents=True, exist_ok=True)
        except PermissionError: return messagebox.showerror("权限不足", str(target))
        self._installing = True; self.btn.config(state=tk.DISABLED, text="安装中...")
        threading.Thread(target=self._install, args=(target,), daemon=True).start()

    def _install(self, target):
        src = get_bundled_app_dir()
        if not src.exists(): return self._err(f"未找到安装源:\\n{{src}}")
        files = [f for f in src.rglob("*") if f.is_file()]
        total = len(files)
        self._report(10, f"正在安装 ({{total}} 个文件)...")
        for i, f in enumerate(files):
            rel = f.relative_to(src); dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(f), str(dst))
            if i % 20 == 0: self._report(10 + int((i+1)/total*80), f"安装中... ({{i+1}}/{{total}})")
        # 桌面快捷方式
        if IS_WIN:
            ps = f'$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut([Environment]::GetFolderPath("Desktop")+"\\\\{name}.lnk");$s.TargetPath="{{target / get_exe_name()}}";$s.WorkingDirectory="{{target}}";$s.Save()'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
        elif IS_MAC:
            sc = Path.home() / "Desktop" / f"{name}.command"
            sc.write_text(f'#!/bin/bash\\ncd "{{target}}"\\nopen "{{target / get_exe_name()}}"')
            os.chmod(sc, 0o755)
        self._report(100, "安装完成！")

    def _report(self, pct, msg):
        self.root.after(0, lambda: [self.progress.configure(value=pct), self.status_var.set(msg)])

    def _err(self, msg):
        self.root.after(0, lambda: [self.status_var.set(msg), messagebox.showerror("安装失败", msg),
                                     self.btn.config(state=tk.NORMAL, text="重试安装")])

    def _check_thread(self, t):
        if t.is_alive(): self.root.after(200, lambda: self._check_thread(t))
        else:
            self.btn.config(state=tk.NORMAL, text="安装完成 ✓")
            if self.launch_var.get():
                exe = Path(self.path_var.get()) / get_exe_name()
                if exe.exists(): subprocess.Popen([str(exe)], cwd=str(exe.parent))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    Installer().run()
'''
            (d / "installer.py").write_text(installer_code, encoding="utf-8")
            append("  ✓ installer.py\n")

            # 4. uninstaller.py
            append("创建 uninstaller.py...\n")
            uninst_code = f'''""" {name} — 卸载程序 """
import sys, os, shutil, subprocess, tempfile, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
APP_NAME = "{name}"

def run_cleanup(install_dir: str):
    time.sleep(2)
    try: shutil.rmtree(install_dir, ignore_errors=True)
    except Exception: pass

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--cleanup":
        run_cleanup(sys.argv[2])
        sys.exit(0)
    UninstallerWindow().run()

class UninstallerWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{{APP_NAME}} — 卸载")
        self.root.geometry("500x360")
        self.root.resizable(True, True)
        self.root.minsize(460, 300)
        self._dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        self._build_ui()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg="#e74c3c", height=50)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"⚠ 卸载 {{APP_NAME}}", font=("Microsoft YaHei", 14, "bold"),
                 fg="white", bg="#e74c3c").pack(pady=10)
        body = tk.Frame(self.root, padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)
        for w, c in [("以下操作将不可撤销：", "#e74c3c"),
                      (f"  删除安装目录: {{self._dir}}", "#333"),
                      ("  删除桌面快捷方式", "#333")] + \\
                      ([("  删除开始菜单文件夹", "#333"), ("  清除注册表记录", "#333")] if IS_WIN else []):
            tk.Label(body, text=w, font=("Microsoft YaHei", 10), fg=c, anchor=tk.W, wraplength=440).pack(anchor=tk.W)
        self.confirm_var = tk.BooleanVar()
        tk.Checkbutton(body, text="我确认要彻底卸载此程序", variable=self.confirm_var,
                       font=("Microsoft YaHei", 10, "bold")).pack(pady=(15, 5))
        self.status_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self.status_var, font=("Microsoft YaHei", 10), fg="#888", wraplength=440).pack()
        bf = tk.Frame(body); bf.pack(fill=tk.X, pady=(15, 0))
        tk.Button(bf, text="确认卸载", command=self._do_uninstall, bg="#e74c3c", fg="white",
                  font=("Microsoft YaHei", 11, "bold"), relief=tk.FLAT, padx=25, pady=8).pack(side=tk.LEFT)
        tk.Button(bf, text="取消", command=self.root.destroy, font=("Microsoft YaHei", 10), padx=15, pady=6).pack(side=tk.RIGHT)

    def _do_uninstall(self):
        if not self.confirm_var.get():
            messagebox.showwarning("提示", "请先勾选确认框")
            return
        self.root.config(cursor="watch"); self.root.update()
        self.status_var.set("正在删除桌面快捷方式..."); self.root.update()
        d = str(self._dir)
        try:
            if IS_WIN:
                for n in [f"{{APP_NAME}}.lnk", APP_NAME]:
                    p = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / n
                    if p.exists(): os.remove(p)
                sd = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
                if sd.exists(): shutil.rmtree(sd)
            elif IS_MAC:
                sc = Path.home() / "Desktop" / f"{{APP_NAME}}.command"
                if sc.exists(): os.remove(sc)
        except Exception: pass
        if IS_WIN:
            self.status_var.set("正在清除注册表..."); self.root.update()
            import winreg
            for h in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try: winreg.DeleteKey(h, r"SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{{APP_NAME}}")
                except OSError: pass
        self.status_var.set("正在卸载..."); self.root.update()
        frozen = getattr(sys, 'frozen', False)
        my_exe = str(sys.executable) if frozen else __file__
        if IS_WIN:
            tmp_exe = Path(tempfile.gettempdir()) / "_uninst_cleanup.exe"
            try:
                shutil.copy2(my_exe, str(tmp_exe))
                subprocess.Popen([str(tmp_exe), "--cleanup", d],
                    creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
            except Exception: pass
        else:
            sh = f'#!/bin/bash\\\\nsleep 2\\\\nrm -rf "{{d}}"\\\\nrm -f "$0"'
            tmp = Path(tempfile.gettempdir()) / "_uninst.sh"
            tmp.write_text(sh); os.chmod(tmp, 0o755)
            subprocess.Popen(["bash", str(tmp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.root.destroy(); sys.exit(0)

    def run(self): self.root.mainloop()

if __name__ == "__main__": main()
'''
            (d / "uninstaller.py").write_text(uninst_code, encoding="utf-8")
            append("  ✓ uninstaller.py\n")

            # 5. build_all.bat (Windows 完整构建)
            append("创建 build_all.bat...\n")
            bat = f'''@echo off
chcp 65001 >nul
echo ========================================
echo   {name} — 一键构建
echo ========================================
echo.
echo [1/4] 构建主程序...
pyinstaller build_gui.spec --noconfirm
if %errorlevel% neq 0 exit /b %errorlevel%
echo.
echo [2/4] 构建卸载程序...
pyinstaller build_uninstaller.spec --noconfirm
if %errorlevel% neq 0 exit /b %errorlevel%
echo.
echo [3/4] 复制卸载程序到 dist...
copy /Y "dist\\{name}卸载程序.exe" "dist\\{name}\\" 2>nul
echo.
echo [4/4] 构建安装程序...
pyinstaller build_installer.spec --noconfirm
if %errorlevel% neq 0 exit /b %errorlevel%
echo.
echo ========================================
echo   构建完成！
echo   dist/{name}安装程序.exe   安装程序
echo   dist/{name}/               主程序目录
echo ========================================
pause
'''
            (d / "build_all.bat").write_text(bat, encoding="utf-8")
            append("  ✓ build_all.bat\n")

            # 5b. build_all.sh (macOS)
            append("创建 build_all.sh...\n")
            sh = f'''#!/bin/bash
set -e
echo "构建 {name}..."
echo "[1/4] 构建主程序..."
pyinstaller build_gui.spec --noconfirm
echo "[2/4] 构建卸载程序..."
pyinstaller build_uninstaller.spec --noconfirm
echo "[3/4] 复制卸载程序..."
cp "dist/{name}卸载程序" "dist/{name}/" 2>/dev/null || true
echo "[4/4] 构建安装程序..."
pyinstaller build_installer.spec --noconfirm
echo "构建完成！"
'''
            (d / "build_all.sh").write_text(sh, encoding="utf-8")
            append("  ✓ build_all.sh\n")

            # 5c. build_installer.spec
            append("创建 build_installer.spec...\n")
            inst_spec = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
PROJECT_ROOT = Path(SPECPATH)
DIST_DIR = PROJECT_ROOT / "dist" / "{name}"
dist_datas = []
if DIST_DIR.exists():
    for f in DIST_DIR.rglob("*"):
        if f.is_file():
            rel = f.relative_to(DIST_DIR)
            dest = str(rel.parent) if str(rel.parent) != '.' else '.'
            dist_datas.append((str(f), dest))
a = Analysis(
    [str(PROJECT_ROOT / "installer.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[], datas=dist_datas,
    hiddenimports=[], hookspath=[], hooksconfig={{}}, runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "test"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
    name="{name}安装程序", debug=False, strip=False, upx=True, console=False,
)
'''
            (d / "build_installer.spec").write_text(inst_spec, encoding="utf-8")
            append("  ✓ build_installer.spec\n")

            # 5d. build_uninstaller.spec
            append("创建 build_uninstaller.spec...\n")
            unst_spec = f'''# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
PROJECT_ROOT = Path(SPECPATH)
a = Analysis(
    [str(PROJECT_ROOT / "uninstaller.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[], datas=[],
    hiddenimports=[], hookspath=[], hooksconfig={{}}, runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "test"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
    name="{name}卸载程序", debug=False, strip=False, upx=True, console=False,
)
'''
            (d / "build_uninstaller.spec").write_text(unst_spec, encoding="utf-8")
            append("  ✓ build_uninstaller.spec\n")

            # 6. .gitignore
            append("创建 .gitignore...\n")
            (d / ".gitignore").write_text("build/\ndist/\n__pycache__/\n*.pyc\n.env\n*.log\n")
            append("  ✓ .gitignore\n")

            append("\n━━━━━━━━━━━━━━━━━━━━\n")
            append(f"✓ 项目 '{name}' 创建完成！\n")
            append(f"  目录: {d}\n")
            append("  下一步: 回到主界面选择此目录，然后点「GitHub 仓库设置」初始化\n")

        tk.Button(btn_row, text="创建项目", command=do_create,
                  bg=ACC, fg="white", font=FONT_BOLD,
                  relief=tk.FLAT, cursor="hand2", padx=24, pady=6).pack(side=tk.LEFT)
        tk.Button(btn_row, text="关闭", command=win.destroy,
                  bg="#666", fg="white", font=FONT, padx=14, pady=6,
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)

    # ── GitHub 帮助 ──────────────────────────────────

    def _show_github_help(self):
        import webbrowser

        if not self._project_dir:
            messagebox.showwarning("提示", "请先选择项目目录")
            return

        proj_name = self._project_dir.name
        # 如果当前目录已是 git 仓库，获取 remote url
        existing_remote = ""
        r = subprocess.run("git remote get-url origin 2>nul" if IS_WIN else "git remote get-url origin 2>/dev/null",
                          shell=True, cwd=str(self._project_dir), capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            existing_remote = r.stdout.strip()

        win = tk.Toplevel(self.root, bg=SURF)
        win.title("Git 仓库初始化")
        win.geometry("600x660")
        win.resizable(True, True)
        win.minsize(500, 500)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Git 仓库初始化", bg=ACC, fg="white",
                 font=FONT_TITLE).pack(fill=tk.X, pady=(0, 12))

        # 可滚动区域
        scroll_frame = tk.Frame(win, bg=SURF)
        scroll_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_frame, bg=SURF, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_frame, orient=tk.VERTICAL, command=canvas.yview)
        body = tk.Frame(canvas, bg=SURF, padx=20)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor=tk.NW, tags="body")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(e):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(e):
            canvas.unbind_all("<MouseWheel>")

        body.bind("<Enter>", _bind_wheel)
        body.bind("<Leave>", _unbind_wheel)

        # canvas 宽度跟随窗口
        def _resize_canvas(event):
            canvas.itemconfig("body", width=event.width)
        canvas.bind("<Configure>", _resize_canvas)

        if existing_remote:
            tk.Label(body, text=f"✓ 已关联远程仓库: {existing_remote}", bg=SURF, fg=SUCC,
                     font=FONT).pack(anchor=tk.W, pady=(10, 12))

        # GitHub 链接
        tk.Label(body, text="GitHub 链接（可点击打开）:", bg=SURF, fg=FG,
                 font=FONT).pack(anchor=tk.W, pady=(6, 2))

        links_frame = tk.Frame(body, bg=SURF)
        links_frame.pack(fill=tk.X, padx=(8, 0), pady=(2, 8))

        link_new = tk.Label(links_frame, text="▶ 新建仓库",
                           bg=SURF, fg=ACC, font=FONT_BOLD, cursor="hand2")
        link_new.pack(side=tk.LEFT, padx=(0, 15))
        link_new.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/new"))

        link_list = tk.Label(links_frame, text="▶ 我的仓库列表",
                            bg=SURF, fg=ACC, font=FONT_BOLD, cursor="hand2")
        link_list.pack(side=tk.LEFT)
        link_list.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ctlxh1341078783?tab=repositories"))

        # 输入区域
        tk.Label(body, text="", bg=SURF).pack()
        tk.Label(body, text="填写仓库信息后点「执行初始化」:", bg=SURF, fg=FG,
                 font=FONT_BOLD).pack(anchor=tk.W, pady=(4, 8))

        # 仓库地址
        url_frame = tk.Frame(body, bg=SURF)
        url_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(url_frame, text="仓库地址:", bg=SURF, fg=FG, font=FONT,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        remote_var = tk.StringVar(
            value=existing_remote or f"https://github.com/你的用户名/{proj_name}.git")
        remote_entry = ttk.Entry(url_frame, textvariable=remote_var, font=FONT, width=45)
        remote_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 分支名
        branch_frame = tk.Frame(body, bg=SURF)
        branch_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(branch_frame, text="分支名:", bg=SURF, fg=FG, font=FONT,
                 width=10, anchor=tk.W).pack(side=tk.LEFT)
        branch_var = tk.StringVar(value="main")
        branch_entry = ttk.Entry(branch_frame, textvariable=branch_var, font=FONT, width=15)
        branch_entry.pack(side=tk.LEFT)

        tk.Label(body, text="", bg=SURF).pack()

        # 预览命令
        preview_var = tk.StringVar()
        tk.Label(body, text="将执行以下命令:", bg=SURF, fg=FG, font=FONT).pack(anchor=tk.W, pady=(8, 2))

        preview_box = tk.Text(body, height=9, font=MONO, bg="#1e1e1e", fg="#82aaff",
                               relief=tk.FLAT, padx=12, pady=10, width=58,
                               state=tk.DISABLED)
        preview_box.pack(fill=tk.X, pady=(2, 4))

        def update_preview(*_):
            r = remote_var.get().strip()
            b = branch_var.get().strip() or "main"
            cmds = [
                f"cd {self._project_dir}",
                "git init",
                "git add .",
                'git commit -m "初始版本"',
                f"git branch -M {b}",
                f"git remote add origin {r}",
                f"git push -u origin {b}",
            ]
            preview_box.configure(state=tk.NORMAL)
            preview_box.delete("1.0", tk.END)
            preview_box.insert("1.0", "\n".join(cmds))
            preview_box.configure(state=tk.DISABLED)

        remote_var.trace_add("write", update_preview)
        branch_var.trace_add("write", update_preview)
        update_preview()

        # 日志
        tk.Label(body, text="执行日志:", bg=SURF, fg=FG, font=FONT).pack(anchor=tk.W, pady=(10, 2))
        log_box = tk.Text(body, height=6, font=MONO, bg="#1e1e1e", fg="#d4d4d4",
                           relief=tk.FLAT, padx=10, pady=6, width=58)
        log_box.pack(fill=tk.X, pady=(2, 8))

        # 按钮
        btn_row = tk.Frame(body, bg=SURF)
        btn_row.pack(fill=tk.X, pady=(0, 12))

        def do_init():
            remote = remote_var.get().strip()
            branch = branch_var.get().strip() or "main"
            if not remote or "github.com" not in remote:
                messagebox.showwarning("提示", "请输入有效的 GitHub 仓库地址")
                return

            p = str(self._project_dir)
            log_box.delete("1.0", tk.END)
            btn.config(state=tk.DISABLED, text="执行中...")
            win.update()

            def append(text):
                log_box.insert(tk.END, text)
                log_box.see(tk.END)
                win.update()

            def run_cmds():
                cmds = [
                    ("git init", "初始化仓库"),
                    ("git add .", "暂存文件"),
                    ('git commit -m "初始版本"', "创建提交"),
                    (f"git branch -M {branch}", f"设置分支为 {branch}"),
                    (f"git remote add origin {remote}", "关联远程仓库"),
                    (f"git push -u origin {branch}", "推送到 GitHub"),
                ]
                success = True
                for cmd, desc in cmds:
                    append(f"⏳ {desc}...\n")
                    append(f"   $ {cmd}\n")

                    # 用 Popen 流式读取，避免卡住感
                    proc = subprocess.Popen(cmd, shell=True, cwd=p,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            text=True)

                    # 边读边显示
                    for line in proc.stdout:
                        line = line.strip()
                        if line:
                            append(f"     {line}\n")
                    proc.wait()

                    # stderr
                    stderr_lines = []
                    for line in proc.stderr:
                        line = line.strip()
                        if line:
                            stderr_lines.append(line)
                            append(f"     {line}\n")

                    if proc.returncode != 0:
                        # 有些 git 命令的 warning 会走 stderr，不算失败
                        # git push 失败才是真失败
                        if "fatal" in "".join(stderr_lines).lower() or "error" in "".join(stderr_lines).lower():
                            append(f"   ✗ {desc} 失败\n\n")
                            success = False
                            break
                        # git add . 的 warning (CRLF) 不是错误，继续

                    append(f"   ✓ {desc}\n\n")

                if success:
                    append("━━━━━━━━━━━━━━━━━━━━\n")
                    append("✓ Git 初始化完成！\n")
                    append("  以后改完代码，点「一键发布」即可\n")

                btn.config(state=tk.NORMAL, text="执行初始化")

            threading.Thread(target=run_cmds, daemon=True).start()

        btn = tk.Button(btn_row, text="执行初始化", command=do_init,
                        bg=SUCC, fg="white", font=FONT_BOLD,
                        relief=tk.FLAT, cursor="hand2", padx=24, pady=6)
        btn.pack(side=tk.LEFT)

        tk.Button(btn_row, text="关闭", command=win.destroy,
                  bg=ACC, fg="white", font=FONT, padx=24, pady=6,
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)

    # ── 发布主流程 ────────────────────────────────────

    def _publish(self, push: bool = True):
        if self._building:
            return
        if not self._project_dir:
            messagebox.showwarning("提示", "请先选择项目目录")
            return
        if not self._version_file:
            messagebox.showwarning("提示", "所选目录没有 version.json")
            return

        # 自动检测构建命令
        build_commands = self._detect_build_commands()

        changes = self.changelog_text.get("1.0", tk.END).strip()
        if not changes:
            messagebox.showwarning("提示", "请输入更新内容")
            return

        self._building = True
        self.publish_btn.config(state=tk.DISABLED, text="发布中...")
        self.build_only_btn.config(state=tk.DISABLED)
        self.progress.pack(side=tk.LEFT, padx=(12, 0))
        self.progress.start()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.status_var.set("正在发布...")

        thread = threading.Thread(target=self._do_publish,
                                   args=(changes, build_commands, push), daemon=True)
        thread.start()

    def _detect_build_commands(self):
        """自动检测项目的构建方式"""
        if not self._project_dir:
            return []
        p = self._project_dir

        # 检查 build_all.bat
        if (p / "build_all.bat").exists():
            if IS_WIN:
                return ["build_all.bat"]
            else:
                # Mac: 将 .bat 转为等效的 Python 命令
                return self._detect_from_specs(p)

        # 检查 .spec 文件
        specs = list(p.glob("build*.spec"))
        if specs:
            return self._detect_from_specs(p)

        return []

    def _detect_from_specs(self, p: Path):
        """从 spec 文件推导构建命令"""
        cmds = []
        # 图标转换
        if (p / "tools" / "convert_icon.py").exists():
            cmds.append("python tools/convert_icon.py")

        specs = sorted(p.glob("build*.spec"))
        for s in specs:
            name = s.stem  # e.g. build_gui, build_installer, build_uninstaller
            cmds.append(f"pyinstaller {s.name} --noconfirm")

        # 复制卸载程序到主程序目录
        if IS_WIN:
            cmds.append('copy /Y "dist/闲鱼工具卸载程序.exe" "dist/闲鱼数据采集分析工具/"')
        else:
            cmds.append('cp "dist/闲鱼工具卸载程序" "dist/闲鱼数据采集分析工具/"')

        return cmds

    def _do_publish(self, changes: str, build_commands: list, push: bool):
        try:
            p = self._project_dir

            # 1. 检查 Git 仓库
            r = subprocess.run("git status", shell=True, cwd=str(p),
                               capture_output=True, text=True)
            git_ready = r.returncode == 0

            if not git_ready and push and self.auto_push_var.get():
                self._root_log("⚠ Git 仓库未初始化", "warn")
                self._root_log("请先在终端运行：", "warn")
                self._root_log(f"  cd {p}", "info")
                self._root_log("  git init && git add . && git commit -m '初始版本'", "info")
                self._root_log("  git branch -M main", "info")
                self._root_log("  git remote add origin https://github.com/你的用户名/项目名.git", "info")
                self._root_log("  git push -u origin main", "info")
                self._root_log("", "info")
                self._root_log("或者点击「GitHub 仓库设置」查看详细步骤", "warn")
                self._done(False, "Git 未初始化，请先设置仓库")
                return

            # 2. 更新版本文件
            self._root_log("更新版本信息...")
            new_ver = self.new_ver_var.get().strip()
            if not new_ver:
                parts = self._version_info["version"].split(".")
                new_ver = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

            new_build = self._version_info.get("build_number", 0) + 1
            today = datetime.date.today().isoformat()
            changelog_lines = [l.strip() for l in changes.split("\n") if l.strip()]

            ver_data = self._version_info.copy()
            ver_data["version"] = new_ver
            ver_data["build_number"] = new_build
            ver_data["build_date"] = today
            ver_data["changelog"] = changelog_lines + ver_data.get("changelog", [])

            self._version_file.write_text(json.dumps(ver_data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._root_log(f"version.json → v{new_ver} (构建 {new_build}, {today})", "ok")

            # 3. 构建
            if build_commands:
                self._root_log("开始构建...")
                for cmd in build_commands:
                    self._root_log(f"执行: {cmd}")
                    result = subprocess.run(cmd, shell=True, cwd=str(p),
                                            capture_output=True, text=True, timeout=600)
                    if result.returncode != 0:
                        err = result.stderr.strip() or result.stdout.strip()
                        self._root_log(f"失败: {err[:200]}", "err")
                        self._done(False, f"构建失败: {cmd}")
                        return
                    out_lines = result.stdout.strip().split("\n")
                    last = out_lines[-1][:100] if out_lines else ""
                    self._root_log(f"  → {last}", "ok")
                self._root_log("构建完成", "ok")
            else:
                self._root_log("未检测到构建命令，跳过构建", "warn")

            # 4. Git 操作
            if push and self.auto_push_var.get() and git_ready:
                self._root_log("提交到 Git...")
                commit_msg = f"v{new_ver}: {'; '.join(changelog_lines[:3])}"

                r = subprocess.run("git add .", shell=True, cwd=str(p),
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    self._root_log(f"git add 失败: {r.stderr}", "err")
                    self._done(False, "git add 失败")
                    return

                r = subprocess.run(f'git commit -m "{commit_msg}"', shell=True,
                                   cwd=str(p), capture_output=True, text=True)
                if r.returncode != 0:
                    out = r.stdout + r.stderr
                    if "nothing to commit" in out:
                        self._root_log("没有需要提交的改动", "warn")
                    else:
                        self._root_log(f"git commit 失败: {out}", "err")
                        self._done(False, "git commit 失败")
                        return

                r = subprocess.run("git push", shell=True, cwd=str(p),
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    self._root_log(f"git push 失败: {r.stderr[:200]}", "err")
                    self._done(False, "git push 失败")
                    return
                self._root_log(f"已推送: {commit_msg}", "ok")

            self._root_log("=" * 40)
            self._root_log(f"发布完成！ v{new_ver}", "ok")
            self._root_log("下一步: 在 GitHub Releases 页面创建 Release 并上传安装包", "warn")
            self._root_log(f"  https://github.com/ctlxh1341078783/{p.name}/releases/new", "info")

            self._done(True, f"v{new_ver} 发布完成")

        except Exception as e:
            self._root_log(f"异常: {e}", "err")
            self._done(False, str(e))

    def _root_log(self, msg: str, level: str = "info"):
        self.root.after(0, lambda: self._log(msg, level))

    def _done(self, success: bool, msg: str):
        self.root.after(0, lambda: self._finish(success, msg))

    def _finish(self, success: bool, msg: str):
        self._building = False
        self.publish_btn.config(state=tk.NORMAL, text="一键发布")
        self.build_only_btn.config(state=tk.NORMAL)
        self.progress.stop()
        self.progress.pack_forget()
        self.status_var.set(msg if success else f"失败: {msg}")
        if success:
            self._refresh_version()
            self.changelog_text.delete("1.0", tk.END)

    def run(self):
        self.root.mainloop()


def main():
    app = PublishTool()
    app.run()


if __name__ == "__main__":
    main()
