from __future__ import annotations

import argparse
import ctypes
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas_batch import STATUS_LABELS, FileEntry, Job, export_batch, scan_folder, validate_output
from atlas_processor import Options, ProcessedAtlas, ProcessingSkipped, check_geometry, process_atlas

STRICT = '严格 · 保留原像素'
RESAMPLE = '重采样 · 亚像素对齐'
BG = '#f4f6f9'
INK = '#1e293b'
MUTED = '#64748b'
BLUE = '#2563eb'


class AtlasTrimApp:
    def __init__(self, root: tk.Tk, autodetect: bool = True):
        self.root = root
        self.events = queue.Queue()
        self.preview_requests = queue.Queue(maxsize=1)
        self.preview_closed = threading.Event()
        self.entries: list[FileEntry] = []
        self.grids: dict[str, tuple[int, int]] = {}
        self.scanned_root: Path | None = None
        self.busy = ''
        self.cancel = threading.Event()
        self.closing = False
        self.generation = 0
        self.pending_preview = None
        self.result: ProcessedAtlas | None = None
        self.fallback: Image.Image | None = None
        self.photos = []
        self.frame_index = 0
        self.playing = True
        self.last_tick = time.monotonic()
        self.scale_updating = False
        self.last_report = None
        self.controls = []
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.recursive = tk.BooleanVar(value=False)
        self.columns = tk.StringVar(value='5')
        self.rows = tk.StringVar(value='5')
        self.padding = tk.StringVar(value='2')
        self.threshold = tk.StringVar(value='0')
        self.keep_center = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value=STRICT)
        self.fps = tk.StringVar(value='12')
        self.zoom = tk.StringVar(value='适应窗口')
        self.status = tk.StringVar(value='选择输入文件夹，扫描后设置每张图集的网格。')
        self.summary = tk.StringVar(value='尚未扫描')
        self.preview_name = tk.StringVar(value='同步动画预览')
        self.plan_text = tk.StringVar(value='所有帧使用统一裁剪区域；默认严格模式。')
        self.frame_text = tk.StringVar(value='帧 — / —')
        self._build()
        threading.Thread(target=self._preview_loop, daemon=True).start()
        self.zoom.trace_add('write', lambda *_: self._render())
        for variable in (self.padding, self.threshold, self.keep_center, self.mode):
            variable.trace_add('write', self._parameters_changed)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(40, self._poll)
        root.after(30, self._animate)
        if autodetect:
            base = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
            for folder in (base / 'Origen', base.parent / 'Origen'):
                if folder.is_dir():
                    self.input_path.set(str(folder))
                    self.output_path.set(str(folder.parent / 'Output'))
                    root.after(150, self.scan)
                    break

    def _control(self, widget):
        self.controls.append((widget, str(widget.cget('state'))))
        return widget

    def _build(self):
        self.root.title('AtlasTrim · 序列帧图集裁剪')
        try:
            resource_root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
            self.root.iconbitmap(str(resource_root / 'assets' / 'atlastrim.ico'))
        except tk.TclError:
            pass
        width = min(1420, self.root.winfo_screenwidth() - 80)
        height = min(940, self.root.winfo_screenheight() - 90)
        self.root.geometry(f'{max(1050, width)}x{max(700, height)}')
        self.root.minsize(1050, 700)
        self.root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10), foreground=INK, background=BG)
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG)
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 21, 'bold'))
        style.configure('TButton', padding=(10, 7), background='#e8edf5', borderwidth=0)
        style.map('TButton', background=[('active', '#dbe5f6')])
        style.configure('Accent.TButton', background=BLUE, foreground='white')
        style.map('Accent.TButton', background=[('disabled', '#b6c8e7'), ('active', '#1d4ed8')])
        style.configure('Treeview', rowheight=31, background='white', fieldbackground='white', borderwidth=0)
        style.configure('Treeview.Heading', background='#e8edf5', padding=(5, 8))
        style.map('Treeview', background=[('selected', '#dbeafe')], foreground=[('selected', '#173d88')])
        style.configure('TEntry', padding=6, fieldbackground='white')
        style.configure('TSpinbox', padding=4, fieldbackground='white')
        style.configure('TCombobox', padding=5)

        shell = ttk.Frame(self.root, padding=20)
        shell.pack(fill='both', expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(3, weight=1)
        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 14))
        ttk.Label(header, text='序列帧图集裁剪', style='Title.TLabel').pack(side='left')
        ttk.Label(header, text='AtlasTrim  1.0', style='Muted.TLabel').pack(side='right')
        paths = ttk.Frame(shell)
        paths.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        paths.columnconfigure(1, weight=1)
        for row, (label, variable, callback) in enumerate([
            ('输入文件夹', self.input_path, self.choose_input),
            ('输出文件夹', self.output_path, self.choose_output),
        ]):
            ttk.Label(paths, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10), pady=3)
            self._control(ttk.Entry(paths, textvariable=variable)).grid(row=row, column=1, sticky='ew', pady=3)
            self._control(ttk.Button(paths, text='选择…', command=callback)).grid(row=row, column=2, padx=(8, 0), pady=3)
        tools = ttk.Frame(shell)
        tools.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        self._control(ttk.Checkbutton(tools, text='包含子文件夹', variable=self.recursive)).pack(side='left')
        self._control(ttk.Button(tools, text='扫描 PNG', command=self.scan)).pack(side='left', padx=10)
        ttk.Label(tools, text='只处理透明 PNG · 保持原格子顺序 · 不缩放主体', style='Muted.TLabel').pack(side='right')

        body = ttk.Panedwindow(shell, orient='horizontal')
        body.grid(row=3, column=0, sticky='nsew')
        left, right = ttk.Frame(body), ttk.Frame(body, padding=(18, 0, 0, 0))
        body.add(left, weight=5)
        body.add(right, weight=6)
        ttk.Label(left, text='图集文件  ·  Ctrl / Shift 多选').pack(anchor='w', pady=(0, 8))
        table_area = ttk.Frame(left)
        table_area.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table_area, columns=('file', 'size', 'grid', 'status'), show='headings', selectmode='extended')
        for key, label, size in [('file', '文件', 210), ('size', '原图尺寸', 105), ('grid', '列 × 行', 70), ('status', '状态', 105)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=size, minwidth=55, stretch=key == 'file', anchor='w' if key == 'file' else 'center')
        scrollbar = ttk.Scrollbar(table_area, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.tree.tag_configure('ready', foreground='#166534')
        self.tree.tag_configure('skipped', foreground='#b45309')
        self.tree.tag_configure('failed', foreground='#b91c1c')
        self.tree.tag_configure('success', foreground='#166534')
        self.tree.bind('<<TreeviewSelect>>', self._selected)
        ttk.Label(left, textvariable=self.summary, style='Muted.TLabel').pack(anchor='w', pady=(7, 8))

        grid_controls = ttk.Frame(left)
        grid_controls.pack(fill='x', pady=(0, 9))
        ttk.Label(grid_controls, text='列').pack(side='left')
        self.column_spin = self._control(ttk.Spinbox(grid_controls, from_=1, to=4096, width=4, textvariable=self.columns))
        self.column_spin.pack(side='left', padx=(5, 12))
        ttk.Label(grid_controls, text='行').pack(side='left')
        self._control(ttk.Spinbox(grid_controls, from_=1, to=4096, width=4, textvariable=self.rows)).pack(side='left', padx=(5, 12))
        self._control(ttk.Button(grid_controls, text='应用到选中', command=self.apply_grid)).pack(side='left')
        self._control(ttk.Button(grid_controls, text='应用到全部', command=lambda: self.apply_grid(all_files=True))).pack(side='left', padx=(6, 0))

        params = ttk.Frame(left)
        params.pack(fill='x', pady=(0, 9))
        ttk.Label(params, text='每边留边').pack(side='left')
        self._control(ttk.Spinbox(params, from_=0, to=4096, width=5, textvariable=self.padding)).pack(side='left', padx=6)
        ttk.Label(params, text='px     alpha 阈值').pack(side='left')
        self._control(ttk.Spinbox(params, from_=0, to=255, width=5, textvariable=self.threshold)).pack(side='left', padx=6)
        self._control(ttk.Checkbutton(left, text='保留原画布中心（可能留下更多透明边）', variable=self.keep_center)).pack(anchor='w')
        sampling = ttk.Frame(left)
        sampling.pack(fill='x', pady=(8, 0))
        ttk.Label(sampling, text='采样模式').pack(side='left')
        self._control(ttk.Combobox(sampling, textvariable=self.mode, values=(STRICT, RESAMPLE), state='readonly', width=23)).pack(side='left', padx=8)
        ttk.Label(left, text='严格模式跳过非整除网格；重采样允许改变边缘像素。\n网格按文件设置，其余处理参数适用于全部文件。',
                  style='Muted.TLabel').pack(anchor='w', pady=(7, 0))

        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, textvariable=self.preview_name, font=('Microsoft YaHei UI', 11, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 8))
        previews = ttk.Frame(right)
        previews.grid(row=1, column=0, sticky='nsew')
        previews.columnconfigure(0, weight=1, uniform='preview')
        previews.columnconfigure(1, weight=1, uniform='preview')
        previews.rowconfigure(1, weight=1)
        self.original_label = ttk.Label(previews, text='原始帧', style='Muted.TLabel')
        self.original_label.grid(row=0, column=0, pady=(0, 7))
        ttk.Label(previews, text='处理后', style='Muted.TLabel').grid(row=0, column=1, pady=(0, 7))
        self.canvases = [tk.Canvas(previews, bg='#e7ebf0', highlightthickness=0, width=230, height=270)
                         for _ in range(2)]
        for index, canvas in enumerate(self.canvases):
            canvas.grid(row=1, column=index, sticky='nsew', padx=(0, 5) if index == 0 else (5, 0))
            canvas.bind('<Configure>', lambda event: self._render())
        ttk.Label(right, textvariable=self.plan_text, style='Muted.TLabel', wraplength=560).grid(row=2, column=0, sticky='w', pady=(9, 6))
        timeline = ttk.Frame(right)
        timeline.grid(row=3, column=0, sticky='ew', pady=(2, 8))
        self.play_button = ttk.Button(timeline, text='暂停', command=self.toggle_play, width=5)
        self.play_button.pack(side='left')
        ttk.Button(timeline, text='‹', command=lambda: self.step(-1), width=2).pack(side='left', padx=(7, 3))
        ttk.Button(timeline, text='›', command=lambda: self.step(1), width=2).pack(side='left')
        ttk.Label(timeline, textvariable=self.frame_text).pack(side='left', padx=12)
        ttk.Combobox(timeline, textvariable=self.zoom, values=('适应窗口', '100%', '200%'),
                     state='readonly', width=8).pack(side='left')
        ttk.Spinbox(timeline, from_=1, to=60, width=4, textvariable=self.fps).pack(side='right')
        ttk.Label(timeline, text='预览 FPS').pack(side='right', padx=7)
        self.slider = ttk.Scale(right, from_=0, to=1, command=self._seek)
        self.slider.grid(row=4, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(right, text='处理记录', style='Muted.TLabel').grid(row=5, column=0, sticky='w', pady=(0, 5))
        log_area = ttk.Frame(right)
        log_area.grid(row=6, column=0, sticky='ew')
        self.log = tk.Text(log_area, height=6, wrap='word', font=('Microsoft YaHei UI', 9),
                           relief='flat', background='white', foreground=INK, padx=8, pady=6, state='disabled')
        log_scroll = ttk.Scrollbar(log_area, orient='vertical', command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side='left', fill='both', expand=True)
        log_scroll.pack(side='right', fill='y')

        bottom = ttk.Frame(shell)
        bottom.grid(row=4, column=0, sticky='ew', pady=(16, 0))
        self._control(ttk.Button(bottom, text='批量导出全部', style='Accent.TButton', command=self.export)).pack(side='left')
        self._control(ttk.Button(bottom, text='导出选中', command=lambda: self.export(selected=True))).pack(side='left', padx=8)
        self.cancel_button = ttk.Button(bottom, text='停止', command=self.stop_export, state='disabled')
        self.cancel_button.pack(side='left')
        self._control(ttk.Button(bottom, text='打开输出文件夹', command=self.open_output)).pack(side='right')
        self.report_button = ttk.Button(bottom, text='查看处理清单', command=self.open_report, state='disabled')
        self.report_button.pack(side='right', padx=8)
        self.progress = ttk.Progressbar(shell, mode='determinate')
        self.progress.grid(row=5, column=0, sticky='ew', pady=(12, 6))
        ttk.Label(shell, textvariable=self.status, style='Muted.TLabel', wraplength=1300).grid(row=6, column=0, sticky='w')

    def _log(self, text: str):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _options(self, key: str) -> Options:
        columns, rows = self.grids.get(key, (5, 5))
        try:
            options = Options(columns, rows, int(self.padding.get()), int(self.threshold.get()),
                              self.keep_center.get(), self.mode.get() == RESAMPLE)
            options.validate()
            return options
        except (ValueError, tk.TclError) as error:
            raise ValueError('留边和alpha阈值必须为整数') from error

    def _set_busy(self, name: str):
        self.busy = name
        for widget, state in self.controls:
            widget.configure(state='disabled' if name else state)
        self.cancel_button.configure(state='normal' if name == 'export' else 'disabled')

    def choose_input(self):
        folder = filedialog.askdirectory(title='选择输入图集文件夹', initialdir=self.input_path.get() or None)
        if folder:
            self.input_path.set(folder)
            if not self.output_path.get():
                self.output_path.set(str(Path(folder).parent / 'Output'))
            self.scan()

    def choose_output(self):
        folder = filedialog.askdirectory(title='选择输出文件夹', initialdir=self.output_path.get() or None, mustexist=False)
        if folder:
            self.output_path.set(folder)

    def scan(self):
        if self.busy:
            return
        path = self.input_path.get().strip()
        if not path:
            messagebox.showinfo('选择文件夹', '请先选择输入文件夹')
            return
        recursive = self.recursive.get()
        self._set_busy('scan')
        self.status.set('正在扫描PNG…')
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)
        def work():
            try:
                self.events.put(('scan', (Path(path).resolve(), scan_folder(path, recursive))))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def _scan_done(self, root, entries):
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self._set_busy('')
        self.scanned_root = root
        self.entries = entries
        self.grids = {str(index): (5, 5) for index in range(len(entries))}
        self.tree.delete(*self.tree.get_children())
        self.result = self.fallback = None
        self.generation += 1
        for index, entry in enumerate(entries):
            self.tree.insert('', 'end', iid=str(index), values=(entry.relative, f'{entry.width}×{entry.height}', '5 × 5', ''))
        self._update_rows()
        self.status.set(f'扫描完成：{len(entries)}张PNG。请核对每张图集的列数和行数；其他文件格式不参与处理。')
        self._log(self.status.get())
        if entries:
            self.tree.selection_set('0')
            self.tree.focus('0')
        else:
            self.preview_name.set('同步动画预览')
            self.plan_text.set('当前目录没有PNG。可尝试开启“包含子文件夹”后重新扫描。')
            self.frame_text.set('帧 — / —')
            self._render()

    def _update_rows(self):
        ready, skipped = 0, 0
        for index, entry in enumerate(self.entries):
            key = str(index)
            try:
                options = self._options(key)
                if entry.error:
                    raise ValueError(entry.error)
                check_geometry(entry.width, entry.height, options)
                label, tag = '待检测', 'ready'
                ready += 1
            except Exception as error:
                label, tag = '需核对' if entry.error else '将跳过', 'skipped'
                skipped += 1
            columns, rows = self.grids[key]
            self.tree.set(key, 'grid', f'{columns} × {rows}')
            self.tree.set(key, 'status', label)
            self.tree.item(key, tags=(tag,))
        self.summary.set(f'{len(self.entries)}张  ·  {ready}张可继续检测  ·  {skipped}张需调整或将跳过')

    def _selected(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        key = self.tree.focus()
        if key not in selection:
            key = selection[0]
        columns, rows = self.grids.get(key, (5, 5))
        self.columns.set(str(columns))
        self.rows.set(str(rows))
        self._schedule_preview()

    def apply_grid(self, all_files=False):
        if self.busy:
            return
        try:
            columns, rows = int(self.columns.get()), int(self.rows.get())
            Options(columns=columns, rows=rows).validate()
        except Exception as error:
            messagebox.showerror('网格不合法', str(error))
            return
        keys = self.tree.get_children() if all_files else self.tree.selection()
        if not keys:
            messagebox.showinfo('选择图片', '请先选择要设置网格的图片')
            return
        for key in keys:
            self.grids[key] = (columns, rows)
        self._update_rows()
        self._schedule_preview()

    def _parameters_changed(self, *_):
        if self.busy:
            return
        self._update_rows()
        self._schedule_preview()

    def _schedule_preview(self):
        self.generation += 1
        self.result = None
        self.fallback = None
        self.frame_text.set('正在计算…')
        if self.pending_preview is not None:
            self.root.after_cancel(self.pending_preview)
        self.pending_preview = self.root.after(240, self._start_preview)

    def _start_preview(self):
        self.pending_preview = None
        selection = self.tree.selection()
        if not selection:
            self._render()
            return
        key = self.tree.focus()
        if key not in selection:
            key = selection[0]
        entry = self.entries[int(key)]
        self.preview_name.set(entry.relative)
        generation = self.generation
        try:
            options = self._options(key)
        except Exception as error:
            self.plan_text.set(str(error))
            self._render()
            return
        self.plan_text.set('正在计算统一裁剪区域…')
        self._render()
        request = (generation, entry, options)
        try:
            self.preview_requests.get_nowait()
        except queue.Empty:
            pass
        self.preview_requests.put_nowait(request)

    def _preview_loop(self):
        while not self.preview_closed.is_set():
            request = self.preview_requests.get()
            if request is None:
                return
            generation, entry, options = request
            try:
                result = process_atlas(entry.path, options)
                self.events.put(('preview', (generation, result, None, '')))
            except Exception as error:
                fallback = None
                try:
                    with Image.open(entry.path) as image:
                        fallback = image.convert('RGBA')
                        fallback.thumbnail((800, 800))
                except Exception:
                    pass
                self.events.put(('preview', (generation, None, fallback, str(error))))

    def _preview_done(self, generation, result, fallback, reason):
        if generation != self.generation:
            return
        self.result, self.fallback = result, fallback
        self.frame_index = 0
        self.last_tick = time.monotonic()
        if result:
            self.original_label.configure(text='源像素参考' if self.mode.get() == RESAMPLE else '原始帧')
            plan = result.plan
            mode = '重采样' if self.mode.get() == RESAMPLE else '严格复制'
            self.plan_text.set(f'原帧 {plan.frame_width:g}×{plan.frame_height:g}  →  方形帧 {plan.side}×{plan.side}\n'
                               f'图集 {result.atlas.width}×{result.atlas.height}  ·  {mode}  ·  统一偏移 ({-plan.crop_x:g}, {-plan.crop_y:g})'
                               + ('\n' + '；'.join(result.warnings) if result.warnings else ''))
            self.slider.configure(to=max(1, len(result.frames) - 1))
            self.playing = True
            self.play_button.configure(text='暂停')
        else:
            self.original_label.configure(text='源图集')
            self.plan_text.set('当前设置无法导出：' + reason)
            self.frame_text.set('原图集总览（无法逐帧预览）')
        self._render()

    def toggle_play(self):
        self.playing = not self.playing
        self.last_tick = time.monotonic()
        self.play_button.configure(text='暂停' if self.playing else '播放')

    def step(self, delta):
        if not self.result:
            return
        self.playing = False
        self.play_button.configure(text='播放')
        self.frame_index = (self.frame_index + delta) % len(self.result.frames)
        self._render()

    def _seek(self, value):
        if self.scale_updating or not self.result:
            return
        self.playing = False
        self.play_button.configure(text='播放')
        self.frame_index = min(len(self.result.frames) - 1, max(0, round(float(value))))
        self._render()

    def _animate(self):
        if self.playing and self.result:
            try:
                fps = max(1, min(60, float(self.fps.get())))
            except ValueError:
                fps = 12
            now = time.monotonic()
            steps = int((now - self.last_tick) * fps)
            if steps:
                self.last_tick += steps / fps
                self.frame_index = (self.frame_index + steps) % len(self.result.frames)
                self._render()
        else:
            self.last_tick = time.monotonic()
        self.root.after(25, self._animate)

    def _render(self):
        if not hasattr(self, 'canvases'):
            return
        images = [None, None]
        if self.result:
            images = [self.result.originals[self.frame_index], self.result.frames[self.frame_index]]
            self.frame_text.set(f'帧 {self.frame_index + 1} / {len(self.result.frames)}')
            self.scale_updating = True
            self.slider.set(self.frame_index)
            self.scale_updating = False
        elif self.fallback:
            images[0] = self.fallback
        sizes = [(max(10, canvas.winfo_width()), max(10, canvas.winfo_height())) for canvas in self.canvases]
        present = [image for image in images if image is not None]
        # A constant zoom over the entire animation, even when fractional cell
        # bounds give the raw reference frames different integer ROI sizes.
        references = (self.result.originals + self.result.frames) if self.result else present
        zoom = min(1.0, min((width - 24) / max(image.width for image in references) for width, _ in sizes),
                   min((height - 24) / max(image.height for image in references) for _, height in sizes)) if references else 1
        if self.zoom.get() != '适应窗口':
            zoom = 1 if self.zoom.get() == '100%' else 2
        zoom = max(0.01, zoom)
        photos = []
        for index, (canvas, (width, height), image) in enumerate(zip(self.canvases, sizes, images)):
            background = Image.new('RGBA', (width, height), '#e4e8ed')
            draw = ImageDraw.Draw(background)
            for y in range(0, height, 18):
                for x in range(0, width, 18):
                    if (x // 18 + y // 18) % 2 == 0:
                        draw.rectangle((x, y, x + 17, y + 17), fill='#f2f4f7')
            draw.line((width // 2, 0, width // 2, height), fill='#cbd3df')
            draw.line((0, height // 2, width, height // 2), fill='#cbd3df')
            if image:
                box_width, box_height = image.width, image.height
                x, y = (width - image.width * zoom) / 2, (height - image.height * zoom) / 2
                if index == 0 and self.result:
                    plan = self.result.plan
                    offset_x, offset_y = self.result.original_offsets[self.frame_index]
                    x = width / 2 + (offset_x - plan.frame_width / 2) * zoom
                    y = height / 2 + (offset_y - plan.frame_height / 2) * zoom
                    box_width, box_height = plan.frame_width, plan.frame_height
                view = image.transform((width, height), Image.Transform.AFFINE,
                                       (1 / zoom, 0, -x / zoom, 0, 1 / zoom, -y / zoom),
                                       Image.Resampling.NEAREST if zoom >= 1 else Image.Resampling.BILINEAR)
                background.alpha_composite(view)
                ImageDraw.Draw(background).rectangle(((width - box_width * zoom) / 2, (height - box_height * zoom) / 2,
                                                     (width + box_width * zoom) / 2, (height + box_height * zoom) / 2), outline='#94a3b8')
            photo = ImageTk.PhotoImage(background)
            photos.append(photo)
            canvas.delete('all')
            canvas.create_image(0, 0, image=photo, anchor='nw')
            if image is None:
                canvas.create_text(width // 2, height // 2, text='等待裁剪预览' if self.entries else '选择并扫描图集',
                                   fill=MUTED, font=('Microsoft YaHei UI', 11), width=max(80, width - 30))
        self.photos = photos

    def export(self, selected=False):
        if self.busy:
            return
        try:
            if not self.scanned_root or not self.entries:
                raise ValueError('请先扫描包含PNG的输入文件夹')
            if Path(self.input_path.get().strip()).resolve() != self.scanned_root:
                raise ValueError('输入文件夹已变化，请重新扫描')
            if not self.output_path.get().strip():
                raise ValueError('请选择输出文件夹')
            source, target = validate_output(self.scanned_root, self.output_path.get().strip())
            keys = self.tree.selection() if selected else self.tree.get_children()
            if not keys:
                raise ValueError('请先选中要导出的图片')
            jobs = [Job(self.entries[int(key)].path, self._options(key)) for key in keys]
        except Exception as error:
            messagebox.showerror('无法导出', str(error))
            return
        self.cancel.clear()
        self._set_busy('export')
        self.progress.configure(mode='determinate', maximum=len(jobs), value=0)
        self.status.set(f'正在导出{len(jobs)}张图集…')
        self._log(self.status.get())
        def work():
            try:
                def update(index, record):
                    self.events.put(('batch_item', (index, record)))
                report = export_batch(jobs, source, target, update, self.cancel)
                self.events.put(('batch_done', report))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def stop_export(self):
        self.cancel.set()
        self.cancel_button.configure(state='disabled')
        self.status.set('正在完成当前图片，随后停止并保存处理清单…')

    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'scan':
                    self._scan_done(*data)
                elif kind == 'preview':
                    self._preview_done(*data)
                elif kind == 'batch_item':
                    index, record = data
                    label = STATUS_LABELS[record['status']]
                    for entry_index, entry in enumerate(self.entries):
                        if str(entry.path) == record['input']:
                            self.tree.set(str(entry_index), 'status', label)
                            self.tree.item(str(entry_index), tags=(record['status'],))
                            break
                    self.progress.configure(value=index + 1)
                    detail = record.get('output_size', record['reason'])
                    self._log(f'{label} · {Path(record["input"]).name} · {detail}')
                    for warning in record['warnings']:
                        self._log('  提示：' + warning)
                    self.status.set(f'已处理{index + 1}张 · {label} · {Path(record["input"]).name}')
                elif kind == 'batch_done':
                    self._set_busy('')
                    self.last_report = data
                    self.report_button.configure(state='normal' if data['csv_path'] else 'disabled')
                    counts = data['counts']
                    state = '已停止' if data['cancelled'] else '导出完成'
                    suffix = '部分清单未保存，详情见处理记录。' if data['report_errors'] else '处理清单已保存。'
                    self.status.set(f'{state}：成功 {counts["success"]} · 跳过 {counts["skipped"]} · 失败 {counts["failed"]}。' + suffix)
                    self._log(self.status.get())
                    for error in data['report_errors']:
                        self._log(error)
                    if self.closing:
                        self._destroy()
                        return
                elif kind == 'error':
                    self.progress.stop()
                    self._set_busy('')
                    self.status.set('操作失败：' + data)
                    self._log(self.status.get())
                    if self.closing:
                        self._destroy()
                        return
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def open_output(self):
        folder = Path(self.output_path.get().strip())
        if folder.is_dir():
            os.startfile(str(folder.resolve()))
        else:
            messagebox.showinfo('输出文件夹', '输出文件夹尚未创建，导出时会自动创建')

    def open_report(self):
        if self.last_report and self.last_report['csv_path']:
            os.startfile(self.last_report['csv_path'])

    def _destroy(self):
        self.preview_closed.set()
        try:
            self.preview_requests.get_nowait()
        except queue.Empty:
            pass
        self.preview_requests.put_nowait(None)
        self.root.destroy()

    def close(self):
        if self.busy == 'export':
            if messagebox.askyesno('正在导出', '完成当前图片并保存清单后退出？'):
                self.closing = True
                self.stop_export()
        else:
            self._destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-report')
    parser.add_argument('--verify-manifest')
    args = parser.parse_args()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    if args.smoke_report:
        from verify_runtime import verify_runtime
        verify_runtime(Path(args.smoke_report), args.verify_manifest)
        return
    root = tk.Tk()
    app = AtlasTrimApp(root)
    root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        detail = traceback.format_exc()
        folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'AtlasTrim'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'startup-error.log').write_text(detail, encoding='utf-8')
        try:
            messagebox.showerror('AtlasTrim 启动失败', f'错误详情已保存到：{folder / "startup-error.log"}\n{detail}')
        except Exception:
            pass
        raise
