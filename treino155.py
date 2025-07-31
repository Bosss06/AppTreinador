# === APP DO TREINADOR - VERSÃO SIMPLIFICADA E OTIMIZADA ===
import os
import json
import bcrypt
import time
import uuid
import streamlit as st
from PIL import Image, ImageOps
from io import BytesIO
from datetime import datetime
from data_manager_simples import DataManager
import dropbox
from dropbox.exceptions import AuthError

# === CONFIGURAÇÃO OTIMIZADA ===
st.set_page_config(
    page_title="App do Treinador ⚽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === CONFIGURAÇÕES SIMPLES ===
DROPBOX_TOKEN = st.secrets.get("DROPBOX_ACCESS_TOKEN", os.getenv("DROPBOX_ACCESS_TOKEN"))

# === VERIFICAR SE É CLOUD ===
def is_cloud():
    """Detecta se está no Streamlit Cloud de forma simples"""
    return (
        'streamlit.app' in os.getenv('HOSTNAME', '') or
        os.getenv('STREAMLIT_SHARING_MODE') == 'true' or
        not os.path.exists('C:\\')
    )

# === CLIENTE DROPBOX SIMPLES ===
@st.cache_resource(ttl=3600)
def get_dropbox_client():
    """Obtém cliente Dropbox simples e eficiente"""
    if not DROPBOX_TOKEN:
        return None
    try:
        return dropbox.Dropbox(DROPBOX_TOKEN)
    except:
        return None

# === CACHE DE DADOS ===
@st.cache_data(ttl=300, show_spinner=False)
def load_data_cached():
    """Carrega dados com cache de 5 minutos"""
    return DataManager.load_data()

# === GESTÃO DE FOTOS SIMPLIFICADA ===
def upload_foto_dropbox(foto_bytes, nome_jogador):
    """Upload de foto para Dropbox - Versão Simplificada"""
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
        st.error(f"❌ Erro no upload: {str(e)}")
        return None

def baixar_foto_dropbox(caminho_dropbox):
    """Download de foto do Dropbox - Versão Simplificada"""
    dbx = get_dropbox_client()
    if not dbx or not caminho_dropbox:
        return None
    
    try:
        metadata, response = dbx.files_download(caminho_dropbox)
        return response.content
    except:
        return None

def salvar_foto_local(foto, nome_jogador):
    """Salva foto localmente"""
    try:
        os.makedirs("data/fotos", exist_ok=True)
        foto_path = f"data/fotos/{nome_jogador.lower().replace(' ', '_')}.png"
        
        img = ImageOps.fit(Image.open(foto), (300, 300))
        img.save(foto_path)
        return foto_path
    except Exception as e:
        st.error(f"❌ Erro ao salvar foto: {str(e)}")
        return None

# === BACKUP SIMPLIFICADO ===
def criar_backup_simples():
    """Cria backup simples dos dados"""
    try:
        data = DataManager.load_data()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Backup local
        if not is_cloud():
            os.makedirs("backups", exist_ok=True)
            backup_path = f"backups/backup_simples_{timestamp}.json"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Backup Dropbox se no cloud
        if is_cloud():
            dbx = get_dropbox_client()
            if dbx:
                backup_content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                dbx.files_upload(backup_content, f"/app_treinador/backup_simples_{timestamp}.json", 
                               mode=dropbox.files.WriteMode.overwrite)
        
        return True
    except Exception as e:
        st.error(f"❌ Erro no backup: {str(e)}")
        return False

# === AUTENTICAÇÃO SIMPLIFICADA ===
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

# === INTERFACE SIMPLIFICADA ===
def mostrar_jogador_simples(jogador):
    """Mostra card de jogador de forma simples"""
    col1, col2 = st.columns([1, 3])
    
    with col1:
        foto_mostrada = False
        
        # Tentar mostrar foto
        if is_cloud() and jogador.get('foto_dropbox'):
            foto_bytes = baixar_foto_dropbox(jogador['foto_dropbox'])
            if foto_bytes:
                st.image(foto_bytes, use_container_width=True)
                foto_mostrada = True
        
        if not foto_mostrada and jogador.get('foto') and os.path.exists(jogador['foto']):
            st.image(jogador['foto'], use_container_width=True)
            foto_mostrada = True
        
        if not foto_mostrada:
            st.image("https://via.placeholder.com/150?text=" + jogador.get('nome', '?')[:2], 
                    use_container_width=True)
    
    with col2:
        st.write(f"**{jogador.get('nome', 'N/A')}**")
        st.write(f"Posição: {jogador.get('posicao', 'N/A')}")
        st.write(f"Idade: {jogador.get('idade', 'N/A')} anos")
        st.write(f"Número: {jogador.get('nr_camisola', 'N/A')}")

def formulario_jogador_simples(jogador_data=None):
    """Formulário simplificado para jogador"""
    modo_edicao = jogador_data is not None
    dados = jogador_data or {}
    
    st.subheader("✏️ Editar Jogador" if modo_edicao else "➕ Novo Jogador")
    
    with st.form("form_jogador_simples"):
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
                
                # Processar foto
                if foto:
                    if is_cloud():
                        # Upload para Dropbox
                        img = ImageOps.fit(Image.open(foto), (300, 300))
                        img_bytes = BytesIO()
                        img.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        caminho_dropbox = upload_foto_dropbox(img_bytes.getvalue(), nome)
                        if caminho_dropbox:
                            novo_jogador["foto_dropbox"] = caminho_dropbox
                            st.success("📸 Foto enviada para Dropbox!")
                    else:
                        # Salvar localmente
                        foto_path = salvar_foto_local(foto, nome)
                        if foto_path:
                            novo_jogador["foto"] = foto_path
                
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
                
                if DataManager.save_data(data):
                    # Limpar cache
                    load_data_cached.clear()
                    
                    # Criar backup
                    criar_backup_simples()
                    
                    st.success("✅ Jogador salvo com sucesso!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Erro ao salvar dados")
                    
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")

# === PÁGINAS SIMPLIFICADAS ===
def pagina_login_simples():
    """Página de login simplificada"""
    st.title("🔐 Login - App do Treinador")
    
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
                
                # Verificar admin
                if login == "admin" and senha == "admin123":
                    st.session_state.autenticado = True
                    st.session_state.tipo_usuario = "treinador"
                    st.session_state.user = "Administrador"
                    st.success("✅ Login realizado com sucesso!")
                    time.sleep(1)
                    st.rerun()
                    return
                
                # Verificar jogadores
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

def pagina_jogadores_simples():
    """Página de gestão de jogadores simplificada"""
    st.title("👥 Gestão de Jogadores")
    
    # Botões de ação
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("➕ Novo Jogador"):
            st.session_state.show_form = True
    with col2:
        if st.button("🔄 Backup"):
            if criar_backup_simples():
                st.success("✅ Backup criado!")
    with col3:
        if st.button("🔄 Atualizar"):
            load_data_cached.clear()
            st.rerun()
    
    # Formulário de novo jogador
    if st.session_state.get('show_form'):
        formulario_jogador_simples()
        if st.button("❌ Cancelar"):
            st.session_state.show_form = False
            st.rerun()
        st.divider()
    
    # Formulário de edição
    if st.session_state.get('edit_player'):
        formulario_jogador_simples(st.session_state['edit_player'])
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
    
    st.subheader(f"📋 Jogadores Cadastrados ({len(jogadores)})")
    
    for jogador in jogadores:
        with st.container():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                mostrar_jogador_simples(jogador)
            
            with col2:
                if st.button("✏️", key=f"edit_{jogador['id']}", help="Editar"):
                    st.session_state.edit_player = jogador
                    if 'show_form' in st.session_state:
                        del st.session_state['show_form']
                    st.rerun()
                
                if st.button("🗑️", key=f"del_{jogador['id']}", help="Remover"):
                    data['jogadores'] = [j for j in data['jogadores'] if j['id'] != jogador['id']]
                    if DataManager.save_data(data):
                        load_data_cached.clear()
                        st.success(f"✅ {jogador['nome']} removido!")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()

def pagina_dashboard_simples():
    """Dashboard simplificado"""
    st.title("📊 Dashboard")
    
    data = load_data_cached()
    jogadores = data.get('jogadores', [])
    
    # Métricas básicas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 Jogadores", len(jogadores))
    with col2:
        st.metric("🥅 Guarda-Redes", len([j for j in jogadores if j.get('posicao') == 'Guarda-Redes']))
    with col3:
        st.metric("🛡️ Defesas", len([j for j in jogadores if j.get('posicao') == 'Defesa']))
    with col4:
        st.metric("⚽ Avançados", len([j for j in jogadores if j.get('posicao') == 'Avançado']))
    
    if jogadores:
        st.subheader("👥 Últimos Jogadores Adicionados")
        for jogador in sorted(jogadores, key=lambda x: x.get('id', ''), reverse=True)[:3]:
            mostrar_jogador_simples(jogador)
            st.divider()

# === SIDEBAR SIMPLIFICADA ===
def show_sidebar():
    """Sidebar simplificada com informações essenciais"""
    with st.sidebar:
        st.write("### 🎯 Status da App")
        
        # Status básico
        data = load_data_cached()
        st.metric("👥 Jogadores", len(data.get('jogadores', [])))
        
        # Dropbox status
        if is_cloud():
            dbx = get_dropbox_client()
            if dbx:
                st.success("☁️ Dropbox conectado")
            else:
                st.error("❌ Dropbox desconectado")
        else:
            st.info("💻 Modo local")
        
        st.divider()
        
        # Ações rápidas
        if st.button("🔄 Backup Rápido"):
            if criar_backup_simples():
                st.success("✅ Backup criado!")
        
        if st.button("🔄 Limpar Cache"):
            load_data_cached.clear()
            st.success("✅ Cache limpo!")
        
        if st.button("🚪 Logout"):
            for key in ['autenticado', 'tipo_usuario', 'user', 'jogador_info']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# === APLICAÇÃO PRINCIPAL ===
def main():
    """Aplicação principal simplificada"""
    
    # Inicializar session state
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    # Verificar autenticação
    if not st.session_state.get('autenticado'):
        pagina_login_simples()
        return
    
    # Mostrar sidebar
    show_sidebar()
    
    # Menu principal
    if st.session_state.get('tipo_usuario') == 'treinador':
        tab1, tab2 = st.tabs(["📊 Dashboard", "👥 Jogadores"])
        
        with tab1:
            pagina_dashboard_simples()
        
        with tab2:
            pagina_jogadores_simples()
    
    else:
        # Área do jogador
        st.title(f"👋 Bem-vindo, {st.session_state.get('user', 'Jogador')}!")
        
        jogador_info = st.session_state.get('jogador_info', {})
        if jogador_info:
            mostrar_jogador_simples(jogador_info)

if __name__ == "__main__":
    main()
