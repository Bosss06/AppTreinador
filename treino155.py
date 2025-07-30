import os
import json
import bcrypt
import logging
import smtplib
import uuid
from datetime import datetime, date
from io import BytesIO
from typing import Dict, List, Optional
import time
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
from fpdf import FPDF, HTMLMixin
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from data_manager import DataManager
import dropbox
from dropbox import Dropbox
from dropbox.exceptions import AuthError, ApiError, HttpError
import calendar

# === CONFIGURAÇÃO PARA STREAMLIT CLOUD ===
def ensure_directories():
    """Garante que as pastas essenciais existem (importante para Streamlit Cloud)"""
    directories = ["data", "data/fotos", "backups", "data/backups"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # Para Streamlit Cloud: verificar se fotos placeholder existem
    fotos_dir = "data/fotos"
    fotos_esperadas = [
        "fabio.png", "rafa.png", "freitas.png", "gui.png", "dani.png",
        "cardoso.png", "moura.png", "oliveira.png", "joel.png", "rsilva.png"
    ]
    
    for foto in fotos_esperadas:
        foto_path = os.path.join(fotos_dir, foto)
        if not os.path.exists(foto_path):
            # Criar placeholder mínimo
            try:
                with open(foto_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Placeholder para {foto} - gerado automaticamente\n")
            except:
                pass  # Falha silenciosa para evitar crash

# Executar configuração inicial
ensure_directories()

# === FUNÇÃO PARA CORRIGIR PROBLEMAS DE CODIFICAÇÃO ===
def fix_env_encoding():
    """Corrige problemas de codificação no arquivo .env"""
    env_file = ".env"
    if os.path.exists(env_file):
        try:
            # Tentar ler com UTF-8
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return True
        except UnicodeDecodeError:
            try:
                # Tentar ler com codificação Windows
                with open(env_file, 'r', encoding='latin-1') as f:
                    content = f.read()
                
                # Reescrever em UTF-8
                with open(env_file, 'w', encoding='utf-8') as f:
                    # Remover caracteres problemáticos
                    clean_content = content.replace('ç', 'c').replace('ã', 'a').replace('õ', 'o')
                    f.write(clean_content)
                
                st.success("✅ Arquivo .env corrigido para UTF-8")
                return True
            except Exception as e:
                st.error(f"❌ Erro ao corrigir .env: {str(e)}")
                return False
    return True

# Executar correção na inicialização
fix_env_encoding()

# === FUNÇÕES ESPECÍFICAS PARA STREAMLIT CLOUD ===
def is_streamlit_cloud():
    """Detecta se está rodando no Streamlit Cloud"""
    # Múltiplas verificações para detectar Streamlit Cloud
    cloud_indicators = [
        os.getenv('STREAMLIT_SHARING_MODE') == 'true',
        'streamlit.app' in os.getenv('HOSTNAME', ''),
        'streamlit' in os.getenv('HOSTNAME', ''),
        os.getenv('STREAMLIT_SERVER_PORT') is not None,
        not os.path.exists('C:\\'),  # Não é Windows local
        os.path.exists('/app')  # Diretório típico do container
    ]
    
    return any(cloud_indicators)

def create_cloud_safe_backup():
    """Cria backup otimizado para Streamlit Cloud"""
    try:
        # No Streamlit Cloud, priorizar backup no Dropbox
        if is_streamlit_cloud():
            st.info("🌐 Detectado Streamlit Cloud - Priorizando backup no Dropbox")
            return DataManager.create_secure_backup(dropbox_only=True)
        else:
            # Localmente, usar backup normal
            return DataManager.create_secure_backup()
    except Exception as e:
        st.error(f"❌ Erro no backup: {str(e)}")
        return False

def handle_photos_for_cloud():
    """Garante que fotos existem para backup no Streamlit Cloud"""
    fotos_dir = "data/fotos"
    if not os.path.exists(fotos_dir):
        os.makedirs(fotos_dir, exist_ok=True)
    
    # Verificar se há fotos reais ou placeholders
    photos = [f for f in os.listdir(fotos_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not photos:
        st.warning("⚠️ Nenhuma foto encontrada. Criando estrutura básica...")
        ensure_directories()  # Re-executar para criar placeholders
        return False
    
    return True
import requests
import calendar

# --- Configurações Iniciais ---
# Carregar variáveis de ambiente com tratamento de erro
try:
    load_dotenv()
except UnicodeDecodeError:
    # Se houver erro de codificação no .env, tentar recriar
    st.warning("⚠️ Problema de codificação no arquivo .env detectado. Reconfiguração necessária.")
    # Continuar sem .env - usar variáveis de ambiente do sistema
    pass
except Exception as e:
    st.error(f"❌ Erro ao carregar .env: {str(e)}")
    pass

st.set_page_config(
    page_title="App do Treinador PRO ⚽", 
    layout="wide",
    initial_sidebar_state="expanded"
)
logging.basicConfig(level=logging.INFO)

def auto_refresh_dropbox_token():
    """Tenta renovar automaticamente o token do Dropbox se necessário"""
    try:
        import requests
        
        refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
        app_key = os.getenv('DROPBOX_APP_KEY')
        app_secret = os.getenv('DROPBOX_APP_SECRET')
        
        if not all([refresh_token, app_key, app_secret]):
            return False
            
        # Fazer requisição para renovar o token
        auth_url = 'https://api.dropbox.com/oauth2/token'
        auth_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': app_key,
            'client_secret': app_secret
        }
        
        response = requests.post(auth_url, data=auth_data)
        
        if response.status_code == 200:
            token_data = response.json()
            new_access_token = token_data.get('access_token')
            
            if new_access_token:
                # Atualizar a variável de ambiente temporariamente
                os.environ['DROPBOX_ACCESS_TOKEN'] = new_access_token
                return True
                
    except Exception as e:
        print(f"Erro ao renovar token Dropbox: {str(e)}")
        
    return False

def get_dropbox_client_with_retry():
    """Obtém cliente Dropbox com tentativa de renovação automática"""
    try:
        # Primeira tentativa com token atual
        token = os.getenv('DROPBOX_ACCESS_TOKEN')
        if token:
            dbx = Dropbox(token)
            # Testar se o token está válido
            dbx.users_get_current_account()
            return dbx
    except AuthError:
        # Token expirado, tentar renovar
        if auto_refresh_dropbox_token():
            try:
                new_token = os.getenv('DROPBOX_ACCESS_TOKEN')
                dbx = Dropbox(new_token)
                # Testar novamente
                dbx.users_get_current_account()
                return dbx
            except:
                pass
    except Exception:
        pass
    
    return None

def create_backup_with_auto_retry(local_only=False, dropbox_only=False):
    """Cria backup com tentativa automática de renovação do token Dropbox - Otimizado para Cloud"""
    try:
        # Para Streamlit Cloud: garantir estrutura de fotos
        if is_streamlit_cloud():
            handle_photos_for_cloud()
            # No cloud, priorizar Dropbox se não especificado local_only
            if not local_only:
                dropbox_only = True
        
        if dropbox_only or not local_only:
            # Se vai usar Dropbox, garantir que temos cliente válido
            dbx = get_dropbox_client_with_retry()
            if not dbx and (dropbox_only or not local_only):
                if local_only:
                    return False
                # Se não conseguiu Dropbox mas não é local_only, tentar só local
                return DataManager.create_secure_backup(local_only=True)
        
        # Usar a função original do DataManager
        return DataManager.create_secure_backup(local_only=local_only, dropbox_only=dropbox_only)
        
    except Exception as e:
        print(f"Erro ao criar backup: {str(e)}")
        # Se falhar e não for local_only, tentar backup local
        if not local_only and not is_streamlit_cloud():
            try:
                return DataManager.create_secure_backup(local_only=True)
            except:
                pass
        return False

def list_dropbox_backups_with_retry():
    """Lista backups do Dropbox com renovação automática do token"""
    try:
        dbx = get_dropbox_client_with_retry()
        if not dbx:
            return []
        
        # Usar a função original do DataManager mas com nosso cliente
        return DataManager.list_dropbox_backups()
        
    except Exception as e:
        print(f"Erro ao listar backups do Dropbox: {str(e)}")
        return []

def restore_from_dropbox_with_retry(backup_name, restore_photos=True):
    """Restaura backup do Dropbox com renovação automática do token"""
    try:
        dbx = get_dropbox_client_with_retry()
        if not dbx:
            return False
        
        # Usar a função original do DataManager
        return DataManager.restore_from_dropbox(backup_name, restore_photos)
        
    except Exception as e:
        print(f"Erro ao restaurar backup do Dropbox: {str(e)}")
        return False

def pagina_calendario_treinos():
    """Página de calendário de treinos para visualização mensal e semanal"""
    st.title("📅 Calendário de Treinos")
    
    data = DataManager.load_data()
    treinos = data.get('treinos', {})
    
    if not treinos:
        st.info("📅 Nenhum treino agendado")
        return
    
    # Filtro por jogador (se não for treinador)
    is_treinador = st.session_state.get('tipo_usuario') == 'treinador'
    jogador_info = st.session_state.get('jogador_info', {})
    jogador_nome = jogador_info.get('nome') if not is_treinador else None
    
    # Seleção do mês/ano
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        ano_atual = datetime.now().year
        ano = st.selectbox("Ano", range(ano_atual - 1, ano_atual + 2), index=1)
    
    with col2:
        mes_atual = datetime.now().month
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_nome = st.selectbox("Mês", meses, index=mes_atual - 1)
        mes = meses.index(mes_nome) + 1
    
    with col3:
        view_type = st.radio("Visualização", ["📅 Mensal", "📊 Semanal"], horizontal=True)
    
    # Filtrar treinos do mês/ano selecionado
    treinos_filtrados = {}
    for data_treino, detalhes in treinos.items():
        try:
            # Verificar se é uma data válida (formato YYYY-MM-DD)
            if len(data_treino) == 10 and data_treino.count('-') == 2:
                treino_date = datetime.strptime(data_treino, '%Y-%m-%d')
                if treino_date.year == ano and treino_date.month == mes:
                    # Se for jogador, filtrar apenas treinos onde está convocado
                    if not is_treinador:
                        participantes = detalhes.get('participantes', [])
                        if jogador_nome in participantes:
                            treinos_filtrados[data_treino] = detalhes
                    else:
                        treinos_filtrados[data_treino] = detalhes
        except ValueError:
            # Ignorar entradas que não são datas válidas (como UUIDs)
            continue
    
    if view_type == "📅 Mensal":
        exibir_calendario_mensal(ano, mes, treinos_filtrados)
    else:
        exibir_calendario_semanal(ano, mes, treinos_filtrados)

def exibir_calendario_mensal(ano, mes, treinos):
    """Exibe calendário mensal com treinos"""
    st.subheader(f"📅 {calendar.month_name[mes]} {ano}")
    
    # Obter calendário do mês
    cal = calendar.monthcalendar(ano, mes)
    dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    
    # Cabeçalho dos dias da semana
    cols = st.columns(7)
    for i, dia in enumerate(dias_semana):
        cols[i].markdown(f"**{dia}**")
    
    # Exibir calendário
    for semana in cal:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            if dia == 0:
                cols[i].write("")  # Dias vazios
            else:
                data_str = f"{ano}-{mes:02d}-{dia:02d}"
                
                if data_str in treinos:
                    # Dia com treino
                    treino = treinos[data_str]
                    objetivo = treino.get('objetivo', 'Treino')
                    hora = treino.get('hora', '')
                    
                    # Determinar cor baseada no tipo de treino
                    cor = get_cor_treino(objetivo)
                    
                    with cols[i].container():
                        st.markdown(f"""
                        <div style="
                            background-color: {cor}; 
                            padding: 8px; 
                            border-radius: 5px; 
                            margin: 2px 0;
                            border: 1px solid #ddd;
                        ">
                            <strong>{dia}</strong><br>
                            <small>{hora}</small><br>
                            <small>{objetivo[:15]}...</small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Expandir detalhes do treino
                        if st.button(f"Ver", key=f"treino_{data_str}"):
                            exibir_detalhes_treino(data_str, treino)
                else:
                    # Dia sem treino
                    cols[i].markdown(f"""
                    <div style="
                        padding: 8px; 
                        text-align: center;
                        color: #888;
                    ">
                        {dia}
                    </div>
                    """, unsafe_allow_html=True)

def exibir_calendario_semanal(ano, mes, treinos):
    """Exibe calendário semanal detalhado"""
    st.subheader(f"📊 Vista Semanal - {calendar.month_name[mes]} {ano}")
    
    # Agrupar treinos por semana
    treinos_por_semana = {}
    for data_str, treino in treinos.items():
        data_obj = datetime.strptime(data_str, '%Y-%m-%d')
        semana = data_obj.isocalendar()[1]  # Número da semana
        
        if semana not in treinos_por_semana:
            treinos_por_semana[semana] = []
        treinos_por_semana[semana].append((data_str, treino))
    
    if not treinos_por_semana:
        st.info("📅 Nenhum treino agendado para este mês")
        return
    
    # Exibir cada semana
    for semana in sorted(treinos_por_semana.keys()):
        treinos_semana = sorted(treinos_por_semana[semana])
        
        st.write(f"**Semana {semana}**")
        
        for data_str, treino in treinos_semana:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d')
            dia_semana = data_obj.strftime('%A')
            data_formatada = data_obj.strftime('%d/%m/%Y')
            
            # Traduzir dia da semana
            dias_pt = {
                'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 
                'Wednesday': 'Quarta-feira', 'Thursday': 'Quinta-feira',
                'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }
            dia_semana_pt = dias_pt.get(dia_semana, dia_semana)
            
            with st.expander(f"🏃 {dia_semana_pt}, {data_formatada} - {treino.get('objetivo', 'Treino')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**⏰ Hora:** {treino.get('hora', 'Não definida')}")
                    st.write(f"**📍 Local:** {treino.get('local', 'Não definido')}")
                    st.write(f"**⏱️ Duração:** {treino.get('duracao', 90)} minutos")
                
                with col2:
                    st.write(f"**🎯 Objetivo:** {treino.get('objetivo', 'Não definido')}")
                    
                    participantes = treino.get('participantes', [])
                    if participantes:
                        st.write(f"**👥 Participantes:** {len(participantes)}")
                        with st.expander("Ver lista"):
                            for p in participantes:
                                st.write(f"• {p}")
                
                # Exercícios
                exercicios = treino.get('exercicios', [])
                if exercicios:
                    st.write("**🏋️ Exercícios:**")
                    if isinstance(exercicios[0], dict):
                        # Exercícios detalhados (como Treino Nº 6)
                        for ex in exercicios:
                            st.write(f"• **{ex.get('nome', 'Exercício')}** ({ex.get('duracao', 0)} min)")
                            if ex.get('descricao'):
                                st.write(f"  _{ex.get('descricao')}_")
                    else:
                        # Lista simples de exercícios
                        for ex in exercicios:
                            st.write(f"• {ex}")
        
        st.divider()

def get_cor_treino(objetivo):
    """Retorna cor baseada no tipo de treino"""
    objetivo_lower = objetivo.lower()
    
    if 'físico' in objetivo_lower or 'resistência' in objetivo_lower:
        return '#ffebee'  # Vermelho claro
    elif 'técnica' in objetivo_lower or 'técnico' in objetivo_lower:
        return '#e8f5e8'  # Verde claro  
    elif 'tático' in objetivo_lower or 'tática' in objetivo_lower:
        return '#e3f2fd'  # Azul claro
    elif 'jogo' in objetivo_lower:
        return '#fff3e0'  # Laranja claro
    else:
        return '#f5f5f5'  # Cinza claro

def exibir_detalhes_treino(data_str, treino):
    """Exibe detalhes completos do treino em modal"""
    data_obj = datetime.strptime(data_str, '%Y-%m-%d')
    data_formatada = data_obj.strftime('%d/%m/%Y')
    
    st.info(f"**Treino de {data_formatada}**")
    st.write(f"**Objetivo:** {treino.get('objetivo', 'Não definido')}")
    st.write(f"**Hora:** {treino.get('hora', 'Não definida')}")
    st.write(f"**Local:** {treino.get('local', 'Não definido')}")
    st.write(f"**Duração:** {treino.get('duracao', 90)} minutos")

# Função para manter a app ativa
def keep_alive():
    """Mantém a aplicação ativa fazendo pequenas operações em background"""
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = time.time()
    
    current_time = time.time()
    # Se passou mais de 10 minutos sem atividade, faz uma operação pequena
    if current_time - st.session_state.last_activity > 600:  # 10 minutos
        st.session_state.last_activity = current_time
        # Operação invisível para manter sessão ativa
        _ = DataManager.load_data()

# Script JavaScript para manter atividade
def inject_keep_alive_script():
    """Injeta JavaScript para manter a sessão ativa"""
    st.markdown("""
    <script>
    // Ping a cada 5 minutos para manter sessão ativa
    setInterval(function() {
        fetch(window.location.href, {
            method: 'HEAD'
        }).catch(function() {
            // Ignorar erros
        });
    }, 300000); // 5 minutos
    
    // Detectar atividade do usuário
    let lastActivity = Date.now();
    
    ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'].forEach(function(event) {
        document.addEventListener(event, function() {
            lastActivity = Date.now();
        }, true);
    });
    
    // Verificar inatividade
    setInterval(function() {
        if (Date.now() - lastActivity < 600000) { // 10 minutos
            // Usuário ativo, fazer ping
            fetch(window.location.href, {
                method: 'HEAD'
            }).catch(function() {});
        }
    }, 60000); // Verificar a cada minuto
    </script>
    """, unsafe_allow_html=True)

# --- Constantes ---
ASSETS_DIR = "assets"
BACKUP_DIR = "data/backups/"

# Caminhos das imagens locais
IMAGE_PATHS = {
    "campo": os.path.join(ASSETS_DIR, "campo_futebol.png"),
    "aquecimento": os.path.join(ASSETS_DIR, "aquecimento_icon.png"),
    "principal": os.path.join(ASSETS_DIR, "parte_principal_icon.png"),
    "volta_calma": os.path.join(ASSETS_DIR, "volta_calma_icon.png"),
    "logo": os.path.join(ASSETS_DIR, "logo.png")
}

# --- Classes Principais ---
class Authentication:
    """Gerencia autenticação de usuários"""
    def __init__(self):
        pass
         
    
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def login(self, username: str, password: str) -> bool:
        try:
            # Debug: mostrar tentativa de login
            logging.info(f"Tentativa de login: {username}")
            
            # Verifica admin
            admin_user = os.getenv('ADMIN_USER')
            admin_hash = os.getenv('ADMIN_PASSWORD_HASH')
            
            logging.info(f"Admin configurado: {admin_user}, Hash existe: {bool(admin_hash)}")
        
            if username == admin_user and admin_hash:
                if bcrypt.checkpw(password.encode('utf-8'), admin_hash.encode('utf-8')):
                    logging.info(f"Login admin bem-sucedido: {username}")
                    st.session_state.update({
                        'autenticado': True,
                        'tipo_usuario': 'treinador',
                        'user': admin_user,
                        'jogador_info': None
                    })
                    return True
                else:
                    logging.warning(f"Senha incorreta para admin: {username}")

            # Verifica jogadores
            data = DataManager.load_data()
            jogadores_com_senha = [j for j in data.get('jogadores', []) if j.get('senha_hash')]
            logging.info(f"Jogadores com senha configurada: {len(jogadores_com_senha)}")
            
            for jogador in jogadores_com_senha:
                login_jogador = jogador.get('login', jogador['nome'].lower().replace(' ', '_'))
                if login_jogador.lower() == username.lower():
                    logging.info(f"Jogador encontrado: {jogador['nome']} (login: {login_jogador})")
                    if bcrypt.checkpw(password.encode('utf-8'), jogador['senha_hash'].encode('utf-8')):
                        logging.info(f"Login jogador bem-sucedido: {username}")
                        st.session_state.update({
                            'autenticado': True,
                            'tipo_usuario': jogador.get('tipo', 'jogador'),
                            'user': jogador['nome'],
                            'jogador_info': jogador
                        })
                        return True
                    else:
                        logging.warning(f"Senha incorreta para jogador: {username}")
                        
            logging.warning(f"Usuário não encontrado: {username}")
            return False
        except Exception as e:
            logging.error(f"Erro na autenticação: {str(e)}")
            return False
            return False

class PDFGenerator:
    """Gera PDFs profissionais para planos de treino"""
    @staticmethod
    def gerar_plano_treino(dados: Dict) -> str:
        try:
            # Verificar assets
            if not PDFGenerator._verificar_assets():
                raise Exception("Assets necessários não encontrados")
            
            pdf = FPDF()
            pdf.add_page()
            
            # Cabeçalho
            pdf.set_font("Arial", 'B', 18)
            pdf.cell(0, 10, f"PLANO DE TREINO - {dados['data']}", 0, 1, 'C')
            pdf.ln(10)
            
            # Informações básicas
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 10, f"Treinador: {dados['treinador']}", 0, 1)
            pdf.cell(0, 10, f"Época: {dados['epoca']} | Escalão: {dados['escalao']}", 0, 1)
            pdf.cell(0, 10, f"Data: {dados['data']} | Hora: {dados['hora']}", 0, 1)
            pdf.cell(0, 10, f"Dominante: {dados['dominante']} | Intensidade: {dados['intensidade']}", 0, 1)
            pdf.ln(15)
            
            # Seções do treino
            PDFGenerator._adicionar_secao(pdf, "1. AQUECIMENTO", dados['aquecimento'], IMAGE_PATHS['aquecimento'])
            pdf.add_page()
            PDFGenerator._adicionar_secao(pdf, "2. PARTE PRINCIPAL", dados['parte_principal'], IMAGE_PATHS['principal'])
            
            # Adicionar imagem do campo
            campo_anotado = PDFGenerator._anotar_imagem_campo(dados['parte_principal'])
            temp_path = os.path.join(ASSETS_DIR, "campo_anotado_temp.png")
            campo_anotado.save(temp_path)
            pdf.image(temp_path, x=10, y=None, w=180)
            os.remove(temp_path)
            
            pdf.add_page()
            PDFGenerator._adicionar_secao(pdf, "3. VOLTA À CALMA", dados['volta_calma'], IMAGE_PATHS['volta_calma'])
            
            # Materiais
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Materiais Necessários:", 0, 1)
            pdf.set_font("Arial", '', 12)
            pdf.multi_cell(0, 10, dados['materiais'])
            
            # Salvar PDF
            pdf_path = f"Plano_Treino_{dados['data'].replace('/', '-')}.pdf"
            pdf.output(pdf_path)
            
            return pdf_path
        except Exception as e:
            logging.error(f"Erro ao gerar PDF: {str(e)}")
            raise

    @staticmethod
    def _verificar_assets() -> bool:
        """Verifica se os assets necessários existem"""
        if not os.path.exists(ASSETS_DIR):
            os.makedirs(ASSETS_DIR)
            return False
        
        for nome, caminho in IMAGE_PATHS.items():
            if not os.path.exists(caminho):
                logging.warning(f"Asset não encontrado: {caminho}")
                return False
        return True

    @staticmethod
    def _adicionar_secao(pdf, titulo: str, conteudo: str, icone_path: str = None):
        """Adiciona uma seção ao PDF"""
        if icone_path and os.path.exists(icone_path):
            pdf.image(icone_path, x=10, y=20, w=30)
        
        pdf.set_font("Arial", 'B', 16)
        pdf.set_text_color(0, 51, 102)
        pdf.text(45, 30, titulo)
        
        pdf.set_font("Arial", '', 12)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(10, 40)
        pdf.multi_cell(0, 8, conteudo)
        pdf.ln(10)

    @staticmethod
    def _anotar_imagem_campo(descricao: str) -> Image:
        """Anota a imagem do campo com base na descrição"""
        try:
            img = Image.open(IMAGE_PATHS['campo'])
            img = img.convert("RGB")
            img.thumbnail((800, 600))
            
            draw = ImageDraw.Draw(img)
            
            # Tentar carregar fonte local
            try:
                font_path = os.path.join(ASSETS_DIR, "arial.ttf")
                font = ImageFont.truetype(font_path, 20) if os.path.exists(font_path) else ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Adicionar anotações
            draw.text((50, 30), "Exercícios:", fill="red", font=font)
            
            y_pos = 60
            for linha in descricao.split('\n'):
                if linha.strip():
                    draw.text((50, y_pos), linha.strip(), fill="black", font=font)
                    y_pos += 30
            
            return img
        except Exception as e:
            logging.error(f"Erro ao anotar imagem: {str(e)}")
            return Image.open(IMAGE_PATHS['campo'])  # Retorna imagem original em caso de erro

class EmailSender:
    """Envia e-mails para jogadores"""
    @staticmethod
    def enviar_treino(destinatario: str, assunto: str, corpo: str) -> bool:
        try:
            remetente = os.getenv("EMAIL_USER")
            senha = os.getenv("EMAIL_PASSWORD")
            
            if not remetente or not senha:
                raise Exception("Configurações de e-mail não encontradas")
            
            msg = MIMEMultipart()
            msg['From'] = remetente
            msg['To'] = destinatario
            msg['Subject'] = assunto
            msg.attach(MIMEText(corpo, 'html'))
            
            with smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), 
                             int(os.getenv("SMTP_PORT", 587))) as server:
                server.starttls()
                server.login(remetente, senha)
                server.send_message(msg)
                return True
        except Exception as e:
            logging.error(f"Erro no envio de e-mail: {str(e)}")
            return False

# --- Componentes da Interface ---
class UIComponents:
    """Componentes reutilizáveis da interface"""
    
    @staticmethod
    def baixar_foto_dropbox(caminho_dropbox):
        """Baixa foto do Dropbox"""
        try:
            dbx = get_dropbox_client_with_retry()
            if not dbx:
                return None
            
            # Baixar arquivo do Dropbox
            metadata, response = dbx.files_download(caminho_dropbox)
            return response.content
            
        except Exception as e:
            print(f"Erro ao baixar foto do Dropbox: {str(e)}")
            return None
    
    @staticmethod
    def upload_foto_dropbox(foto_bytes, nome_jogador):
        """Faz upload de foto para o Dropbox"""
        try:
            dbx = get_dropbox_client_with_retry()
            if not dbx:
                return None
            
            # Caminho no Dropbox
            caminho_dropbox = f"/app_treinador/fotos/{nome_jogador.lower().replace(' ', '_')}.png"
            
            # Upload para Dropbox
            dbx.files_upload(foto_bytes, caminho_dropbox, mode=dropbox.files.WriteMode.overwrite)
            return caminho_dropbox
            
        except Exception as e:
            print(f"Erro ao fazer upload de foto para Dropbox: {str(e)}")
            return None
    
    @staticmethod
    def sincronizar_fotos_dropbox():
        """Sincroniza todas as fotos com o Dropbox"""
        if not is_streamlit_cloud():
            return True  # Não precisa sincronizar localmente
        
        try:
            dbx = get_dropbox_client_with_retry()
            if not dbx:
                st.warning("⚠️ Não foi possível conectar ao Dropbox para sincronizar fotos")
                return False
            
            data = DataManager.load_data()
            jogadores = data.get('jogadores', [])
            
            fotos_sincronizadas = 0
            
            for jogador in jogadores:
                nome = jogador.get('nome', '')
                login = jogador.get('login', nome.lower().replace(' ', '_'))
                
                # Verificar se já tem foto no Dropbox
                if jogador.get('foto_dropbox'):
                    continue
                
                # Tentar criar foto placeholder e fazer upload
                try:
                    foto_placeholder = UIComponents.criar_foto_placeholder(nome)
                    caminho_dropbox = UIComponents.upload_foto_dropbox(foto_placeholder, nome)
                    
                    if caminho_dropbox:
                        # Atualizar dados do jogador
                        jogador['foto_dropbox'] = caminho_dropbox
                        fotos_sincronizadas += 1
                        
                except Exception as e:
                    print(f"Erro ao sincronizar foto de {nome}: {str(e)}")
            
            if fotos_sincronizadas > 0:
                DataManager.save_data(data)
                st.success(f"✅ {fotos_sincronizadas} fotos sincronizadas com Dropbox!")
            
            return True
            
        except Exception as e:
            st.error(f"❌ Erro na sincronização de fotos: {str(e)}")
            return False
    
    @staticmethod
    def criar_foto_placeholder(nome_jogador):
        """Cria uma foto placeholder para um jogador"""
        try:
            from io import BytesIO
            
            # Criar imagem 150x150 com nome do jogador
            img = Image.new('RGB', (150, 150), color='#007acc')
            draw = ImageDraw.Draw(img)
            
            # Adicionar texto com o nome
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            # Pegar iniciais do nome
            iniciais = ''.join([palavra[0].upper() for palavra in nome_jogador.split() if palavra])[:3]
            
            # Calcular posição central do texto
            if font:
                bbox = draw.textbbox((0, 0), iniciais, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            else:
                text_width, text_height = 30, 10
            
            x = (150 - text_width) // 2
            y = (150 - text_height) // 2
            
            # Desenhar o texto
            draw.text((x, y), iniciais, fill='white', font=font)
            
            # Converter para bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
            
        except Exception as e:
            print(f"Erro ao criar foto placeholder: {str(e)}")
            return None
    
    @staticmethod
    def mostrar_card_jogador(jogador: Dict, read_only: bool = False, hide_contacts: bool = False):
        col1, col2 = st.columns([1, 3])
        
        with col1:
            foto_exibida = False
            
            # Tentar carregar foto do Dropbox se estiver no cloud
            if is_streamlit_cloud() and jogador.get('foto_dropbox'):
                try:
                    foto_bytes = UIComponents.baixar_foto_dropbox(jogador['foto_dropbox'])
                    if foto_bytes:
                        st.image(foto_bytes, use_container_width=True)
                        foto_exibida = True
                except Exception as e:
                    st.warning(f"Erro ao carregar foto do Dropbox: {str(e)}")
            
            # Tentar foto local se não conseguiu do Dropbox
            if not foto_exibida and jogador.get('foto') and os.path.exists(jogador['foto']):
                try:
                    with Image.open(jogador['foto']) as img:
                        st.image(jogador['foto'], use_container_width=True)
                        foto_exibida = True
                except (IOError, OSError, Exception):
                    pass
            
            # Se nenhuma foto funcionou, usar avatar padrão
            if not foto_exibida:
                avatar_url = f"https://ui-avatars.com/api/?name={jogador['nome'].replace(' ', '+')}&size=150&background=007acc&color=fff"
                st.image(avatar_url, use_container_width=True)
        
        with col2:
            st.subheader(f"#{jogador.get('nr_camisola', '')} {jogador['nome']}")
            st.caption(f"Login: {jogador.get('login', 'N/A')} | Posição: {jogador['posicao']} | Idade: {jogador['idade']}")
            st.write(f"**Altura:** {jogador.get('altura', 'N/A')}m")
            st.write(f"**Peso:** {jogador.get('peso', 'N/A')}kg")
            st.write(f"**Último Clube:** {jogador.get('ultimo_clube', 'N/A')}")
            
            # Esconde contatos se hide_contacts=True
            if not hide_contacts:
                st.write(f"**Telefone:** {jogador.get('telefone', '--')}")
                st.write(f"**E-mail:** {jogador.get('email', '--')}")
            
            if jogador.get('pontos_fortes'):
                st.write("**Pontos Fortes:**")
                cols = st.columns(3)
                for i, pf in enumerate(jogador['pontos_fortes']):
                    cols[i%3].success(f"✓ {pf}")
            
            # Botões só para treinador
            if not read_only and st.session_state.get('tipo_usuario') == 'treinador':
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("✏️ Editar", key=f"edit_{jogador['id']}"):
                        st.session_state['edit_player'] = jogador.copy()
                        st.rerun()
                with bcol2:
                    if st.button("❌ Remover", key=f"del_{jogador['id']}"):
                        st.session_state['delete_player'] = jogador.copy()
                        st.rerun()

    @staticmethod
    def formulario_jogador(jogador_data=None):
        """Formulário para adicionar/editar jogador"""
        try:
            # Dados padrão
            dados = {
                'id': str(uuid.uuid4()),
                'nome': '',
                'login': '',
                'posicao': 'Meio-Campo',
                'nr_camisola': 1,
                'idade': 18,
                'altura': 1.75,
                'peso': 70,
                'ultimo_clube': '',
                'telefone': '',
                'email': '',
                'pontos_fortes': [],
                'foto': None,
                'senha_hash': None
            }


            # Se receber dados do jogador, atualiza os valores padrão
            if jogador_data:
                dados.update(jogador_data)
                modo_edicao = True
                titulo = "✏️ Editar Jogador"
            else:
                modo_edicao = False
                titulo = "➕ Adicionar Novo Jogador"

            with st.form(key=f"form_jogador_{'edit' if modo_edicao else 'new'}"):
                st.subheader(titulo)
                if st.session_state.get('tipo_usuario') == 'treinador':
                    tipo_usuario = st.selectbox(
                        "Tipo de Usuário",
                        ["jogador", "treinador_adjunto"],
                        index=0 if not modo_edicao or dados.get('tipo', 'jogador') == 'jogador' else 1
                    )
                else:
                    tipo_usuario = dados.get('tipo', 'jogador')  
                
                # Layout do formulário
                cols = st.columns(2)
                with cols[0]:
                    nome = st.text_input("Nome Completo*", value=dados['nome'])
                    login = st.text_input("Login* (sem espaços)", value=dados['login'], disabled=modo_edicao)
                    
                    # Lista completa de posições incluindo "Adjunto"
                    posicoes_disponiveis = ["Guarda-Redes", "Defesa", "Meio-Campo", "Adjunto", "Ataque"]
                    
                    # Determinar índice da posição atual
                    try:
                        posicao_index = posicoes_disponiveis.index(dados['posicao'])
                    except ValueError:
                        # Se a posição não estiver na lista, usar Meio-Campo como padrão
                        posicao_index = 2  # Meio-Campo
                    
                    posicao = st.selectbox("Posição*", posicoes_disponiveis, index=posicao_index)
                    numero = st.number_input("Nº Camisola", value=dados['nr_camisola'], min_value=1, max_value=99)
                    altura = st.number_input("Altura (m)*", value=dados['altura'], min_value=1.50, max_value=2.20, step=0.01)
                
                with cols[1]:
                    idade = st.number_input("Idade*", value=dados['idade'], min_value=16, max_value=50)
                    peso = st.number_input("Peso (kg)*", value=dados['peso'], min_value=40, max_value=120)
                    ultimo_clube = st.text_input("Último Clube*", value=dados['ultimo_clube'])
                    telefone = st.text_input("Telefone*", value=dados['telefone'])
                    email = st.text_input("E-mail*", value=dados['email'])
                    foto = st.file_uploader("Foto (opcional)", type=["jpg", "png", "jpeg"])
                
                pontos_fortes = st.multiselect(
                    "Pontos Fortes",
                    ["Finalização", "Velocidade", "Força", "Agressivo", "Agil", "Visão de Jogo", "Cabeceamento"],
                    default=dados['pontos_fortes']
                )

                # Só mostra campo de senha para novo jogador
                if not modo_edicao:
                    senha = st.text_input("Senha*", type="password")
                else:
                    nova_senha = st.text_input("Nova Senha (opcional)", type="password")
                    # Nota: Reset de senha será feito após salvar se necessário

                # Botões de ação
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("💾 Salvar")
                with col2:
                    cancelar = st.form_submit_button("❌ Cancelar")

                # Processar cancelamento
                if cancelar:
                    if 'edit_player' in st.session_state:
                        del st.session_state['edit_player']
                    st.rerun()

                if submitted:
                    # Validar campos obrigatórios
                    campos_obrigatorios = [nome, login, posicao, idade, altura, peso, ultimo_clube, telefone, email]
                    if not modo_edicao:
                        campos_obrigatorios.append(senha)
                    
                    if not all(campos_obrigatorios):
                        st.error("Preencha todos os campos obrigatórios (*)")
                    else:
                        try:
                            # Preparar dados do jogador
                            novo_jogador = {
                                "id": dados['id'],  # Mantém o ID existente ou usa o novo
                                "tipo": tipo_usuario,
                                "nome": nome,
                                "login": login.lower().strip(),
                                "posicao": posicao,
                                "nr_camisola": numero,
                                "idade": idade,
                                "altura": altura,
                                "peso": peso,
                                "ultimo_clube": ultimo_clube,
                                "telefone": telefone,
                                "email": email,
                                "pontos_fortes": pontos_fortes,
                                "foto": dados['foto']
                            }
                            
                            # Gerenciar senha
                            if modo_edicao:
                                if nova_senha:
                                    # Se uma nova senha foi fornecida, hash ela
                                    novo_jogador["senha_hash"] = Authentication().hash_password(nova_senha)
                                else:
                                    # Manter senha existente
                                    novo_jogador["senha_hash"] = dados['senha_hash']
                            else:
                                # Novo jogador, hash a senha fornecida
                                novo_jogador["senha_hash"] = Authentication().hash_password(senha)

                            # Processar foto se fornecida
                            if foto:
                                try:
                                    # Redimensionar imagem
                                    img = ImageOps.fit(Image.open(foto), (300, 300))
                                    
                                    if is_streamlit_cloud():
                                        # No Streamlit Cloud, fazer upload direto para Dropbox
                                        img_bytes = BytesIO()
                                        img.save(img_bytes, format='PNG')
                                        img_bytes.seek(0)
                                        
                                        caminho_dropbox = UIComponents.upload_foto_dropbox(img_bytes.getvalue(), nome)
                                        if caminho_dropbox:
                                            novo_jogador["foto_dropbox"] = caminho_dropbox
                                            st.success("📸 Foto enviada para Dropbox com sucesso!")
                                        else:
                                            st.warning("⚠️ Não foi possível enviar foto para Dropbox")
                                    else:
                                        # Localmente, salvar no sistema de arquivos
                                        os.makedirs("data/fotos", exist_ok=True)
                                        foto_path = f"data/fotos/{login.lower().replace(' ', '_')}.png"
                                        img.save(foto_path)
                                        novo_jogador["foto"] = foto_path
                                        
                                except Exception as e:
                                    st.error(f"❌ Erro ao processar foto: {str(e)}")
                                    # Continuar sem foto

                            # Salvar no banco de dados
                            data = DataManager.load_data()
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
                                if modo_edicao and nova_senha:
                                    st.success("Jogador atualizado e senha redefinida com sucesso!")
                                else:
                                    st.success("Jogador salvo com sucesso!")
                                
                                time.sleep(1)
                                if 'edit_player' in st.session_state:
                                    del st.session_state['edit_player']
                                st.rerun()
                            else:
                                st.error("Erro ao salvar dados")

                        except Exception as e:
                            st.error(f"Erro ao salvar: {str(e)}")
                            import traceback
                            st.error(traceback.format_exc())

        except Exception as e:
            st.error(f"Erro inesperado no formulário: {str(e)}")

# --- Funções Auxiliares ---
def mostrar_uso_recursos():
    """Mostra estatísticas de uso de recursos na barra lateral"""
    data = DataManager.load_data()
    st.sidebar.subheader("📊 Estatísticas")
    
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Jogadores", len(data.get('jogadores', [])))
    col2.metric("Treinos", len(data.get('treinos', {})))
    
    if 'jogos' in data:
        st.sidebar.metric("Jogos", len(data['jogos']))

def resetar_senha_jogador(login_jogador, nova_senha):
    """Reseta a senha de um jogador"""
    try:
        data = DataManager.load_data()
        auth = Authentication()
        
        for jogador in data.get('jogadores', []):
            if jogador.get('login') == login_jogador:
                jogador['senha_hash'] = auth.hash_password(nova_senha)
                if DataManager.save_data(data):
                    return True
        return False
    except Exception as e:
        logging.error(f"Erro ao resetar senha: {str(e)}")
        return False

# --- Páginas da Aplicação ---
def pagina_login():
    """Página de login"""
    st.title("🔐 Acesso Restrito")
    auth = Authentication()
    
    # Debug de credenciais (só mostrar se não autenticado)
    if not st.session_state.get('autenticado', False):
        with st.expander("🔍 Debug - Credenciais Disponíveis", expanded=False):
            st.info("**CREDENCIAIS DE TESTE:**")
            st.code("""
ADMIN/TREINADOR:
   Usuário: admin
   Senha: 123456

JOGADORES EXEMPLO:
   fabio / [senha configurada]
   rafa / [senha configurada] 
   freitas / [senha configurada]
   
TREINADORES ADJUNTOS:
   nuno / [senha configurada]
   joel / [senha configurada]
            """)
            st.warning("⚠️ Se não souber a senha dos jogadores, use 'admin' para acessar e resetar")
    
    with st.form("login_form"):
        username = st.text_input("Usuário (Login)")
        password = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Entrar"):
            if auth.login(username, password):
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("❌ Credenciais inválidas")
                st.info("💡 Verifique as credenciais no painel de debug acima")

def pagina_dashboard():
    """Página inicial do sistema"""
    st.title("📊 Dashboard do Treinador" if st.session_state.get('tipo_usuario') == 'treinador' else "📋 Meu Painel")
    
    # Indicador de ambiente (importante para debug)
    if is_streamlit_cloud():
        st.info("🌐 **Executando no Streamlit Cloud** - Backups priorizados no Dropbox")
    else:
        st.success("💻 **Executando localmente** - Backup local + Dropbox disponível")
    
    data = DataManager.load_data()
    
    # Métricas
    if st.session_state.get('tipo_usuario') == 'treinador':
        col1, col2, col3 = st.columns(3)
        col1.metric("👥 Jogadores", len(data.get('jogadores', [])))
        col2.metric("📅 Treinos", len(data.get('treinos', {})))
        col3.metric("⚽ Jogos", len(data.get('jogos', [])))
    else:
        jogador = st.session_state.get('jogador_info', {})
        col1, col2 = st.columns(2)
        col1.metric("📅 Próximos Treinos", len([t for t in data.get('treinos', {}).values() if jogador.get('nome') in t.get('participantes', [])]))
        col2.metric("⚽ Próximos Jogos", len([j for j in data.get('jogos', []) if not j.get('resultado') and jogador.get('nome') in j.get('convocados', [])]))
    
    # Próximos compromissos
    st.subheader("📅 Próximos Compromissos")
    tab1, tab2 = st.tabs(["Próximos Treinos", "Próximos Jogos"])
    
    with tab1:
        if st.session_state.get('tipo_usuario') == 'treinador':
            treinos = data.get('treinos', {}).items()
        else:
            jogador_nome = st.session_state.get('jogador_info', {}).get('nome')
            treinos = [(dt, t) for dt, t in data.get('treinos', {}).items() if jogador_nome in t.get('participantes', [])]
        
        if treinos:
            # Filtrar apenas treinos com data válida (formato YYYY-MM-DD)
            treinos_com_data = []
            for dt, t in treinos:
                try:
                    # Verificar se a chave é uma data válida
                    datetime.strptime(dt, '%Y-%m-%d')
                    treinos_com_data.append((dt, t))
                except ValueError:
                    # Se não for uma data (ex: UUID), verificar se tem data_criacao ou similar
                    continue
            
            if treinos_com_data:
                next_train = min(treinos_com_data, key=lambda x: datetime.strptime(x[0], '%Y-%m-%d'))
                st.write(f"**Data:** {next_train[0]}")
                st.write(f"**Objetivo:** {next_train[1].get('objetivo', 'N/A')}")
                if 'exercicios' in next_train[1] and isinstance(next_train[1]['exercicios'], list):
                    st.write(f"**Exercícios:** {', '.join(next_train[1]['exercicios'])}")
                else:
                    st.write("**Exercícios:** Não especificados")
            else:
                st.info("Nenhum treino com data específica agendado")
        else:
            st.warning("Nenhum treino agendado")
    
    with tab2:
        if st.session_state.get('tipo_usuario') == 'treinador':
            jogos = [j for j in data.get('jogos', []) if not j.get('resultado')]
        else:
            jogador_nome = st.session_state.get('jogador_info', {}).get('nome')
            jogos = [j for j in data.get('jogos', []) if not j.get('resultado') and jogador_nome in j.get('convocados', [])]
        
        if jogos:
            next_game = min(jogos, key=lambda x: datetime.strptime(x['data'], '%Y-%m-%d'))
            st.write(f"**Data:** {next_game['data']}")
            st.write(f"**Adversário:** {next_game['adversario']}")
            st.write(f"**Local:** {next_game.get('local', 'A definir')}")
        else:
            st.warning("Nenhum jogo agendado")

def pagina_jogadores():
    """Página de gestão de jogadores"""
    st.title("👥 Lista de Jogadores")
    
    # Sincronizar fotos no Streamlit Cloud
    if is_streamlit_cloud():
        if st.button("🔄 Sincronizar Fotos com Dropbox", help="Criar fotos para jogadores que não têm"):
            with st.spinner("Sincronizando fotos..."):
                UIComponents.sincronizar_fotos_dropbox()
    
    data = DataManager.load_data()

    is_treinador = st.session_state.get('tipo_usuario') == 'treinador'

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        posicoes = list({j['posicao'] for j in data.get('jogadores', [])}) if data.get('jogadores', []) else []
        pos_filter = st.selectbox("Filtrar por posição", ["Todos"] + posicoes)
    with col2:
        search_term = st.text_input("Buscar por nome")
    with col3:
        items_per_page = st.selectbox("Jogadores por página", [5, 10, 20], index=1)

    # Aplicar filtros
    filtered_players = data.get('jogadores', [])
    if pos_filter != "Todos":
        filtered_players = [j for j in filtered_players if j['posicao'] == pos_filter]
    if search_term:
        filtered_players = [j for j in filtered_players if search_term.lower() in j['nome'].lower()]

    # Paginação
    total_pages = max(1, (len(filtered_players) // items_per_page + 1))
    page = st.number_input("Página", min_value=1, max_value=total_pages, value=1)
    paginated_players = filtered_players[(page-1)*items_per_page : page*items_per_page]

    # Adicionar novo jogador (apenas treinador)
    if is_treinador:
        with st.expander("➕ Adicionar Novo Jogador", expanded=False):
            UIComponents.formulario_jogador()

    # Lista de jogadores
    st.subheader(f"🏃‍♂️ Elenco ({len(filtered_players)} jogadores)")

    if not paginated_players:
        st.warning("Nenhum jogador encontrado com os filtros atuais")
    else:
        for jogador in paginated_players:
            UIComponents.mostrar_card_jogador(jogador, read_only=not is_treinador, hide_contacts=not is_treinador)

    # Edição e exclusão (apenas treinador)
    if is_treinador:
        if 'edit_player' in st.session_state:
            st.write("")  # Espaçamento
            with st.expander(f"✏️ Editando {st.session_state['edit_player']['nome']}", expanded=True):
                UIComponents.formulario_jogador(jogador_data=st.session_state['edit_player'])

        if 'delete_player' in st.session_state:
            jogador = st.session_state['delete_player']
            st.warning(f"Tem certeza que deseja remover {jogador['nome']} permanentemente?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirmar", key="confirm_delete"):
                    try:
                        data = DataManager.load_data()
                        data['jogadores'] = [j for j in data.get('jogadores', []) if j['id'] != jogador['id']]
                        if DataManager.save_data(data):
                            if jogador.get('foto') and os.path.exists(jogador['foto']):
                                os.remove(jogador['foto'])
                            st.success(f"Jogador {jogador['nome']} removido com sucesso!")
                            time.sleep(1)
                            del st.session_state['delete_player']
                            st.rerun()
                        else:
                            st.error("Erro ao salvar dados")
                    except Exception as e:
                        st.error(f"Erro ao remover jogador: {str(e)}")
            with col2:
                if st.button("❌ Cancelar", key="cancel_delete"):
                    del st.session_state['delete_player']
                    st.rerun()
                
def pagina_perfil_jogador():
    """Página de visualização do perfil do jogador"""
    st.title("👤 Meu Perfil")
    jogador = st.session_state.get('jogador_info')
    
    if not jogador:
        st.warning("Informações do jogador não disponíveis")
        return
    
    UIComponents.mostrar_card_jogador(jogador, read_only=True)
    
    # Próximos treinos do jogador
    st.subheader("📅 Meus Próximos Treinos")
    data = DataManager.load_data()
    treinos_jogador = []
    
    for data_treino, detalhes in data.get('treinos', {}).items():
        if jogador['nome'] in detalhes.get('participantes', []):
            treinos_jogador.append((data_treino, detalhes))
    
    if not treinos_jogador:
        st.warning("Nenhum treino agendado para você")
    else:
        for data_treino, detalhes in sorted(treinos_jogador):
            # Exibir nome do treino ou data, dependendo do formato
            titulo_treino = detalhes.get('nome', data_treino)
            objetivo = detalhes.get('objetivo', 'N/A')
            
            with st.expander(f"📅 {titulo_treino} - {objetivo}", expanded=False):
                if 'local' in detalhes:
                    st.write(f"**Local:** {detalhes['local']}")
                if 'duracao' in detalhes:
                    st.write(f"**Duração:** {detalhes['duracao']} min")
                
                # Exercícios (pode ser lista de strings ou lista de objetos)
                exercicios = detalhes.get('exercicios', [])
                if exercicios:
                    st.write("**Exercícios:**")
                    for exercicio in exercicios:
                        if isinstance(exercicio, dict):
                            # Exercício é um objeto com nome e descrição
                            nome_ex = exercicio.get('nome', 'Exercício sem nome')
                            st.write(f"- {nome_ex}")
                        else:
                            # Exercício é uma string simples
                            st.write(f"- {exercicio}")
                else:
                    st.write("**Exercícios:** Não especificados")
    
    # Próximos jogos do jogador
    st.subheader("⚽ Meus Próximos Jogos")
    jogos_jogador = [j for j in data.get('jogos', []) 
                    if not j.get('resultado') and jogador['nome'] in j.get('convocados', [])]
    
    if not jogos_jogador:
        st.warning("Nenhum jogo agendado para você")
    else:
        for jogo in sorted(jogos_jogador, key=lambda x: x['data']):
            with st.expander(f"📅 {jogo['data']} - vs {jogo['adversario']} ({jogo['tipo']})", expanded=False):
                st.write(f"**Local:** {jogo['local']}")
                st.write(f"**Hora:** {jogo['hora']}")
                st.write(f"**Tática Recomendada:** {jogo.get('tatica', 'A definir')}")

def pagina_treinos():
    """Página de gestão de treinos"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
    
    st.title("📅 Gestão de Treinos")
    data = DataManager.load_data()
    
    # Agendar novo treino
    with st.expander("➕ Agendar Novo Treino", expanded=False):
        with st.form(key="form_novo_treino", clear_on_submit=True):
            data_treino = st.date_input("Data do Treino", min_value=datetime.today())
            hora = st.time_input("Hora")
            local = st.text_input("Local")
            objetivo = st.text_input("Objetivo do Treino")
            duracao = st.number_input("Duração (minutos)", min_value=30, max_value=180, value=90)
            
            exercicios_disponiveis = []
            # Verificar se existe a estrutura de exercícios
            if 'exercicios' in data and data['exercicios']:
                for categoria, exercs in data['exercicios'].items():
                    for exerc, duracao in exercs.items():
                        exercicios_disponiveis.append(f"{categoria}: {exerc}")
            else:
                # Exercícios padrão caso não existam na estrutura de dados
                exercicios_padrao = [
                    "Técnica: Controle de bola",
                    "Técnica: Passe e receção",
                    "Técnica: Finalização",
                    "Física: Corrida contínua",
                    "Física: Sprint",
                    "Física: Resistência",
                    "Tática: Posicionamento",
                    "Tática: Marcação",
                    "Tática: Construção de jogo"
                ]
                exercicios_disponiveis = exercicios_padrao
            
            exercicios = st.multiselect("Exercícios", exercicios_disponiveis)
            
            jogadores_disponiveis = [j['nome'] for j in data.get('jogadores', [])]
            participantes = st.multiselect("Participantes", jogadores_disponiveis)
            
            if st.form_submit_button("💾 Agendar Treino"):
                data_str = data_treino.strftime('%Y-%m-%d')
                if 'treinos' not in data:
                    data['treinos'] = {}
                data['treinos'][data_str] = {
                    'hora': hora.strftime('%H:%M'),
                    'local': local,
                    'objetivo': objetivo,
                    'duracao': duracao,
                    'exercicios': exercicios,
                    'participantes': participantes
                }
                
                if DataManager.save_data(data):
                    st.success("Treino agendado com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar treino")
    
    # Lista de treinos agendados
    st.subheader("📅 Treinos Agendados")
    if not data['treinos']:
        st.warning("Nenhum treino agendado")
    else:
        for data_treino, detalhes in sorted(data['treinos'].items()):
            # Exibir nome do treino ou ID, dependendo do formato
            titulo_treino = detalhes.get('nome', data_treino)
            objetivo = detalhes.get('objetivo', 'N/A')
            local = detalhes.get('local', 'N/A')
            
            with st.expander(f"{titulo_treino} - {objetivo} ({local})", expanded=False):
                if 'hora' in detalhes:
                    st.write(f"**Hora:** {detalhes['hora']}")
                if 'duracao' in detalhes:
                    st.write(f"**Duração:** {detalhes['duracao']} minutos")
                
                # Participantes
                participantes = detalhes.get('participantes', [])
                if participantes:
                    st.write(f"**Participantes:** {', '.join(participantes)}")
                
                # Exercícios (pode ser lista de strings ou lista de objetos)
                exercicios = detalhes.get('exercicios', [])
                if exercicios:
                    st.write("**Exercícios:**")
                    for exercicio in exercicios:
                        if isinstance(exercicio, dict):
                            # Exercício é um objeto com nome e descrição
                            nome_ex = exercicio.get('nome', 'Exercício sem nome')
                            st.write(f"- {nome_ex}")
                        else:
                            # Exercício é uma string simples
                            st.write(f"- {exercicio}")
                else:
                    st.write("**Exercícios:** Não especificados")
                    
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_treino_{data_treino}"):
                        st.session_state['edit_treino'] = (data_treino, detalhes)
                        st.rerun()
                with col2:
                    if st.button("🗑️ Eliminar", key=f"del_treino_{data_treino}"):
                        if 'treinos' in data and data_treino in data['treinos']:
                            data['treinos'].pop(data_treino)
                            DataManager.save_data(data)
                            st.success("Treino eliminado!")
                        st.rerun()
                        # Formulário de edição (fora do loop)
        if 'edit_treino' in st.session_state:
            data_treino, detalhes = st.session_state['edit_treino']
            with st.form(key="form_edit_treino"):
                st.subheader(f"Editar Treino: {data_treino}")
                # Verificar se existe hora, senão usar valor padrão
                hora_default = datetime.strptime("09:00", "%H:%M").time()
                if 'hora' in detalhes and detalhes['hora']:
                    try:
                        hora_default = datetime.strptime(detalhes['hora'], "%H:%M").time()
                    except (ValueError, TypeError):
                        hora_default = datetime.strptime("09:00", "%H:%M").time()
                
                hora = st.time_input("Hora", value=hora_default)
                local = st.text_input("Local", value=detalhes.get('local', ''))
                objetivo = st.text_input("Objetivo", value=detalhes.get('objetivo', ''))
                duracao = st.number_input("Duração (minutos)", value=detalhes.get('duracao', 90), min_value=30, max_value=180)
                
                # Exercícios disponíveis
                exercicios_disponiveis = []
                if 'exercicios' in data and data['exercicios']:
                    for categoria, exercs in data['exercicios'].items():
                        for exerc, duracao_ex in exercs.items():
                            exercicios_disponiveis.append(f"{categoria}: {exerc}")
                else:
                    exercicios_disponiveis = [
                        "Técnica: Controle de bola",
                        "Técnica: Passe e receção", 
                        "Técnica: Finalização",
                        "Física: Corrida contínua",
                        "Física: Sprint",
                        "Física: Resistência",
                        "Tática: Posicionamento",
                        "Tática: Marcação",
                        "Tática: Construção de jogo"
                    ]
                
                # Filtrar exercícios existentes
                exercicios_atuais = detalhes.get('exercicios', [])
                exercicios_validos = [ex for ex in exercicios_atuais if ex in exercicios_disponiveis]
                
                exercicios = st.multiselect("Exercícios", 
                                           exercicios_disponiveis, 
                                           default=exercicios_validos)
                
                # Participantes - filtrar apenas nomes válidos
                nomes_jogadores = [j['nome'] for j in data.get('jogadores', [])]
                participantes_atuais = detalhes.get('participantes', [])
                
                # Filtrar participantes válidos
                participantes_validos = []
                for participante in participantes_atuais:
                    if participante in nomes_jogadores:
                        participantes_validos.append(participante)
                    else:
                        # Tentar encontrar jogador similar
                        for nome_jogador in nomes_jogadores:
                            if participante.lower() in nome_jogador.lower() or nome_jogador.lower().startswith(participante.lower()):
                                participantes_validos.append(nome_jogador)
                                break
                
                participantes = st.multiselect("Participantes", 
                                              nomes_jogadores, 
                                              default=participantes_validos)
                
                col1, col2 = st.columns(2)
                with col1:
                    salvar = st.form_submit_button("💾 Salvar Alterações")
                with col2:
                    cancelar = st.form_submit_button("❌ Cancelar")
                
                if salvar:
                    if 'treinos' not in data:
                        data['treinos'] = {}
                    data['treinos'][data_treino] = {
                        'hora': hora.strftime('%H:%M'),
                        'local': local,
                        'objetivo': objetivo,
                        'duracao': duracao,
                        'exercicios': exercicios,
                        'participantes': participantes
                    }
                    if DataManager.save_data(data):
                        del st.session_state['edit_treino']
                        st.success("Treino editado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar treino")
                        
                if cancelar:
                    del st.session_state['edit_treino']
                    st.rerun()

    # Notificar jogadores
    st.subheader("📧 Notificar Jogadores sobre Treino")
    
    if not data.get('treinos', {}):
        st.info("Nenhum treino agendado para notificar.")
        return
    
    treino_selecionado = st.selectbox(
        "Selecione o treino para notificar",
        options=list(data.get('treinos', {}).keys()),
        format_func=lambda x: f"{data.get('treinos', {}).get(x, {}).get('nome', x)} - {data.get('treinos', {}).get(x, {}).get('objetivo', 'N/A')}"
    )
    
    treino_detalhes = data.get('treinos', {}).get(treino_selecionado, {})
    nome_treino = treino_detalhes.get('nome', treino_selecionado)
    
    assunto = st.text_input(
        "Assunto do e-mail",
        value=f"Informações sobre o treino: {nome_treino}"
    )
    
    # Preparar lista de exercícios para email
    exercicios_lista = []
    for exercicio in treino_detalhes.get('exercicios', []):
        if isinstance(exercicio, dict):
            exercicios_lista.append(exercicio.get('nome', 'Exercício sem nome'))
        else:
            exercicios_lista.append(str(exercicio))
    
    corpo = st.text_area(
        "Mensagem (suporta HTML)",
        value=f"""
        <h2>Informações do Treino</h2>
        <p><strong>Nome:</strong> {nome_treino}</p>
        <p><strong>Objetivo:</strong> {treino_detalhes.get('objetivo', 'N/A')}</p>
        <p><strong>Local:</strong> {treino_detalhes.get('local', 'N/A')}</p>
        <p><strong>Duração:</strong> {treino_detalhes.get('duracao', 'N/A')} minutos</p>
        <p><strong>Exercícios:</strong></p>
        <ul>
            {"".join(f"<li>{ex}</li>" for ex in exercicios_lista)}
        </ul>
        """
    )

    if st.button("📤 Enviar Notificações"):
        detalhes_treino = data['treinos'][treino_selecionado]
        participantes = detalhes_treino['participantes']
        
        emails = []
        for jogador in data['jogadores']:
            if jogador['nome'] in participantes and jogador.get('email'):
                emails.append(jogador['email'])
        
        if not emails:
            st.error("Nenhum e-mail válido encontrado para os participantes")
            return
        
        success_count = 0
        for email in emails:
            if EmailSender.enviar_treino(email, assunto, corpo):
                success_count += 1
        
        st.success(f"E-mails enviados com sucesso: {success_count}/{len(emails)}")

def pagina_plano_treino():
    """Página para criar planos de treino"""
    st.title("📋 Gerador de Plano de Treino")
    
    # Inicializa session_state se necessário
    if 'dados_treino' not in st.session_state:
        st.session_state.dados_treino = None
    
    # Formulário para coletar dados
    with st.form(key='plano_form'):
        st.subheader("Informações Gerais")
        treinador = st.text_input("Treinador", value="João Casal")
        epoca = st.text_input("Época", value="2025/2026")
        escalao = st.text_input("Escalão", value="Seniores")
        data_treino = st.date_input("Data do treino", value=date.today())
        hora = st.time_input("Hora do treino")
        periodo = st.selectbox("Período", ["Pré-época", "Época", "Férias"])
        dominante = st.selectbox("Dominante", ["Tática", "Técnica", "Física", "Psicológica"])
        intensidade = st.selectbox("Intensidade", ["Baixa", "Média", "Alta"])

        st.subheader("1. Aquecimento")
        aquecimento = st.text_area("Descrição do aquecimento", """- Corrida contínua (55% intensidade)
- Corrida com bola (1 toque, variação velocidade)
- Corrida com bola (2 toques, mudança direção)
- Condução com remate
- Corrida lateral e corrida para trás
- Passe e recepção esquerda/direita
- Transição com remate""")

        st.subheader("2. Parte Principal")
        parte_principal = st.text_area("Descrição da parte principal", """A. Jogo Reduzido (5x5 ou 6x6)
- Equipa A: Máx. 3 toques (posse bola)
- Equipa B: Joga com menos experientes
- Foco: Transição ofensiva e defensiva

B. Jogo Reduzido Pressão
- Finalizações rápidas com transição defensiva

C. Finalização (2x2+GR)
- Cruzamentos e remates
- Situações 2x2 com GR""")

        st.subheader("3. Volta à Calma")
        volta_calma = st.text_area("Descrição da volta à calma", "- Alongamentos gerais e específicos")

        st.subheader("Materiais")
        materiais = st.text_input("Materiais necessários", "Bolas, coletes, cones")

        st.subheader("Campo com Posicionamentos")
        if os.path.exists(IMAGE_PATHS['campo']):
            st.image(IMAGE_PATHS['campo'], caption="Diagrama do Campo", use_container_width=True)
        else:
            st.warning("Imagem do campo não encontrada")
        
        # Botão para submeter o formulário
        if st.form_submit_button("Preparar Plano de Treino"):
            st.session_state.dados_treino = {
                'treinador': treinador,
                'epoca': epoca,
                'escalao': escalao,
                'data': str(data_treino),
                'hora': str(hora),
                'periodo': periodo,
                'dominante': dominante,
                'intensidade': intensidade,
                'aquecimento': aquecimento,
                'parte_principal': parte_principal,
                'volta_calma': volta_calma,
                'materiais': materiais
            }
            st.success("Dados do treino preparados! Clique em Gerar PDF abaixo.")

    # Seção de geração de PDF (FORA do formulário)
    if st.session_state.dados_treino:
        st.divider()
        st.subheader("Gerar PDF")
        
        if st.button("⬇️ Gerar PDF do Plano de Treino"):
            try:
                with st.spinner("Gerando PDF..."):
                    pdf_path = PDFGenerator.gerar_plano_treino(st.session_state.dados_treino)
                    
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "Baixar Plano Completo",
                            data=f,
                            file_name=f"Plano_Treino_{st.session_state.dados_treino['data'].replace('/', '-')}.pdf",
                            mime="application/pdf"
                        )
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {str(e)}")
                st.error("Verifique se todos os campos foram preenchidos corretamente.")

def pagina_jogos():
    """Página de gestão de jogos"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
    
    st.title("⚽ Gestão de Jogos")
    data = DataManager.load_data()
    
    
    # Agendar novo jogo
    with st.expander("➕ Agendar Novo Jogo", expanded=False):
        with st.form(key="form_novo_jogo", clear_on_submit=True):
            data_jogo = st.date_input("Data do Jogo", min_value=datetime.today())
            hora = st.time_input("Hora")
            adversario = st.text_input("Adversário")
            local = st.text_input("Local")
            tipo = st.selectbox("Tipo de Jogo", ["Amistoso", "Campeonato", "Copa", "Treino"])
            
            jogadores_disponiveis = [j['nome'] for j in data['jogadores']]
            convocados = st.multiselect("Convocados", jogadores_disponiveis)
            
            if st.form_submit_button("💾 Agendar Jogo"):
                novo_jogo = {
                    'data': data_jogo.strftime('%Y-%m-%d'),
                    'hora': hora.strftime('%H:%M'),
                    'adversario': adversario,
                    'local': local,
                    'tipo': tipo,
                    'convocados': convocados,
                    'resultado': None
                }
                data['jogos'].append(novo_jogo)
                
                if DataManager.save_data(data):
                    st.success("Jogo agendado com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar jogo")
    
    # Lista de jogos agendados
    st.subheader("📅 Jogos Agendados")
    if not data['jogos']:
        st.warning("Nenhum jogo agendado")
    else:
        for jogo in sorted(data['jogos'], key=lambda x: x['data']):
            with st.expander(f"{jogo['data']} vs {jogo['adversario']} ({jogo['tipo']})", expanded=False):
                st.write(f"**Hora:** {jogo['hora']}")
                st.write(f"**Local:** {jogo['local']}")
                st.write(f"**Convocados:** {', '.join(jogo['convocados'])}")
                if jogo.get('resultado'):
                    st.write(f"**Resultado:** {jogo['resultado']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_jogo_{jogo['data']}_{jogo['adversario']}"):
                        st.session_state['edit_jogo'] = jogo
                        st.rerun()
                with col2:
                    if st.button("🗑️ Eliminar", key=f"del_jogo_{jogo['data']}_{jogo['adversario']}"):
                        data['jogos'].remove(jogo)
                        DataManager.save_data(data)
                        st.success("Jogo eliminado!")
                        st.rerun()
                        
    if 'edit_jogo' in st.session_state:
        jogo = st.session_state['edit_jogo']
        jogadores_disponiveis = [j['nome'] for j in data['jogadores']]
        # Garante que só nomes válidos vão para o default
        convocados_default = [nome for nome in jogo['convocados'] if nome in jogadores_disponiveis]
        with st.form(key="form_edit_jogo"):
            st.subheader(f"Editar Jogo: {jogo['data']} vs {jogo['adversario']}")
            hora = st.time_input("Hora", value=datetime.strptime(jogo['hora'], "%H:%M").time())
            adversario = st.text_input("Adversário", value=jogo['adversario'])
            local = st.text_input("Local", value=jogo['local'])
            tipo = st.selectbox("Tipo de Jogo", ["Amistoso", "Campeonato", "Copa", "Treino"], index=["Amistoso", "Campeonato", "Copa", "Treino"].index(jogo['tipo']))
            convocados = st.multiselect("Convocados", jogadores_disponiveis, default=convocados_default)
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Salvar Alterações"):
                    updated = False
                    # Tenta atualizar pelo objeto
                    for idx, j in enumerate(data['jogos']):
                        if j is jogo:
                            data['jogos'][idx].update({
                                'hora': hora.strftime('%H:%M'),
                                'adversario': adversario,
                                'local': local,
                                'tipo': tipo,
                                'convocados': convocados
                            })
                            updated = True
                            break
                    # Se não encontrou pelo objeto, tenta pelo campo único
                    if not updated:
                        for idx, j in enumerate(data['jogos']):
                            if j['data'] == jogo['data'] and j['adversario'] == jogo['adversario']:
                                data['jogos'][idx].update({
                                    'hora': hora.strftime('%H:%M'),
                                    'adversario': adversario,
                                    'local': local,
                                    'tipo': tipo,
                                    'convocados': convocados
                                })
                                break
                    DataManager.save_data(data)
                    del st.session_state['edit_jogo']
                    st.success("Jogo editado com sucesso!")
                    st.rerun()
        with col2:
            if st.form_submit_button("❌ Cancelar"):
                del st.session_state['edit_jogo']
                st.rerun()
            
                        
def pagina_taticas():
    """Página de editor tático"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta funcionalidade")
        return
        
    st.title("📐 Editor Tático")
    data = DataManager.load_data()
    
    formacao = st.selectbox("Formação", ["4-4-2", "4-3-3", "3-5-2", "5-3-2"])
    cor_time = st.color_picker("Cor do Time", "#1E90FF")
    
    jogadores = [j for j in data['jogadores'] if j.get('posicao')]
    
    st.subheader("Posicionamento dos Jogadores")
    
    if formacao == "4-4-2":
        posicoes = ["Guarda-Redes", "Defesa 1", "Defesa 2", "Defesa 3", "Defesa 4", 
                   "Meio 1", "Meio 2", "Meio 3", "Meio 4", 
                   "Atacante 1", "Atacante 2"]
    elif formacao == "4-3-3":
        posicoes = ["Guarda-Redes", "Defesa 1", "Defesa 2", "Defesa 3", "Defesa 4", 
                   "Meio 1", "Meio 2", "Meio 3", 
                   "Atacante 1", "Atacante 2", "Atacante 3"]
    else:  # 3-5-2
        posicoes = ["Guarda-Redes", "Defesa 1", "Defesa 2", "Defesa 3", 
                   "Meio 1", "Meio 2", "Meio 3", "Meio 4", "Meio 5", 
                   "Atacante 1", "Atacante 2"]
    
    tatica = {}
    for pos in posicoes:
        jogadores_pos = [j['nome'] for j in jogadores if pos.split()[0].lower() in j['posicao'].lower()]
        tatica[pos] = st.selectbox(pos, [""] + jogadores_pos)
    
    nome_tatica = st.text_input("Nome da Tática")
    
    if st.button("💾 Salvar Tática"):
        if not nome_tatica:
            st.error("Digite um nome para a tática")
        else:
            nova_tatica = {
                'nome': nome_tatica,
                'formacao': formacao,
                'cor': cor_time,
                'posicionamento': tatica
            }
            data['taticas'].append(nova_tatica)
            
            if DataManager.save_data(data):
                st.success("Tática salva com sucesso!")
            else:
                st.error("Erro ao salvar tática")

