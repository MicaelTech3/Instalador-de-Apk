import os
import subprocess
import sys
import shutil

# Pasta raiz do projeto
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def build_app():
    try:
        # 1. Compilar o frontend React
        print("=== 1. COMPILANDO FRONTEND REACT ===")
        frontend_dir = os.path.join(ROOT_DIR, "frontend")
        os.chdir(frontend_dir)
        
        # Executa build do vite
        subprocess.run("npm run build", shell=True, check=True)
        os.chdir(ROOT_DIR)
        
        # 2. Instalar PyInstaller no ambiente virtual
        print("\n=== 2. INSTALANDO PYINSTALLER ===")
        subprocess.run(f'"{sys.executable}" -m pip install pyinstaller', shell=True, check=True)
        
        # 3. Gerar o arquivo Executável (.exe)
        print("\n=== 3. GERANDO O EXECUTÁVEL COM PYINSTALLER ===")
        # Comando para empacotar
        # Usamos --noconfirm para sobrescrever builds anteriores e --windowed para não exibir o cmd preto por trás
        pyinstaller_cmd = (
            'pyinstaller --noconfirm --onedir --windowed '
            '--add-data "frontend/dist;frontend/dist" '
            '--name "ADB_Companion" '
            'server.py'
        )
        
        subprocess.run(pyinstaller_cmd, shell=True, check=True)
        
        print("\n" + "="*40)
        print("SUCESSO! O executável foi gerado com êxito.")
        print(f"Você pode encontrá-lo em: D:\\instalador de apps\\dist\\ADB_Companion\\ADB_Companion.exe")
        print("="*40)
        
    except Exception as e:
        print(f"\n❌ Ocorreu um erro durante o build: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    build_app()
