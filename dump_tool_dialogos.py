import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import re
import os
import json
import glob
import gc

class UnityDumpToolComplete:
    def __init__(self, root):
        self.root = root
        self.root.title("Unity Dump Tool V34 - Fixed (Aspas & Newlines)")
        self.root.geometry("1300x850")

        # --- ESTILOS ---
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Segoe UI", 9))
        self.style.configure("TLabel", font=("Segoe UI", 9))
        self.style.configure("Bold.TLabel", font=("Segoe UI", 9, "bold"))
        self.style.configure("Success.TLabel", foreground="green", font=("Segoe UI", 9, "bold"))
        self.style.configure("Safe.TCheckbutton", foreground="green")
        self.style.configure("Unsafe.TCheckbutton", foreground="red")
        
        # --- DADOS ---
        self.mode = None 
        self.project_data = {"base_folder": "", "files": {}}
        self.project_json_path = None
        
        # Memória
        self.current_filename = None
        self.content_raw = None
        self.clean_xml = None
        self.entries = [] 
        self.current_edit_entry = None
        
        # Colunas e Filtros
        self.file_type_detected = None 
        self.detected_columns = []
        self.target_columns = []
        
        self.safe_keywords = ["name", "desc", "text", "content", "value", "message"]
        self.unsafe_keywords = ["id", "guid", "sprite", "icon", "costume", "category", "quest", "trigger", "lock", "unlock"]

        # Regex Poderosos
        self.re_script = re.compile(r'(1 string m_Script = ")([\s\S]*?)("\s*\n\s*1 string m_sourcePrefab|"\s*$)', re.MULTILINE)
        self.re_row = re.compile(r'(<Row[^>]*>)(.*?)(</Row>)', re.DOTALL)
        self.re_cell_capture = re.compile(r'(<Cell\b[^>]*>)(.*?)(</Cell>)|(<Cell\b[^>]*/>)', re.DOTALL)
        self.re_data_val = re.compile(r'<Data\s+[^>]*>(.*?)</Data>', re.DOTALL)
        self.re_attr_index = re.compile(r'ss:Index="(\d+)"')
        self.re_topic = re.compile(r'(<topic\b[^>]*?\btext=")([^"]*)(")', re.DOTALL)

        self.focus_mode_var = tk.BooleanVar(value=False)
        self.filter_editable_var = tk.BooleanVar(value=False)

        self.build_launcher()

    # =========================================================================
    # UI
    # =========================================================================
    def build_launcher(self):
        self.clear_window()
        frame = ttk.Frame(self.root)
        frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ttk.Label(frame, text="Unity Dump Tool V34", font=("Segoe UI", 24, "bold")).pack(pady=20)
        ttk.Label(frame, text="Correção de Syntax: Aspas e \\N", foreground="green").pack(pady=10)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="📄 MODO INDIVIDUAL", command=lambda: self.start_mode("single")).pack(side=tk.LEFT, padx=10, ipadx=15, ipady=10)
        ttk.Button(btn_frame, text="🗂️ MODO PROJETO", command=lambda: self.start_mode("project")).pack(side=tk.LEFT, padx=10, ipadx=15, ipady=10)

    def clear_window(self):
        for widget in self.root.winfo_children(): widget.destroy()

    def start_mode(self, mode):
        self.mode = mode
        self.build_main_ui(mode == "project")
        if mode == "single": self.single_load_file()

    def build_main_ui(self, is_project_mode):
        self.clear_window()
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        if is_project_mode:
            file_menu.add_command(label="Novo Projeto...", command=self.proj_new)
            file_menu.add_command(label="Abrir Projeto...", command=self.proj_load_json)
            file_menu.add_command(label="Salvar Projeto", command=self.proj_save_json)
            file_menu.add_separator()
            file_menu.add_command(label="Exportar TUDO (.txt)", command=self.proj_export_batch)
        else:
            file_menu.add_command(label="Abrir Arquivo...", command=self.single_load_file)
            file_menu.add_command(label="Salvar Arquivo", command=self.single_save_file)
        
        ext_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tradução Externa", menu=ext_menu)
        ext_menu.add_command(label="📤 Exportar para JSON", command=self.export_json_external)
        ext_menu.add_command(label="📥 Importar de JSON (FIX)", command=self.import_json_external)

        file_menu.add_separator()
        file_menu.add_command(label="Voltar", command=self.build_launcher)

        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ESQUERDA (Arquivos)
        if is_project_mode:
            self.frame_files = ttk.LabelFrame(main_paned, text="Arquivos", padding=2, width=220)
            main_paned.add(self.frame_files, weight=1)
            
            ff_inner = ttk.Frame(self.frame_files)
            ff_inner.pack(fill=tk.BOTH, expand=True)
            sb_files = ttk.Scrollbar(ff_inner)
            sb_files.pack(side=tk.RIGHT, fill=tk.Y)
            self.list_files = tk.Listbox(ff_inner, font=("Segoe UI", 9), exportselection=False, yscrollcommand=sb_files.set)
            self.list_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb_files.config(command=self.list_files.yview)
            self.list_files.bind('<<ListboxSelect>>', self.on_file_list_select)

        # CENTRAL (Dados)
        frame_mid = ttk.LabelFrame(main_paned, text="Dados & Filtros", padding=2, width=350)
        main_paned.add(frame_mid, weight=1)

        filter_frame = ttk.Frame(frame_mid)
        filter_frame.pack(fill=tk.X, pady=2)
        ttk.Label(filter_frame, text="Busca:").pack(side=tk.LEFT)
        self.entry_filter = ttk.Entry(filter_frame)
        self.entry_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.entry_filter.bind('<KeyRelease>', self.filter_list)
        
        # Botão de Colunas
        col_frame = ttk.Frame(frame_mid)
        col_frame.pack(fill=tk.X, pady=2)
        self.btn_cols = ttk.Button(col_frame, text="⚙️ Colunas", command=self.open_column_selector, state=tk.DISABLED)
        self.btn_cols.pack(side=tk.LEFT, padx=2)

        self.chk_safe = ttk.Checkbutton(col_frame, text="Somente Editáveis", variable=self.filter_editable_var, command=self.filter_list)
        self.chk_safe.pack(side=tk.LEFT, padx=5)
        
        self.btn_mark = ttk.Button(frame_mid, text="✅ Marcar (Espaço)", command=self.toggle_mark)
        self.btn_mark.pack(fill=tk.X, pady=2)

        list_frame = ttk.Frame(frame_mid)
        list_frame.pack(fill=tk.BOTH, expand=True)
        sb_ids = ttk.Scrollbar(list_frame)
        sb_ids.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_ids = tk.Listbox(list_frame, font=("Consolas", 10), exportselection=False, yscrollcommand=sb_ids.set)
        self.list_ids.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_ids.config(command=self.list_ids.yview)
        self.list_ids.bind('<<ListboxSelect>>', self.on_id_select)
        self.list_ids.bind('<space>', lambda e: self.toggle_mark())
        
        self.lbl_progress = ttk.Label(frame_mid, text="0 / 0", style="Success.TLabel")
        self.lbl_progress.pack(anchor="w")

        # DIREITA (Editor)
        frame_editor = ttk.LabelFrame(main_paned, text="Editor Visual", padding=2)
        main_paned.add(frame_editor, weight=3)
        
        # Legenda e Foco
        ctrl_ed = ttk.Frame(frame_editor)
        ctrl_ed.pack(fill=tk.X, pady=2)
        self.chk_focus = ttk.Checkbutton(ctrl_ed, text="Modo Foco", variable=self.focus_mode_var, command=self.apply_highlighting)
        self.chk_focus.pack(side=tk.LEFT)
        
        ttk.Separator(ctrl_ed, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        self.add_legend(ctrl_ed, "Texto", "white", "black")
        self.add_legend(ctrl_ed, "Tags", "white", "blue")
        self.add_legend(ctrl_ed, "\\N", "#eee", "red")
        self.add_legend(ctrl_ed, "Cmds", "white", "purple")

        ed_frame = ttk.Frame(frame_editor)
        ed_frame.pack(fill=tk.BOTH, expand=True)
        sb_ed = ttk.Scrollbar(ed_frame)
        sb_ed.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_editor = scrolledtext.ScrolledText(ed_frame, font=("Consolas", 12), wrap=tk.WORD, undo=True, yscrollcommand=sb_ed.set)
        self.txt_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_ed.config(command=self.txt_editor.yview)
        self.txt_editor.bind('<KeyRelease>', self.on_text_change)
        self.setup_tags()

        self.status_bar = ttk.Label(self.root, text="Pronto.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def add_legend(self, parent, text, bg, fg):
        tk.Label(parent, text=f" {text} ", bg=bg, fg=fg, font=("Segoe UI", 8, "bold"), relief="flat").pack(side=tk.LEFT, padx=2)

    def setup_tags(self):
        self.txt_editor.tag_config("dimmed", foreground="#cccccc", background="white")
        self.txt_editor.tag_config("highlight_text", background="#fffacd", foreground="black")
        self.txt_editor.tag_config("structure", foreground="blue")
        self.txt_editor.tag_config("linebreak", foreground="red", background="#eeeeee")
        self.txt_editor.tag_config("command", foreground="purple")
        self.txt_editor.tag_config("entity", foreground="#8e44ad")
        self.txt_editor.tag_config("richtext", foreground="#d35400")
        self.txt_editor.tag_config("search_match", background="yellow", foreground="black")

    # =========================================================================
    # LÓGICA (REGEX & PARSING) - CORRIGIDO PARA \N
    # =========================================================================
    
    def escape(self, t): 
        # FIX: O jogo usa \N para quebra de linha dentro do atributo XML.
        # Removemos \r para limpar e transformamos \n (python) em \N (jogo)
        return t.replace('\n', '\\N').replace('\r', '')

    def unescape(self, t): 
        # FIX: Converte o \N do jogo para quebra de linha visual no editor (\n)
        # Também garante suporte caso haja \n legado
        return t.replace('\\N', '\n').replace('\\n', '\n')

    def is_safe_column(self, col_name):
        cl = col_name.lower()
        for bad in self.unsafe_keywords: 
            if bad in cl: return False
        for good in self.safe_keywords: 
            if good in cl: return True
        return False

    def load_file_content(self, filename):
        path = os.path.join(self.project_data["base_folder"], filename)
        if not os.path.exists(path): return
        
        self.entries = []; self.current_edit_entry = None; self.detected_columns = []; self.target_columns = []
        self.txt_editor.delete(1.0, tk.END); self.list_ids.delete(0, tk.END)
        gc.collect()

        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f: raw = f.read()
            match = self.re_script.search(raw)
            if not match:
                messagebox.showerror("Erro", "Arquivo inválido (sem m_Script).")
                return

            self.current_filename = filename
            self.content_raw = raw
            self.clean_xml = match.group(2).replace('\\"', '"')

            if '<topic' in self.clean_xml and 'text="' in self.clean_xml: self.file_type_detected = "mindmap"
            elif '<Row' in self.clean_xml and '<Data' in self.clean_xml: self.file_type_detected = "xml"
            else: self.file_type_detected = "text"

            saved_edits = {}; saved_marks = set(); saved_cols = None
            if self.mode == "project":
                info = self.project_data["files"].get(filename, {})
                saved_edits = info.get("edits", {})
                saved_marks = set(info.get("marked", []))
                saved_cols = info.get("columns")

            if self.file_type_detected == "xml":
                self.btn_cols.config(state=tk.NORMAL)
                rows = list(self.re_row.finditer(self.clean_xml))
                if rows:
                    header_map = self.parse_row_cells(rows[0].group(2))
                    self.detected_columns = [header_map.get(i, f"Col{i}") for i in range(max(header_map.keys())+1)]
                    
                    if saved_cols: self.target_columns = saved_cols
                    else:
                        self.target_columns = [c for c in self.detected_columns if self.is_safe_column(c)]
                        if not self.target_columns and len(self.detected_columns)>1: self.target_columns = [self.detected_columns[1]]
                        if "XML_id" in self.target_columns: self.target_columns.remove("XML_id")

                    for i, r_match in enumerate(rows):
                        if i == 0: continue
                        row_data = self.parse_row_cells(r_match.group(2))
                        row_id = row_data.get(0)
                        if not row_id or row_id == "XML_id": continue

                        for idx, text in row_data.items():
                            if idx == 0: continue
                            col_name = header_map.get(idx, f"Col_{idx}")
                            if col_name not in self.target_columns: continue
                            
                            key = f"{row_id}|{col_name}"
                            curr_text = saved_edits.get(key, text)
                            
                            self.entries.append({
                                'unique_key': key, 'id_display': row_id, 'col_name': col_name,
                                'original': self.escape(text), 'current': self.escape(curr_text), 'marked': key in saved_marks
                            })
            
            elif self.file_type_detected == "mindmap":
                self.btn_cols.config(state=tk.DISABLED)
                matches = list(self.re_topic.finditer(self.clean_xml))
                for i, m in enumerate(matches):
                    txt = m.group(2)
                    if txt == os.path.splitext(filename)[0]: continue
                    eid = f"Topic_{i}"
                    curr = saved_edits.get(eid, txt)
                    self.entries.append({'unique_key': eid, 'id_display': eid, 'col_name': 'Text', 'original': self.escape(txt), 'current': self.escape(curr), 'marked': eid in saved_marks})

            else: # Text
                self.btn_cols.config(state=tk.DISABLED)
                fid = os.path.basename(filename)
                txt = self.clean_xml
                curr = saved_edits.get(fid, txt)
                self.entries.append({'unique_key': fid, 'id_display': fid, 'col_name': 'Content', 'original': self.escape(txt), 'current': self.escape(curr), 'marked': fid in saved_marks})

            self.populate_list()
            self.status_bar.config(text=f"Carregado: {filename} ({self.file_type_detected})")

        except Exception as e: messagebox.showerror("Erro", str(e))

    def parse_row_cells(self, row_content):
        data = {}
        current_idx = 0
        for m in self.re_cell_capture.finditer(row_content):
            full_tag = m.group(0)
            idx_match = self.re_attr_index.search(full_tag)
            if idx_match: current_idx = int(idx_match.group(1)) - 1
            val_match = self.re_data_val.search(full_tag)
            if val_match: data[current_idx] = val_match.group(1)
            current_idx += 1
        return data

    def open_column_selector(self):
        if not self.detected_columns: return
        win = tk.Toplevel(self.root)
        win.title("Colunas")
        win.geometry("350x600")
        
        frame_list = ttk.Frame(win); frame_list.pack(fill=tk.BOTH, expand=True)
        cv = tk.Canvas(frame_list); sb = ttk.Scrollbar(frame_list, command=cv.yview)
        scf = ttk.Frame(cv); scf.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=scf, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        vars = {}
        for col in self.detected_columns:
            v = tk.BooleanVar(value=col in self.target_columns)
            style = "Safe.TCheckbutton" if self.is_safe_column(col) else "Unsafe.TCheckbutton"
            ttk.Checkbutton(scf, text=col, variable=v, style=style).pack(anchor='w', padx=5)
            vars[col] = v
        
        def apply():
            self.target_columns = [c for c, v in vars.items() if v.get()]
            if self.mode == "project":
                if self.current_filename not in self.project_data["files"]: self.project_data["files"][self.current_filename]={}
                self.project_data["files"][self.current_filename]["columns"] = self.target_columns
            win.destroy(); self.load_file_content(self.current_filename)
        
        ttk.Button(win, text="Aplicar", command=apply).pack(pady=10)

    # --- LISTAS ---
    def populate_list(self):
        self.list_ids.delete(0, tk.END)
        q = self.entry_filter.get().lower()
        only_safe = self.filter_editable_var.get()
        count_mod = 0
        self.visible_entries_map = [] 

        for entry in self.entries:
            if only_safe and not self.is_safe_column(entry['col_name']): continue
            txt_s = f"{entry['id_display']} {entry['col_name']} {entry['current']}".lower()
            if q and q not in txt_s: continue

            self.visible_entries_map.append(entry)
            display = f"{entry['id_display']} [{entry['col_name']}]"
            self.list_ids.insert(tk.END, display)
            
            idx = self.list_ids.size() - 1
            if entry['marked']: self.list_ids.itemconfig(idx, {'bg': '#d4fcd4'}); count_mod+=1
            elif entry['current'] != entry['original']: self.list_ids.itemconfig(idx, {'bg': '#fffacd'})
        
        self.lbl_progress.config(text=f"Editados: {count_mod}")

    def filter_list(self, event=None): self.populate_list()

    def on_id_select(self, event):
        sel = self.list_ids.curselection()
        if not sel: return
        entry = self.visible_entries_map[sel[0]]
        self.current_edit_entry = entry
        self.txt_editor.delete(1.0, tk.END)
        self.txt_editor.insert(tk.END, entry['current'])
        self.apply_highlighting()

    def on_text_change(self, event=None):
        if not self.current_edit_entry: return
        txt = self.txt_editor.get(1.0, "end-1c")
        if self.current_edit_entry['current'] != txt:
            self.current_edit_entry['current'] = txt
            if not self.current_edit_entry['marked']:
                self.current_edit_entry['marked'] = True
                sel = self.list_ids.curselection()
                if sel: self.list_ids.itemconfig(sel[0], {'bg': '#d4fcd4'})
        self.apply_highlighting()

    def toggle_mark(self):
        if not self.current_edit_entry: return
        self.current_edit_entry['marked'] = not self.current_edit_entry['marked']
        sel = self.list_ids.curselection()
        if sel:
            color = '#d4fcd4' if self.current_edit_entry['marked'] else 'white'
            self.list_ids.itemconfig(sel[0], {'bg': color})

    def apply_highlighting(self):
        for t in ["dimmed", "highlight_text", "structure", "linebreak", "command", "entity", "richtext", "search_match"]:
            self.txt_editor.tag_remove(t, "1.0", tk.END)
        # FIX: Highlight para \N literal
        patterns = [(r'&#10;|\\n|\\r|\\N', "linebreak"), (r'&lt;.*?&gt;', "structure"), (r'&lt;/?(b|i|u|size|color).*?&gt;', "richtext"), (r'&quot;', "entity"), (r'\[.*?\]', "command")]
        if self.focus_mode_var.get():
            self.txt_editor.tag_add("highlight_text", "1.0", tk.END)
            for p, _ in patterns: self.highlight_pattern(p, "dimmed")
        else:
            for p, t in patterns: self.highlight_pattern(p, t)
        q = self.entry_filter.get().strip()
        if q and len(q)>1: self.highlight_pattern(re.escape(q), "search_match", True)

    def highlight_pattern(self, pat, tag, nocase=True):
        start="1.0"
        while True:
            pos = self.txt_editor.search(pat, start, stopindex=tk.END, regexp=True, nocase=True)
            if not pos: break
            txt = self.txt_editor.get(pos, tk.END)
            m = re.match(pat, txt, re.IGNORECASE)
            if not m: start=f"{pos}+1c"; continue
            end = f"{pos}+{len(m.group(0))}c"
            self.txt_editor.tag_add(tag, pos, end)
            start = end

    # =========================================================================
    # JSON EXTERNAL (FIX CRÍTICO DE SYNTAX)
    # =========================================================================
    def export_json_external(self):
        if not self.entries: return
        f = filedialog.asksaveasfilename(defaultextension=".json")
        if f:
            data = {e['unique_key']: self.unescape(e['current']) for e in self.entries}
            json.dump(data, open(f,'w',encoding='utf-8'), indent=4, ensure_ascii=False)
            messagebox.showinfo("OK", "Exportado")

    def import_json_external(self):
        if not self.entries: return
        f = filedialog.askopenfilename()
        if f:
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
                
                c = 0
                for e in self.entries:
                    if e['unique_key'] in data:
                        raw_translated = data[e['unique_key']]
                        
                        # --- CORREÇÃO DE SINTAXE XML ---
                        # 1. Substitui aspas duplas por simples para não quebrar atributo text="..."
                        sanitized = raw_translated.replace('"', "'")
                        
                        # 2. Aplica o escape correto (\n vira \N)
                        n = self.escape(sanitized)
                        
                        if n != e['current']: 
                            e['current'] = n
                            e['marked'] = True
                            c += 1
                
                self.populate_list()
                if self.mode == "project": self.sync_ram()
                messagebox.showinfo("OK", f"{c} linhas importadas e corrigidas (Aspas/Quebras).")
                
            except Exception as e:
                messagebox.showerror("Erro JSON", f"Falha ao ler JSON:\n{str(e)}")

    # --- SAVE/PROJECT BOILERPLATE ---
    def single_load_file(self): 
        p = filedialog.askopenfilename(); 
        if p: self.project_data["base_folder"]=os.path.dirname(p); self.load_file_content(os.path.basename(p))
    def single_save_file(self): self.perform_save()
    def proj_new(self): 
        d = filedialog.askdirectory()
        if d: self.project_data={"base_folder":d,"files":{}}; self.refresh_list()
    def proj_save_json(self):
        self.sync_ram()
        f=filedialog.asksaveasfilename(defaultextension=".json")
        if f: json.dump(self.project_data, open(f,'w'), indent=4); messagebox.showinfo("OK", "Salvo")
    def proj_load_json(self):
        f=filedialog.askopenfilename()
        if f: self.project_data=json.load(open(f)); self.refresh_list()
    def refresh_list(self): 
        self.list_files.delete(0,tk.END)
        for f in glob.glob(os.path.join(self.project_data["base_folder"], "*.txt")): self.list_files.insert(tk.END, os.path.basename(f))
    def on_file_list_select(self, e):
        s=self.list_files.curselection()
        if s: self.sync_ram(); self.load_file_content(self.list_files.get(s[0]))
    def sync_ram(self):
        if not self.current_filename: return
        edits={}; marks=[]
        for e in self.entries:
            if e['current']!=e['original']: edits[e['unique_key']] = self.unescape(e['current'])
            if e['marked']: marks.append(e['unique_key'])
        if self.current_filename not in self.project_data["files"]: self.project_data["files"][self.current_filename]={}
        self.project_data["files"][self.current_filename].update({"edits":edits, "marked":marks, "columns":self.target_columns})
    
    def perform_save(self):
        self.sync_ram()
        if not self.current_filename: return
        edits = self.project_data["files"][self.current_filename]["edits"]
        cnt = self.generate_export_content(self.current_filename, edits)
        
        initial = self.project_data["base_folder"]
        target = filedialog.askdirectory(initialdir=initial, title="Salvar Onde?")
        if not target: return
        
        self.save_logic_handler(target, self.current_filename, cnt)

    def proj_export_batch(self):
        self.sync_ram()
        d = filedialog.askdirectory()
        if d:
            c=0
            for f,dat in self.project_data["files"].items():
                if dat.get("edits"):
                    if self.save_logic_handler(d,f,self.generate_export_content(f,dat["edits"])): c+=1
            messagebox.showinfo("Fim",f"{c} exportados")

    def save_logic_handler(self, target_dir, filename, content):
        full_path = os.path.join(target_dir, filename)
        if os.path.exists(full_path):
            resp = messagebox.askyesnocancel("Arquivo Existe", f"'{filename}' existe.\nSobrescrever?", detail="Sim=Substituir, Não=Renomear")
            if resp is None: return False
            elif resp is False: full_path = self.get_unique_path(target_dir, filename)
        try: open(full_path, 'w', encoding='utf-8').write(content); return True
        except Exception as e: messagebox.showerror("Erro", str(e)); return False

    def get_unique_path(self, directory, filename):
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_name = f"{base} ({counter}){ext}"
            full = os.path.join(directory, new_name)
            if not os.path.exists(full): return full
            counter += 1

    def generate_export_content(self, filename, edits_map):
        path = os.path.join(self.project_data["base_folder"], filename)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f: raw = f.read()
        match = self.re_script.search(raw)
        clean = match.group(2).replace('\\"', '"')
        modified = clean

        if self.file_type_detected == "xml":
            rows_iter = list(self.re_row.finditer(clean))
            header_map = self.parse_row_cells(rows_iter[0].group(2))
            
            def row_sub(m):
                row_body = m.group(2)
                row_data = self.parse_row_cells(row_body)
                rid = row_data.get(0)
                if not rid: return m.group(0)
                
                new_body = ""
                last = 0
                curr = 0
                for cm in self.re_cell_capture.finditer(row_body):
                    new_body += row_body[last:cm.start()]
                    ft = cm.group(0)
                    im = self.re_attr_index.search(ft)
                    if im: curr = int(im.group(1)) - 1
                    
                    col = header_map.get(curr)
                    key = f"{rid}|{col}"
                    if key in edits_map:
                        # Uso escape() corrigido para \N
                        val = self.escape(edits_map[key])
                        if '<Data' in ft:
                            new_tag = re.sub(r'(<Data[^>]*>)(.*?)(</Data>)', lambda x: f"{x.group(1)}{val}{x.group(3)}", ft, flags=re.DOTALL)
                            new_body += new_tag
                        else: new_body += ft
                    else: new_body += ft
                    last = cm.end(); curr += 1
                new_body += row_body[last:]
                return f"{m.group(1)}{new_body}{m.group(3)}"
            modified = self.re_row.sub(row_sub, clean)

        elif self.file_type_detected == "text":
             k = f"{os.path.basename(filename)}|Content"
             if k in edits_map: 
                 # Uso escape() corrigido
                 modified = self.escape(edits_map[k])
        
        elif self.file_type_detected == "mindmap":
            state = {"i": 0}
            def rep_topic(m):
                txt = m.group(2)
                if txt == os.path.splitext(filename)[0]: return m.group(0)
                eid = f"Topic_{state['i']}"
                state['i'] += 1
                if eid in edits_map: 
                    # Uso escape() corrigido para \N
                    val = self.escape(edits_map[eid])
                    return f"{m.group(1)}{val}{m.group(3)}"
                return m.group(0)
            modified = self.re_topic.sub(rep_topic, clean)

        # Re-escapa aspas globais para o formato string do C#
        final_esc = modified.replace('"', '\\"')
        return self.re_script.sub(lambda m: f"{m.group(1)}{final_esc}{m.group(3)}", raw, count=1)

if __name__ == "__main__":
    root = tk.Tk()
    app = UnityDumpToolComplete(root)
    root.mainloop()