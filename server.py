import os
import sys
import json
import urllib.request
import zipfile
import subprocess
import re
import time
import http.server
import socketserver
import threading
import webbrowser

try:
    import webview
    USE_PYWEBVIEW = True
except ImportError:
    USE_PYWEBVIEW = False

# Porta do Servidor Web
PORT = 5000

# Localização do ADB (evita WinError 5 usando LOCALAPPDATA quando compilado)
if hasattr(sys, 'frozen'):
    SCRIPT_DIR = os.path.dirname(sys.executable)
    # Salva o ADB e dados na pasta do usuário (%LOCALAPPDATA%) para garantir permissão de escrita
    APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "ADB_Companion")
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DATA_DIR = SCRIPT_DIR

ADB_DIR = os.path.join(APP_DATA_DIR, "platform-tools")
ADB_PATH = os.path.join(ADB_DIR, "adb.exe" if os.name == 'nt' else "adb")

# Garante que a pasta de dados exista
os.makedirs(APP_DATA_DIR, exist_ok=True)

# Cache em memória
selected_device = None
recent_logs = []
adb_download_percent = 0
adb_download_status = "Aguardando inicialização"

def log_event(message):
    timestamp = time.strftime("[%H:%M:%S]")
    log_line = f"{timestamp} {message}"
    recent_logs.append(log_line)
    if len(recent_logs) > 150:
        recent_logs.pop(0)
    print(log_line)

def run_adb_command(args, device_id=None):
    """Executa um comando ADB e retorna (stdout, stderr, returncode)."""
    if not os.path.exists(ADB_PATH):
        return "", "ADB não está instalado no servidor.", -1
        
    cmd = [ADB_PATH]
    if device_id or selected_device:
        cmd.extend(["-s", device_id or selected_device])
    cmd.extend(args)
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
    cmd_str = "adb " + " ".join([f'"{a}"' if ' ' in a else a for a in (["-s", device_id or selected_device] if (device_id or selected_device) else []) + args])
    log_event(f"Executando: {cmd_str}")
    
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            startupinfo=startupinfo,
            timeout=40
        )
        if res.returncode == 0:
            log_event(f"Sucesso (código 0)")
        else:
            log_event(f"Erro (código {res.returncode}): {res.stderr.strip()}")
        return res.stdout, res.stderr, res.returncode
    except subprocess.TimeoutExpired:
        log_event("Erro: Comando expirou por limite de tempo.")
        return "", "Erro: O comando ADB expirou.", -1
    except Exception as e:
        log_event(f"Falha ao executar subprocesso: {str(e)}")
        return "", str(e), -1

def download_adb_in_background():
    global adb_download_percent, adb_download_status
    if os.path.exists(ADB_PATH):
        adb_download_percent = 100
        adb_download_status = "Pronto"
        return
        
    try:
        adb_download_status = "Iniciando download..."
        os.makedirs(ADB_DIR, exist_ok=True)
        
        url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
        if sys.platform.startswith("linux"):
            url = "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
        elif sys.platform == "darwin":
            url = "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
            
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        zip_path = os.path.join(APP_DATA_DIR, "platform_tools_temp.zip")
        
        log_event("Baixando Platform Tools do site oficial da Google...")
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))
            block_size = 1024 * 128
            downloaded = 0
            
            with open(zip_path, 'wb') as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    f.write(buffer)
                    
                    percent = int((downloaded / total_size) * 85) if total_size > 0 else 0
                    adb_download_percent = percent
                    adb_download_status = f"Baixando: {downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB"
                    
        adb_download_status = "Extraindo arquivos do zip..."
        adb_download_percent = 90
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(APP_DATA_DIR)
            
        try:
            os.remove(zip_path)
        except Exception:
            pass
            
        if os.name != 'nt':
            try:
                os.chmod(ADB_PATH, 0o755)
            except Exception:
                pass
                
        adb_download_percent = 100
        adb_download_status = "Pronto"
        log_event("ADB instalado com sucesso!")
    except Exception as e:
        adb_download_status = f"Falha no download: {str(e)}"
        adb_download_percent = -1
        log_event(f"Erro ao baixar ADB: {str(e)}")