def pagina_relatorios():
    """Página de relatórios e estatísticas"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
        
    st.title("📊 Relatórios e Estatísticas")
    data = DataManager.load_data()
    
    tab1, tab2, tab3 = st.tabs(["Jogadores", "Treinos", "Jogos"])
    
    with tab1:
        st.subheader("Relatório de Jogadores")
        
        if not data['jogadores']:
            st.warning("Nenhum jogador cadastrado")
        else:
            if st.button("📄 Gerar PDF de Jogadores"):
                pdf = FPDF()
                pdf.add_page()
                
                pdf.set_font('Arial', 'B', 16)
                pdf.cell(0, 10, 'Relatório de Jogadores', 0, 1, 'C')
                pdf.ln(10)
                
                pdf.set_font('Arial', '', 12)
                for jogador in data['jogadores']:
                    pdf.cell(0, 10, f"Nome: {jogador['nome']}", 0, 1)
                    pdf.cell(0, 10, f"Posição: {jogador['posicao']} | Nº: {jogador.get('nr_camisola', 'N/A')}", 0, 1)
                    pdf.cell(0, 10, f"Idade: {jogador['idade']} | Altura: {jogador.get('altura', 'N/A')}m | Peso: {jogador.get('peso', 'N/A')}kg", 0, 1)
                    pdf.cell(0, 10, f"Último Clube: {jogador.get('ultimo_clube', 'N/A')}", 0, 1)
                    pdf.cell(0, 10, f"Contato: {jogador.get('telefone', 'N/A')} | Email: {jogador.get('email', 'N/A')}", 0, 1)
                    pdf.cell(0, 10, f"Pontos Fortes: {', '.join(jogador.get('pontos_fortes', []))}", 0, 1)
                    pdf.cell(0, 10, "-"*50, 0, 1)
                    pdf.ln(5)
                
                pdf_file = "relatorio_jogadores.pdf"
                pdf.output(pdf_file)
                
                with open(pdf_file, "rb") as f:
                    st.download_button(
                        "⬇️ Baixar Relatório",
                        data=f,
                        file_name=pdf_file,
                        mime="application/pdf"
                    )
    
    with tab2:
        st.subheader("Estatísticas de Treinos")
        st.write("Em desenvolvimento...")
    
    with tab3:
        st.subheader("Histórico de Jogos")
        st.write("Em desenvolvimento...")

def pagina_configuracoes():
    import os  # Garantir que os está disponível
    st.title("⚙️ Configurações do Sistema")
    
    # Seção de status do Dropbox
    st.subheader("📡 Status do Dropbox")
    
    # Verificação dos tokens
    access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
    refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
    app_key = os.getenv('DROPBOX_APP_KEY')
    app_secret = os.getenv('DROPBOX_APP_SECRET')
    
    # Status das variáveis
    st.write("**Status das Variáveis de Ambiente:**")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"🔑 ACCESS_TOKEN: {'✅ Configurado' if access_token else '❌ Ausente'}")
        st.write(f"🔄 REFRESH_TOKEN: {'✅ Configurado' if refresh_token else '❌ Ausente'}")
    with col2:
        st.write(f"🗝️ APP_KEY: {'✅ Configurado' if app_key else '❌ Ausente'}")
        st.write(f"🔐 APP_SECRET: {'✅ Configurado' if app_secret else '❌ Ausente'}")
    
    if not refresh_token:
        st.warning("⚠️ **REFRESH_TOKEN ausente!** Renovação automática não funcionará.")
        st.info("💡 Precisa refazer o fluxo OAuth completo para gerar o refresh_token.")
        
        with st.expander("🔧 Como Gerar REFRESH_TOKEN", expanded=False):
            st.write("""
            **Passos para gerar o REFRESH_TOKEN:**
            
            1. **App do Dropbox**: Vá para https://www.dropbox.com/developers/apps
            2. **Configurar OAuth**: Ative "Allow implicit grant" = OFF e "Allow PKCE" = ON
            3. **Scopes**: Adicione `files.content.read`, `files.content.write`, `files.metadata.read`
            4. **URL de Redirecionamento**: Adicione `http://localhost:8080/callback`
            5. **Gerar URL OAuth**: Use este formato:
            """)
            
            if app_key:
                oauth_url = f"https://www.dropbox.com/oauth2/authorize?client_id={app_key}&response_type=code&token_access_type=offline&redirect_uri=http://localhost:8080/callback"
                st.code(oauth_url)
                st.write("6. **Acesse a URL acima** e autorize a aplicação")
                st.write("7. **Capture o código** da URL de redirecionamento")
                st.write("8. **Use o código** para trocar por access_token e refresh_token")
            
            # Ferramenta para trocar código por tokens
            st.write("**🔄 Trocar Código OAuth por Tokens:**")
            oauth_code = st.text_input("Cole aqui o código OAuth capturado:", key="oauth_code")
            
            if oauth_code and app_key and app_secret:
                if st.button("🔄 Gerar Tokens"):
                    try:
                        import requests
                        
                        # Trocar código por tokens
                        token_url = "https://api.dropbox.com/oauth2/token"
                        token_data = {
                            'code': oauth_code,
                            'grant_type': 'authorization_code',
                            'redirect_uri': 'http://localhost:8080/callback',
                            'client_id': app_key,
                            'client_secret': app_secret
                        }
                        
                        response = requests.post(token_url, data=token_data)
                        
                        if response.status_code == 200:
                            tokens = response.json()
                            new_access_token = tokens.get('access_token')
                            new_refresh_token = tokens.get('refresh_token')
                            
                            st.success("✅ Tokens gerados com sucesso!")
                            st.write("**Adicione estas variáveis ao Streamlit Cloud:**")
                            st.code(f"""
