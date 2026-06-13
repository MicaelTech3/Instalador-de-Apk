import os
import subprocess
import shutil
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def create_inno_script():
    iss_content = f"""[Setup]
AppName=ADB Companion
AppVersion=1.0
DefaultDirName={{autopf}}\\ADB Companion
DefaultGroupName=ADB Companion
UninstallDisplayIcon={{app}}\\ADB_Companion.exe
SetupIconFile={ROOT_DIR}\\coding.ico
OutputDir={ROOT_DIR}\\dist
OutputBaseFilename=ADB_Companion_Setup
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin

[Files]
Source: "{ROOT_DIR}\\dist\\ADB_Companion\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\ADB Companion"; Filename: "{{app}}\\ADB_Companion.exe"
Name: "{{autodesktop}}\\ADB Companion"; Filename: "{{app}}\\ADB_Companion.exe"

[Run]
Filename: "{{app}}\\ADB_Companion.exe"; Description: "Iniciar ADB Companion"; Flags: nowait postinstall skipifsilent
"""
    iss_path = os.path.join(ROOT_DIR, "installer.iss")
    with open(iss_path, "w", encoding="utf-8") as f:
        f.write(iss_content)
    print(f"📄 Script do Inno Setup criado em: {iss_path}")
    return iss_path

def compile_installer(iss_path):
    # Caminhos comuns de instalação do Inno Setup 6
    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "ISCC.exe" # Se estiver no PATH
    ]
    
    compiler_path = None
    for path in possible_paths:
        if shutil.which(path) or os.path.exists(path):
            compiler_path = path
            break
            
    if not compiler_path:
        print("\n⚠️ Inno Setup não foi localizado automaticamente.")
        print("Para gerar o instalador automaticamente:")
        print("1. Baixe e instale o Inno Setup (grátis): https://jrsoftware.org/isdl.php")
        print("2. Abra o arquivo 'installer.iss' no Inno Setup e clique em 'Compile' (F9).")
        return False

    print(f"🔨 Compilador do Inno Setup encontrado: {compiler_path}")
    print("Compilando instalador... (isso pode levar alguns segundos)")
    
    try:
        subprocess.run([compiler_path, iss_path], check=True)
        setup_src = os.path.join(ROOT_DIR, "dist", "ADB_Companion_Setup.exe")
        public_dest = os.path.join(ROOT_DIR, "frontend", "public", "ADB_Companion_Setup.exe")
        
        if os.path.exists(setup_src):
            shutil.copy(setup_src, public_dest)
            print(f"✅ Instalador gerado e copiado para: {public_dest}")
            return True
    except Exception as e:
        print(f"❌ Erro ao compilar o instalador: {str(e)}")
        
    return False

if __name__ == "__main__":
    iss_path = create_inno_script()
    compile_installer(iss_path)
