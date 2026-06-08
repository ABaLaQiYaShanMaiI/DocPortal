"""
GUI application — FolderKnowledgeSiteGeneratorForAI.

Split from gui.py into: app (UI + scan + generate), i18n, server.
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Fast startup: only import light modules at load time ──
from src.scanner import collect_files_info, is_file_supported
from src.utils import human_readable_size
from src.ui.i18n import LANG
from src.ui.server import ServerManager

# Lazy imports: heavy modules loaded only when needed
_build_text_from_files = None
_build_markdown_from_files = None
_generate_portal_split = None
_HAS_PORTAL = None

def _get_portal():
    """Lazy-load portal generator (imports python-magic, pdfminer, etc)."""
    global _generate_portal_split, _HAS_PORTAL
    if _generate_portal_split is None:
        try:
            from src.generator.portal import generate_portal_split
            _generate_portal_split = generate_portal_split
            _HAS_PORTAL = True
        except ImportError:
            _generate_portal_split = None
            _HAS_PORTAL = False
    return _generate_portal_split

def _get_build_text():
    global _build_text_from_files
    if _build_text_from_files is None:
        from src.scanner import build_text_from_files
        _build_text_from_files = build_text_from_files
    return _build_text_from_files

def _get_build_md():
    global _build_markdown_from_files
    if _build_markdown_from_files is None:
        from src.scanner import build_markdown_from_files
        _build_markdown_from_files = build_markdown_from_files
    return _build_markdown_from_files


class App:
    """Main GUI application."""

    CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".folderknowledge_settings.json")

    COLORS = {
        'bg': '#f0f2f5', 'card': '#ffffff', 'primary': '#1a73e8',
        'primary_hover': '#1557b0', 'success': '#34a853', 'warning': '#fbbc04',
        'error': '#ea4335', 'text': '#202124', 'text_secondary': '#5f6368',
        'border': '#dadce0', 'drop_bg': '#e8f0fe', 'drop_bg_hover': '#d2e3fc',
    }

    def __init__(self, root):
        self.root = root
        self._lang = 'en'
        self.current_folder = None
        self.file_list = []
        self.total_size = 0
        self.generating = False
        self.input_is_file = False
        self.target_file = None
        self.output_format = 'txt'
        self.output_path = os.path.join(os.path.expanduser("~"), "Desktop", "knowledge_export.txt")
        self._content_search_index = {}
        self._pout_auto = True
        self._pout_updating = False

        self.server = ServerManager(on_status_change=self._on_server_status)

        self._load_settings()
        self.root.title("FolderKnowledgeSiteGeneratorForAI")
        self.root.geometry("820x720")
        self.root.minsize(700, 600)
        self.setup_styles()
        self.build_all()
        self.center_window()
        self.bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── i18n & settings ──

    def tr(self, key):
        return LANG[self._lang][key]

    def set_lang(self, lang):
        if lang != self._lang:
            saved_mode = self.mode_var.get() if hasattr(self, 'mode_var') else 'single'
            saved_skip = self.skip_var.get() if hasattr(self, 'skip_var') else True
            saved_fname = self.fname_var.get() if hasattr(self, 'fname_var') else 'knowledge_export'
            saved_output = self.out_var.get() if hasattr(self, 'out_var') else self.output_path
            saved_pout = self.pout_var.get() if hasattr(self, 'pout_var') else os.path.join(os.path.expanduser("~"), "Desktop", "knowledge_portal")
            self._lang = lang
            self._save_settings()
            self.build_all()
            self.mode_var.set(saved_mode)
            self.skip_var.set(saved_skip)
            self.fname_var.set(saved_fname)
            self.out_var.set(saved_output)
            self.pout_var.set(saved_pout)
            self.on_mode_change()

    def _save_settings(self):
        try:
            data = {"language": self._lang, "server_port": self.server.port}
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_settings(self):
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                lang = data.get("language", "en")
                if lang in LANG:
                    self._lang = lang
                self.server.port = data.get("server_port", 8080)
        except Exception:
            pass

    def _on_close(self):
        self.server.stop()
        self.root.destroy()

    # ── Styles ──

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        c = self.COLORS
        style.configure('TFrame', background=c['bg'])
        style.configure('TLabel', background=c['bg'], foreground=c['text'], font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=(12, 6))
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), foreground=c['primary'])
        style.configure('Subtitle.TLabel', font=('Segoe UI', 10), foreground=c['text_secondary'])
        style.configure('Heading.TLabel', font=('Segoe UI', 11, 'bold'), foreground=c['text'])
        style.configure('Treeview', font=('Segoe UI', 9), rowheight=26)
        style.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', c['primary'])])
        style.configure('TProgressbar', thickness=10, background=c['primary'])

    # ── Build UI ──

    def build_all(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.main = ttk.Frame(self.root, padding="10")
        self.main.pack(fill=tk.BOTH, expand=True)
        self._build_header()
        self._build_folder_row()
        self._build_file_list()
        self._build_settings()
        self._build_server_controls()
        self._build_gen_section()

    def _build_header(self):
        hdr = tk.Frame(self.main, bg=self.COLORS['bg'])
        hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(hdr, text=self.tr('title'), style='Title.TLabel').pack(side=tk.LEFT)
        ttk.Label(hdr, text=self.tr('subtitle'), style='Subtitle.TLabel').pack(side=tk.LEFT, padx=(8, 0))
        lang_f = tk.Frame(hdr, bg=self.COLORS['bg'])
        lang_f.pack(side=tk.RIGHT)
        for lcode, ltxt in [('en', 'EN'), ('zh', '中文')]:
            bg = self.COLORS['primary'] if self._lang == lcode else '#ccc'
            fg = 'white' if self._lang == lcode else '#333'
            btn = tk.Button(lang_f, text=ltxt, font=('Segoe UI', 9, 'bold'),
                            bg=bg, fg=fg, relief='flat', padx=8, pady=2,
                            cursor='hand2', command=lambda c=lcode: self.set_lang(c))
            btn.pack(side=tk.LEFT, padx=1)

    def _build_folder_row(self):
        folder_f = tk.Frame(self.main, bg=self.COLORS['card'],
                            highlightbackground=self.COLORS['primary'],
                            highlightthickness=2, padx=10, pady=8, cursor='hand2')
        folder_f.pack(fill=tk.X, pady=(0, 6))
        self.folder_drop_frame = folder_f
        try:
            from tkinterdnd2 import DND_FILES
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            # Drag-and-drop unavailable — show visible hint in the drop zone
            tk.Label(folder_f, text="(Drag & drop unavailable — install tkinterdnd2)",
                     font=('Segoe UI', 7), bg=self.COLORS['card'],
                     fg=self.COLORS['warning']).pack(pady=(0, 2))
        folder_f.bind('<Enter>', lambda e: folder_f.configure(bg=self.COLORS['drop_bg_hover']))
        folder_f.bind('<Leave>', lambda e: folder_f.configure(bg=self.COLORS['card']))
        folder_f.bind('<Button-1>', lambda e: self.browse_folder())
        tk.Label(folder_f, text=self.tr('drop'), font=('Segoe UI', 11, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['primary'], cursor='hand2').pack()
        tk.Label(folder_f, text=self.tr('hint'), font=('Segoe UI', 8),
                 bg=self.COLORS['card'], fg=self.COLORS['text_secondary']).pack(pady=(2, 6))
        row = tk.Frame(folder_f, bg=self.COLORS['card'])
        row.pack(fill=tk.X)
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(row, textvariable=self.path_var, font=('Segoe UI', 10))
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        path_entry.bind('<Return>', lambda e: self.load_from_path())
        self._make_btn(row, self.tr('browse'), self.browse_folder, self.COLORS['primary'])
        self._make_btn(row, self.tr('paste_btn'), self.paste_folder, self.COLORS['primary'])
        self._make_btn(row, 'Clear', self.clear_folder, self.COLORS['error'])

    def _make_btn(self, parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, font=('Segoe UI', 10),
                        bg=bg_color, fg='white', relief='flat',
                        cursor='hand2', command=command, padx=14, pady=3)
        btn._normal_bg = bg_color
        btn._hover_bg = '#1557b0' if text != 'Clear' else '#d32f2f'
        btn.pack(side=tk.LEFT, padx=2)
        btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=b._hover_bg))
        btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=b._normal_bg))
        return btn

    def _build_file_list(self):
        card = tk.Frame(self.main, bg=self.COLORS['card'],
                        highlightbackground=self.COLORS['border'],
                        highlightthickness=1, padx=10, pady=8)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        hdr_f = tk.Frame(card, bg=self.COLORS['card'])
        hdr_f.pack(fill=tk.X, pady=(0, 3))
        tk.Label(hdr_f, text=self.tr('file_list'), font=('Segoe UI', 11, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.stats_lbl = tk.Label(hdr_f, text=self.tr('no_folder'),
                                  font=('Segoe UI', 9),
                                  bg=self.COLORS['card'], fg=self.COLORS['text_secondary'])
        self.stats_lbl.pack(side=tk.RIGHT)

        search_row = tk.Frame(card, bg=self.COLORS['card'])
        search_row.pack(fill=tk.X, pady=(0, 3))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self._filter_file_tree())
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, font=('Segoe UI', 10))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        clear_btn = tk.Button(search_row, text='\u2715', font=('Segoe UI', 9),
                              bg=self.COLORS['text_secondary'], fg='white',
                              relief='flat', width=3, cursor='hand2',
                              command=lambda: self.search_var.set(''))
        clear_btn.pack(side=tk.LEFT, padx=1)
        clear_btn.bind('<Enter>', lambda e: clear_btn.configure(bg='#999'))
        clear_btn.bind('<Leave>', lambda e: clear_btn.configure(bg=self.COLORS['text_secondary']))

        self.search_mode_var = tk.StringVar(value='name')
        for val, lbl in [('name', 'Name'), ('code', 'Code')]:
            rb = tk.Radiobutton(search_row, text=lbl, variable=self.search_mode_var,
                                value=val, font=('Segoe UI', 8),
                                bg=self.COLORS['card'], selectcolor=self.COLORS['card'],
                                command=self._filter_file_tree)
            rb.pack(side=tk.LEFT, padx=(2, 0))

        self.search_hint_lbl = tk.Label(search_row, text='', font=('Segoe UI', 7),
                                        bg=self.COLORS['card'], fg=self.COLORS['text_secondary'])
        self.search_hint_lbl.pack(side=tk.RIGHT, padx=(0, 6))
        shortcut_text = 'Double-click open  |  Esc quit' if self._lang != 'zh' else '双击打开  |  Esc退出'
        tk.Label(search_row, text=shortcut_text, font=('Segoe UI', 7),
                 bg=self.COLORS['card'], fg=self.COLORS['text_secondary']).pack(side=tk.RIGHT, padx=(0, 2))

        tree_f = tk.Frame(card, bg=self.COLORS['card'])
        tree_f.pack(fill=tk.BOTH, expand=True)
        vs = ttk.Scrollbar(tree_f, orient=tk.VERTICAL)
        hs = ttk.Scrollbar(tree_f, orient=tk.HORIZONTAL)
        self.tree = ttk.Treeview(tree_f, columns=('name', 'size', 'chars', 'status'),
                                 show='tree headings',
                                 yscrollcommand=vs.set, xscrollcommand=hs.set, height=6)
        vs.config(command=self.tree.yview)
        hs.config(command=self.tree.xview)
        self.tree.column('#0', width=0, stretch=False)
        self.tree.column('name', width=350, minwidth=150)
        self.tree.column('size', width=80, minwidth=60, anchor=tk.E)
        self.tree.column('chars', width=60, minwidth=50, anchor=tk.E)
        self.tree.column('status', width=70, minwidth=60, anchor=tk.CENTER)
        for col, txt in [('name', 'Name'), ('size', 'Size'), ('chars', 'Chars'), ('status', 'Status')]:
            self.tree.heading(col, text=txt, anchor=tk.W if col == 'name' else tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.tag_configure('ok', foreground=self.COLORS['text'])
        self.tree.tag_configure('skip', foreground=self.COLORS['text_secondary'])
        self.tree.tag_configure('even', background='#fafafa')
        self.tree.tag_configure('odd', background='#ffffff')
        self.tree.tag_configure('matched', background='#fff3cd')
        self.tree.bind('<Double-1>', self._on_tree_double_click)
        self.tree.bind('<Return>', self._on_tree_double_click)
        self._update_search_hint()

    def _build_settings(self):
        self.set_f = tk.Frame(self.main, bg=self.COLORS['card'],
                              highlightbackground=self.COLORS['border'],
                              highlightthickness=1, padx=10, pady=8)
        self.set_f.pack(fill=tk.X, pady=(0, 6))

        mode_f = tk.Frame(self.set_f, bg=self.COLORS['card'])
        mode_f.pack(fill=tk.X, pady=(0, 4))
        tk.Label(mode_f, text=self.tr('mode_label'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value='single')
        for val, txt in [('single', self.tr('single')), ('chunked', self.tr('chunked_mode')), ('portal', self.tr('portal_mode'))]:
            rb = tk.Radiobutton(mode_f, text=txt, variable=self.mode_var, value=val,
                                command=self.on_mode_change, font=('Segoe UI', 10),
                                bg=self.COLORS['card'], selectcolor=self.COLORS['card'])
            rb.pack(side=tk.LEFT, padx=(8, 0))
        has_p = _get_portal() is not None
        ps = self.tr('ready') if has_p else self.tr('unavail')
        pc = self.COLORS['success'] if has_p else self.COLORS['warning']
        tk.Label(mode_f, text=f"({ps})", font=('Segoe UI', 9),
                 bg=self.COLORS['card'], fg=pc).pack(side=tk.LEFT, padx=(6, 0))

        sep = tk.Frame(self.set_f, bg=self.COLORS['border'], height=1)
        sep.pack(fill=tk.X, pady=(4, 6))

        # Single TXT settings
        self.single_f = tk.Frame(self.set_f, bg=self.COLORS['card'])
        self.single_f.pack(fill=tk.X)
        r1 = tk.Frame(self.single_f, bg=self.COLORS['card'])
        r1.pack(fill=tk.X, pady=1)
        tk.Label(r1, text=self.tr('output'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.out_var = tk.StringVar(value=self.output_path)
        ttk.Entry(r1, textvariable=self.out_var, font=('Segoe UI', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        out_btn = tk.Button(r1, text=self.tr('browse'), font=('Segoe UI', 9),
                            bg=self.COLORS['primary'], fg='white', relief='flat',
                            cursor='hand2', command=self.browse_txt_output, padx=10)
        out_btn.pack(side=tk.LEFT)
        out_btn.bind('<Enter>', lambda e: out_btn.configure(bg=self.COLORS['primary_hover']))
        out_btn.bind('<Leave>', lambda e: out_btn.configure(bg=self.COLORS['primary']))
        r2 = tk.Frame(self.single_f, bg=self.COLORS['card'])
        r2.pack(fill=tk.X, pady=1)
        tk.Label(r2, text=self.tr('fname'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.fname_var = tk.StringVar(value='knowledge_export')
        ttk.Entry(r2, textvariable=self.fname_var, width=16).pack(side=tk.LEFT, padx=(4, 2))
        self.fname_var.trace_add('write', lambda *a: self.update_out_path())
        tk.Label(r2, text='Format:', font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT, padx=(12, 2))
        self.format_var = tk.StringVar(value='txt')
        for fmt_val, fmt_txt in [('txt', '.txt'), ('md', '.md')]:
            rb = tk.Radiobutton(r2, text=fmt_txt, variable=self.format_var, value=fmt_val,
                                command=self._on_format_change, font=('Segoe UI', 10),
                                bg=self.COLORS['card'], selectcolor=self.COLORS['card'])
            rb.pack(side=tk.LEFT, padx=(2, 0))
        self.format_ext_lbl = tk.Label(r2, text='.txt', font=('Segoe UI', 10, 'bold'),
                                       bg=self.COLORS['card'], fg=self.COLORS['primary'])
        self.format_ext_lbl.pack(side=tk.LEFT, padx=(4, 0))
        self.skip_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.single_f, text=self.tr('show_skip'),
                       variable=self.skip_var, font=('Segoe UI', 10),
                       bg=self.COLORS['card'], selectcolor=self.COLORS['card']).pack(anchor=tk.W, pady=(2, 0))

        # Chunked settings
        self.chunked_f = tk.Frame(self.set_f, bg=self.COLORS['card'])
        cr1 = tk.Frame(self.chunked_f, bg=self.COLORS['card'])
        cr1.pack(fill=tk.X, pady=1)
        tk.Label(cr1, text=self.tr('out_dir'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.chunk_out_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "knowledge_chunked"))
        ttk.Entry(cr1, textvariable=self.chunk_out_var, font=('Segoe UI', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        chunk_out_btn = tk.Button(cr1, text=self.tr('browse'), font=('Segoe UI', 9),
                                  bg=self.COLORS['primary'], fg='white', relief='flat',
                                  cursor='hand2', command=self.browse_chunked_out, padx=10)
        chunk_out_btn.pack(side=tk.LEFT)
        chunk_out_btn.bind('<Enter>', lambda e: chunk_out_btn.configure(bg=self.COLORS['primary_hover']))
        chunk_out_btn.bind('<Leave>', lambda e: chunk_out_btn.configure(bg=self.COLORS['primary']))
        cr2 = tk.Frame(self.chunked_f, bg=self.COLORS['card'])
        cr2.pack(fill=tk.X, pady=1)
        tk.Label(cr2, text=self.tr('chunk_size_label'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.chunk_size_var = tk.StringVar(value='500000')
        ttk.Entry(cr2, textvariable=self.chunk_size_var, width=12).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(cr2, text=self.tr('chunk_chars'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        self.force_split_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.chunked_f, text=self.tr('force_split'),
                       variable=self.force_split_var, font=('Segoe UI', 10),
                       bg=self.COLORS['card'], selectcolor=self.COLORS['card']).pack(anchor=tk.W, pady=(2, 0))

        # Portal settings
        self.portal_f = tk.Frame(self.set_f, bg=self.COLORS['card'])
        pr1 = tk.Frame(self.portal_f, bg=self.COLORS['card'])
        pr1.pack(fill=tk.X, pady=1)
        tk.Label(pr1, text=self.tr('out_dir'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.pout_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "knowledge_portal"))
        self.pout_var.trace_add('write', lambda *a: setattr(self, '_pout_auto', self._pout_updating or True))
        ttk.Entry(pr1, textvariable=self.pout_var, font=('Segoe UI', 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        pout_btn = tk.Button(pr1, text=self.tr('browse'), font=('Segoe UI', 9),
                             bg=self.COLORS['primary'], fg='white', relief='flat',
                             cursor='hand2', command=self.browse_portal_out, padx=10)
        pout_btn.pack(side=tk.LEFT)
        pout_btn.bind('<Enter>', lambda e: pout_btn.configure(bg=self.COLORS['primary_hover']))
        pout_btn.bind('<Leave>', lambda e: pout_btn.configure(bg=self.COLORS['primary']))
        pr2 = tk.Frame(self.portal_f, bg=self.COLORS['card'])
        pr2.pack(fill=tk.X, pady=1)
        tk.Label(pr2, text=self.tr('port_label'), font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=str(self.server.port))
        ttk.Entry(pr2, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=(4, 8))
        self.port_var.trace_add('write', lambda *a: self._save_port())
        tk.Checkbutton(self.portal_f, text=self.tr('show_skip'),
                       variable=self.skip_var, font=('Segoe UI', 10),
                       bg=self.COLORS['card'], selectcolor=self.COLORS['card']).pack(anchor=tk.W, pady=(2, 0))

    def _build_server_controls(self):
        self.server_f = tk.Frame(self.main, bg=self.COLORS['card'],
                                 highlightbackground=self.COLORS['border'],
                                 highlightthickness=1, padx=10, pady=6)
        self.server_f.pack(fill=tk.X, pady=(0, 6))
        self.server_status_lbl = tk.Label(
            self.server_f, text=self.tr('status_ready'), font=('Segoe UI', 10),
            bg=self.COLORS['card'], fg=self.COLORS['text_secondary'])
        self.server_status_lbl.pack(side=tk.LEFT, padx=(0, 8))
        self.server_start_btn = tk.Button(
            self.server_f, text=f"\u25b6 {self.tr('server_start')}", font=('Segoe UI', 9),
            bg=self.COLORS['primary'], fg='white', relief='flat', cursor='hand2',
            command=self._on_server_start, padx=10, pady=2)
        self.server_start_btn.pack(side=tk.LEFT, padx=2)
        self.server_stop_btn = tk.Button(
            self.server_f, text=f"\u23f9 {self.tr('server_stop')}", font=('Segoe UI', 9),
            bg=self.COLORS['error'], fg='white', relief='flat', cursor='hand2',
            command=self.server.stop, padx=10, pady=2)
        self.server_copy_btn = tk.Button(
            self.server_f, text=f"\U0001f4cb {self.tr('copy_url')}", font=('Segoe UI', 9),
            bg=self.COLORS['primary'], fg='white', relief='flat', cursor='hand2',
            command=lambda: self.server.copy_url_to_clipboard(self.root), padx=10, pady=2)
        self._update_server_ui()

    def _build_gen_section(self):
        gen_f = tk.Frame(self.main, bg=self.COLORS['bg'])
        gen_f.pack(fill=tk.X)
        self.gen_btn = tk.Button(gen_f, text=self.tr('gen_btn'),
                                 font=('Segoe UI', 14, 'bold'),
                                 bg=self.COLORS['primary'], fg='white', relief='flat',
                                 cursor='hand2', command=self.generate, padx=40, pady=10,
                                 state='disabled')
        self.gen_btn.pack(pady=(0, 4))
        self.gen_btn.bind('<Enter>', lambda e: self._btn_hover(True))
        self.gen_btn.bind('<Leave>', lambda e: self._btn_hover(False))
        self.prog = ttk.Progressbar(gen_f, mode='determinate', length=400)
        st_f = tk.Frame(self.main, bg=self.COLORS['bg'], height=24)
        st_f.pack(fill=tk.X)
        st_f.pack_propagate(False)
        self.dot = tk.Canvas(st_f, width=8, height=8, bg=self.COLORS['bg'], highlightthickness=0)
        self.dot.pack(side=tk.LEFT, padx=(0, 4))
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['text_secondary'], outline='')
        self.status_var = tk.StringVar(value=self.tr('start_hint'))
        tk.Label(st_f, textvariable=self.status_var, font=('Segoe UI', 9),
                 bg=self.COLORS['bg'], fg=self.COLORS['text_secondary'],
                 anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.footer_var = tk.StringVar(value=self.tr('status_ready'))
        tk.Label(st_f, textvariable=self.footer_var, font=('Segoe UI', 9),
                 bg=self.COLORS['bg'], fg=self.COLORS['text_secondary'],
                 anchor=tk.E).pack(side=tk.RIGHT)

    def center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def bind_shortcuts(self):
        self.root.bind('<Control-o>', lambda e: self.browse_folder())
        self.root.bind('<Control-g>', lambda e: self.generate())
        self.root.bind('<Control-v>', lambda e: self.paste_folder())
        self.root.bind('<Escape>', lambda e: self.root.quit() if not self.generating else None)

    def _btn_hover(self, enter):
        if not self.generating:
            self.gen_btn.configure(bg=self.COLORS['primary_hover'] if enter else self.COLORS['primary'])

    # ── Server UI ──

    def _on_server_status(self, _running):
        self._update_server_ui()

    def _on_server_start(self):
        self._save_port()
        if not self.server.root or not os.path.isdir(self.server.root):
            return self.status_var.set("No portal output directory. Generate a portal first.")
        if self.server.start(self.server.root, port=self.server.port):
            self.status_var.set(f"\U0001f7e2 Server started at {self.server.url}")

    def _update_server_ui(self):
        if not hasattr(self, 'server_status_lbl'):
            return
        if self.server.is_running:
            self.server_status_lbl.config(
                text=f"\U0001f7e2 {self.tr('server_running')} {self.server.url}",
                fg=self.COLORS['success'])
            self.server_start_btn.pack_forget()
            self.server_stop_btn.pack(side=tk.LEFT, padx=2)
            self.server_copy_btn.pack(side=tk.LEFT, padx=2)
        else:
            self.server_status_lbl.config(text=self.tr('status_ready'), fg=self.COLORS['text_secondary'])
            self.server_stop_btn.pack_forget()
            self.server_copy_btn.pack_forget()
            self.server_start_btn.pack(side=tk.LEFT, padx=2)

    def _save_port(self):
        try:
            self.server.port = int(self.port_var.get().strip())
        except (ValueError, AttributeError):
            pass

    # ── Folder loading ──

    def load_from_path(self):
        path = self.path_var.get().strip().strip('"')
        if os.path.isfile(path):
            self.load_path(path)
        elif os.path.isdir(path):
            self.load_folder(path)
        else:
            self.status_var.set(f"Invalid path: {path}")

    def load_path(self, path):
        if self.generating:
            return
        self.input_is_file = True
        self.target_file = os.path.basename(path)
        self.current_folder = os.path.dirname(path)
        file_size = os.path.getsize(path)
        ext = os.path.splitext(path)[1].lower()
        supported = is_file_supported(path, ext)
        self.file_list = [{
            'path': path, 'rel_path': self.target_file, 'size': file_size,
            'size_hr': human_readable_size(file_size), 'ext': ext, 'supported': supported,
        }]
        self.total_size = file_size
        self.root.after(0, lambda: self._on_scanned_single(self.file_list, self.total_size))

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select a folder or file (cancel to pick a file)")
        if folder:
            self.path_var.set(folder)
            self.load_folder(folder)
        else:
            file_path = filedialog.askopenfilename(
                title="Select a file",
                filetypes=[
                    ("All supported files", "*.pdf *.docx *.doc *.txt *.md *.html *.py *.js *.ts *.json *.xml *.csv *.yaml *.yml"),
                    ("All files", "*.*")])
            if file_path:
                self.path_var.set(file_path)
                self.load_path(file_path)

    def clear_folder(self):
        self.current_folder = None
        self.file_list = []
        self.total_size = 0
        self.input_is_file = False
        self.target_file = None
        self.path_var.set('')
        self._content_search_index = {}
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.gen_btn.config(state='disabled')
        self.stats_lbl.config(text=self.tr('no_folder'))
        self.status_var.set(self.tr('start_hint'))
        self.footer_var.set(self.tr('status_ready'))
        self.dot.delete('all')
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['text_secondary'], outline='')
        self.fname_var.set('knowledge_export')

    def paste_folder(self):
        try:
            path = self.root.clipboard_get().strip().strip('"')
            if os.path.isdir(path):
                self.path_var.set(path)
                self.load_folder(path)
                self.status_var.set(self.tr('paste_done'))
            else:
                self.status_var.set(self.tr('clip_empty'))
        except Exception:
            self.status_var.set(self.tr('clip_empty'))

    def load_folder(self, folder_path):
        if self.generating:
            return
        self._content_search_index = {}
        self.current_folder = folder_path
        self.status_var.set(f"{self.tr('scanning')} {folder_path}")
        self.root.update_idletasks()
        def scan():
            fl, ts = collect_files_info(folder_path)
            self.root.after(0, lambda: self._on_scanned(fl, ts))
        threading.Thread(target=scan, daemon=True).start()

    def _on_scanned_single(self, file_list, total_size):
        self.file_list = file_list
        self.total_size = total_size
        supported = sum(1 for f in file_list if f['supported'])
        self.stats_lbl.config(text=f"1 {self.tr('files')} | {'1 ' + self.tr('supported') if supported else '0 supported'} | {human_readable_size(total_size)}")
        self._update_tree()
        if file_list and supported:
            self.gen_btn.config(state='normal')
            self.status_var.set(f"Single file: {self.target_file} ({'supported' if supported else 'unsupported'})")
            self.dot.delete('all')
            self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['success'], outline='')
        else:
            self.gen_btn.config(state='disabled')
            self.status_var.set("File is not supported or unreadable")
            self.dot.delete('all')
            self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['warning'], outline='')
        base_name = os.path.splitext(self.target_file)[0]
        self.fname_var.set(f"{base_name}_export")
        if self._pout_auto:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            self._pout_updating = True
            self.pout_var.set(os.path.join(desktop, f"{base_name}_portal"))
            self._pout_updating = False

    def _on_scanned(self, file_list, total_size):
        self.file_list = file_list
        self.total_size = total_size
        supported = sum(1 for f in file_list if f['supported'])
        self.stats_lbl.config(text=f"{len(file_list)} {self.tr('files')} | {supported} {self.tr('supported')} | {human_readable_size(total_size)}")
        self._update_tree()
        if file_list:
            self.gen_btn.config(state='normal')
            self.status_var.set(f"{len(file_list)} {self.tr('files')}, {supported} {self.tr('parseable')}")
            self.dot.delete('all')
            self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['success'], outline='')
        else:
            self.gen_btn.config(state='disabled')
            self.status_var.set(self.tr('empty'))
            self.dot.delete('all')
            self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['warning'], outline='')
        folder_basename = os.path.basename(os.path.normpath(self.current_folder))
        self.fname_var.set(f"{folder_basename}_export")
        if self._pout_auto:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            self._pout_updating = True
            self.pout_var.set(os.path.join(desktop, f"{folder_basename}_portal"))
            self._pout_updating = False

    def _update_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, f in enumerate(self.file_list):
            icon = '\U0001f4c4' if f['supported'] else '\u23ed\ufe0f'
            status = 'OK' if f['supported'] else 'Skip'
            tag = ('ok' if f['supported'] else 'skip', 'even' if i % 2 == 0 else 'odd')
            self.tree.insert('', 'end', values=(f"{icon} {f['rel_path']}", f['size_hr'], '-', status), tags=tag)
        supported_count = sum(1 for f in self.file_list if f['supported'])
        self.footer_var.set(f"{len(self.file_list)} {self.tr('files')} | {supported_count} {self.tr('parseable')}")

    def _on_drop(self, event):
        import re
        raw = event.data or ""
        if not raw:
            return
        candidates = re.findall(r'\{([^}]+)\}|"([^"]+)"|(\S+)', raw)
        paths = [p for group in candidates for p in group if p]
        for candidate in paths:
            path = candidate.strip().strip('"').strip("'")
            if os.path.isfile(path):
                self.path_var.set(path)
                return self.load_path(path)
            if os.path.isdir(path):
                self.path_var.set(path)
                return self.load_folder(path)
        path = raw.strip('{}').strip('"')
        if os.path.isfile(path):
            self.path_var.set(path)
            self.load_path(path)
        elif os.path.isdir(path):
            self.path_var.set(path)
            self.load_folder(path)

    # ── Mode switching ──

    def on_mode_change(self):
        mode = self.mode_var.get()
        is_portal = mode == 'portal'
        is_chunked = mode == 'chunked'
        self.single_f.pack_forget()
        self.portal_f.pack_forget()
        self.chunked_f.pack_forget()
        if is_portal:
            self.portal_f.pack(fill=tk.X)
            self.gen_btn.config(text=self.tr('gen_portal_btn'))
        elif is_chunked:
            self.chunked_f.pack(fill=tk.X)
            self.gen_btn.config(text='Generate Split TXT')
        else:
            self.single_f.pack(fill=tk.X)
            self.gen_btn.config(text=self.tr('gen_btn'))

    def browse_txt_output(self):
        fmt = self.format_var.get() if hasattr(self, 'format_var') else 'txt'
        ext = '.md' if fmt == 'md' else '.txt'
        ftypes = [("Markdown files", "*.md")] if fmt == 'md' else [("Text files", "*.txt")]
        fp = filedialog.asksaveasfilename(title=f"Save {fmt.upper()}", defaultextension=ext,
                                          filetypes=ftypes + [("All files", "*.*")],
                                          initialfile=self.fname_var.get() + ext)
        if fp:
            self.out_var.set(fp)
            self.fname_var.set(os.path.splitext(os.path.basename(fp))[0])

    def browse_portal_out(self):
        f = filedialog.askdirectory(title="Output directory")
        if f:
            self.pout_var.set(f)

    def browse_chunked_out(self):
        f = filedialog.askdirectory(title="Output directory for chunked files")
        if f:
            self.chunk_out_var.set(f)

    def _on_format_change(self):
        fmt = self.format_var.get()
        self.output_format = fmt
        ext = '.md' if fmt == 'md' else '.txt'
        self.format_ext_lbl.config(text=ext)
        cur = self.out_var.get().strip()
        if cur:
            base, _ = os.path.splitext(cur)
            self.out_var.set(base + ext)

    def update_out_path(self):
        name = self.fname_var.get().strip()
        if name:
            cur = self.out_var.get()
            d = os.path.dirname(cur) if os.path.dirname(cur) else os.path.join(os.path.expanduser("~"), "Desktop")
            ext = '.md' if self.format_var.get() == 'md' else '.txt'
            self.out_var.set(os.path.join(d, f"{name}{ext}"))

    # ── Generate ──

    def generate(self):
        if self.generating or not self.current_folder or not self.file_list:
            return
        self._save_port()
        mode = self.mode_var.get()
        is_portal = mode == 'portal'
        is_chunked = mode == 'chunked'
        skip = self.skip_var.get()

        if is_chunked:
            self._gen_chunked()
            return

        if is_portal:
            self._gen_portal(skip)
            return

        self._gen_text(skip)

    def _gen_text(self, skip):
        fmt = self.format_var.get() if hasattr(self, 'format_var') else 'txt'
        out = self.out_var.get().strip()
        if not out:
            return messagebox.showerror("Error", "Set output path")
        expected_ext = '.md' if fmt == 'md' else '.txt'
        if not out.lower().endswith(expected_ext):
            out += expected_ext
            self.out_var.set(out)
        mode_label = "MD" if fmt == 'md' else "TXT"
        self._start_gen(f"Generating {mode_label}...")

        def task():
            try:
                if fmt == 'md':
                    text, parsed, skipped, errors, chars = _get_build_md()(
                        self.current_folder, self.file_list, include_skipped=skip, language=self._lang)
                else:
                    text, parsed, skipped, errors, chars = _get_build_text()(
                        self.current_folder, self.file_list, include_skipped=skip)
                with open(out, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.root.after(0, lambda: self._gen_done(out, parsed, skipped, errors, chars))
            except Exception as e:
                self.root.after(0, lambda e=e: self._gen_err(str(e)))

        threading.Thread(target=task, daemon=True).start()
        self._sim_progress()

    def _gen_chunked(self):
        try:
            from src.chunker import write_chunks
        except ImportError:
            return messagebox.showerror("Error", "Chunked output module (src/chunker) not available")

        out_dir = self.chunk_out_var.get().strip()
        if not out_dir:
            return messagebox.showerror("Error", "Set output directory for chunked files")
        try:
            chunk_size = int(self.chunk_size_var.get().strip())
            if chunk_size < 10000:
                return messagebox.showerror("Error", "Chunk size must be at least 10,000")
        except ValueError:
            return messagebox.showerror("Error", "Invalid chunk size")

        force_split = self.force_split_var.get()
        self._start_gen("Generating split TXT files...")

        def task():
            try:
                result = write_chunks(
                    folder_path=self.current_folder, output_dir=out_dir,
                    chunk_size=chunk_size, force_split=force_split)
                self.root.after(0, lambda: self._chunked_done(result))
            except Exception as e:
                self.root.after(0, lambda e=e: self._gen_err(str(e)))

        threading.Thread(target=task, daemon=True).start()
        self._sim_progress()

    def _gen_portal(self, skip):
        g = _get_portal()
        if not g:
            return messagebox.showerror("Error", "Portal module unavailable")
        out_dir = self.pout_var.get().strip()
        if not out_dir:
            return messagebox.showerror("Error", "Set output directory")
        self._start_gen("Generating portal...")

        def task():
            try:
                r = _get_portal()(
                    folder_path=self.current_folder, output_dir=out_dir,
                    include_skipped=skip, language=self._lang)
                self.server._root = r.get("output_dir", out_dir)
                self.root.after(0, lambda: self._portal_done(r))
            except Exception as e:
                self.root.after(0, lambda e=e: self._gen_err(str(e)))

        threading.Thread(target=task, daemon=True).start()
        self._sim_progress()

    def _start_gen(self, msg):
        self.generating = True
        self.gen_btn.config(state='disabled', text=msg, bg='#999')
        self.prog['value'] = 0
        self.prog.pack(pady=(4, 0))
        self.status_var.set(msg)
        self.dot.delete('all')
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['warning'], outline='')

    def _sim_progress(self):
        if self.generating:
            v = self.prog['value']
            if v < 90:
                self.prog['value'] = min(v + 5, 90)
                self.root.after(300, self._sim_progress)

    def _gen_done(self, out_path, parsed, skipped, errors, chars):
        self.generating = False
        self.prog['value'] = 100
        fs = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        self.gen_btn.config(state='normal', text=self.tr('gen_btn'), bg=self.COLORS['primary'])
        st = (f"{self.tr('gen_done')} {parsed} files" + (f", {skipped} skipped" if skipped else "") +
              (f", {errors} errors" if errors else "") + f" | {chars:,} chars | {human_readable_size(fs)}")
        self.status_var.set(st)
        self.footer_var.set(f"OK {os.path.basename(out_path)}")
        self.dot.delete('all')
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['success'], outline='')
        if messagebox.askyesno("Success", f"TXT generated!\n\nOutput: {out_path}\nParsed: {parsed}\nSkipped: {skipped}\nErrors: {errors}\nChars: {chars:,}\nSize: {human_readable_size(fs)}\n\n{self.tr('open_folder')}"):
            self._open_folder(out_path)

    def _chunked_done(self, result):
        self.generating = False
        self.prog['value'] = 100
        cc, tc, tf = result["chunks_count"], result["total_chars"], result["total_files"]
        od = result["output_dir"]
        self.gen_btn.config(state='normal', text='Generate Split TXT', bg=self.COLORS['primary'])
        self.status_var.set(f"Split TXT generated: {cc} chunks, {tf} files, {tc:,} chars")
        self.footer_var.set(f"OK {cc} chunks")
        self.dot.delete('all')
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['success'], outline='')
        if messagebox.askyesno("Success", f"Split TXT generated!\n\nOutput: {od}\nChunks: {cc}\nFiles: {tf}\nTotal chars: {tc:,}\n\nOpen output folder?"):
            try:
                if sys.platform == 'win32':
                    os.startfile(od)
            except Exception:
                pass

    def _portal_done(self, result):
        self.generating = False
        self.prog['value'] = 100
        dc, tc = result["doc_count"], result["total_chars"]
        od, idx = result["output_dir"], result.get("index_file", "")
        sk, er = result.get("skipped", 0), result.get("errors", 0)
        self.gen_btn.config(state='normal', text=self.tr('gen_portal_btn'), bg=self.COLORS['primary'])
        st = (f"{self.tr('portal_done')} {dc} files" + (f", {sk} skipped" if sk else "") +
              (f", {er} errors" if er else "") + f" | {tc:,} chars")
        self.status_var.set(st)
        self.footer_var.set(f"OK {os.path.basename(od)}")
        self.dot.delete('all')
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['success'], outline='')
        hi = idx and os.path.exists(idx)
        msg = f"Portal generated!\n\nOutput: {od}\nFiles: {dc}\nSkipped: {sk}\nErrors: {er}\nChars: {tc:,}\n\n"
        if hi:
            ask_msg = msg + self.tr('server_ask')
            if messagebox.askyesno("Success", ask_msg):
                if self.server.start(od, port=self.server.port):
                    self.status_var.set(f"\U0001f7e2 {self.tr('server_running')} {self.server.url}")
                else:
                    self.status_var.set("\u274c Failed to start server")
            else:
                if messagebox.askyesno("Success", msg + self.tr('open_folder')):
                    self._open_folder(idx)
        else:
            messagebox.showinfo("Done", msg + "No pages generated")

    # ── File tree search ──

    def _update_search_hint(self):
        mode = self.search_mode_var.get()
        hint = 'Search file names' if mode == 'name' else 'Search code content'
        if self._lang == 'zh':
            hint = '搜索文件名' if mode == 'name' else '搜索代码内容'
        self.search_hint_lbl.config(text=hint)

    def _build_content_search_index(self):
        from src.parser.dispatcher import parse_file
        idx = {}
        for i, f in enumerate(self.file_list):
            if not f['supported']:
                continue
            try:
                result = parse_file(f['path'])
                if result:
                    text = (result.get("text") or "").strip()
                    if text:
                        idx[i] = text.lower()
            except Exception:
                pass
        return idx

    def _filter_file_tree(self):
        query = self.search_var.get().strip().lower()
        mode = self.search_mode_var.get()
        if not self.tree.get_children():
            return
        if not query:
            total = len(self.tree.get_children())
            for item in self.tree.get_children():
                self.tree.item(item, tags=())
            self.footer_var.set(f"{total} {self.tr('files')}")
            self.stats_lbl.config(text=f"{len(self.file_list)} {self.tr('files')} | {sum(1 for f in self.file_list if f['supported'])} {self.tr('supported')} | {human_readable_size(self.total_size)}")
            return
        if mode == 'code' and not self._content_search_index:
            self.status_var.set("Building content search index...")
            self.root.update_idletasks()
            self._content_search_index = self._build_content_search_index()
            self.status_var.set("Search ready")
        matched_count = 0
        for i, item in enumerate(self.tree.get_children()):
            values = self.tree.item(item, 'values')
            if not values:
                continue
            clean_name = values[0].replace('\U0001f4c4', '').replace('\u23ed\ufe0f', '').strip()
            if mode == 'name':
                match = query in clean_name.lower()
            else:
                match = query in clean_name.lower() or (i in self._content_search_index and query in self._content_search_index[i])
            if match:
                self.tree.item(item, tags=('matched',))
                matched_count += 1
            else:
                self.tree.item(item, tags=())
        self.footer_var.set(f"{matched_count}/{len(self.tree.get_children())} matched")

    def _on_tree_double_click(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        clean_name = self.tree.item(selection[0], 'values')[0].replace('\U0001f4c4', '').replace('\u23ed\ufe0f', '').strip()
        for f in self.file_list:
            if f['rel_path'] == clean_name:
                full_path = f['path']
                if os.path.isfile(full_path):
                    try:
                        if sys.platform == 'win32':
                            os.startfile(full_path)
                        elif sys.platform == 'darwin':
                            import subprocess
                            subprocess.run(['open', full_path])
                        else:
                            import subprocess
                            subprocess.run(['xdg-open', full_path])
                        return
                    except Exception:
                        pass

    def _gen_err(self, msg):
        self.generating = False
        self.prog['value'] = 0
        self.prog.pack_forget()
        self.gen_btn.config(state='normal', text=self.tr('gen_btn'), bg=self.COLORS['primary'])
        self.status_var.set("Failed: " + msg)
        self.dot.delete('all')
        self.dot.create_oval(0, 0, 8, 8, fill=self.COLORS['error'], outline='')
        messagebox.showerror("Error", msg)

    def _open_folder(self, path):
        try:
            if sys.platform == 'win32':
                os.startfile(os.path.dirname(path))
        except Exception:
            pass