# === APP DO TREINADOR - VERSÃO HÍBRIDA (LOCAL + CLOUD) ===
import os
import json
import bcrypt
import time
import uuid
import streamlit as st
from PIL import Image, ImageOps
from io import BytesIO
from datetime import datetime

# Importar apenas se disponível
try:
    import dropbox
    from dropbox.exceptions import AuthError
    DROPBOX_AVAILABLE = True
except ImportError:
    DROPBOX_AVAILABLE = False

# === CONFIGURAÇÃO OTIMIZADA ===
st.set_page_config(
    page_title="App do Treinador ⚽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === DETECTAR AMBIENTE ===
def is_cloud():
    """Detecta se está no Streamlit Cloud"""
    return (
        'streamlit.app' in os.getenv('HOSTNAME', '') or
        os.getenv('STREAMLIT_SHARING_MODE') == 'true' or
        not os.path.exists('C:\\')
    )

def is_local():
    """Detecta se está rodando localmente"""
    return not is_cloud()

# === CONFIGURAÇÕES DROPBOX (APENAS PARA CLOUD) ===
def get_dropbox_token():
    """Obtém token do Dropbox de forma segura"""
    if is_cloud():
        return st.secrets.get("DROPBOX_ACCESS_TOKEN", os.getenv("DROPBOX_ACCESS_TOKEN"))
    return None

# === CLIENTE DROPBOX SIMPLIFICADO ===
@st.cache_resource(ttl=3600)
def get_dropbox_client():
    """Obtém cliente Dropbox apenas se no cloud e token disponível"""
    if not is_cloud() or not DROPBOX_AVAILABLE:
        return None
    
    token = get_dropbox_token()
    if not token:
        return None
    
    try:
        dbx = dropbox.Dropbox(token)
        # Testar conexão
        dbx.users_get_current_account()
        return dbx
    except Exception as e:
        st.sidebar.warning(f"⚠️ Dropbox: {str(e)[:50]}...")
        return None

# === DATA MANAGER HÍBRIDO ===
class DataManagerHybrid:
    """Gerenciador que funciona local e cloud"""
    
    DATA_FILE = "data/dados_treino.json"
    
    @staticmethod
    def _get_default_data():
        return {
            "jogadores": [],
            "treinos": {},
            "exercicios": {},
            "taticas": [],
            "jogos": []
        }
    
    @staticmethod
    def ensure_data_dir():
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/fotos", exist_ok=True)
    
    @staticmethod
    def load_data():
        DataManagerHybrid.ensure_data_dir()
        
        try:
            if os.path.exists(DataManagerHybrid.DATA_FILE):
                with open(DataManagerHybrid.DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                default_data = DataManagerHybrid._get_default_data()
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                
                return data
            else:
                data = DataManagerHybrid._get_default_data()
                DataManagerHybrid.save_data(data)
                return data
                
        except Exception as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            return DataManagerHybrid._get_default_data()
    
    @staticmethod
    def save_data(data):
        try:
            DataManagerHybrid.ensure_data_dir()
            
            # Backup antes de salvar
            if os.path.exists(DataManagerHybrid.DATA_FILE):
                backup_name = f"{DataManagerHybrid.DATA_FILE}.backup"
                try:
                    with open(DataManagerHybrid.DATA_FILE, 'r') as original:
                        with open(backup_name, 'w') as backup:
                            backup.write(original.read())
                except:
                    pass
            
            # Salvar novos dados
            with open(DataManagerHybrid.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            st.error(f"Erro ao salvar dados: {str(e)}")
            return False

# === CACHE DE DADOS ===
@st.cache_data(ttl=300, show_spinner=False)
def load_data_cached():
    """Carrega dados com cache de 5 minutos"""
    return DataManagerHybrid.load_data()

# === GESTÃO DE FOTOS HÍBRIDA ===
def salvar_foto_local(foto, nome_jogador):
    """Salva foto localmente - SEMPRE funciona"""
    try:
        DataManagerHybrid.ensure_data_dir()
        foto_path = f"data/fotos/{nome_jogador.lower().replace(' ', '_')}.png"
        
        img = ImageOps.fit(Image.open(foto), (300, 300))
        img.save(foto_path)
        return foto_path
    except Exception as e:
        st.error(f"❌ Erro ao salvar foto local: {str(e)}")
        return None

def upload_foto_dropbox_safe(foto_bytes, nome_jogador):
    """Upload seguro para Dropbox - só tenta se configurado"""
    if not is_cloud():
        return None
    
    dbx = get_dropbox_client()
    if not dbx:
        return None
    
    try:
        caminho = f"/app_treinador/fotos/{nome_jogador.lower().replace(' ', '_')}.png"
        dbx.files_upload(foto_bytes, caminho, mode=dropbox.files.WriteMode.overwrite)
        return caminho
    except Exception as e:
        st.warning(f"⚠️ Dropbox falhou: {str(e)[:30]}... (foto salva localmente)")
        return None

def baixar_foto_dropbox_safe(caminho_dropbox):
    """Download seguro do Dropbox"""
    if not caminho_dropbox:
        return None
    
    dbx = get_dropbox_client()
    if not dbx:
        return None
    
    try:
        metadata, response = dbx.files_download(caminho_dropbox)
        return response.content
    except:
        return None

# === AUTENTICAÇÃO ===
class AuthSimples:
    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(password, hashed):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except:
            return False

# === INTERFACE ===
def mostrar_jogador_hybrid(jogador):
    """Mostra jogador com fotos local + cloud"""
    col1, col2 = st.columns([1, 3])
    
    with col1:
        foto_mostrada = False
        
        # 1. Tentar foto do Dropbox (se no cloud)
        if is_cloud() and jogador.get('foto_dropbox'):
            foto_bytes = baixar_foto_dropbox_safe(jogador['foto_dropbox'])
            if foto_bytes:
                st.image(foto_bytes, use_container_width=True)
                foto_mostrada = True
        
        # 2. Tentar foto local
        if not foto_mostrada and jogador.get('foto') and os.path.exists(jogador['foto']):
            st.image(jogador['foto'], use_container_width=True)
            foto_mostrada = True
        
        # 3. Placeholder se nada funcionar
        if not foto_mostrada:
            placeholder_url = f"https://ui-avatars.com/api/?name={jogador.get('nome', '?')[:2]}&background=007acc&color=fff&size=150"
            st.image(placeholder_url, use_container_width=True)
    
    with col2:
        st.write(f"**{jogador.get('nome', 'N/A')}**")
        st.write(f"Posição: {jogador.get('posicao', 'N/A')}")
        st.write(f"Idade: {jogador.get('idade', 'N/A')} anos")
        st.write(f"Número: {jogador.get('nr_camisola', 'N/A')}")

def formulario_jogador_hybrid(jogador_data=None):
    """Formulário híbrido - funciona local e cloud"""
    modo_edicao = jogador_data is not None
    dados = jogador_data or {}
    
    st.subheader("✏️ Editar Jogador" if modo_edicao else "➕ Novo Jogador")
    
    # Mostrar status do ambiente
    if is_cloud():
        dbx = get_dropbox_client()
        if dbx:
            st.info("☁️ Modo Cloud - Dropbox conectado")
        else:
            st.warning("☁️ Modo Cloud - Dropbox não conectado (fotos apenas locais)")
    else:
        st.info("💻 Modo Local - Fotos salvas localmente")
    
    with st.form("form_jogador_hybrid"):
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input("Nome*", value=dados.get('nome', ''))
            login = st.text_input("Login*", value=dados.get('login', ''))
            posicao = st.selectbox("Posição*", 
                                 ["Guarda-Redes", "Defesa", "Médio", "Avançado"],
                                 index=["Guarda-Redes", "Defesa", "Médio", "Avançado"].index(dados.get('posicao', 'Defesa')) if dados.get('posicao') in ["Guarda-Redes", "Defesa", "Médio", "Avançado"] else 1)
            numero = st.number_input("Número da Camisola", 1, 99, value=dados.get('nr_camisola', 1))
        
        with col2:
            idade = st.number_input("Idade*", 16, 45, value=dados.get('idade', 20))
            altura = st.number_input("Altura (cm)*", 150, 220, value=dados.get('altura', 175))
            peso = st.number_input("Peso (kg)*", 50, 120, value=dados.get('peso', 70))
            telefone = st.text_input("Telefone*", value=dados.get('telefone', ''))
        
        email = st.text_input("E-mail*", value=dados.get('email', ''))
        
        if not modo_edicao:
            senha = st.text_input("Senha*", type="password")
        else:
            nova_senha = st.text_input("Nova Senha (deixe vazio para manter)", type="password")
        
        foto = st.file_uploader("Foto (opcional)", type=["jpg", "png", "jpeg"])
        
        submitted = st.form_submit_button("💾 Salvar", type="primary")
        
        if submitted:
            # Validar campos obrigatórios
            campos_obrigatorios = [nome, login, posicao, idade, altura, peso, telefone, email]
            if not modo_edicao:
                campos_obrigatorios.append(senha)
            
            if not all(str(campo).strip() for campo in campos_obrigatorios):
                st.error("❌ Preencha todos os campos obrigatórios (*)")
                return
            
            try:
                # Preparar dados do jogador
                novo_jogador = {
                    "id": dados.get('id', str(uuid.uuid4())),
                    "tipo": "jogador",
                    "nome": nome.strip(),
                    "login": login.lower().strip(),
                    "posicao": posicao,
                    "nr_camisola": numero,
                    "idade": idade,
                    "altura": altura,
                    "peso": peso,
                    "telefone": telefone.strip(),
                    "email": email.strip(),
                    "pontos_fortes": dados.get('pontos_fortes', []),
                    "foto": dados.get('foto', ''),
                    "foto_dropbox": dados.get('foto_dropbox', '')
                }
                
                # Processar senha
                if modo_edicao:
                    if nova_senha:
                        novo_jogador["senha_hash"] = AuthSimples.hash_password(nova_senha)
                    else:
                        novo_jogador["senha_hash"] = dados['senha_hash']
                else:
                    novo_jogador["senha_hash"] = AuthSimples.hash_password(senha)
                
                # Processar foto de forma híbrida
                if foto:
                    # SEMPRE salvar localmente primeiro
                    foto_path = salvar_foto_local(foto, nome)
                    if foto_path:
                        novo_jogador["foto"] = foto_path
                        st.success("📸 Foto salva localmente!")
                        
                        # Se no cloud, tentar Dropbox também
                        if is_cloud():
                            img = ImageOps.fit(Image.open(foto), (300, 300))
                            img_bytes = BytesIO()
                            img.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            
                            caminho_dropbox = upload_foto_dropbox_safe(img_bytes.getvalue(), nome)
                            if caminho_dropbox:
                                novo_jogador["foto_dropbox"] = caminho_dropbox
                                st.success("☁️ Foto também enviada para Dropbox!")
                            else:
                                st.info("ℹ️ Foto salva localmente (Dropbox indisponível)")
                
                # Salvar dados
                data = load_data_cached()
                if modo_edicao:
                    for i, j in enumerate(data.get('jogadores', [])):
                        if j.get('id') == dados.get('id'):
                            data['jogadores'][i] = novo_jogador
                            break
                else:
                    if 'jogadores' not in data:
                        data['jogadores'] = []
                    data['jogadores'].append(novo_jogador)
                
                if DataManagerHybrid.save_data(data):
                    # Limpar cache
                    load_data_cached.clear()
                    
                    st.success("✅ Jogador salvo com sucesso!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Erro ao salvar dados")
                    
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")

# === PÁGINAS ===
def pagina_login_hybrid():
    """Login híbrido"""
    st.title("🔐 Login - App do Treinador")
    
    # Mostrar status
    col1, col2 = st.columns(2)
    with col1:
        if is_cloud():
            st.info("☁️ Modo Cloud")
        else:
            st.info("💻 Modo Local")
    
    with col2:
        if is_cloud():
            dbx = get_dropbox_client()
            if dbx:
                st.success("✅ Dropbox OK")
            else:
                st.warning("⚠️ Dropbox OFF")
    
    with st.form("login_form"):
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            login = st.text_input("👤 Login")
            senha = st.text_input("🔑 Senha", type="password")
            submitted = st.form_submit_button("🚀 Entrar", type="primary")
            
            if submitted:
                if not login or not senha:
                    st.error("❌ Preencha todos os campos")
                    return
                
                # Admin
                if login == "admin" and senha == "admin123":
                    st.session_state.autenticado = True
                    st.session_state.tipo_usuario = "treinador"
                    st.session_state.user = "Administrador"
                    st.success("✅ Login realizado com sucesso!")
                    time.sleep(1)
                    st.rerun()
                    return
                
                # Jogadores
                data = load_data_cached()
                for jogador in data.get('jogadores', []):
                    if (jogador.get('login') == login.lower() and 
                        jogador.get('senha_hash') and
                        AuthSimples.verify_password(senha, jogador['senha_hash'])):
                        st.session_state.autenticado = True
                        st.session_state.tipo_usuario = "jogador"
                        st.session_state.user = jogador.get('nome', login)
                        st.session_state.jogador_info = jogador
                        st.success("✅ Login realizado com sucesso!")
                        time.sleep(1)
                        st.rerun()
                        return
                
                st.error("❌ Login ou senha incorretos")

def pagina_jogadores_hybrid():
    """Gestão de jogadores híbrida"""
    st.title("👥 Gestão de Jogadores")
    
    # Status do sistema
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("➕ Novo Jogador"):
            st.session_state.show_form = True
    with col2:
        data = load_data_cached()
        st.metric("👥 Total", len(data.get('jogadores', [])))
    with col3:
        if is_cloud():
            dbx = get_dropbox_client()
            if dbx:
                st.success("☁️ Dropbox OK")
            else:
                st.warning("☁️ Local Only")
        else:
            st.info("💻 Local Mode")
    with col4:
        if st.button("🔄 Atualizar"):
            load_data_cached.clear()
            st.rerun()
    
    # Formulários
    if st.session_state.get('show_form'):
        formulario_jogador_hybrid()
        if st.button("❌ Cancelar"):
            st.session_state.show_form = False
            st.rerun()
        st.divider()
    
    if st.session_state.get('edit_player'):
        formulario_jogador_hybrid(st.session_state['edit_player'])
        if st.button("❌ Cancelar Edição"):
            del st.session_state['edit_player']
            st.rerun()
        st.divider()
    
    # Lista de jogadores
    data = load_data_cached()
    jogadores = data.get('jogadores', [])
    
    if not jogadores:
        st.info("ℹ️ Nenhum jogador cadastrado ainda.")
        return
    
    st.subheader(f"📋 Jogadores ({len(jogadores)})")
    
    for jogador in jogadores:
        with st.container():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                mostrar_jogador_hybrid(jogador)
            
            with col2:
                if st.button("✏️", key=f"edit_{jogador['id']}", help="Editar"):
                    st.session_state.edit_player = jogador
                    if 'show_form' in st.session_state:
                        del st.session_state['show_form']
                    st.rerun()
                
                if st.button("🗑️", key=f"del_{jogador['id']}", help="Remover"):
                    data['jogadores'] = [j for j in data['jogadores'] if j['id'] != jogador['id']]
                    if DataManagerHybrid.save_data(data):
                        load_data_cached.clear()
                        st.success(f"✅ {jogador['nome']} removido!")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()

def pagina_dashboard_hybrid():
    """Dashboard híbrido"""
    st.title("📊 Dashboard")
    
    data = load_data_cached()
    jogadores = data.get('jogadores', [])
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 Jogadores", len(jogadores))
    with col2:
        st.metric("🥅 Guarda-Redes", len([j for j in jogadores if j.get('posicao') == 'Guarda-Redes']))
    with col3:
        st.metric("🛡️ Defesas", len([j for j in jogadores if j.get('posicao') == 'Defesa']))
    with col4:
        st.metric("⚽ Avançados", len([j for j in jogadores if j.get('posicao') == 'Avançado']))
    
    # Status do sistema
    st.subheader("🔧 Status do Sistema")
    col1, col2 = st.columns(2)
    
    with col1:
        if is_cloud():
            st.info("☁️ **Streamlit Cloud**")
            dbx = get_dropbox_client()
            if dbx:
                st.success("✅ Dropbox conectado e funcional")
            else:
                st.warning("⚠️ Dropbox não conectado - usando apenas local")
        else:
            st.info("💻 **Modo Local**")
            st.success("✅ Todas as fotos salvas localmente")
    
    with col2:
        st.metric("📁 Arquivos de dados", "JSON")
        st.metric("📸 Storage de fotos", "Local + Cloud" if is_cloud() else "Local")
    
    if jogadores:
        st.subheader("👥 Últimos Jogadores")
        for jogador in sorted(jogadores, key=lambda x: x.get('id', ''), reverse=True)[:3]:
            mostrar_jogador_hybrid(jogador)
            st.divider()

# === SIDEBAR ===
def show_sidebar_hybrid():
    """Sidebar híbrida"""
    with st.sidebar:
        st.write("### 🎯 Status")
        
        data = load_data_cached()
        st.metric("👥 Jogadores", len(data.get('jogadores', [])))
        
        if is_cloud():
            st.info("☁️ Cloud Mode")
            dbx = get_dropbox_client()
            if dbx:
                st.success("✅ Dropbox OK")
            else:
                st.error("❌ Dropbox OFF")
        else:
            st.info("💻 Local Mode")
        
        st.divider()
        
        if st.button("🔄 Atualizar"):
            load_data_cached.clear()
            st.rerun()
        
        if st.button("🚪 Logout"):
            for key in ['autenticado', 'tipo_usuario', 'user', 'jogador_info']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# === MAIN ===
def main():
    """Aplicação híbrida"""
    
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.get('autenticado'):
        pagina_login_hybrid()
        return
    
    show_sidebar_hybrid()
    
    if st.session_state.get('tipo_usuario') == 'treinador':
        tab1, tab2 = st.tabs(["📊 Dashboard", "👥 Jogadores"])
        
        with tab1:
            pagina_dashboard_hybrid()
        
        with tab2:
            pagina_jogadores_hybrid()
    
    else:
        st.title(f"👋 Bem-vindo, {st.session_state.get('user', 'Jogador')}!")
        
        jogador_info = st.session_state.get('jogador_info', {})
        if jogador_info:
            mostrar_jogador_hybrid(jogador_info)

if __name__ == "__main__":
    main()
