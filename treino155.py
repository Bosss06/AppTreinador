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

# --- Configurações Iniciais ---
load_dotenv()
st.set_page_config(page_title="App do Treinador PRO ⚽", layout="wide")
logging.basicConfig(level=logging.INFO)

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
        if 'autenticado' not in st.session_state:
            st.session_state.update({
                'autenticado': False,
                'tipo_usuario': None,
                'user': None,
                'jogador_info': None
            })
    
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def login(self, username: str, password: str) -> bool:
        try:
            # Verifica admin
            admin_user = os.getenv('ADMIN_USER')
            admin_hash = os.getenv('ADMIN_PASSWORD_HASH')
            
            if username == admin_user and admin_hash:
                if bcrypt.checkpw(password.encode('utf-8'), admin_hash.encode('utf-8')):
                    st.session_state.update({
                        'autenticado': True,
                        'tipo_usuario': 'treinador',
                        'user': username
                    })
                    return True

            # Verifica jogadores
            data = DataManager.load_data()
            for jogador in data.get('jogadores', []):
                login_jogador = jogador.get('login', jogador['nome'].lower().replace(' ', '_'))
                if login_jogador.lower() == username.lower() and jogador.get('senha_hash'):
                    if bcrypt.checkpw(password.encode('utf-8'), jogador['senha_hash'].encode('utf-8')):
                        st.session_state.update({
                            'autenticado': True,
                            'tipo_usuario': 'jogador',
                            'user': jogador['nome'],
                            'jogador_info': jogador
                        })
                        return True
            return False
        except Exception as e:
            logging.error(f"Erro na autenticação: {str(e)}")
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
    def mostrar_card_jogador(jogador: Dict, read_only: bool = False, hide_contacts: bool = False):
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if jogador.get('foto') and os.path.exists(jogador['foto']):
                st.image(jogador['foto'], use_container_width=True)
            else:
                avatar_url = f"https://ui-avatars.com/api/?name={jogador['nome'].replace(' ', '+')}&size=150"
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
                
                # Layout do formulário
                cols = st.columns(2)
                with cols[0]:
                    nome = st.text_input("Nome Completo*", value=dados['nome'])
                    login = st.text_input("Login* (sem espaços)", value=dados['login'], disabled=modo_edicao)
                    posicao = st.selectbox("Posição*", ["Goleiro", "Defesa", "Meio-Campo", "Ataque"],
                                         index=["Goleiro", "Defesa", "Meio-Campo", "Ataque"].index(dados['posicao']))
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
                    ["Finalização", "Velocidade", "Força", "Visão de Jogo", "Cabeceamento"],
                    default=dados['pontos_fortes']
                )

                # Só mostra campo de senha para novo jogador
            
                if not modo_edicao:
                        senha = st.text_input("Senha*", type="password")
                else:
                        nova_senha = st.text_input("Nova Senha (opcional)", type="password")
                        if nova_senha:
                            if st.form_submit_button("🔑 Resetar Senha"):
                                if resetar_senha_jogador(login, nova_senha):
                                    st.success("Senha redefinida com sucesso!")
                                    st.experimental_rerun()
                            else:
                                st.error("Erro ao redefinir senha.") 

                # Botões de ação
                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("💾 Salvar")
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        if 'edit_player' in st.session_state:
                            del st.session_state['edit_player']
                        st.rerun()

                if submitted:
                    campos_obrigatorios = [nome, login, posicao, idade, altura, peso, ultimo_clube, telefone, email]
                    if not all(campos_obrigatorios):
                        st.error("Preencha todos os campos obrigatórios (*)")
                    else:
                        try:
                            novo_jogador = {
                                "id": dados['id'],  # Mantém o ID existente ou usa o novo
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
                                "senha_hash": dados['senha_hash'] if modo_edicao else Authentication().hash_password(senha),
                                "foto": dados['foto']
                            }

                            if foto:
                                os.makedirs("data/fotos", exist_ok=True)
                                img = ImageOps.fit(Image.open(foto), (300, 300))
                                foto_path = f"data/fotos/{login.lower().replace(' ', '_')}.png"
                                img.save(foto_path)
                                novo_jogador["foto"] = foto_path

                            data = DataManager.load_data()
                            if modo_edicao:
                                for i, j in enumerate(data['jogadores']):
                                    if j.get('id') == dados.get('id'):
                                        data['jogadores'][i] = novo_jogador
                                        break
                            else:
                                data['jogadores'].append(novo_jogador)

                            if DataManager.save_data(data):
                                st.success("Jogador salvo com sucesso!")
                                time.sleep(1)
                                if 'edit_player' in st.session_state:
                                    del st.session_state['edit_player']
                                st.rerun()

                        except Exception as e:
                            st.error(f"Erro ao salvar: {str(e)}")

        except Exception as e:
            st.error(f"Erro inesperado no formulário: {str(e)}")

