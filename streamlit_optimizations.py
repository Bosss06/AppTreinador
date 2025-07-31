# Configuração para melhorar desempenho e evitar timeouts

import os
import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Cache para dados
@st.cache_data(ttl=3600, show_spinner=False)
def load_cached_data():
    """Carrega dados com cache para melhor performance"""
    from data_manager import DataManager
    return DataManager.load_data()

# Cache para cliente Dropbox
@st.cache_resource(ttl=1800, show_spinner=False)
def get_cached_dropbox_client():
    """Obtém cliente Dropbox com cache"""
    from APP_FINAL import get_dropbox_client_with_retry
    return get_dropbox_client_with_retry()

# Configurações de timeout para requests

def create_robust_session():
    """Cria sessão HTTP robusta com retry automático"""
    session = requests.Session()
    
    # Configurar retry automático
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Timeout mais generoso
    session.timeout = 30
    
    return session

# Cache para sessão HTTP
@st.cache_resource
def get_robust_session():
    return create_robust_session()

# Função para verificação de conectividade
def check_internet_connectivity():
    """Verifica conectividade com a internet"""
    try:
        session = get_robust_session()
        response = session.get("https://httpbin.org/get", timeout=10)
        return response.status_code == 200
    except:
        return False

# Otimizações para Streamlit Cloud
def optimize_for_cloud():
    """Aplica otimizações específicas para Streamlit Cloud"""
    
    # Verificar se está no cloud
    from APP_FINAL import is_streamlit_cloud
    
    if is_streamlit_cloud():
        # Reduzir tamanho máximo de upload
        try:
            st.set_option('client.maxMessageSize', 200)
        except:
            pass
        
        # Otimizar cache
        try:
            st.set_option('server.maxUploadSize', 10)
        except:
            pass
        
        # Configurar timeouts mais generosos
        os.environ.setdefault('STREAMLIT_SERVER_TIMEOUT', '300')
        
        return True
    
    return False