DROPBOX_ACCESS_TOKEN={new_access_token}
DROPBOX_REFRESH_TOKEN={new_refresh_token}
                            """)
                            
                        else:
                            st.error(f"❌ Erro ao gerar tokens: {response.text}")
                            
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
    
    st.divider()
    
    # Verificação unificada do status Dropbox
    st.write("**🔍 Teste de Conexão:**")
    
    with st.spinner("Testando conexão com Dropbox..."):
        dbx = get_dropbox_client_with_retry()
    
    if dbx:
        try:
            # Testar se a conexão realmente funciona
            account = dbx.users_get_current_account()
            st.success(f"✅ **Conectado com sucesso!** Usuário: {account.name.display_name}")
            st.info(f"📧 Email: {account.email}")
            
            # Verificar espaço usado
            try:
                usage = dbx.users_get_space_usage()
                used_gb = usage.used / (1024**3)
                allocated_gb = usage.allocation.get_individual().allocated / (1024**3)
                st.metric("💾 Espaço Usado", f"{used_gb:.2f} GB / {allocated_gb:.2f} GB")
            except Exception as e:
                st.warning(f"⚠️ Não foi possível obter informações de espaço: {str(e)}")
                
        except Exception as e:
            st.error(f"❌ Erro na conexão: {str(e)}")
            st.info("💡 Tentativa automática de renovação do token...")
            
            # Tentar renovação automática
            if auto_refresh_dropbox_token():
                st.success("✅ Token renovado automaticamente!")
                st.rerun()
            else:
                st.error("❌ Falha na renovação automática")
    else:
        st.error("❌ Não foi possível conectar ao Dropbox")
        st.warning("⚠️ Verifique se todas as variáveis estão configuradas corretamente")
        
        # Diagnóstico detalhado
        st.write("**🔍 Diagnóstico Detalhado:**")
        
        if not refresh_token:
            st.info("💡 **REFRESH_TOKEN ausente** - renovação automática não funcionará")
        elif not access_token:
            st.info("💡 **ACCESS_TOKEN ausente** - configure o token inicial")
        elif not app_key or not app_secret:
            st.info("💡 **APP_KEY ou APP_SECRET ausentes** - necessários para renovação")
        else:
            # Todas as variáveis existem, mas conexão falha
            st.warning("🚨 **Todas as variáveis estão configuradas, mas a conexão falha**")
            
            # Testar cada token individualmente
            st.write("**🧪 Teste Individual dos Tokens:**")
            
            # Teste 1: Access Token direto
            try:
                test_dbx = Dropbox(access_token)
                test_account = test_dbx.users_get_current_account()
                st.success(f"✅ ACCESS_TOKEN válido: {test_account.name.display_name}")
            except AuthError as e:
                st.error(f"❌ ACCESS_TOKEN inválido/expirado: {str(e)}")
                
                # Teste 2: Tentar renovação manual
                st.info("🔄 Tentando renovar token...")
                try:
                    import requests
                    
                    token_url = "https://api.dropbox.com/oauth2/token"
                    token_data = {
                        'grant_type': 'refresh_token',
                        'refresh_token': refresh_token,
                        'client_id': app_key,
                        'client_secret': app_secret
                    }
                    
                    response = requests.post(token_url, data=token_data)
                    
                    if response.status_code == 200:
                        token_result = response.json()
                        new_token = token_result.get('access_token')
                        st.success("✅ Token renovado com sucesso!")
                        st.info("💡 **Problema identificado**: TOKEN expirado, mas renovação funciona")
                        st.warning("🔧 **Solução**: Configure o novo token no Streamlit Cloud:")
                        st.code(f"DROPBOX_ACCESS_TOKEN={new_token}")
                        
                    else:
                        st.error(f"❌ Falha na renovação: {response.text}")
                        if "invalid_grant" in response.text:
                            st.error("🚨 **REFRESH_TOKEN inválido** - precisa gerar novos tokens")
                        elif "invalid_client" in response.text:
                            st.error("🚨 **APP_KEY/APP_SECRET inválidos** - verifique as credenciais da app")
                            
                except Exception as e:
                    st.error(f"❌ Erro na renovação: {str(e)}")
                    
            except Exception as e:
                st.error(f"❌ Erro de conexão: {str(e)}")
                if "network" in str(e).lower() or "timeout" in str(e).lower():
                    st.warning("🌐 **Problema de rede** - verifique a conexão com a internet")
                    
            # Teste 3: Verificar formato dos tokens
            st.write("**📋 Verificação de Formato:**")
            if access_token:
                if access_token.startswith('sl.'):
                    st.success("✅ ACCESS_TOKEN tem formato correto (sl.)")
                else:
                    st.warning("⚠️ ACCESS_TOKEN pode ter formato incorreto")
            
            if refresh_token:
                if len(refresh_token) > 20:
                    st.success("✅ REFRESH_TOKEN tem tamanho adequado")
                else:
                    st.warning("⚠️ REFRESH_TOKEN pode estar incompleto")
                    
            if app_key and app_secret:
                if len(app_key) > 10 and len(app_secret) > 10:
                    st.success("✅ APP_KEY e APP_SECRET têm tamanho adequado")
                else:
                    st.warning("⚠️ APP_KEY ou APP_SECRET podem estar incorretos")

    st.divider()
    
    # Seção de backup
    st.subheader("🔄 Gestão de Backups")
    
    # Backup automático
    col1, col2 = st.columns(2)
    with col1:
        destino_backup = st.selectbox(
            "Destino do backup",
            ["Local", "Dropbox", "Ambos"],
            index=2  # Padrão: Ambos
        )
        
        include_photos = st.checkbox("📷 Incluir fotos dos jogadores", value=True)
    
    with col2:
        if st.button("🔄 Criar Backup Completo"):
            with st.spinner("Criando backup completo..."):
                try:
                    if destino_backup == "Local":
                        success = create_backup_with_auto_retry(local_only=True)
                    elif destino_backup == "Dropbox":
                        success = create_backup_with_auto_retry(dropbox_only=True)
                    else:  # Ambos
                        success = create_backup_with_auto_retry()
                    
                    if success:
                        st.success("✅ Backup criado com sucesso!")
                        if include_photos:
                            st.info("📷 Fotos incluídas no backup")
                        
                        # Mostrar informações do backup criado
                        st.write("**📍 Informações do Backup:**")
                        
                        # Verificar se backups locais foram criados
                        backup_dir = "backups"
                        if os.path.exists(backup_dir):
                            backup_files = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.json')]
                            if backup_files:
                                latest_backup = sorted(backup_files)[-1]
                                backup_path = os.path.join(backup_dir, latest_backup)
                                file_size = os.path.getsize(backup_path)
                                st.info(f"📁 **Backup Local**: {latest_backup} ({file_size:,} bytes)")
                                st.code(f"Caminho: {os.path.abspath(backup_path)}")
                            else:
                                st.warning("⚠️ Nenhum backup local encontrado")
                        else:
                            st.warning("⚠️ Pasta 'backups' não existe localmente")
                        
                        # Verificar Dropbox
                        if destino_backup in ["Dropbox", "Ambos"]:
                            dbx_test = get_dropbox_client_with_retry()
                            if dbx_test:
                                try:
                                    # Listar arquivos na pasta /backups do Dropbox
                                    result = dbx_test.files_list_folder("/backups")
                                    dropbox_backups = [entry.name for entry in result.entries if entry.name.startswith('backup_')]
                                    if dropbox_backups:
                                        latest_dropbox = sorted(dropbox_backups)[-1]
                                        st.info(f"☁️ **Backup Dropbox**: {latest_dropbox}")
                                    else:
                                        st.warning("⚠️ Nenhum backup encontrado no Dropbox")
                                except Exception as e:
                                    st.error(f"❌ Erro ao verificar Dropbox: {str(e)}")
                            else:
                                st.warning("⚠️ Não foi possível verificar Dropbox")
                                
                    else:
                        st.error("❌ Falha ao criar backup")
                except Exception as e:
                    st.error(f"❌ Erro inesperado: {str(e)}")

    # Seção de download de backup
    st.write("**💾 Download de Backup Atual**")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Baixar Backup Atual"):
            try:
                # Criar backup temporário para download
                data = DataManager.load_data()
                
                import json
                from datetime import datetime
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"backup_{timestamp}.json"
                
                # Criar conteúdo do backup
                backup_content = json.dumps(data, indent=2, ensure_ascii=False)
                
                # Botão de download
                st.download_button(
                    label="💾 Fazer Download",
                    data=backup_content,
                    file_name=backup_filename,
                    mime="application/json"
                )
                
                st.success("✅ Backup preparado para download!")
                
            except Exception as e:
                st.error(f"❌ Erro ao preparar backup: {str(e)}")
    
    with col2:
        st.info("""
        **💡 Como Funciona:**
        
        • **Versão Online**: Backups criados no servidor Streamlit Cloud
        • **Versão Local**: Backups salvos no seu PC
        • **Download**: Use este botão para baixar dados da versão online
        """)

    st.divider()

    # Seção de restauração
    st.subheader("🗂️ Restaurar Backup")
    
    tab1, tab2, tab3 = st.tabs(["📁 Upload Manual", "💻 Backup Local", "☁️ Backup Dropbox"])
    
    with tab1:
        st.write("**Restaurar arquivo de backup manualmente**")
        uploaded_file = st.file_uploader("Arquivo de dados (.json)", type=["json"])
        uploaded_photos = st.file_uploader("Arquivo de fotos (.zip) - Opcional", type=["zip"])
        
        if uploaded_file is not None:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⚠️ Restaurar Dados", type="primary"):
                    try:
                        temp_path = "data/temp_restore.json"
                        os.makedirs("data", exist_ok=True)
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.read())
                        
                        photos_path = None
                        if uploaded_photos:
                            photos_path = "data/temp_photos.zip"
                            with open(photos_path, "wb") as f:
                                f.write(uploaded_photos.read())
                        
                        if DataManager.restore_backup(temp_path, photos_path):
                            st.success("✅ Backup restaurado com sucesso! Recarregue a página.")
                        else:
                            st.error("❌ Falha ao restaurar backup")
                            
                        # Limpar arquivos temporários
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        if photos_path and os.path.exists(photos_path):
                            os.remove(photos_path)
                            
                    except Exception as e:
                        st.error(f"❌ Erro ao restaurar: {str(e)}")
            
            with col2:
                st.info("⚠️ **ATENÇÃO:** Isso substituirá todos os dados atuais!")

    with tab2:
        st.write("**Restaurar de backups locais existentes**")
        local_backup_dir = "backups"
        if os.path.exists(local_backup_dir):
            backups = sorted([f for f in os.listdir(local_backup_dir) 
                            if f.startswith('backup_') and f.endswith('.json')], reverse=True)
            photos_backups = sorted([f for f in os.listdir(local_backup_dir) 
                                   if f.startswith('fotos_backup_') and f.endswith('.zip')], reverse=True)
            
            if backups:
                selected_local = st.selectbox("Escolha um backup local", backups)
                
                # Verificar se existe backup de fotos correspondente
                corresponding_photo_backup = None
                backup_timestamp = selected_local.replace('backup_', '').replace('.json', '')
                for photo_backup in photos_backups:
                    if backup_timestamp in photo_backup:
                        corresponding_photo_backup = photo_backup
                        break
                
                if corresponding_photo_backup:
                    st.success(f"📷 Backup de fotos encontrado: {corresponding_photo_backup}")
                    restore_photos = st.checkbox("Restaurar fotos também", value=True)
                else:
                    st.warning("📷 Nenhum backup de fotos correspondente encontrado")
                    restore_photos = False
                
                if st.button("⚠️ Restaurar Backup Local", type="primary"):
                    backup_path = os.path.join(local_backup_dir, selected_local)
                    photos_path = os.path.join(local_backup_dir, corresponding_photo_backup) if restore_photos and corresponding_photo_backup else None
                    
                    if DataManager.restore_backup(backup_path, photos_path):
                        st.success("✅ Backup local restaurado com sucesso! Recarregue a página.")
                    else:
                        st.error("❌ Falha ao restaurar backup local")
            else:
                st.info("ℹ️ Nenhum backup local encontrado")
        else:
            st.info("ℹ️ Pasta de backups locais não encontrada")

    with tab3:
        st.write("**Restaurar backup do Dropbox**")
        if dbx:
            try:
                dropbox_backups = list_dropbox_backups_with_retry()
                if dropbox_backups:
                    backup_options = []
                    for backup in dropbox_backups:
                        size_mb = backup['size'] / (1024*1024)
                        date_str = backup['modified'].strftime('%Y-%m-%d %H:%M')
                        backup_options.append(f"{backup['name']} ({date_str}, {size_mb:.1f}MB)")
                    
                    selected_idx = st.selectbox("Escolha um backup do Dropbox", range(len(backup_options)), 
                                              format_func=lambda i: backup_options[i])
                    
                    restore_photos_dropbox = st.checkbox("Tentar restaurar fotos também", value=True)
                    
                    if st.button("⚠️ Restaurar do Dropbox", type="primary"):
                        with st.spinner("Baixando e restaurando backup do Dropbox..."):
                            selected_backup = dropbox_backups[selected_idx]
                            if restore_from_dropbox_with_retry(selected_backup['name'], restore_photos_dropbox):
                                st.success("✅ Backup do Dropbox restaurado com sucesso! Recarregue a página.")
                            else:
                                st.error("❌ Falha ao restaurar backup do Dropbox")
                else:
                    st.info("ℹ️ Nenhum backup encontrado no Dropbox")
            except Exception as e:
                st.error(f"❌ Erro ao listar backups do Dropbox: {str(e)}")
        else:
            st.warning("⚠️ Dropbox não conectado")

    st.divider()
    
    # Seção de manutenção
    st.subheader("🔧 Manutenção do Sistema")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Limpeza de arquivos temporários**")
        if st.button("🧹 Limpar Cache"):
            try:
                # Limpar arquivos temporários
                temp_files = ["data/temp_restore.json", "data/temp_photos.zip", "data/temp_restore_dropbox.json"]
                cleaned = 0
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        cleaned += 1
                
                # Limpar backups antigos (manter apenas os 10 mais recentes)
                if os.path.exists("backups"):
                    backups = sorted([f for f in os.listdir("backups") if f.endswith('.json') or f.endswith('.zip')])
                    if len(backups) > 20:  # Manter 10 dados + 10 fotos
                        for old_backup in backups[:-20]:
                            os.remove(os.path.join("backups", old_backup))
                            cleaned += 1
                
                st.success(f"✅ {cleaned} arquivos limpos")
            except Exception as e:
                st.error(f"❌ Erro na limpeza: {str(e)}")
    
    with col2:
        st.write("**Informações do sistema**")
        data = DataManager.load_data()
        st.metric("� Total de Jogadores", len(data.get('jogadores', [])))
        st.metric("� Total de Treinos", len(data.get('treinos', {})))
        st.metric("⚽ Total de Jogos", len(data.get('jogos', [])))
        st.metric("📐 Total de Táticas", len(data.get('taticas', [])))

    # Informações sobre prevenção de reboot
    st.divider()
    st.subheader("⏰ Prevenção de Reboot")
    st.info("""
    �️ **Sistema de Prevenção Ativo:**
    - A aplicação faz ping automático a cada 5 minutos
    - Detecta atividade do usuário automaticamente  
    - Mantém sessão ativa durante uso normal
    - Reduz significativamente reboots por inatividade
    """)
    
    if st.checkbox("🔍 Mostrar detalhes técnicos"):
        st.code("""
        • JavaScript injected para detectar atividade
        • Fetch requests automáticos em background
        • Session state management otimizado
        • Operações leves para manter conexão
        """)

def get_menu_options(user_type):
    """Retorna os menus baseados no tipo de usuário"""
    return {
        "treinador": {
            "🏠 Dashboard": pagina_dashboard,
            "👥 Jogadores": pagina_jogadores,
            "📅 Treinos": pagina_treinos,
            "� Calendário": pagina_calendario_treinos,
            "�📋 Plano de Treino": pagina_plano_treino,
            "⚽ Jogos": pagina_jogos,
            "📐 Táticas": pagina_taticas,
            "📊 Relatórios": pagina_relatorios,
            "⚙️ Configurações": pagina_configuracoes
        },
        "treinador_adjunto": {  # NOVO
            "🏠 Dashboard": pagina_dashboard,
            "👥 Jogadores": pagina_jogadores,
            "📅 Treinos": pagina_treinos,
            "📆 Calendário": pagina_calendario_treinos,
            "📋 Plano de Treino": pagina_plano_treino,
            "⚽ Jogos": pagina_jogos,
            "📐 Táticas": pagina_taticas,
            "📊 Relatórios": pagina_relatorios
            # Não inclui configurações!
        },
        "jogador": {
            "🏠 Meu Perfil": pagina_perfil_jogador,
            "📆 Calendário": pagina_calendario_treinos,
            "👥 Jogadores": pagina_jogadores
        }
    }.get(user_type, {"🏠 Meu Perfil": pagina_perfil_jogador})

def main():
    """Função principal da aplicação"""
    # Manter aplicação ativa
    keep_alive()
    inject_keep_alive_script()
    
    # Verificação de ambiente
    if os.path.exists('secrets.toml'):
        st.sidebar.info("✅ Modo local detectado")
    else:
        st.sidebar.warning("🌐 Executando no Streamlit Cloud")
    
    # Verificar e inicializar dados
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)
    
    auth = Authentication()
    
    # Inicializar dados
    data = DataManager.load_data()
    needs_save = False
    for jogador in data['jogadores']:
        if 'id' not in jogador:
            jogador['id'] = str(uuid.uuid4())
            needs_save = True

    if needs_save:
        DataManager.save_data(data)
    
    # Verificação de autenticação
    if not st.session_state.get('autenticado'):
        pagina_login()
        return

    # Verificação e sincronização de fotos (apenas no Streamlit Cloud)
    if is_streamlit_cloud() and st.session_state.get('tipo_usuario') == 'treinador':
        if 'fotos_verificadas' not in st.session_state:
            # Verificar se há jogadores sem foto no Dropbox
            data = DataManager.load_data()
            jogadores_sem_foto = [j for j in data.get('jogadores', []) if not j.get('foto_dropbox')]
            
            if len(jogadores_sem_foto) > 0:
                st.sidebar.warning(f"⚠️ {len(jogadores_sem_foto)} jogadores sem foto")
                if st.sidebar.button("🔄 Criar Fotos Automaticamente"):
                    with st.spinner("Criando fotos..."):
                        UIComponents.sincronizar_fotos_dropbox()
                        st.rerun()
            else:
                st.sidebar.success("✅ Todas as fotos sincronizadas")
            
            st.session_state['fotos_verificadas'] = True

    # Obter menus
    user_type = st.session_state.get('tipo_usuario', 'jogador')
    menu_options = get_menu_options(user_type)

    # Barra lateral
    with st.sidebar:
        if os.path.exists(IMAGE_PATHS['logo']):
            st.image(IMAGE_PATHS['logo'], use_container_width=True)
        else:
            st.title("App do Treinador")
        
        st.write(f"Olá, **{st.session_state.get('user', 'Usuário')}**")

        selected = st.radio("Menu", list(menu_options.keys()))

        if user_type == 'treinador':
            mostrar_uso_recursos()

        if st.button("🚪 Sair"):
            st.session_state.clear()
            st.rerun()

    # Exibir página selecionada
    if selected in menu_options:
        menu_options[selected]()
    else:
        st.error("Página não encontrada")
        pagina_dashboard()  # Fallback

if __name__ == "__main__":
    main()
