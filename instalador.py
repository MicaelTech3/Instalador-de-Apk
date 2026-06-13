import os
import sys
import subprocess
import threading
import queue
import urllib.request
import zipfile
import re
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Configuração de Aparência (Design Premium Dark Mode)
BG_MAIN = "#121214"        # Cor de fundo principal
BG_CARD = "#1a1a24"        # Cor de fundo dos painéis/cards
BG_ENTRY = "#252530"       # Cor de fundo dos campos de entrada
BG_LIST = "#1d1d28"        # Cor de fundo das listas
FG_TEXT = "#e0e0e0"        # Cor de texto padrão
FG_MUTED = "#88889a"       # Cor de texto secundário/silenciado
ACCENT_PURPLE = "#7c4dff"  # Cor de destaque roxo
ACCENT_GREEN = "#00e676"   # Cor verde (OK/Conectado)
ACCENT_RED = "#ff3d00"     # Cor vermelha (Desconectado/Erro)
ACCENT_BLUE = "#00b0ff"    # Cor azul (Ações secundárias)

class ADBClient:
    """Cliente para execução de comandos ADB."""
    def __init__(self, adb_path):
        self.adb_path = adb_path
        self.device = None  # ID do dispositivo selecionado
        
    def run_cmd(self, args):
        """Executa um comando ADB e retorna (stdout, stderr, returncode)."""
        if not os.path.exists(self.adb_path):
            return "", "ADB não encontrado no caminho especificado.", -1
            
        cmd = [self.adb_path]
        if self.device:
            cmd.extend(["-s", self.device])
        cmd.extend(args)
        
        # Evita a abertura de janelas CMD no Windows ao executar subprocessos
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
                startupinfo=startupinfo,
                timeout=45
            )
            return res.stdout, res.stderr, res.returncode
        except subprocess.TimeoutExpired:
            return "", "Erro: O comando ADB expirou.", -1
        except Exception as e:
            return "", f"Erro ao executar comando: {str(e)}", -1

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Instalador de APK & Companheiro ADB")
        self.root.geometry("1000x700")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(900, 600)
        
        # Localização do ADB
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.adb_dir = os.path.join(script_dir, "platform-tools")
        self.adb_path = os.path.join(self.adb_dir, "adb.exe" if os.name == 'nt' else "adb")
        self.adb_client = ADBClient(self.adb_path)
        
        # Variáveis do App
        self.connected_devices = []
        self.selected_apk_path = tk.StringVar(value="")
        self.install_replace_var = tk.BooleanVar(value=True)
        self.install_grant_var = tk.BooleanVar(value=True)
        self.show_system_apps_var = tk.BooleanVar(value=False)
        
        # Lista de pacotes obtidos (para cache/filtro local)
        self.all_installed_packages = []
        
        # Fila para comunicação entre threads
        self.gui_queue = queue.Queue()
        
        # Configurar Estilos do Tkinter
        self.setup_styles()
        
        # Montar a interface principal
        self.build_ui()
        
        # Verificar se o ADB já está presente; se não, inicia o download
        self.check_or_download_adb()
        
        # Iniciar monitor de tarefas/mensagens em background
        self.process_queue_loop()
        
        # Iniciar monitor de dispositivos conectados
        self.start_device_monitor()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurações globais
        style.configure(".", background=BG_MAIN, foreground=FG_TEXT, fieldbackground=BG_ENTRY)
        
        # Customização de Notebooks (Abas) e Progressbars
        style.configure("TProgressbar", thickness=15, troughcolor=BG_ENTRY, background=ACCENT_PURPLE)
        style.configure("TCheckbutton", background=BG_CARD, foreground=FG_TEXT, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[('active', BG_CARD)], foreground=[('active', FG_TEXT)])
        
        style.configure("TCombobox", fieldbackground=BG_ENTRY, background=BG_CARD, foreground=FG_TEXT, bordercolor=BG_ENTRY, arrowcolor=FG_TEXT)
        style.map("TCombobox", fieldbackground=[('readonly', BG_ENTRY)], selectbackground=[('readonly', ACCENT_PURPLE)], selectforeground=[('readonly', '#ffffff')])

    def build_ui(self):
        # Frame Principal com espaçamento
        self.main_container = tk.Frame(self.root, bg=BG_MAIN)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # --- PAINEL SUPERIOR: STATUS & CONEXÃO ---
        self.top_bar = tk.Frame(self.main_container, bg=BG_CARD, bd=1, relief="flat", highlightbackground="#30303f", highlightthickness=1)
        self.top_bar.pack(fill="x", side="top", pady=(0, 10))
        
        # Indicador Visual "OK" / Status
        self.status_dot = tk.Label(self.top_bar, text="●", fg=ACCENT_RED, bg=BG_CARD, font=("Segoe UI", 18))
        self.status_dot.pack(side="left", padx=(15, 5))
        
        self.status_label = tk.Label(self.top_bar, text="Nenhum dispositivo encontrado", fg=FG_TEXT, bg=BG_CARD, font=("Segoe UI", 11, "bold"))
        self.status_label.pack(side="left", padx=5, pady=12)
        
        # Combobox para múltiplos dispositivos
        tk.Label(self.top_bar, text="Aparelho:", fg=FG_MUTED, bg=BG_CARD, font=("Segoe UI", 10)).pack(side="left", padx=(30, 5))
        self.device_combo = ttk.Combobox(self.top_bar, state="readonly", width=25, postcommand=self.refresh_devices_combo)
        self.device_combo.pack(side="left", padx=5, pady=10)
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_selected)
        
        # Botão Atualizar Conexão
        self.btn_refresh = self.create_flat_button(
            self.top_bar, "🔄 Atualizar", self.refresh_devices_now, 
            bg_color="#303040", fg_color=FG_TEXT, hover_color="#454555", font=("Segoe UI", 9, "bold")
        )
        self.btn_refresh.pack(side="right", padx=15, pady=8)
        
        # --- DIVISÃO CENTRAL (GRID 2 COLUNAS) ---
        self.grid_container = tk.Frame(self.main_container, bg=BG_MAIN)
        self.grid_container.pack(fill="both", expand=True)
        self.grid_container.grid_columnconfigure(0, weight=1, uniform="equal")
        self.grid_container.grid_columnconfigure(1, weight=1, uniform="equal")
        self.grid_container.grid_rowconfigure(0, weight=1)
        
        # --- COLUNA ESQUERDA: INSTALADOR APK & LAUNCHER ---
        self.left_column = tk.Frame(self.grid_container, bg=BG_MAIN)
        self.left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        # Card 1: Instalação de APK
        self.apk_card = tk.LabelFrame(self.left_column, text=" Instalar APK ", fg="#ffffff", bg=BG_CARD, font=("Segoe UI", 11, "bold"), bd=1, relief="flat", highlightbackground="#30303f", highlightthickness=1)
        self.apk_card.pack(fill="both", expand=True, pady=(0, 10))
        
        # Área de Arquivo APK
        self.apk_select_frame = tk.Frame(self.apk_card, bg=BG_CARD)
        self.apk_select_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        self.btn_choose_apk = self.create_flat_button(
            self.apk_select_frame, "📁 Escolher APK...", self.choose_apk_file,
            bg_color=ACCENT_BLUE, fg_color="#ffffff", hover_color="#33c1ff"
        )
        self.btn_choose_apk.pack(side="left", padx=(0, 10))
        
        self.apk_label = tk.Label(self.apk_select_frame, text="Nenhum arquivo APK selecionado", fg=FG_MUTED, bg=BG_CARD, font=("Segoe UI", 9), anchor="w")
        self.apk_label.pack(side="left", fill="x", expand=True)
        
        # Opções de Instalação (Checkboxes)
        self.chk_replace = ttk.Checkbutton(self.apk_card, text="Substituir app se já existir (-r)", variable=self.install_replace_var)
        self.chk_replace.pack(anchor="w", padx=15, pady=2)
        
        self.chk_grant = ttk.Checkbutton(self.apk_card, text="Conceder todas permissões automaticamente (-g)", variable=self.install_grant_var)
        self.chk_grant.pack(anchor="w", padx=15, pady=2)
        
        # Botão Grande de Instalação
        self.btn_install = self.create_flat_button(
            self.apk_card, "⚡ INSTALAR APK NO DISPOSITIVO", self.install_apk_now,
            bg_color=ACCENT_PURPLE, fg_color="#ffffff", hover_color="#996cff", font=("Segoe UI", 10, "bold")
        )
        self.btn_install.pack(fill="x", padx=15, pady=(20, 15))
        
        # Card 2: Controles de Launcher
        self.launcher_card = tk.LabelFrame(self.left_column, text=" Controles de Launcher (TV / Android) ", fg="#ffffff", bg=BG_CARD, font=("Segoe UI", 11, "bold"), bd=1, relief="flat", highlightbackground="#30303f", highlightthickness=1)
        self.launcher_card.pack(fill="both", expand=True)
        
        # Mostrar Launcher Atual
        self.launcher_status_frame = tk.Frame(self.launcher_card, bg=BG_CARD)
        self.launcher_status_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        tk.Label(self.launcher_status_frame, text="Launcher Padrão Atual:", fg=FG_MUTED, bg=BG_CARD, font=("Segoe UI", 9)).pack(anchor="w")
        self.launcher_current_lbl = tk.Label(self.launcher_status_frame, text="Desconhecido (Atualize status)", fg="#ffffff", bg=BG_CARD, font=("Segoe UI", 10, "bold"), anchor="w", wraplength=400, justify="left")
        self.launcher_current_lbl.pack(fill="x", pady=2)
        
        # Combobox para selecionar launcher
        tk.Label(self.launcher_card, text="Selecionar Launcher para Ações:", fg=FG_MUTED, bg=BG_CARD, font=("Segoe UI", 9)).pack(anchor="w", padx=15, pady=(10, 2))
        
        self.launcher_combo_frame = tk.Frame(self.launcher_card, bg=BG_CARD)
        self.launcher_combo_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.launcher_combo = ttk.Combobox(self.launcher_combo_frame, state="readonly")
        self.launcher_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_refresh_launchers = self.create_flat_button(
            self.launcher_combo_frame, "🔍 Procurar Launchers", self.query_device_launchers,
            bg_color="#303040", fg_color=FG_TEXT, hover_color="#454555", font=("Segoe UI", 9)
        )
        self.btn_refresh_launchers.pack(side="right")
        
        # Botões de Ações de Launcher
        self.launcher_actions_frame = tk.Frame(self.launcher_card, bg=BG_CARD)
        self.launcher_actions_frame.pack(fill="x", padx=15, pady=5)
        
        self.btn_set_launcher = self.create_flat_button(
            self.launcher_actions_frame, "🏠 Definir como Padrão", self.set_selected_launcher_default,
            bg_color=ACCENT_BLUE, fg_color="#ffffff", hover_color="#33c1ff", font=("Segoe UI", 9, "bold")
        )
        self.btn_set_launcher.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_clear_launcher = self.create_flat_button(
            self.launcher_actions_frame, "🧹 Limpar Padrão", self.clear_launcher_default,
            bg_color="#42424d", fg_color=FG_TEXT, hover_color="#555566", font=("Segoe UI", 9, "bold")
        )
        self.btn_clear_launcher.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        self.btn_picker_launcher = self.create_flat_button(
            self.launcher_card, "📺 Abrir Seletor de Launcher no Aparelho", self.open_launcher_picker_device,
            bg_color="#303040", fg_color=FG_TEXT, hover_color="#454555", font=("Segoe UI", 9)
        )
        self.btn_picker_launcher.pack(fill="x", padx=15, pady=(10, 15))
        
        # --- COLUNA DIREITA: GERENCIADOR DE APPS ---
        self.right_column = tk.Frame(self.grid_container, bg=BG_MAIN)
        self.right_column.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        self.apps_card = tk.LabelFrame(self.right_column, text=" Gerenciador de Aplicativos ", fg="#ffffff", bg=BG_CARD, font=("Segoe UI", 11, "bold"), bd=1, relief="flat", highlightbackground="#30303f", highlightthickness=1)
        self.apps_card.pack(fill="both", expand=True)
        
        # Filtro de Busca
        self.search_frame = tk.Frame(self.apps_card, bg=BG_CARD)
        self.search_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_app_list)
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, bg=BG_ENTRY, fg=FG_TEXT, insertbackground=FG_TEXT, bd=0, font=("Segoe UI", 10))
        self.search_entry.pack(fill="x", side="left", expand=True, ipady=6, padx=(0, 10))
        self.placeholder_text = "🔍 Filtrar apps instalados..."
        self.search_entry.insert(0, self.placeholder_text)
        self.search_entry.bind("<FocusIn>", self.on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self.on_search_focus_out)
        
        self.chk_system = ttk.Checkbutton(self.apps_card, text="Exibir Apps do Sistema", variable=self.show_system_apps_var, command=self.load_installed_apps_thread)
        self.chk_system.pack(anchor="w", padx=15, pady=2)
        
        # Listbox de Aplicativos
        self.list_frame = tk.Frame(self.apps_card, bg=BG_CARD)
        self.list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.apps_listbox = tk.Listbox(
            self.list_frame, bg=BG_LIST, fg=FG_TEXT, bd=0, 
            highlightthickness=0, font=("Consolas", 10), 
            selectbackground=ACCENT_PURPLE, selectforeground="#ffffff"
        )
        self.apps_listbox.pack(side="left", fill="both", expand=True)
        
        self.list_scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.apps_listbox.yview)
        self.list_scrollbar.pack(side="right", fill="y")
        self.apps_listbox.config(yscrollcommand=self.list_scrollbar.set)
        
        # Botões de Ação para App Selecionado
        self.app_actions_grid = tk.Frame(self.apps_card, bg=BG_CARD)
        self.app_actions_grid.pack(fill="x", padx=15, pady=(10, 15))
        self.app_actions_grid.grid_columnconfigure(0, weight=1)
        self.app_actions_grid.grid_columnconfigure(1, weight=1)
        self.app_actions_grid.grid_rowconfigure(0, weight=1)
        self.app_actions_grid.grid_rowconfigure(1, weight=1)
        
        self.btn_run_app = self.create_flat_button(
            self.app_actions_grid, "🚀 Iniciar App", self.launch_selected_app,
            bg_color=ACCENT_GREEN, fg_color="#121214", hover_color="#53ff9d", font=("Segoe UI", 9, "bold")
        )
        self.btn_run_app.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 4))
        
        self.btn_stop_app = self.create_flat_button(
            self.app_actions_grid, "⏹️ Forçar Parada", self.force_stop_selected_app,
            bg_color="#42424d", fg_color=FG_TEXT, hover_color="#555566", font=("Segoe UI", 9)
        )
        self.btn_stop_app.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 4))
        
        self.btn_clear_app = self.create_flat_button(
            self.app_actions_grid, "🧹 Limpar Dados", self.clear_selected_app_data,
            bg_color="#42424d", fg_color=FG_TEXT, hover_color="#555566", font=("Segoe UI", 9)
        )
        self.btn_clear_app.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(4, 0))
        
        self.btn_uninstall_app = self.create_flat_button(
            self.app_actions_grid, "🗑️ Desinstalar App", self.uninstall_selected_app,
            bg_color=ACCENT_RED, fg_color="#ffffff", hover_color="#ff6633", font=("Segoe UI", 9, "bold")
        )
        self.btn_uninstall_app.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(4, 0))
        
        # --- PAINEL INFERIOR: CONSOLE / LOGS ---
        self.console_card = tk.LabelFrame(self.main_container, text=" Log do Sistema / Terminal ADB ", fg="#ffffff", bg=BG_CARD, font=("Segoe UI", 10, "bold"), bd=1, relief="flat", highlightbackground="#30303f", highlightthickness=1)
        self.console_card.pack(fill="x", side="bottom", pady=(10, 0))
        
        self.console_frame = tk.Frame(self.console_card, bg=BG_CARD)
        self.console_frame.pack(fill="x", padx=15, pady=(10, 10))
        
        self.console_txt = tk.Text(
            self.console_frame, bg="#0f0f15", fg="#54ff8e", bd=0, 
            height=6, font=("Consolas", 9), wrap="word", 
            insertbackground="#54ff8e"
        )
        self.console_txt.pack(side="left", fill="x", expand=True)
        self.console_txt.config(state="disabled")
        
        self.console_scrollbar = ttk.Scrollbar(self.console_frame, orient="vertical", command=self.console_txt.yview)
        self.console_scrollbar.pack(side="right", fill="y")
        self.console_txt.config(yscrollcommand=self.console_scrollbar.set)
        
        self.console_actions = tk.Frame(self.console_card, bg=BG_CARD)
        self.console_actions.pack(fill="x", padx=15, pady=(0, 10))
        
        self.btn_clear_logs = self.create_flat_button(
            self.console_actions, "Limpar Logs", self.clear_console_logs,
            bg_color="#303040", fg_color=FG_TEXT, hover_color="#454555", font=("Segoe UI", 8)
        )
        self.btn_clear_logs.pack(side="right")
        
    def create_flat_button(self, parent, text, command, bg_color, fg_color, hover_color, font=("Segoe UI", 10), **kwargs):
        """Helper para criar botões com hover e visual moderno."""
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            activebackground=hover_color,
            activeforeground=fg_color,
            font=font,
            bd=0,
            padx=12,
            pady=6,
            relief="flat",
            cursor="hand2",
            **kwargs
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_color))
        return btn

    def log(self, message):
        """Imprime mensagem no console gráfico do app."""
        timestamp = time.strftime("[%H:%M:%S] ")
        self.console_txt.config(state="normal")
        self.console_txt.insert(tk.END, f"{timestamp}{message}\n")
        self.console_txt.see(tk.END)
        self.console_txt.config(state="disabled")

    # --- MONITOR DE DISPOSITIVOS ---
    def start_device_monitor(self):
        """Inicia thread para checar periodicamente os aparelhos conectados."""
        def monitor_loop():
            # Primeira checagem imediata
            self.check_connected_devices()
            while True:
                time.sleep(4)
                # Verifica a conexão em background
                self.check_connected_devices()
        
        t = threading.Thread(target=monitor_loop, daemon=True)
        t.start()
        
    def check_connected_devices(self):
        """Executa 'adb devices' e identifica mudanças na conexão."""
        if not os.path.exists(self.adb_path):
            return
            
        # Executa comando direto para economizar self.adb_client.device temporariamente
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
        try:
            res = subprocess.run(
                [self.adb_path, "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
                startupinfo=startupinfo,
                timeout=5
            )
            stdout = res.stdout
        except Exception:
            return
            
        lines = stdout.splitlines()
        devices = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
                
        # Envia atualização para a thread GUI se houver mudanças
        if devices != self.connected_devices:
            self.gui_queue.put(("devices_changed", devices))

    def handle_devices_changed(self, new_devices):
        old_devices = self.connected_devices
        self.connected_devices = new_devices
        
        # Atualiza a combobox
        self.refresh_devices_combo()
        
        # Se um dispositivo padrão desconectou ou um novo conectou
        if not new_devices:
            self.adb_client.device = None
            self.status_dot.config(fg=ACCENT_RED)
            self.status_label.config(text="Nenhum dispositivo encontrado")
            self.launcher_current_lbl.config(text="Desconectado", fg=FG_MUTED)
            self.clear_app_listbox()
            self.log("Dispositivo desconectado.")
        else:
            # Seleciona o primeiro por padrão se nenhum estiver selecionado
            current_sel = self.device_combo.get()
            if not current_sel or current_sel not in new_devices:
                self.device_combo.set(new_devices[0])
                self.adb_client.device = new_devices[0]
                
            self.status_dot.config(fg=ACCENT_GREEN)
            self.status_label.config(text=f"Dispositivo OK ({self.adb_client.device})")
            
            # Se for uma nova conexão, notifica e puxa dados
            newly_added = set(new_devices) - set(old_devices)
            if newly_added:
                self.log(f"Dispositivo conectado: {self.adb_client.device}")
                self.load_installed_apps_thread()
                self.update_launcher_status()

    def refresh_devices_combo(self):
        self.device_combo['values'] = self.connected_devices
        if self.connected_devices:
            if not self.device_combo.get() or self.device_combo.get() not in self.connected_devices:
                self.device_combo.set(self.connected_devices[0])
                self.adb_client.device = self.connected_devices[0]
        else:
            self.device_combo.set("")
            self.adb_client.device = None

    def on_device_selected(self, event):
        selected = self.device_combo.get()
        if selected:
            self.adb_client.device = selected
            self.status_dot.config(fg=ACCENT_GREEN)
            self.status_label.config(text=f"Dispositivo OK ({selected})")
            self.log(f"Dispositivo selecionado: {selected}")
            self.load_installed_apps_thread()
            self.update_launcher_status()

    def refresh_devices_now(self):
        self.log("Buscando dispositivos conectados...")
        self.check_connected_devices()

    # --- INSTALAÇÃO DE APK ---
    def choose_apk_file(self):
        filepath = filedialog.askopenfilename(
            title="Escolher Arquivo APK",
            filetypes=[("Arquivos APK", "*.apk"), ("Todos arquivos", "*.*")]
        )
        if filepath:
            self.selected_apk_path.set(filepath)
            # Exibe o nome do arquivo encurtado se necessário
            filename = os.path.basename(filepath)
            if len(filename) > 35:
                filename = filename[:32] + "..."
            self.apk_label.config(text=filename, fg=FG_TEXT)
            self.log(f"APK selecionado: {filepath}")

    def install_apk_now(self):
        apk = self.selected_apk_path.get()
        if not apk:
            messagebox.showwarning("Nenhum APK", "Por favor, selecione um arquivo APK primeiro.")
            return
        if not self.adb_client.device:
            messagebox.showerror("Sem Dispositivo", "Nenhum dispositivo conectado para instalar.")
            return
            
        # Desabilita botão de instalar para evitar duplo clique
        self.btn_install.config(state="disabled", text="INSTALANDO... AGUARDE")
        self.log(f"Instalando APK: {os.path.basename(apk)}...")
        
        def run_install():
            args = ["install"]
            if self.install_replace_var.get():
                args.append("-r")
            if self.install_grant_var.get():
                args.append("-g")
            args.append(apk)
            
            stdout, stderr, code = self.adb_client.run_cmd(args)
            self.gui_queue.put(("install_result", (code, stdout, stderr)))
            
        threading.Thread(target=run_install, daemon=True).start()

    def handle_install_result(self, result):
        code, stdout, stderr = result
        self.btn_install.config(state="normal", text="⚡ INSTALAR APK NO DISPOSITIVO")
        
        if code == 0:
            self.log("APK instalado com sucesso!")
            messagebox.showinfo("Sucesso", "APK instalado com sucesso no dispositivo!")
            self.load_installed_apps_thread()
        else:
            err_msg = stderr.strip() or stdout.strip() or "Erro desconhecido"
            self.log(f"Falha na instalação: {err_msg}")
            messagebox.showerror("Erro de Instalação", f"Não foi possível instalar o APK.\n\nDetalhes:\n{err_msg}")

    # --- CONTROLES DE LAUNCHER ---
    def update_launcher_status(self):
        """Busca o launcher padrão do aparelho conectado."""
        if not self.adb_client.device:
            self.launcher_current_lbl.config(text="Sem conexão", fg=FG_MUTED)
            return
            
        def fetch():
            # Método 1: cmd package resolve-activity
            stdout, stderr, code = self.adb_client.run_cmd(["shell", "cmd", "package", "resolve-activity", "-c", "android.intent.category.HOME"])
            launcher = "Não definido"
            if code == 0 and stdout:
                match = re.search(r'([\w\.]+)/([\w\.\+]+)', stdout)
                if match:
                    # remove flags e extras se houver
                    act = match.group(2).split()[0] if ' ' in match.group(2) else match.group(2)
                    launcher = f"{match.group(1)}/{act}"
                elif "ResolverActivity" in stdout:
                    launcher = "Nenhum padrão (Seletor do Sistema Ativo)"
            
            # Se falhar, tenta método alternativo dumpsys window
            if launcher == "Não definido" or code != 0:
                stdout_d, _, code_d = self.adb_client.run_cmd(["shell", "dumpsys", "window", "intents"])
                if code_d == 0 and stdout_d:
                    # Tenta achar o resolveInfo de Home
                    for line in stdout_d.splitlines():
                        if "android.intent.category.HOME" in line or "mCurrentFocus" in line:
                            match = re.search(r'([\w\.]+)/([\w\.]+)', line)
                            if match:
                                launcher = f"{match.group(1)}/{match.group(2)}"
                                break
                                
            self.gui_queue.put(("launcher_status", launcher))
            
        threading.Thread(target=fetch, daemon=True).start()

    def handle_launcher_status(self, launcher):
        if "Nenhum" in launcher or "Seletor" in launcher:
            self.launcher_current_lbl.config(text=launcher, fg=ACCENT_BLUE)
        elif launcher == "Sem conexão" or launcher == "Desconectado":
            self.launcher_current_lbl.config(text=launcher, fg=FG_MUTED)
        else:
            self.launcher_current_lbl.config(text=launcher, fg=ACCENT_GREEN)

    def query_device_launchers(self):
        """Lista todos os launchers instalados no dispositivo."""
        if not self.adb_client.device:
            messagebox.showwarning("Sem Dispositivo", "Conecte um dispositivo primeiro.")
            return
            
        self.btn_refresh_launchers.config(state="disabled", text="Buscando...")
        self.log("Buscando launchers instalados no aparelho...")
        
        def run_query():
            stdout, stderr, code = self.adb_client.run_cmd([
                "shell", "pm", "query-activities", 
                "-c", "android.intent.category.HOME", 
                "-a", "android.intent.action.MAIN"
            ])
            launchers = []
            if code == 0 and stdout:
                # Encontra padrões do tipo com.package.name/.ActivityName
                matches = re.findall(r'([\w\.]+)/([\w\.\+]+)', stdout)
                seen = set()
                for pkg, act in matches:
                    act = act.split()[0] if ' ' in act else act
                    item = f"{pkg}/{act}"
                    if item not in seen:
                        seen.add(item)
                        launchers.append(item)
            self.gui_queue.put(("launchers_list", launchers))
            
        threading.Thread(target=run_query, daemon=True).start()

    def handle_launchers_list(self, launchers):
        self.btn_refresh_launchers.config(state="normal", text="🔍 Procurar Launchers")
        if not launchers:
            self.log("Nenhum launcher alternativo encontrado.")
            self.launcher_combo['values'] = []
            self.launcher_combo.set("")
            return
            
        self.log(f"Encontrados {len(launchers)} launchers no dispositivo.")
        self.launcher_combo['values'] = launchers
        self.launcher_combo.set(launchers[0])

    def set_selected_launcher_default(self):
        """Define o launcher selecionado na combo como o padrão."""
        launcher = self.launcher_combo.get()
        if not launcher:
            messagebox.showwarning("Sem Seleção", "Por favor, selecione um launcher na lista primeiro.")
            return
        if not self.adb_client.device:
            return
            
        self.log(f"Definindo launcher padrão: {launcher}...")
        
        def run_set():
            # Comando: adb shell cmd package set-home-activity <package/activity>
            stdout, stderr, code = self.adb_client.run_cmd(["shell", "cmd", "package", "set-home-activity", launcher])
            self.gui_queue.put(("set_launcher_result", (code, stdout, stderr, launcher)))
            
        threading.Thread(target=run_set, daemon=True).start()

    def handle_set_launcher_result(self, result):
        code, stdout, stderr, launcher = result
        if code == 0:
            self.log(f"Sucesso! {launcher} definido como launcher padrão.")
            messagebox.showinfo("Sucesso", f"O launcher padrão foi alterado para:\n{launcher}")
            self.update_launcher_status()
        else:
            err = stderr.strip() or stdout.strip() or "Erro desconhecido"
            # Em aparelhos antigos ou customizações, pode falhar. Exibe aviso amigável.
            self.log(f"Falha ao definir pelo ADB (código {code}): {err}")
            messagebox.showwarning(
                "Aviso do Sistema", 
                f"Não foi possível definir automaticamente via ADB.\n\n"
                f"Aparelho retornou: '{err}'.\n\n"
                f"Por favor, use o botão 'Abrir Seletor' para escolher manualmente na tela do aparelho."
            )

    def clear_launcher_default(self):
        """Limpa o launcher padrão atual (faz o Android perguntar novamente)."""
        if not self.adb_client.device:
            return
        self.log("Limpando launcher padrão...")
        
        def run_clear():
            stdout, stderr, code = self.adb_client.run_cmd(["shell", "cmd", "package", "set-home-activity", "--clear"])
            self.gui_queue.put(("clear_launcher_result", (code, stdout, stderr)))
            
        threading.Thread(target=run_clear, daemon=True).start()

    def handle_clear_launcher_result(self, result):
        code, stdout, stderr = result
        if code == 0:
            self.log("Launcher padrão limpo com sucesso!")
            messagebox.showinfo("Sucesso", "O launcher padrão foi limpo.\n\nNa próxima vez que apertar 'Home' no aparelho, o Android solicitará a escolha do novo launcher.")
            self.update_launcher_status()
        else:
            self.log(f"Falha ao limpar launcher padrão: {stderr.strip() or stdout.strip()}")

    def open_launcher_picker_device(self):
        """Abre a tela de seleção de launcher principal no aparelho."""
        if not self.adb_client.device:
            return
        self.log("Abrindo seletor de launcher na tela do dispositivo...")
        
        def run_picker():
            # Envia a intent de HOME que dispara o seletor se não houver padrão,
            # ou abre as configurações de aplicativos padrão.
            self.adb_client.run_cmd(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"])
            
        threading.Thread(target=run_picker, daemon=True).start()

    # --- GERENCIADOR DE APLICATIVOS ---
    def clear_app_listbox(self):
        self.apps_listbox.delete(0, tk.END)
        self.all_installed_packages = []

    def load_installed_apps_thread(self):
        """Inicia busca de aplicativos instalados em segundo plano."""
        if not self.adb_client.device:
            self.clear_app_listbox()
            return
            
        self.log("Carregando lista de aplicativos instalados...")
        self.apps_listbox.delete(0, tk.END)
        self.apps_listbox.insert(tk.END, "Carregando aplicativos...")
        
        def run_load():
            # Define se lista apenas do usuário (-3) ou tudo (que inclui sistema)
            # Se show_system for False, usamos '-3'. Se True, listamos tudo
            args = ["shell", "pm", "list", "packages"]
            if not self.show_system_apps_var.get():
                args.append("-3")
                
            stdout, stderr, code = self.adb_client.run_cmd(args)
            packages = []
            if code == 0 and stdout:
                for line in stdout.splitlines():
                    if line.startswith("package:"):
                        pkg = line.replace("package:", "").strip()
                        packages.append(pkg)
                packages.sort()
            self.gui_queue.put(("apps_loaded", packages))
            
        threading.Thread(target=run_load, daemon=True).start()

    def handle_apps_loaded(self, packages):
        self.apps_listbox.delete(0, tk.END)
        self.all_installed_packages = packages
        
        # Filtra de acordo com o texto atual na barra de pesquisa
        self.filter_app_list()
        self.log(f"Carregados {len(packages)} aplicativos do dispositivo.")

    def filter_app_list(self, *args):
        """Filtra dinamicamente a Listbox de acordo com o texto digitado na pesquisa."""
        if not hasattr(self, 'apps_listbox'):
            return
        query = self.search_var.get().strip().lower()
        
        # Se for o placeholder, não filtra
        if query == self.placeholder_text.lower():
            query = ""
            
        self.apps_listbox.delete(0, tk.END)
        for pkg in self.all_installed_packages:
            if not query or query in pkg.lower():
                self.apps_listbox.insert(tk.END, pkg)

    def on_search_focus_in(self, event):
        if self.search_entry.get() == self.placeholder_text:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg=FG_TEXT)

    def on_search_focus_out(self, event):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, self.placeholder_text)
            self.search_entry.config(fg=FG_MUTED)

    # AÇÕES DO GERENCIADOR DE APPS
    def get_selected_package(self):
        try:
            index = self.apps_listbox.curselection()[0]
            return self.apps_listbox.get(index)
        except IndexError:
            messagebox.showwarning("Nenhum App Selecionado", "Por favor, selecione um aplicativo na lista primeiro.")
            return None

    def launch_selected_app(self):
        pkg = self.get_selected_package()
        if not pkg or not self.adb_client.device:
            return
            
        self.log(f"Iniciando app {pkg}...")
        def run():
            # Monkey command para disparar launcher
            stdout, stderr, code = self.adb_client.run_cmd(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            if code == 0:
                self.log(f"App {pkg} iniciado com sucesso.")
            else:
                self.log(f"Falha ao iniciar app: {stderr.strip() or stdout.strip()}")
        threading.Thread(target=run, daemon=True).start()

    def force_stop_selected_app(self):
        pkg = self.get_selected_package()
        if not pkg or not self.adb_client.device:
            return
            
        self.log(f"Forçando parada de {pkg}...")
        def run():
            stdout, stderr, code = self.adb_client.run_cmd(["shell", "am", "force-stop", pkg])
            if code == 0:
                self.log(f"App {pkg} parado.")
            else:
                self.log(f"Erro: {stderr.strip()}")
        threading.Thread(target=run, daemon=True).start()

    def clear_selected_app_data(self):
        pkg = self.get_selected_package()
        if not pkg or not self.adb_client.device:
            return
            
        if not messagebox.askyesno("Limpar Dados", f"Tem certeza que deseja apagar todos os dados de {pkg}?\nIsso resetará o app."):
            return
            
        self.log(f"Limpando dados de {pkg}...")
        def run():
            stdout, stderr, code = self.adb_client.run_cmd(["shell", "pm", "clear", pkg])
            if code == 0:
                self.log(f"Dados do app {pkg} limpos com sucesso.")
            else:
                self.log(f"Erro: {stderr.strip()}")
        threading.Thread(target=run, daemon=True).start()

    def uninstall_selected_app(self):
        pkg = self.get_selected_package()
        if not pkg or not self.adb_client.device:
            return
            
        if not messagebox.askyesno("Desinstalar App", f"Deseja realmente desinstalar o aplicativo {pkg} do dispositivo?"):
            return
            
        self.log(f"Desinstalando {pkg}...")
        def run():
            stdout, stderr, code = self.adb_client.run_cmd(["uninstall", pkg])
            self.gui_queue.put(("uninstall_result", (code, stdout, stderr, pkg)))
        threading.Thread(target=run, daemon=True).start()

    def handle_uninstall_result(self, result):
        code, stdout, stderr, pkg = result
        if code == 0:
            self.log(f"App {pkg} desinstalado com sucesso!")
            messagebox.showinfo("Sucesso", f"O aplicativo {pkg} foi desinstalado.")
            self.load_installed_apps_thread()
        else:
            err = stderr.strip() or stdout.strip() or "Erro desconhecido"
            self.log(f"Erro ao desinstalar {pkg}: {err}")
            messagebox.showerror("Erro", f"Não foi possível desinstalar {pkg}.\n\nDetalhes:\n{err}")

    def clear_console_logs(self):
        self.console_txt.config(state="normal")
        self.console_txt.delete("1.0", tk.END)
        self.console_txt.config(state="disabled")

    # --- INSTALAÇÃO AUTOMÁTICA DE ADB ---
    def check_or_download_adb(self):
        """Verifica a presença do ADB. Se não houver, mostra tela de download."""
        if os.path.exists(self.adb_path):
            self.log("ADB detectado e pronto para uso.")
            return
            
        # Cria overlay de download
        self.download_overlay = tk.Toplevel(self.root)
        self.download_overlay.title("Configurando dependências")
        self.download_overlay.geometry("450x180")
        self.download_overlay.configure(bg=BG_CARD)
        self.download_overlay.resizable(False, False)
        self.download_overlay.transient(self.root)
        self.download_overlay.grab_set()
        
        # Centraliza na tela relativo à janela principal
        self.download_overlay.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (self.download_overlay.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (self.download_overlay.winfo_height() // 2)
        self.download_overlay.geometry(f"+{x}+{y}")
        
        # Elementos do overlay
        tk.Label(
            self.download_overlay, 
            text="ADB não encontrado localmente!", 
            fg="#ffffff", bg=BG_CARD, font=("Segoe UI", 12, "bold")
        ).pack(pady=(20, 5))
        
        self.download_status_lbl = tk.Label(
            self.download_overlay, 
            text="Iniciando download do Android Platform Tools (oficial)...", 
            fg=FG_MUTED, bg=BG_CARD, font=("Segoe UI", 9), wraplength=400
        ).pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(self.download_overlay, orient="horizontal", mode="determinate", style="TProgressbar")
        self.progress_bar.pack(fill="x", padx=40, pady=10)
        
        # Desabilita botões da janela principal enquanto baixa
        self.btn_choose_apk.config(state="disabled")
        self.btn_install.config(state="disabled")
        
        # Inicia download em thread separada
        def download_worker():
            try:
                # Cria pasta platform-tools se necessário
                os.makedirs(self.adb_dir, exist_ok=True)
                
                url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
                # Se for Linux/macOS, baixa a versão adequada
                if sys.platform.startswith("linux"):
                    url = "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
                elif sys.platform == "darwin":
                    url = "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
                
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                
                # Pasta de destino temporária
                script_dir = os.path.dirname(os.path.abspath(__file__))
                zip_path = os.path.join(script_dir, "adb_temp.zip")
                
                with urllib.request.urlopen(req) as response:
                    total_size = int(response.info().get('Content-Length', 0))
                    block_size = 1024 * 128  # 128KB
                    downloaded = 0
                    
                    with open(zip_path, 'wb') as f:
                        while True:
                            buffer = response.read(block_size)
                            if not buffer:
                                break
                            downloaded += len(buffer)
                            f.write(buffer)
                            
                            percent = int((downloaded / total_size) * 100) if total_size > 0 else 0
                            self.gui_queue.put(("download_progress", (percent, f"Baixando: {downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB")))
                
                self.gui_queue.put(("download_progress", (95, "Extraindo arquivos...")))
                
                # Extrai zip
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # O zip oficial extrai numa pasta chamada 'platform-tools'
                    # Então extraímos direto no diretório do script para que fique no caminho correto
                    zip_ref.extractall(script_dir)
                
                # Remove o zip temporário
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
                
                # Se for Unix, dá permissão de execução
                if os.name != 'nt':
                    try:
                        os.chmod(self.adb_path, 0o755)
                    except Exception:
                        pass
                
                self.gui_queue.put(("download_complete", None))
            except Exception as e:
                self.gui_queue.put(("download_error", str(e)))
                
        threading.Thread(target=download_worker, daemon=True).start()

    def handle_download_progress(self, data):
        percent, text = data
        self.progress_bar['value'] = percent
        # Atualiza o label se o overlay ainda existir
        if hasattr(self, 'download_overlay') and self.download_overlay.winfo_exists():
            for child in self.download_overlay.winfo_children():
                if isinstance(child, tk.Label) and child.cget("text") != "ADB não encontrado localmente!":
                    child.config(text=text)

    def handle_download_complete(self):
        if hasattr(self, 'download_overlay') and self.download_overlay.winfo_exists():
            self.download_overlay.grab_release()
            self.download_overlay.destroy()
            
        self.btn_choose_apk.config(state="normal")
        self.btn_install.config(state="normal")
        self.log("ADB baixado e instalado com sucesso na pasta 'platform-tools'.")
        messagebox.showinfo("Sucesso", "O Android Platform Tools (ADB) foi baixado e configurado com sucesso!")
        
        # Força o monitor a checar novamente e atualiza o estado
        self.refresh_devices_now()

    def handle_download_error(self, err_msg):
        if hasattr(self, 'download_overlay') and self.download_overlay.winfo_exists():
            self.download_overlay.grab_release()
            self.download_overlay.destroy()
            
        self.log(f"Falha ao baixar o ADB: {err_msg}")
        messagebox.showerror(
            "Erro de Configuração", 
            f"Não foi possível baixar o ADB automaticamente.\n\n"
            f"Erro: {err_msg}\n\n"
            f"Por favor, verifique sua conexão com a internet e reinicie o programa."
        )

    # --- CONTROLE E PROCESSAMENTO DA FILA GUI ---
    def process_queue_loop(self):
        """Lê mensagens da fila e processa na thread principal (seguro para GUI)."""
        try:
            while True:
                msg_type, data = self.gui_queue.get_nowait()
                
                # Roteia de acordo com a mensagem
                if msg_type == "devices_changed":
                    self.handle_devices_changed(data)
                elif msg_type == "install_result":
                    self.handle_install_result(data)
                elif msg_type == "apps_loaded":
                    self.handle_apps_loaded(data)
                elif msg_type == "uninstall_result":
                    self.handle_uninstall_result(data)
                elif msg_type == "launcher_status":
                    self.handle_launcher_status(data)
                elif msg_type == "launchers_list":
                    self.handle_launchers_list(data)
                elif msg_type == "set_launcher_result":
                    self.handle_set_launcher_result(data)
                elif msg_type == "clear_launcher_result":
                    self.handle_clear_launcher_result(data)
                elif msg_type == "download_progress":
                    self.handle_download_progress(data)
                elif msg_type == "download_complete":
                    self.handle_download_complete()
                elif msg_type == "download_error":
                    self.handle_download_error(data)
                    
                self.gui_queue.task_done()
        except queue.Empty:
            pass
        finally:
            # Reagenda para rodar novamente em 100ms
            self.root.after(100, self.process_queue_loop)

if __name__ == "__main__":
    # Em sistemas modernos, habilita suporte a DPI alto para que fontes não fiquem borradas
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    root = tk.Tk()
    app = App(root)
    root.mainloop()