# --- Funções Auxiliares ---
def mostrar_uso_recursos():
    """Mostra estatísticas de uso de recursos na barra lateral"""
    data = DataManager.load_data()
    st.sidebar.subheader("📊 Estatísticas")
    
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Jogadores", len(data['jogadores']))
    col2.metric("Treinos", len(data['treinos']))
    
    if 'jogos' in data:
        st.sidebar.metric("Jogos", len(data['jogos']))

def resetar_senha_jogador(login_jogador, nova_senha):
    """Reseta a senha de um jogador"""
    try:
        data = DataManager.load_data()
        auth = Authentication()
        
        for jogador in data['jogadores']:
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
    
    with st.form("login_form"):
        username = st.text_input("Usuário (Login)")
        password = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Entrar"):
            if auth.login(username, password):
                st.rerun()
            else:
                st.error("Credenciais inválidas")

def pagina_dashboard():
    """Página inicial do sistema"""
    st.title("📊 Dashboard do Treinador" if st.session_state.get('tipo_usuario') == 'treinador' else "📋 Meu Painel")
    data = DataManager.load_data()
    
    # Métricas
    if st.session_state.get('tipo_usuario') == 'treinador':
        col1, col2, col3 = st.columns(3)
        col1.metric("👥 Jogadores", len(data['jogadores']))
        col2.metric("📅 Treinos", len(data['treinos']))
        col3.metric("⚽ Jogos", len(data.get('jogos', [])))
    else:
        jogador = st.session_state.get('jogador_info', {})
        col1, col2 = st.columns(2)
        col1.metric("📅 Próximos Treinos", len([t for t in data['treinos'].values() if jogador.get('nome') in t.get('participantes', [])]))
        col2.metric("⚽ Próximos Jogos", len([j for j in data.get('jogos', []) if not j.get('resultado') and jogador.get('nome') in j.get('convocados', [])]))
    
    # Próximos compromissos
    st.subheader("📅 Próximos Compromissos")
    tab1, tab2 = st.tabs(["Próximos Treinos", "Próximos Jogos"])
    
    with tab1:
        if st.session_state.get('tipo_usuario') == 'treinador':
            treinos = data['treinos'].items()
        else:
            jogador_nome = st.session_state.get('jogador_info', {}).get('nome')
            treinos = [(dt, t) for dt, t in data['treinos'].items() if jogador_nome in t.get('participantes', [])]
        
        if treinos:
            next_train = min(treinos, key=lambda x: datetime.strptime(x[0], '%Y-%m-%d'))
            st.write(f"**Data:** {next_train[0]}")
            st.write(f"**Objetivo:** {next_train[1]['objetivo']}")
            st.write(f"**Exercícios:** {', '.join(next_train[1]['exercicios'])}")
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
    data = DataManager.load_data()

    is_treinador = st.session_state.get('tipo_usuario') == 'treinador'

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        posicoes = list({j['posicao'] for j in data['jogadores']}) if data['jogadores'] else []
        pos_filter = st.selectbox("Filtrar por posição", ["Todos"] + posicoes)
    with col2:
        search_term = st.text_input("Buscar por nome")
    with col3:
        items_per_page = st.selectbox("Jogadores por página", [5, 10, 20], index=1)

    # Aplicar filtros
    filtered_players = data['jogadores']
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
                        data['jogadores'] = [j for j in data['jogadores'] if j['id'] != jogador['id']]
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
    
    for data_treino, detalhes in data['treinos'].items():
        if jogador['nome'] in detalhes.get('participantes', []):
            treinos_jogador.append((data_treino, detalhes))
    
    if not treinos_jogador:
        st.warning("Nenhum treino agendado para você")
    else:
        for data_treino, detalhes in sorted(treinos_jogador):
            with st.expander(f"📅 {data_treino} - {detalhes['objetivo']}", expanded=False):
                st.write(f"**Local:** {detalhes['local']}")
                st.write(f"**Duração:** {detalhes['duracao']} min")
                st.write("**Exercícios:**")
                for exercicio in detalhes['exercicios']:
                    st.write(f"- {exercicio}")
    
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
            for categoria, exercs in data['exercicios'].items():
                for exerc, duracao in exercs.items():
                    exercicios_disponiveis.append(f"{categoria}: {exerc}")
            
            exercicios = st.multiselect("Exercícios", exercicios_disponiveis)
            
            jogadores_disponiveis = [j['nome'] for j in data['jogadores']]
            participantes = st.multiselect("Participantes", jogadores_disponiveis)
            
            if st.form_submit_button("💾 Agendar Treino"):
                data_str = data_treino.strftime('%Y-%m-%d')
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
            with st.expander(f"{data_treino} - {detalhes['objetivo']} ({detalhes['local']})", expanded=False):
                st.write(f"**Hora:** {detalhes['hora']}")
                st.write(f"**Duração:** {detalhes['duracao']} minutos")
                st.write(f"**Participantes:** {', '.join(detalhes['participantes'])}")
                st.write("**Exercícios:**")
                for exercicio in detalhes['exercicios']:
                    st.write(f"- {exercicio}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_treino_{data_treino}"):
                        st.session_state['edit_treino'] = (data_treino, detalhes)
                        st.rerun()
                with col2:
                    if st.button("🗑️ Eliminar", key=f"del_treino_{data_treino}"):
                        data['treinos'].pop(data_treino)
                        DataManager.save_data(data)
                        st.success("Treino eliminado!")
                        st.rerun()
                        # Formulário de edição (fora do loop)
        if 'edit_treino' in st.session_state:
            data_treino, detalhes = st.session_state['edit_treino']
            with st.form(key="form_edit_treino"):
                st.subheader(f"Editar Treino: {data_treino}")
                hora = st.time_input("Hora", value=datetime.strptime(detalhes['hora'], "%H:%M").time())
                local = st.text_input("Local", value=detalhes['local'])
                objetivo = st.text_input("Objetivo", value=detalhes['objetivo'])
                duracao = st.number_input("Duração (minutos)", value=detalhes['duracao'], min_value=30, max_value=180)
                exercicios = st.multiselect("Exercícios", detalhes['exercicios'], default=detalhes['exercicios'])
                participantes = st.multiselect("Participantes", [j['nome'] for j in data['jogadores']], default=detalhes['participantes'])
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Salvar Alterações"):
                        data['treinos'][data_treino] = {
                            'hora': hora.strftime('%H:%M'),
                            'local': local,
                            'objetivo': objetivo,
                            'duracao': duracao,
                            'exercicios': exercicios,
                            'participantes': participantes
                        }
                        DataManager.save_data(data)
                        del st.session_state['edit_treino']
                        st.success("Treino editado com sucesso!")
                        st.rerun()
                with col2:
                    if st.form_submit_button("❌ Cancelar"):
                        del st.session_state['edit_treino']
                        st.rerun()

    # Notificar jogadores
    st.subheader("📧 Notificar Jogadores sobre Treino")
    
    if not data['treinos']:
        st.warning("Nenhum treino agendado para notificar")
        return
    
    treino_selecionado = st.selectbox(
        "Selecione o treino para notificar",
        options=list(data['treinos'].keys()),
        format_func=lambda x: f"{x} - {data['treinos'][x]['objetivo']}"
    )
    
    assunto = st.text_input(
        "Assunto do e-mail",
        value=f"Informações sobre o treino de {treino_selecionado}"
    )
    
    corpo = st.text_area(
        "Mensagem (suporta HTML)",
        value=f"""
        <h2>Informações do Treino</h2>
        <p><strong>Data:</strong> {treino_selecionado}</p>
        <p><strong>Objetivo:</strong> {data['treinos'][treino_selecionado]['objetivo']}</p>
        <p><strong>Local:</strong> {data['treinos'][treino_selecionado]['local']}</p>
        <p><strong>Exercícios:</strong></p>
        <ul>
            {"".join(f"<li>{ex}</li>" for ex in data['treinos'][treino_selecionado]['exercicios'])}
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
        with st.form(key="form_edit_jogo"):
            st.subheader(f"Editar Jogo: {jogo['data']} vs {jogo['adversario']}")
            hora = st.time_input("Hora", value=datetime.strptime(jogo['hora'], "%H:%M").time())
            adversario = st.text_input("Adversário", value=jogo['adversario'])
            local = st.text_input("Local", value=jogo['local'])
            tipo = st.selectbox("Tipo de Jogo", ["Amistoso", "Campeonato", "Copa", "Treino"], index=["Amistoso", "Campeonato", "Copa", "Treino"].index(jogo['tipo']))
            convocados = st.multiselect("Convocados", [j['nome'] for j in data['jogadores']], default=jogo['convocados'])
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
        posicoes = ["Goleiro", "Defesa 1", "Defesa 2", "Defesa 3", "Defesa 4", 
                   "Meio 1", "Meio 2", "Meio 3", "Meio 4", 
                   "Atacante 1", "Atacante 2"]
    elif formacao == "4-3-3":
        posicoes = ["Goleiro", "Defesa 1", "Defesa 2", "Defesa 3", "Defesa 4", 
                   "Meio 1", "Meio 2", "Meio 3", 
                   "Atacante 1", "Atacante 2", "Atacante 3"]
    else:  # 3-5-2
        posicoes = ["Goleiro", "Defesa 1", "Defesa 2", "Defesa 3", 
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
    st.title("⚙️ Configurações do Sistema")
    
    # Seção de status
    st.subheader("Status do Dropbox")
    dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
    dbx = None
    if not dropbox_token:
        st.error("❌ Token do Dropbox não configurado")
    else:
        try:
            dbx = dropbox.Dropbox(dropbox_token)
            account = dbx.users_get_current_account()
            st.success(f"✅ Conectado ao Dropbox como: {account.name.display_name}")
        except AuthError:
            st.error("❌ Token do Dropbox expirado ou inválido")
        except Exception as e:
            st.error(f"⚠️ Erro na conexão: {str(e)}")
    
    # Botão de backup
    if st.button("🔄 Criar Backup Agora"):
        with st.spinner("Criando backup..."):
            try:
                success = DataManager.create_secure_backup()
                # ...restante do seu código de backup...
            except Exception as e:
                st.error(f"❌ Erro inesperado: {str(e)}")

    # --- NOVA SEÇÃO: Restaurar Backup de Segurança ---
    st.subheader("🗂️ Restaurar Backup de Segurança")

    # Opção 1: Upload manual
    uploaded_file = st.file_uploader("Restaurar backup manualmente (.json)", type=["json"])
    if uploaded_file is not None:
        if st.button("⚠️ Restaurar este backup (upload manual)"):
            try:
                temp_path = "data/temp_restore.json"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.read())
                if DataManager.restore_backup(temp_path):
                    st.success("Backup restaurado com sucesso! Recarregue a página.")
                else:
                    st.error("Falha ao restaurar backup.")
            except Exception as e:
                st.error(f"Erro ao restaurar backup: {str(e)}")

    # Opção 2: Restaurar de backups locais
    st.markdown("---")
    st.subheader("Restaurar backup local existente")
    local_backup_dir = "backups"
    if os.path.exists(local_backup_dir):
        backups = sorted([f for f in os.listdir(local_backup_dir) if f.startswith('backup_') and f.endswith('.json')], reverse=True)
        if backups:
            selected_local = st.selectbox("Escolha um backup local", backups)
            if st.button("⚠️ Restaurar este backup local"):
                backup_path = os.path.join(local_backup_dir, selected_local)
                if DataManager.restore_backup(backup_path):
                    st.success("Backup local restaurado com sucesso! Recarregue a página.")
                else:
                    st.error("Falha ao restaurar backup local.")
        else:
            st.info("Nenhum backup local encontrado.")
    else:
        st.info("Pasta de backups locais não encontrada.")

    # Opção 3: Restaurar do Dropbox
    if dropbox_token:
        st.markdown("---")
        st.subheader("Restaurar backup do Dropbox")
        try:
            dbx = dropbox.Dropbox(dropbox_token)
            files = dbx.files_list_folder("/backups").entries
            backups_dropbox = [f for f in files if isinstance(f, dropbox.files.FileMetadata) and f.name.endswith(".json")]
            backups_dropbox = sorted(backups_dropbox, key=lambda x: x.server_modified, reverse=True)
            if backups_dropbox:
                nomes = [f"{b.name} ({b.server_modified.strftime('%Y-%m-%d %H:%M')})" for b in backups_dropbox]
                selected_idx = st.selectbox("Escolha um backup do Dropbox", range(len(nomes)), format_func=lambda i: nomes[i])
                if st.button("⚠️ Restaurar este backup do Dropbox"):
                    with st.spinner("Baixando e restaurando backup..."):
                        backup_file = backups_dropbox[selected_idx]
                        _, res = dbx.files_download(backup_file.path_display)
                        temp_path = "data/temp_restore_dropbox.json"
                        with open(temp_path, "wb") as f:
                            f.write(res.content)
                        if DataManager.restore_backup(temp_path):
                            st.success("Backup do Dropbox restaurado com sucesso! Recarregue a página.")
                        else:
                            st.error("Falha ao restaurar backup do Dropbox.")
            else:
                st.info("Nenhum backup encontrado no Dropbox.")
        except Exception as e:
            st.error(f"Erro ao listar/restaurar backups do Dropbox: {str(e)}")

def get_menu_options(user_type):
    """Retorna os menus baseados no tipo de usuário"""
    return {
        "treinador": {
            "🏠 Dashboard": pagina_dashboard,
            "👥 Jogadores": pagina_jogadores,
            "📅 Treinos": pagina_treinos,
            "📋 Plano de Treino": pagina_plano_treino,
            "⚽ Jogos": pagina_jogos,
            "📐 Táticas": pagina_taticas,
            "📊 Relatórios": pagina_relatorios,
            "⚙️ Configurações": pagina_configuracoes
        },
        "jogador": {
            "🏠 Meu Perfil": pagina_perfil_jogador,
            "👥 Jogadores": pagina_jogadores  # <-- Adicione esta linha
        }
    }.get(user_type, {"🏠 Meu Perfil": pagina_perfil_jogador})

def main():
    """Função principal da aplicação"""
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
