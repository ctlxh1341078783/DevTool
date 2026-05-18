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
        self.root.geometry("580x660")
        self.root.configure(bg=BG)
        self.root.minsize(480, 540)

        self.config = load_config()
        self._project_dir = None
        self._version_info = {}
        self._version_file = None
        self._building = False

        self._build_ui()

        # 自动恢复上次目录
        recent = self.config.get("recent_dirs", [])
        if recent:
            self.dir_var.set(recent[0])
            self._on_dir_changed()

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
        win.geometry("600x620")
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
                    log_box.insert(tk.END, f"$ {cmd}\n")
                    log_box.see(tk.END)
                    win.update()

                    r2 = subprocess.run(cmd, shell=True, cwd=p,
                                        capture_output=True, text=True)
                    out = r2.stdout.strip()
                    err = r2.stderr.strip()

                    if out:
                        for line in out.split("\n")[:5]:
                            log_box.insert(tk.END, f"  {line}\n")
                    if err:
                        for line in err.split("\n")[:5]:
                            log_box.insert(tk.END, f"  {line}\n")
                    log_box.see(tk.END)
                    win.update()

                    if r2.returncode != 0:
                        log_box.insert(tk.END, f"✗ {desc}失败\n")
                        log_box.insert(tk.END, f"  请检查仓库地址是否正确，或GitHub上是否已创建仓库\n")
                        success = False
                        break
                    log_box.insert(tk.END, f"✓ {desc}\n\n")
                    log_box.see(tk.END)
                    win.update()

                if success:
                    log_box.insert(tk.END, "━━━━━━━━━━━━━━━━━━━━\n")
                    log_box.insert(tk.END, "✓ Git 初始化完成！\n")
                    log_box.insert(tk.END, "  以后改完代码，回到本工具点「一键发布」即可\n")
                    log_box.see(tk.END)

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
            cmds.append('copy /Y "dist/闲鱼工具卸载程序/闲鱼工具卸载程序.exe" "dist/闲鱼数据采集分析工具/"')
        else:
            cmds.append('cp "dist/闲鱼工具卸载程序/闲鱼工具卸载程序" "dist/闲鱼数据采集分析工具/"')

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