# Parser manual de multipart/form-data para evitar o cgi obsoleto (Python 3.13+)
def parse_multipart_file(headers, rfile):
    content_type = headers.get('Content-Type')
    if not content_type or 'boundary=' not in content_type:
        return None, "Cabeçalho Content-Type inválido ou sem boundary."
        
    boundary_str = content_type.split('boundary=')[1].strip()
    if boundary_str.startswith('"') and boundary_str.endswith('"'):
        boundary_str = boundary_str[1:-1]
        
    boundary = ('--' + boundary_str).encode('utf-8')
    content_length = int(headers.get('Content-Length', 0))
    if content_length == 0:
        return None, "Corpo da requisição vazio."
        
    body = rfile.read(content_length)
    parts = body.split(boundary)
    
    for part in parts:
        if b'Content-Disposition:' in part and b'filename=' in part:
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                header_end = part.find(b'\n\n')
                if header_end == -1:
                    continue
                header_offset = 2
            else:
                header_offset = 4
                
            part_headers = part[:header_end].decode('utf-8', errors='ignore')
            filename_match = re.search(r'filename="([^"]+)"', part_headers)
            filename = filename_match.group(1) if filename_match else "app.apk"
            
            content = part[header_end + header_offset:]
            if content.endswith(b'\r\n'):
                content = content[:-2]
            elif content.endswith(b'\n'):
                content = content[:-1]
                
            return content, filename
            
    return None, "Nenhum arquivo encontrado na requisição multipart."

class APIRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Configura o diretório estático como dist da frontend (suporta PyInstaller)
        if hasattr(sys, '_MEIPASS'):
            dist_dir = os.path.join(sys._MEIPASS, "frontend", "dist")
        else:
            dist_dir = os.path.join(SCRIPT_DIR, "frontend", "dist")
            
        if not os.path.exists(dist_dir):
            os.makedirs(dist_dir, exist_ok=True)
        super().__init__(*args, directory=dist_dir, **kwargs)

    def end_headers(self):
        # Habilitar CORS para fins de desenvolvimento local
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        global selected_device
        path = self.path.split('?')[0]
        
        # Se for a raiz e o build não existir, serve uma página de instrução amigável
        if hasattr(sys, '_MEIPASS'):
            dist_index = os.path.join(sys._MEIPASS, "frontend", "dist", "index.html")
        else:
            dist_index = os.path.join(SCRIPT_DIR, "frontend", "dist", "index.html")
            
        if (path == "/" or path == "/index.html") and not os.path.exists(dist_index) and not is_vite_running():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Vite React ADB Companion</title>
                <style>
                    body {
                        background-color: #0a0a0d;
                        color: #f0f0f5;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                        text-align: center;
                    }
                    .card {
                        background: rgba(23, 23, 33, 0.7);
                        border: 1px solid rgba(60, 60, 80, 0.4);
                        padding: 30px;
                        border-radius: 16px;
                        max-width: 500px;
                        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
                    }
                    h1 { color: #7c4dff; margin-bottom: 10px; }
                    p { color: #8888a5; line-height: 1.6; }
                    .code {
                        background: #12121a;
                        padding: 10px;
                        border-radius: 8px;
                        font-family: monospace;
                        color: #00e676;
                        margin: 15px 0;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Interface Não Compilada</h1>
                    <p>Você precisa compilar o frontend React antes de rodar o servidor em produção, ou manter o servidor de desenvolvimento aberto.</p>
                    <div class="code">cd frontend && npm install && npm run build</div>
                    <p>Após gerar o build, reinicie o <code>server.py</code>.</p>
                    <p style="font-size: 0.8rem; color: #ff3d00;">Se preferir rodar em desenvolvimento, execute <code>npm run dev</code> na pasta frontend e reabra o servidor.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode('utf-8'))
            return

        # Rotas da API
        if path == "/api/adb-status":
            adb_ready = os.path.exists(ADB_PATH)
            self.send_json({
                "ready": adb_ready,
                "percent": adb_download_percent,
                "status": adb_download_status
            })
            return
            
        elif path == "/api/devices":
            if not os.path.exists(ADB_PATH):
                self.send_json({"devices": [], "selected": None})
                return
            
            # Executa adb devices
            stdout, _, code = run_adb_command(["devices"])
            devices = []
            if code == 0:
                lines = stdout.splitlines()
                for line in lines[1:]:
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        devices.append(parts[0])
                        
            # Se o dispositivo selecionado não está mais conectado
            if selected_device and selected_device not in devices:
                selected_device = None
                log_event("Dispositivo ativo desconectou.")
                
            # Se não houver nenhum selecionado e tiver dispositivos, seleciona o primeiro
            if not selected_device and devices:
                selected_device = devices[0]
                log_event(f"Selecionado automaticamente: {selected_device}")
                
            self.send_json({
                "devices": devices,
                "selected": selected_device
            })
            return
            
        elif path == "/api/apps":
            # Pega parâmetro query ?system=true
            query_system = False
            if '?' in self.path:
                params = self.path.split('?')[1]
                if "system=true" in params:
                    query_system = True
                    
            args = ["shell", "pm", "list", "packages"]
            if not query_system:
                args.append("-3")
                
            stdout, stderr, code = run_adb_command(args)
            packages = []
            if code == 0 and stdout:
                for line in stdout.splitlines():
                    if line.startswith("package:"):
                        packages.append(line.replace("package:", "").strip())
                packages.sort()
                self.send_json({"packages": packages})
            else:
                self.send_json({"error": stderr or "Falha ao listar apps"}, status=400)
            return
            
        elif path == "/api/apps/download":
            # Extrair parâmetro package do query
            params = self.path.split('?')[1] if '?' in self.path else ""
            pkg = None
            for p in params.split('&'):
                if p.startswith("package="):
                    pkg = p.split("=")[1]
                    break
                    
            if not pkg:
                self.send_json({"error": "Parâmetro 'package' ausente"}, status=400)
                return
                
            log_event(f"Solicitado download do APK para o pacote: {pkg}")
            
            # 1. Encontrar o caminho do APK no aparelho
            stdout, stderr, code = run_adb_command(["shell", "pm", "path", pkg])
            if code != 0 or not stdout:
                self.send_json({"error": f"Não foi possível obter o caminho do app: {stderr or 'App não encontrado'}"}, status=400)
                return
                
            device_apk_path = None
            for line in stdout.splitlines():
                if line.startswith("package:"):
                    path_candidate = line.replace("package:", "").strip()
                    if "base.apk" in path_candidate or not device_apk_path:
                        device_apk_path = path_candidate
                        
            if not device_apk_path:
                self.send_json({"error": "Caminho do APK não encontrado no dispositivo."}, status=400)
                return
                
            # 2. Puxar o APK para o servidor temporariamente
            local_temp_path = os.path.join(SCRIPT_DIR, f"temp_{pkg}.apk")
            log_event(f"Puxando APK do dispositivo ({pkg}) de {device_apk_path}...")
            pull_stdout, pull_stderr, pull_code = run_adb_command(["pull", device_apk_path, local_temp_path])
            
            if pull_code != 0 or not os.path.exists(local_temp_path):
                self.send_json({"error": f"Falha ao extrair APK: {pull_stderr or 'Erro no adb pull'}"}, status=400)
                return
                
            # 3. Retornar o arquivo como download HTTP
            try:
                with open(local_temp_path, "rb") as f:
                    file_data = f.read()
                    
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.android.package-archive')
                self.send_header('Content-Disposition', f'attachment; filename="{pkg}.apk"')
                self.send_header('Content-Length', str(len(file_data)))
                self.end_headers()
                self.wfile.write(file_data)
                log_event(f"APK de {pkg} enviado para download com sucesso!")
            except Exception as e:
                log_event(f"Falha ao transmitir arquivo: {str(e)}")
            finally:
                # Excluir o arquivo temporário
                try:
                    if os.path.exists(local_temp_path):
                        os.remove(local_temp_path)
                except Exception:
                    pass
            return
            
        elif path == "/api/launcher/default":
            stdout, stderr, code = run_adb_command(["shell", "cmd", "package", "resolve-activity", "-c", "android.intent.category.HOME"])
            launcher = "Não definido"
            if code == 0 and stdout:
                match = re.search(r'([\w\.]+)/([\w\.\+]+)', stdout)
                if match:
                    act = match.group(2).split()[0] if ' ' in match.group(2) else match.group(2)
                    launcher = f"{match.group(1)}/{act}"
                elif "ResolverActivity" in stdout:
                    launcher = "Nenhum padrão (Seletor do Sistema Ativo)"
            self.send_json({"launcher": launcher})
            return
            
        elif path == "/api/launcher/list":
            stdout, stderr, code = run_adb_command(["shell", "pm", "query-activities", "-c", "android.intent.category.HOME", "-a", "android.intent.action.MAIN"])
            launchers = []
            if code == 0 and stdout:
                matches = re.findall(r'([\w\.]+)/([\w\.\+]+)', stdout)
                seen = set()
                for pkg, act in matches:
                    act = act.split()[0] if ' ' in act else act
                    item = f"{pkg}/{act}"
                    if item not in seen:
                        seen.add(item)
                        launchers.append(item)
            self.send_json({"launchers": launchers})
            return
            
        elif path == "/api/logs":
            self.send_json({"logs": recent_logs})
            return
            
        # Se for arquivos estáticos, deixa o SimpleHTTPRequestHandler cuidar
        super().do_GET()

    def do_POST(self):
        global selected_device
        path = self.path
        
        # Obter tamanho do corpo para requisições JSON
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = b""
        if content_length > 0 and 'multipart/form-data' not in self.headers.get('Content-Type', ''):
            post_data = self.rfile.read(content_length)
            
        # Parsing JSON seguro
        params = {}
        if post_data:
            try:
                params = json.loads(post_data.decode('utf-8'))
            except Exception:
                pass
                
        if path == "/api/adb-download":
            if not os.path.exists(ADB_PATH):
                import threading
                threading.Thread(target=download_adb_in_background).start()
                self.send_json({"status": "Iniciado"})
            else:
                self.send_json({"status": "ADB já instalado"})
            return
            
        elif path == "/api/select-device":
            device = params.get("device")
            if device:
                selected_device = device
                log_event(f"Dispositivo selecionado: {device}")
                self.send_json({"status": "ok"})
            else:
                self.send_json({"error": "Parâmetro 'device' ausente"}, status=400)
            return
            
        elif path == "/api/install":
            if 'multipart/form-data' not in self.headers.get('Content-Type', ''):
                self.send_json({"error": "Necessário formato multipart/form-data"}, status=400)
                return
                
            # Extrair parâmetros do cabeçalho da URL se houver ou assumir defaults
            replace_existing = True # -r
            grant_permissions = True # -g
            
            # Pega o arquivo enviado
            file_bytes, filename = parse_multipart_file(self.headers, self.rfile)
            if not file_bytes:
                self.send_json({"error": filename or "Falha ao receber arquivo APK"}, status=400)
                return
                
            # Salvar APK temporariamente
            temp_apk_path = os.path.join(SCRIPT_DIR, "temp_upload.apk")
            with open(temp_apk_path, "wb") as f:
                f.write(file_bytes)
                
            log_event(f"Recebido APK: {filename} ({len(file_bytes)/1024/1024:.1f}MB)")
            
            # Instalação via ADB
            args = ["install"]
            if replace_existing:
                args.append("-r")
            if grant_permissions:
                args.append("-g")
            args.append(temp_apk_path)
            
            log_event("Instalando APK no dispositivo...")
            stdout, stderr, code = run_adb_command(args)
            
            # Limpar arquivo temporário
            try:
                os.remove(temp_apk_path)
            except Exception:
                pass
                
            if code == 0:
                self.send_json({"success": True, "message": "Instalado com sucesso"})
            else:
                self.send_json({"success": False, "error": stderr or stdout or "Erro desconhecido na instalação"}, status=400)
            return
            
        elif path == "/api/uninstall":
            pkg = params.get("package")
            if not pkg:
                self.send_json({"error": "Parâmetro 'package' ausente"}, status=400)
                return
            log_event(f"Desinstalando aplicativo: {pkg}...")
            stdout, stderr, code = run_adb_command(["uninstall", pkg])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/launch":
            pkg = params.get("package")
            if not pkg:
                self.send_json({"error": "Parâmetro 'package' ausente"}, status=400)
                return
            log_event(f"Iniciando aplicativo: {pkg}...")
            stdout, stderr, code = run_adb_command(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/stop":
            pkg = params.get("package")
            if not pkg:
                self.send_json({"error": "Parâmetro 'package' ausente"}, status=400)
                return
            log_event(f"Forçando parada de: {pkg}...")
            stdout, stderr, code = run_adb_command(["shell", "am", "force-stop", pkg])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/clear":
            pkg = params.get("package")
            if not pkg:
                self.send_json({"error": "Parâmetro 'package' ausente"}, status=400)
                return
            log_event(f"Limpando dados de: {pkg}...")
            stdout, stderr, code = run_adb_command(["shell", "pm", "clear", pkg])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/launcher/set":
            launcher = params.get("launcher")
            if not launcher:
                self.send_json({"error": "Parâmetro 'launcher' ausente"}, status=400)
                return
            log_event(f"Definindo launcher padrão: {launcher}...")
            stdout, stderr, code = run_adb_command(["shell", "cmd", "package", "set-home-activity", launcher])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/launcher/clear":
            log_event("Limpando preferência de launcher padrão...")
            stdout, stderr, code = run_adb_command(["shell", "cmd", "package", "set-home-activity", "--clear"])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/launcher/picker":
            log_event("Disparando seletor de launcher na tela do dispositivo...")
            stdout, stderr, code = run_adb_command(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"])
            if code == 0:
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": stderr or stdout}, status=400)
            return
            
        elif path == "/api/launcher/test":
            pkg = params.get("package")
            if not pkg:
                self.send_json({"error": "Parâmetro 'package' ausente"}, status=400)
                return
                
            log_event(f"Testando aplicativo {pkg} como Launcher...")
            
            # 1. Procurar a activity correspondente à HOME para este pacote
            stdout, stderr, code = run_adb_command(["shell", "pm", "query-activities", "-c", "android.intent.category.HOME", "-a", "android.intent.action.MAIN"])
            target_launcher = None
            if code == 0 and stdout:
                matches = re.findall(r'([\w\.]+)/([\w\.\+]+)', stdout)
                for matched_pkg, matched_act in matches:
                    matched_act = matched_act.split()[0] if ' ' in matched_act else matched_act
                    if matched_pkg == pkg:
                        target_launcher = f"{matched_pkg}/{matched_act}"
                        break
                        
            if not target_launcher:
                self.send_json({
                    "success": False, 
                    "error": f"O app {pkg} não possui uma atividade de Launcher (HOME) registrada no sistema Android."
                }, status=400)
                return
                
            # 2. Definir como home activity padrão
            log_event(f"Definindo componente do launcher: {target_launcher}")
            stdout, stderr, code = run_adb_command(["shell", "cmd", "package", "set-home-activity", target_launcher])
            if code != 0:
                self.send_json({"success": False, "error": f"Falha ao definir padrão: {stderr or stdout}"}, status=400)
                return
                
            # 3. Chamar a intent de Home para abrir o launcher imediatamente
            log_event("Enviando comando de tela inicial (HOME) para o aparelho...")
            stdout, stderr, code = run_adb_command(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"])
            if code == 0:
                self.send_json({"success": True, "message": f"{pkg} definido como launcher padrão e aberto!"})
            else:
                self.send_json({"success": True, "message": f"{pkg} definido, mas falhou ao simular clique HOME: {stderr or stdout}"})
            return
            
        else:
            self.send_json({"error": "Rota não encontrada"}, status=404)

def is_vite_running():
    """Verifica se o servidor de desenvolvimento do Vite (porta 5173) está ativo."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            s.connect(("127.0.0.1", 5173))
            return True
    except Exception:
        return False

def open_browser():
    """Espera 1.5 segundos para garantir a subida do servidor e abre a interface no navegador."""
    time.sleep(1.5)
    url = "http://localhost:5173" if is_vite_running() else f"http://localhost:{PORT}"
    webbrowser.open(url)

if __name__ == "__main__":
    # Inicia com uma verificação silenciosa se o ADB já está presente
    if os.path.exists(ADB_PATH):
        adb_download_percent = 100
        adb_download_status = "Pronto"
        log_event("ADB detectado no servidor.")
    else:
        log_event("ADB não encontrado. O download será iniciado na primeira requisição ou ao pressionar Configurar no painel.")

    # Inicia servidor local
    handler = APIRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        log_event(f"Servidor ADB Web iniciado no endereço: http://localhost:{PORT}")
        
        if USE_PYWEBVIEW:
            # Se pywebview estiver disponível, o servidor roda em segundo plano 
            # e a janela gráfica roda na thread principal (obrigatório para GUIs)
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            
            url_to_open = "http://localhost:5173" if is_vite_running() else f"http://localhost:{PORT}"
            log_event(f"Iniciando janela nativa desktop (pywebview) apontando para: {url_to_open}...")
            
            # Resolve o caminho do ícone para a janela do pywebview
            icon_path = None
            if hasattr(sys, '_MEIPASS'):
                path_try = os.path.join(sys._MEIPASS, "frontend", "dist", "coding.png")
            else:
                path_try = os.path.join(SCRIPT_DIR, "frontend", "public", "coding.png")
            if os.path.exists(path_try):
                icon_path = path_try
                log_event(f"Ícone da janela carregado de: {icon_path}")
                
            webview.create_window(
                title="Android Companion & ADB Installer",
                url=url_to_open,
                width=1320,
                height=880,
                resizable=True
            )
            webview.start(icon=icon_path)
            log_event("Janela fechada pelo usuário. Encerrando servidor...")
        else:
            # Caso contrário, abre o navegador padrão e roda o servidor na thread principal
            log_event("Dica: execute 'pip install pywebview' para abrir como aplicativo desktop nativo.")
            
            # Dispara abertura automática do navegador
            threading.Thread(target=open_browser, daemon=True).start()
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                log_event("Servidor finalizado pelo usuário.")
                sys.exit(0)
