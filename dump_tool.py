import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import re
import os
import threading
import json
import glob
import gc

class UnityDumpToolFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("Unity Dump Tool V20 - Polished Edition")
        # AJUSTE 1: Tamanho de janela mais contido
        self.root.geometry("1024x700")

        # --- ESTILOS ---
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Segoe UI", 9))
        self.style.configure("TLabel", font=("Segoe UI", 9))
        self.style.configure("Bold.TLabel", font=("Segoe UI", 9, "bold"))
        self.style.configure("Success.TLabel", foreground="green", font=("Segoe UI", 9, "bold"))
        
        # --- ESTADO ---
        self.mode = None 
        self.project_data = {"base_folder": "", "files": {}}
        self.project_json_path = None
        
        # Dados Memória
        self.current_filename = None
        self.content_raw = None
        self.clean_xml = None
        self.entries = []
        self.current_edit_entry = None
        self.file_type_detected = None 

        # Regex
        self.re_script = re.compile(r'(1 string m_Script = ")([\s\S]*?)("\s*\n\s*1 string m_sourcePrefab|"\s*$)', re.MULTILINE)
        self.re_row = re.compile(r'(<Row[^>]*>)(.*?)(</Row>)', re.DOTALL)
        self.re_cell = re.compile(r'<Data\s+([^>]*?)>(.*?)</Data>', re.DOTALL)
        self.re_topic = re.compile(r'(<topic\b[^>]*?\btext=")([^"]*)(")', re.DOTALL)

        self.build_launcher()

    # =========================================================================
    # 1. LAUNCHER (INTERFACE INICIAL AJUSTADA)
    # =========================================================================
    def build_launcher(self):
        self.clear_window()
        
        # Frame Centralizado
        frame = ttk.Frame(self.root)
        frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ttk.Label(frame, text="Unity Dump Tool V20", font=("Segoe UI", 20, "bold")).pack(pady=(0, 20))
        
        # Botões lado a lado com padding reduzido
        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        # AJUSTE 2: Botões menos exagerados
        btn_single = ttk.Button(btn_frame, text="📄 MODO INDIVIDUAL", command=self.start_single_mode)
        btn_single.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=10)

        btn_proj = ttk.Button(btn_frame, text="🗂️ MODO PROJETO", command=self.start_project_mode)
        btn_proj.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=10)

        ttk.Label(frame, text="Selecione como deseja trabalhar", foreground="gray").pack(pady=(20, 0))

    def clear_window(self):
        for widget in self.root.winfo_children(): widget.destroy()

    # =========================================================================
    # 2. INTERFACE PRINCIPAL
    # =========================================================================
    def build_main_ui(self, is_project_mode):
        self.clear_window()
        
        # MENU
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        
        if is_project_mode:
            file_menu.add_command(label="Novo Projeto...", command=self.proj_new)
            file_menu.add_command(label="Abrir Projeto...", command=self.proj_load_json)
            file_menu.add_command(label="Salvar Projeto", command=self.proj_save_json)
            file_menu.add_separator()
            file_menu.add_command(label="Exportar Atual", command=self.proj_export_current)
            file_menu.add_command(label="Exportar TUDO", command=self.proj_export_batch)
        else:
            file_menu.add_command(label="Abrir Arquivo...", command=self.single_load_file)
            file_menu.add_command(label="Salvar...", command=self.single_save_file)

        file_menu.add_separator()
        file_menu.add_command(label="Voltar ao Início", command=self.build_launcher)

        # LAYOUT
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ESQUERDA (Arquivos - Só no modo Projeto)
        if is_project_mode:
            self.frame_files = ttk.LabelFrame(main_paned, text="Arquivos", padding=2, width=200)
            main_paned.add(self.frame_files, weight=1)
            self.list_files = tk.Listbox(self.frame_files, font=("Segoe UI", 9), exportselection=False)
            self.list_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(self.frame_files, command=self.list_files.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
            self.list_files.config(yscrollcommand=sb.set)
            self.list_files.bind('<<ListboxSelect>>', self.on_file_list_select)

        # CENTRO (IDs)
        frame_ids = ttk.LabelFrame(main_paned, text="Strings / IDs", padding=2, width=250)
        main_paned.add(frame_ids, weight=1)

        filter_frame = ttk.Frame(frame_ids); filter_frame.pack(fill=tk.X, pady=2)
        ttk.Label(filter_frame, text="Buscar:").pack(side=tk.LEFT)
        self.entry_filter = ttk.Entry(filter_frame)
        self.entry_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.entry_filter.bind('<KeyRelease>', self.filter_ids_list)

        self.btn_mark = ttk.Button(frame_ids, text="✅ Marcar/Desmarcar", command=self.toggle_mark)
        self.btn_mark.pack(fill=tk.X, pady=2)
        self.lbl_progress = ttk.Label(frame_ids, text="0 / 0", style="Success.TLabel")
        self.lbl_progress.pack(anchor="w")

        self.list_ids = tk.Listbox(frame_ids, font=("Consolas", 10), exportselection=False)
        self.list_ids.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb2 = ttk.Scrollbar(frame_ids, command=self.list_ids.yview); sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_ids.config(yscrollcommand=sb2.set)
        self.list_ids.bind('<<ListboxSelect>>', self.on_id_select)
        self.list_ids.bind('<space>', lambda e: self.toggle_mark())

        # DIREITA (Editor)
        frame_editor = ttk.LabelFrame(main_paned, text="Editor", padding=2)
        main_paned.add(frame_editor, weight=3)
        
        self.txt_editor = scrolledtext.ScrolledText(frame_editor, font=("Consolas", 11), wrap=tk.WORD, undo=True)
        self.txt_editor.pack(fill=tk.BOTH, expand=True)
        self.txt_editor.bind('<KeyRelease>', self.on_text_change)
        self.setup_tags()

        self.status_bar = ttk.Label(self.root, text="Pronto.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_tags(self):
        self.txt_editor.tag_config("structure", foreground="blue")
        self.txt_editor.tag_config("linebreak", foreground="red", background="#eeeeee")
        self.txt_editor.tag_config("command", foreground="purple")
        self.txt_editor.tag_config("entity", foreground="#8e44ad")
        self.txt_editor.tag_config("richtext", foreground="#d35400")
        self.txt_editor.tag_config("search_match", background="yellow", foreground="black")

    def start_single_mode(self):
        self.mode = "single"
        self.build_main_ui(False)
        self.single_load_file()

    def start_project_mode(self):
        self.mode = "project"
        self.build_main_ui(True)

    # =========================================================================
    # 3. LÓGICA CENTRAL DE ARQUIVOS
    # =========================================================================
    def escape_linebreaks(self, text):
        return text.replace('\n', '\\n').replace('\r', '\\r')

    def unescape_linebreaks(self, text):
        return text.replace('\\n', '\n').replace('\\r', '\r')

    def load_file_content(self, filename):
        path = os.path.join(self.project_data["base_folder"], filename)
        if not os.path.exists(path): return
        
        self.entries = []; self.current_edit_entry = None
        self.txt_editor.delete(1.0, tk.END); self.list_ids.delete(0, tk.END)
        gc.collect()

        try:
            with open(path, 'r', encoding='utf-8') as f: raw = f.read()
        except:
            with open(path, 'r', encoding='cp1252', errors='ignore') as f: raw = f.read()

        match = self.re_script.search(raw)
        if not match:
            messagebox.showerror("Erro", "Arquivo inválido.")
            return

        self.current_filename = filename
        self.content_raw = raw
        self.clean_xml = match.group(2).replace('\\"', '"')

        if '<topic' in self.clean_xml and 'text="' in self.clean_xml: self.file_type_detected = "mindmap"
        elif '<Row' in self.clean_xml and '<Data' in self.clean_xml: self.file_type_detected = "xml"
        else: self.file_type_detected = "text"

        saved_edits = {}
        saved_marks = set()
        if self.mode == "project":
            info = self.project_data["files"].get(filename, {})
            saved_edits = info.get("edits", {})
            saved_marks = set(info.get("marked", []))

        if self.file_type_detected == "xml":
            rows = self.re_row.finditer(self.clean_xml)
            for i, row in enumerate(rows):
                cells = list(self.re_cell.finditer(row.group(2)))
                if len(cells) >= 2:
                    id_txt = cells[0].group(2).strip()
                    val_txt = cells[1].group(2)
                    if "XML_id" in id_txt or "displayName" in val_txt: continue
                    if val_txt.strip().startswith("interface_"): continue
                    
                    curr = saved_edits.get(id_txt, val_txt)
                    self.entries.append({
                        'id': id_txt, 'original': self.escape_linebreaks(val_txt),
                        'current': self.escape_linebreaks(curr), 'marked': id_txt in saved_marks
                    })

        elif self.file_type_detected == "mindmap":
            matches = list(self.re_topic.finditer(self.clean_xml))
            for i, m in enumerate(matches):
                txt = m.group(2)
                if txt == os.path.splitext(filename)[0]: continue
                eid = f"Topic_{i}"
                curr = saved_edits.get(eid, txt)
                self.entries.append({
                    'id': eid, 'original': self.escape_linebreaks(txt),
                    'current': self.escape_linebreaks(curr), 'marked': eid in saved_marks
                })

        elif self.file_type_detected == "text":
            fid = os.path.basename(filename)
            txt = self.clean_xml
            curr = saved_edits.get(fid, txt)
            self.entries.append({
                'id': fid, 'original': self.escape_linebreaks(txt),
                'current': self.escape_linebreaks(curr), 'marked': fid in saved_marks
            })

        self.populate_ids_list()
        self.status_bar.config(text=f"{filename} ({self.file_type_detected})")

    def populate_ids_list(self):
        self.list_ids.delete(0, tk.END)
        query = self.entry_filter.get().lower()
        for entry in self.entries:
            if query and (query not in entry['id'].lower() and query not in entry['current'].lower()): continue
            self.list_ids.insert(tk.END, entry['id'])
            if entry['marked']: self.list_ids.itemconfig(self.list_ids.size()-1, {'bg': '#d4fcd4', 'fg': 'black'})
            elif entry['current'] != entry['original']: self.list_ids.itemconfig(self.list_ids.size()-1, {'bg': '#fffacd', 'fg': 'black'})
        self.update_progress_label()

    def filter_ids_list(self, event=None): self.populate_ids_list()

    def on_id_select(self, event):
        sel = self.list_ids.curselection()
        if not sel: return
        sel_id = self.list_ids.get(sel[0])
        for entry in self.entries:
            if entry['id'] == sel_id:
                self.current_edit_entry = entry
                self.txt_editor.delete(1.0, tk.END)
                self.txt_editor.insert(tk.END, entry['current'])
                self.apply_highlighting()
                return

    def on_text_change(self, event=None):
        if not self.current_edit_entry: return
        txt = self.txt_editor.get(1.0, "end-1c")
        if self.current_edit_entry['current'] != txt:
            self.current_edit_entry['current'] = txt
            if not self.current_edit_entry['marked']:
                self.current_edit_entry['marked'] = True
                self.refresh_entry_in_list()
        self.apply_highlighting()

    def toggle_mark(self):
        if not self.current_edit_entry: return
        self.current_edit_entry['marked'] = not self.current_edit_entry['marked']
        self.refresh_entry_in_list()
        self.update_progress_label()

    def refresh_entry_in_list(self):
        sel = self.list_ids.curselection()
        if not sel: return
        e = self.current_edit_entry
        color = '#d4fcd4' if e['marked'] else '#fffacd' if e['current']!=e['original'] else 'white'
        self.list_ids.itemconfig(sel[0], {'bg': color})

    def update_progress_label(self):
        total = len(self.entries)
        done = sum(1 for e in self.entries if e['marked'])
        self.lbl_progress.config(text=f"Progresso: {done} / {total}")

    def apply_highlighting(self):
        for t in ["structure", "linebreak", "command", "entity", "richtext", "search_match"]:
            self.txt_editor.tag_remove(t, "1.0", tk.END)
        self.highlight_pattern(r'&#10;|\\n|\\r|\\N', "linebreak")
        self.highlight_pattern(r'&lt;.*?&gt;', "structure")
        self.highlight_pattern(r'&lt;/?(b|i|u|size|color).*?&gt;', "richtext")
        self.highlight_pattern(r'&quot;', "entity")
        self.highlight_pattern(r'\[.*?\]', "command")
        q = self.entry_filter.get().strip()
        if q and len(q)>1: self.highlight_pattern(re.escape(q), "search_match", True)

    def highlight_pattern(self, pattern, tag, nocase=False):
        start = "1.0"
        while True:
            pos = self.txt_editor.search(pattern, start, stopindex=tk.END, regexp=True, nocase=nocase)
            if not pos: break
            txt = self.txt_editor.get(pos, tk.END)
            m = re.match(pattern, txt, re.IGNORECASE if nocase else 0)
            if not m: start = f"{pos}+1c"; continue
            end = f"{pos}+{len(m.group(0))}c"
            self.txt_editor.tag_add(tag, pos, end)
            start = end

    # =========================================================================
    # 4. SALVAMENTO ROBUSTO (CORREÇÃO CRÍTICA DO FLUXO)
    # =========================================================================
    def generate_content_to_save(self, filename, edits_map):
        # 1. Lê o arquivo ORIGINAL do disco novamente
        path = os.path.join(self.project_data["base_folder"], filename)
        try:
            with open(path, 'r', encoding='utf-8') as f: raw = f.read()
        except:
            with open(path, 'r', encoding='cp1252', errors='ignore') as f: raw = f.read()

        match = self.re_script.search(raw)
        clean_xml = match.group(2).replace('\\"', '"')
        
        # Redetecta
        ftype = "text"
        if '<topic' in clean_xml and 'text="' in clean_xml: ftype = "mindmap"
        elif '<Row' in clean_xml and '<Data' in clean_xml: ftype = "xml"
        
        modified_inner = clean_xml

        # Substituição
        if ftype == "xml":
            def rep(m):
                row = m.group(2)
                cells = list(self.re_cell.finditer(row))
                if len(cells) >= 2:
                    id_txt = cells[0].group(2).strip()
                    if id_txt in edits_map:
                        val = edits_map[id_txt].replace('\n', '\\n').replace('\r', '\\r') # Fix V19
                        c = cells[1]
                        new_c = f"<Data {c.group(1)}>{val}</Data>"
                        return m.group(1) + row.replace(c.group(0), new_c) + m.group(3)
                return m.group(0)
            modified_inner = self.re_row.sub(rep, clean_xml)

        elif ftype == "mindmap":
            state = {"i": 0}
            def rep_topic(m):
                txt = m.group(2)
                if txt == os.path.splitext(filename)[0]: return m.group(0)
                eid = f"Topic_{state['i']}"
                state['i'] += 1
                if eid in edits_map:
                    val = edits_map[eid].replace('\n', '\\n').replace('\r', '\\r') # Fix V19
                    return f"{m.group(1)}{val}{m.group(3)}"
                return m.group(0)
            modified_inner = self.re_topic.sub(rep_topic, clean_xml)

        elif ftype == "text":
            fid = os.path.basename(filename)
            if fid in edits_map:
                val = edits_map[fid].replace('\n', '\\n').replace('\r', '\\r') # Fix V19
                modified_inner = val

        final_esc = modified_inner.replace('"', '\\"')
        return self.re_script.sub(lambda m: f"{m.group(1)}{final_esc}{m.group(3)}", raw, count=1)

    def get_unique_path(self, directory, filename):
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_name = f"{base} ({counter}){ext}"
            full = os.path.join(directory, new_name)
            if not os.path.exists(full): return full
            counter += 1

    def save_logic_handler(self, target_dir, filename, content):
        full_path = os.path.join(target_dir, filename)
        
        # AJUSTE CRÍTICO 3: Verificação real e opções claras
        if os.path.exists(full_path):
            msg = f"O arquivo '{filename}' já existe.\n\nO que deseja fazer?"
            # askyesnocancel: True=Sim, False=Não, None=Cancelar
            resp = messagebox.askyesnocancel("Arquivo Duplicado", msg, detail="Sim = Substituir\nNão = Renomear (criar cópia)\nCancelar = Abortar")
            
            if resp is None: # Cancelar
                return False 
            elif resp is False: # Não -> Renomear
                full_path = self.get_unique_path(target_dir, filename)
            # else (True) -> Substituir (mantém full_path)

        try:
            with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
            return True
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return False

    def single_save_file(self):
        if not self.current_filename: return
        edits = {e['id']: self.unescape_linebreaks(e['current']) for e in self.entries}
        content = self.generate_content_to_save(self.current_filename, edits)
        
        initial = self.project_data["base_folder"]
        target = filedialog.askdirectory(initialdir=initial, title="Salvar Onde?")
        if not target: return
        
        if self.save_logic_handler(target, self.current_filename, content):
            messagebox.showinfo("Sucesso", "Arquivo salvo.")

    # LÓGICA DE PROJETO
    def single_load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Txt", "*.txt")])
        if not path: return
        self.project_data["base_folder"] = os.path.dirname(path)
        self.load_file_content(os.path.basename(path))

    def proj_new(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.project_data = {"base_folder": folder, "files": {}}
        self.refresh_list()

    def refresh_list(self):
        self.list_files.delete(0, tk.END)
        files = glob.glob(os.path.join(self.project_data["base_folder"], "*.txt"))
        for p in files:
            f = os.path.basename(p)
            if f not in self.project_data["files"]: self.project_data["files"][f]={"edits":{}, "marked":[]}
            self.list_files.insert(tk.END, f)

    def on_file_list_select(self, event):
        sel = self.list_files.curselection()
        if not sel: return
        fname = self.list_files.get(sel[0])
        if fname == self.current_filename: return
        self.sync_project()
        self.load_file_content(fname)

    def sync_project(self):
        if self.mode!="project" or not self.current_filename: return
        edits, marks = {}, []
        for e in self.entries:
            if e['current']!=e['original']: edits[e['id']] = self.unescape_linebreaks(e['current'])
            if e['marked']: marks.append(e['id'])
        self.project_data["files"][self.current_filename] = {"edits": edits, "marked": marks}
        
        # Pinta lista
        try:
            idx = self.list_files.get(0, tk.END).index(self.current_filename)
            color = '#e6ffe6' if (edits or marks) else 'white'
            self.list_files.itemconfig(idx, {'bg': color})
        except: pass

    def proj_save_json(self):
        self.sync_project()
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if f:
            with open(f, 'w', encoding='utf-8') as file: json.dump(self.project_data, file, indent=4)
            messagebox.showinfo("Salvo", "Projeto salvo.")

    def proj_load_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if f:
            with open(f, 'r') as file: self.project_data = json.load(file)
            self.refresh_list()
            # Repinta itens modificados
            for i, fname in enumerate(self.list_files.get(0, tk.END)):
                dat = self.project_data["files"].get(fname, {})
                if dat.get("edits") or dat.get("marked"):
                    self.list_files.itemconfig(i, {'bg': '#e6ffe6'})

    def proj_export_current(self): self.single_save_file()

    def proj_export_batch(self):
        self.sync_project()
        target = filedialog.askdirectory()
        if not target: return
        count = 0
        for fname, data in self.project_data["files"].items():
            if data.get("edits"):
                cnt = self.generate_content_to_save(fname, data["edits"])
                if self.save_logic_handler(target, fname, cnt): count += 1
        messagebox.showinfo("Batch", f"{count} arquivos exportados.")

if __name__ == "__main__":
    root = tk.Tk()
    app = UnityDumpToolFinal(root)
    root.mainloop()