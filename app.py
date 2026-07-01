#!/usr/bin/env python3
"""
Entrypoint para o Railway que executa a app principal (app_treinador.py)
"""
import subprocess
import sys
import os

if __name__ == "__main__":
    port = os.environ.get('PORT', '8501')
    cmd = [
        sys.executable, '-m', 'streamlit', 'run', 'app_treinador.py',
        '--server.port', port,
        '--server.address', '0.0.0.0',
        '--server.headless', 'true',
        '--server.enableCORS', 'false',
        '--server.enableXsrfProtection', 'false'
    ]
    
    print(f"🚀 Iniciando app_treinador.py na porta {port}")
    subprocess.run(cmd)