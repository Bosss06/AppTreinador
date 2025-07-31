# Configuração de Deploy para Streamlit Cloud
# Solução para importações circulares e problemas de ambiente

import os
import sys

# === DETECTAR AMBIENTE ===
def detect_environment():
    """Detecta o ambiente de execução"""
    cloud_indicators = [
        os.getenv('STREAMLIT_SHARING_MODE') == 'true',
        'streamlit.app' in os.getenv('HOSTNAME', ''),
        'streamlit' in os.getenv('HOSTNAME', ''),
        os.getenv('STREAMLIT_SERVER_PORT') is not None,
        not os.path.exists('C:\\'),
        os.path.exists('/app')
    ]
    
    return {
        'is_cloud': any(cloud_indicators),
        'is_local': not any(cloud_indicators),
        'hostname': os.getenv('HOSTNAME', 'unknown'),
        'python_path': sys.executable
    }

# === CONFIGURAR IMPORTAÇÕES SEGURAS ===
def safe_import(module_name, fallback=None):
    """Importa módulo de forma segura com fallback"""
    try:
        return __import__(module_name)
    except ImportError as e:
        print(f"Warning: Could not import {module_name}: {e}")
        return fallback

# === VERIFICAR DEPENDÊNCIAS ===
def check_dependencies():
    """Verifica se todas as dependências estão instaladas"""
    required_modules = [
        'streamlit',
        'pandas', 
        'pillow',
        'fpdf2',
        'python-dotenv',
        'bcrypt',
        'dropbox',
        'requests'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    return missing

# === CONFIGURAR OTIMIZAÇÕES ===
def apply_cloud_optimizations():
    """Aplica otimizações específicas para o ambiente"""
    env = detect_environment()
    
    if env['is_cloud']:
        # Configurações para Streamlit Cloud
        os.environ.setdefault('STREAMLIT_SERVER_TIMEOUT', '300')
        os.environ.setdefault('STREAMLIT_CLIENT_TIMEOUT', '300')
        
        # Otimizar uso de memória
        os.environ.setdefault('PYTHONOPTIMIZE', '1')
        
        print("✅ Otimizações para Streamlit Cloud aplicadas")
        
    return env

# === INICIALIZAÇÃO SEGURA ===
def safe_initialization():
    """Inicialização segura para evitar erros de import"""
    try:
        # Detectar e configurar ambiente
        env = apply_cloud_optimizations()
        
        # Verificar dependências
        missing = check_dependencies()
        if missing:
            print(f"⚠️ Dependências em falta: {missing}")
        
        return True, env
        
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        return False, None

# Executar inicialização automaticamente quando importado
if __name__ != "__main__":
    safe_initialization()
