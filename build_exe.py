import os
import subprocess
import sys
import shutil

# Pasta raiz do projeto
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def build_app():
    try:
        # 0. Converter coding.png para coding.ico
        print("=== 0. CONVERTENDO PNG PARA ICO ===")
        png_path = os.path.join(ROOT_DIR, "frontend", "public", "coding.png")
        ico_path = os.path.join(ROOT_DIR, "coding.ico")
        
        try:
            from PIL import Image
        except ImportError:
            print("Instalando Pillow para conversão de imagens...")
            subprocess.run(f'"{sys.executable}" -m pip install pillow', shell=True, check=True)
            from PIL import Image
            
        if os.path.exists(png_path):
            img = Image.open(png_path)
            img.save(ico_path, format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
            print(f"✅ Ícone .ico gerado com sucesso em: {ico_path}")
        else:
            print(f"⚠️ Aviso: coding.png não encontrado em {png_path}")

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
            '--icon "coding.ico" '
            '--add-data "frontend/dist;frontend/dist" '
            '--name "ADB_Companion" '
            'server.py'
        )
        
        subprocess.run(pyinstaller_cmd, shell=True, check=True)
        
        # 4. Comprimir a pasta dist/ADB_Companion em um ZIP na pasta public para download online
        print("\n=== 4. COMPRIMINDO EXECUTÁVEL EM ZIP ===")
        public_dir = os.path.join(ROOT_DIR, "frontend", "public")
        os.makedirs(public_dir, exist_ok=True)
        zip_output_path = os.path.join(public_dir, "ADB_Companion")
        
        # Cria o arquivo ZIP (shutil adicionará o sufixo .zip automaticamente)
        shutil.make_archive(zip_output_path, 'zip', os.path.join(ROOT_DIR, "dist", "ADB_Companion"))
        print(f"ZIP gerado com sucesso em: {zip_output_path}.zip")
        
        # 5. Gerar o instalador Inno Setup
        print("\n=== 5. GERANDO INSTALADOR (INNO SETUP) ===")
        try:
            import build_installer
            iss_path = build_installer.create_inno_script()
            build_installer.compile_installer(iss_path)
        except Exception as err_setup:
            print(f"Aviso: Não foi possível gerar o instalador automático: {err_setup}")
        
        print("\n" + "="*40)
        print("SUCESSO! O executável foi gerado com êxito.")
        print(f"Você pode encontrá-lo em: D:\\instalador de apps\\dist\\ADB_Companion\\ADB_Companion.exe")
        print("E o ZIP em: D:\\instalador de apps\\frontend\\public\\ADB_Companion.zip")
        print("="*40)
        
    except Exception as e:
        print(f"\n❌ Ocorreu um erro durante o build: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    build_app()
