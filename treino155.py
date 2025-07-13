import streamlit as st
import json
from fpdf import FPDF, HTMLMixin
from datetime import datetime
import os
from PIL import Image, ImageOps
import bcrypt
import base64
from dotenv import load_dotenv
from typing import Dict, List, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
import subprocess
import time
from backup_interface import backup_data
import logging

logging.basicConfig(level=logging.DEBUG)

# --- Configurações Iniciais ---
load_dotenv()
st.set_page_config(page_title="App do Treinador PRO ⚽", layout="wide")

# --- Classes de Apoio ---
class PDFReport(FPDF, HTMLMixin):
    """Classe para geração de relatórios em PDF com tratamento robusto de logo"""
    def __init__(self):
        super().__init__()
        self.has_logo = False
        self.logo_path = "assets/logo.png"
        if os.path.exists(self.logo_path):
            self.has_logo = True
    
    def header(self):
        if self.has_logo:
            try:
                self.image(self.logo_path, 10, 8, 25)
            except:
                self.has_logo = False
        
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'Relatório do Time', 0, 0, 'C')
        self.ln(20)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

class Authentication:
    """Gerenciamento de autenticação seguro"""
    def __init__(self):
        if 'autenticado' not in st.session_state:
            st.session_state.update({
                'autenticado': False,
                'tipo_usuario': None,
                'user': None,
                'jogador_info': None
            })
    
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    def login(self, username: str, password: str) -> bool:
        try:
            admin_user = os.getenv('ADMIN_USER')
            admin_hash = os.getenv('ADMIN_PASSWORD_HASH')
            
            if username == admin_user and admin_hash:
                if bcrypt.checkpw(password.encode(), admin_hash.encode()):
                    st.session_state.update({
                        'autenticado': True,
                        'tipo_usuario': 'treinador',
                        'user': username
                    })
                    return True

            data = DataManager.load_data()
            for jogador in data.get('jogadores', []):
                login_jogador = jogador.get('login', jogador['nome'].lower().replace(' ', '_'))
                if login_jogador.lower() == username.lower() and jogador.get('senha_hash'):
                    if bcrypt.checkpw(password.encode(), jogador['senha_hash'].encode()):
                        st.session_state.update({
                            'autenticado': True,
                            'tipo_usuario': 'jogador',
                            'user': jogador['nome'],
                            'jogador_info': jogador
                        })
                        return True
            return False
        except Exception as e:
            st.error(f"Erro na autenticação: {str(e)}")
            return False

    def reset_password(self, username: str, nova_senha: str) -> bool:
        try:
            data = DataManager.load_data()
            for jogador in data.get('jogadores', []):
                if jogador.get('login', '').lower() == username.lower():
                    jogador['senha_hash'] = self.hash_password(nova_senha)
                    DataManager.save_data(data)
                    return True
            return False
        except Exception as e:
            st.error(f"Erro ao redefinir senha: {str(e)}")
            return False

class DataManager:
    """Gerenciamento centralizado de dados"""
    DATA_FILE = 'data/dados_treino.json'
    BACKUP_DIR = 'data/backups/'
    
    @staticmethod
    def load_data() -> Dict:
        try:
            os.makedirs('data', exist_ok=True)
            if not os.path.exists(DataManager.DATA_FILE):
                return DataManager._initialize_data()
                
            with open(DataManager.DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            return DataManager._initialize_data()
    
    @staticmethod
    def _initialize_data() -> Dict:
        return {
            'treinos': {},
            'jogos': [],
            'jogadores': [{
                "nome": "Exemplo Jogador",
                "login": "exemplo",
                "posicao": "Meio-Campo",
                "nr_camisola": 10,
                "idade": 25,
                "altura": 1.80,
                "peso": 75,
                "ultimo_clube": "Clube Anterior",
                "telefone": "912345678",
                "email": "jogador@exemplo.com",
                "pontos_fortes": ["Finalização", "Visão de Jogo"],
                "senha_hash": bcrypt.hashpw("senha".encode(), bcrypt.gensalt()).decode(),
                "foto": None
            }],
            'taticas': [],
            'exercicios': {
                "Técnica": {"Domínio de bola": 20, "Passe curto": 15, "Finalização": 30},
                "Física": {"Velocidade": 25, "Resistência": 40, "Força": 30},
                "Tática": {"Posicionamento": 35, "Transição": 25, "Marcação": 20}
            }
        }
    
    @staticmethod
    def save_data(data: Dict) -> bool:
        try:
            os.makedirs('data', exist_ok=True)
            temp_path = DataManager.DATA_FILE + '.tmp'
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            if os.path.exists(DataManager.DATA_FILE):
                os.remove(DataManager.DATA_FILE)
            
            os.rename(temp_path, DataManager.DATA_FILE)
            
            if os.path.exists(DataManager.DATA_FILE):
                return True
            return False
            
        except Exception as e:
            st.error(f"ERRO GRAVE: Não foi possível salvar os dados ({str(e)})")
            return False

    @staticmethod
    def create_backup() -> str:
        try:
            os.makedirs(DataManager.BACKUP_DIR, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{DataManager.BACKUP_DIR}backup_{timestamp}.json"
            
            data = DataManager.load_data()
            with open(backup_file, 'w') as f:
                json.dump(data, f)
            
            return backup_file
        except Exception as e:
            st.error(f"Erro ao criar backup: {str(e)}")
            return ""

class EmailSender:
    @staticmethod
    def enviar_treino(destinatario: str, assunto: str, corpo: str) -> bool:
        try:
            remetente = os.getenv("EMAIL_USER")
            senha = os.getenv("EMAIL_PASSWORD")
            
            if not remetente or not senha:
                st.error("Configurações de e-mail não encontradas no .env!")
                return False

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
            st.error(f"Erro no envio do e-mail: {str(e)}")
            return False

# --- Componentes da UI ---
def show_player_card(jogador: Dict, edit_callback=None, delete_callback=None, read_only=False) -> None:
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
        st.write(f"**Telefone:** {jogador.get('telefone', '--')}")
        st.write(f"**E-mail:** {jogador.get('email', '--')}")
        
        if jogador.get('pontos_fortes'):
            st.write("**Pontos Fortes:**")
            cols = st.columns(3)
            for i, pf in enumerate(jogador['pontos_fortes']):
                cols[i%3].success(f"✓ {pf}")
        
        if not read_only and edit_callback and delete_callback:
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("✏️ Editar", key=f"edit_{jogador['nome']}"):
                    edit_callback(jogador)
            with bcol2:
                if st.button("❌ Remover", key=f"del_{jogador['nome']}"):
                    delete_callback(jogador)

def delete_player(jogador: Dict) -> None:
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("❌ Apenas treinadores podem remover jogadores")
        return

    jogador_id = jogador.get('login', jogador['nome'].lower().replace(' ', '_'))
    confirm_key = f"confirm_delete_{jogador_id}"

    if confirm_key not in st.session_state:
        if st.button(f"🗑️ Remover {jogador['nome']}", key=f"delete_{jogador_id}"):
            st.session_state[confirm_key] = True
            st.rerun()
        return

    with st.form(key=f"delete_form_{jogador_id}"):
        st.error(f"CONFIRMAÇÃO: Remover permanentemente {jogador['nome']}?")
        
        if st.form_submit_button("✅ CONFIRMAR REMOÇÃO"):
            try:
                data = DataManager.load_data()
                initial_count = len(data['jogadores'])
                
                data['jogadores'] = [j for j in data['jogadores'] 
                                    if j.get('login', '').lower() != jogador_id.lower()]
                
                if len(data['jogadores']) == initial_count:
                    raise Exception("Nenhum jogador removido")
                
                if not DataManager.save_data(data):
                    raise Exception("Falha ao salvar dados")
                
                if jogador.get('foto') and os.path.exists(jogador['foto']):
                    os.remove(jogador['foto'])
                
                st.success(f"✅ {jogador['nome']} removido com sucesso!")
                time.sleep(1)
                del st.session_state[confirm_key]
                st.session_state['data_reload'] = True
                st.rerun()
                
            except Exception as e:
                st.error(f"FALHA CRÍTICA: {str(e)}")
                st.error("Verifique o arquivo data/dados_treino.json manualmente")

        if st.form_submit_button("❌ Cancelar"):
            del st.session_state[confirm_key]
            st.rerun()

def edit_player_form(jogador: Dict) -> None:
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem editar jogadores")
        return

    st.title(f"✏️ Editando: {jogador['nome']}")
    data = DataManager.load_data()
    auth = Authentication()

    login_original = jogador.get('login', jogador['nome'].lower().replace(' ', '_'))

    with st.form(key=f"form_edicao_{login_original}"):
        cols = st.columns(2)
        with cols[0]:
            novo_nome = st.text_input("Nome Completo*", value=jogador['nome'])
            novo_login = st.text_input("Nome para Login*", value=login_original)
            nova_posicao = st.selectbox("Posição*", ["Goleiro", "Defesa", "Meio-Campo", "Ataque"],
                                      index=["Goleiro", "Defesa", "Meio-Campo", "Ataque"].index(jogador['posicao']))
            novo_numero = st.number_input("Nº Camisola*", value=jogador.get('nr_camisola', 1), min_value=1, max_value=99)
            nova_altura = st.number_input("Altura (m)*", value=jogador.get('altura', 1.70), min_value=1.50, max_value=2.20, step=0.01)
        
        with cols[1]:
            nova_idade = st.number_input("Idade*", value=jogador['idade'])
            novo_peso = st.number_input("Peso (kg)*", value=jogador.get('peso', 70), min_value=40, max_value=120)
            ultimo_clube = st.text_input("Último Clube*", value=jogador.get('ultimo_clube', ''))
            novo_telefone = st.text_input("Telefone*", value=jogador.get('telefone', ''))
            novo_email = st.text_input("E-mail*", value=jogador.get('email', ''))
            nova_foto = st.file_uploader("Atualizar Foto", type=["jpg", "png", "jpeg"])

        novos_pontos = st.multiselect(
            "Pontos Fortes",
            ["Finalização", "Velocidade", "Força", "Visão de Jogo", "Cabeceamento"],
            default=jogador.get('pontos_fortes', [])
        )

        nova_senha = st.text_input("Nova Senha (opcional)", type="password")
        confirmar_senha = st.text_input("Confirmar Nova Senha", type="password")

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("💾 Salvar Alterações")
        with col2:
            if st.form_submit_button("❌ Cancelar"):
                del st.session_state['edit_player']
                st.rerun()

        if submitted:
            try:
                if not all([novo_nome, novo_login, nova_posicao, novo_email, ultimo_clube]):
                    st.error("Preencha todos os campos obrigatórios (*)")
                elif ' ' in novo_login:
                    st.error("O nome para login não pode conter espaços")
                elif '@' not in novo_email:
                    st.error("Por favor, insira um e-mail válido")
                elif nova_senha and nova_senha != confirmar_senha:
                    st.error("As senhas não coincidem.")
                else:
                    jogador_atualizado = {
                        'nome': novo_nome,
                        'login': novo_login.lower().strip(),
                        'posicao': nova_posicao,
                        'nr_camisola': novo_numero,
                        'idade': nova_idade,
                        'altura': nova_altura,
                        'peso': novo_peso,
                        'ultimo_clube': ultimo_clube,
                        'telefone': novo_telefone,
                        'email': novo_email,
                        'pontos_fortes': novos_pontos,
                        'senha_hash': jogador.get('senha_hash'),
                        'foto': jogador.get('foto')
                    }

                    if nova_senha:
                        jogador_atualizado['senha_hash'] = auth.hash_password(nova_senha)

                    if nova_foto:
                        if jogador.get('foto') and os.path.exists(jogador['foto']):
                            os.remove(jogador['foto'])

                        os.makedirs("data/fotos", exist_ok=True)
                        img = ImageOps.fit(Image.open(nova_foto), (300, 300))
                        foto_path = f"data/fotos/{novo_login.lower().replace(' ', '_')}.png"
                        img.save(foto_path)
                        jogador_atualizado["foto"] = foto_path

                    for i, j in enumerate(data['jogadores']):
                        if j.get('login', j['nome'].lower().replace(' ', '_')) == login_original:
                            data['jogadores'][i] = jogador_atualizado
                            break

                    DataManager.save_data(data)
                    st.success("Jogador atualizado com sucesso!")

                    jogador_sessao = st.session_state.get('jogador_info')
                    if jogador_sessao and jogador_sessao.get('login') == login_original:
                       st.session_state['jogador_info'] = jogador_atualizado

                    time.sleep(1)
                    del st.session_state['edit_player']
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {str(e)}")

# --- Páginas da Aplicação ---
def login_page(auth: Authentication) -> None:
    st.title("🔐 Acesso Restrito")
    
    with st.form("login_form"):
        username = st.text_input("Usuário (Login)")
        password = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Entrar"):
            if auth.login(username, password):
                st.rerun()
            else:
                st.error("Credenciais inválidas")

def dashboard_page() -> None:
    st.title("📊 Dashboard do Treinador" if st.session_state.get('tipo_usuario') == 'treinador' else "📋 Meu Painel")
    data = DataManager.load_data()
    
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

def training_page() -> None:
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
    
    st.title("📅 Gestão de Treinos")
    data = DataManager.load_data()
    
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
                DataManager.save_data(data)
                st.success("Treino agendado com sucesso!")
                st.rerun()
    
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

def games_page() -> None:
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
    
    st.title("⚽ Gestão de Jogos")
    data = DataManager.load_data()
    
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
                DataManager.save_data(data)
                st.success("Jogo agendado com sucesso!")
                st.rerun()
    
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

def tactics_page() -> None:
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
            DataManager.save_data(data)
            st.success("Tática salva com sucesso!")

def players_page() -> None:
    if st.session_state.get('tipo_usuario') != 'treinador':
        player_view_page()
        return
        
    st.title("👥 Gestão de Jogadores")
    data = DataManager.load_data()
    auth = Authentication()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        posicoes = list({j['posicao'] for j in data['jogadores']}) if data['jogadores'] else []
        pos_filter = st.selectbox("Filtrar por posição", ["Todos"] + posicoes)
    with col2:
        search_term = st.text_input("Buscar por nome")
    with col3:
        items_per_page = st.selectbox("Jogadores por página", [5, 10, 20], index=1)
    
    filtered_players = data['jogadores']
    if pos_filter != "Todos":
        filtered_players = [j for j in filtered_players if j['posicao'] == pos_filter]
    if search_term:
        filtered_players = [j for j in filtered_players if search_term.lower() in j['nome'].lower()]
    
    total_pages = max(1, (len(filtered_players) // items_per_page + 1))
    page = st.number_input("Página", min_value=1, max_value=total_pages, value=1)
    paginated_players = filtered_players[(page-1)*items_per_page : page*items_per_page]
    
    with st.expander("➕ Adicionar Novo Jogador", expanded=False):
        with st.form(key="form_novo_jogador", clear_on_submit=True):
            cols = st.columns(2)
            with cols[0]:
                nome_completo = st.text_input("Nome Completo*")
                login = st.text_input("Nome para Login* (sem espaços, minúsculas)", 
                                    help="Será usado para acessar o sistema")
                posicao = st.selectbox("Posição*", ["Goleiro", "Defesa", "Meio-Campo", "Ataque"])
                nr_camisola = st.number_input("Nº Camisola", min_value=1, max_value=99)
                altura = st.number_input("Altura (m)*", min_value=1.50, max_value=2.20, value=1.75, step=0.01)
            
            with cols[1]:
                idade = st.number_input("Idade*", min_value=16, max_value=50)
                peso = st.number_input("Peso (kg)*", min_value=40, max_value=120, value=70)
                ultimo_clube = st.text_input("Último Clube*")
                telefone = st.text_input("Telefone*", placeholder="912345678")
                email = st.text_input("E-mail*", placeholder="atleta@clube.com")
                foto = st.file_uploader("Foto (opcional)", type=["jpg", "png", "jpeg"])
            
            pontos_fortes = st.multiselect("Pontos Fortes", ["Finalização", "Velocidade", "Força", "Visão de Jogo", "Cabeceamento"])
            
            if st.form_submit_button("💾 Salvar Jogador"):
                if not all([nome_completo, login, posicao, idade, altura, peso, ultimo_clube, telefone, email]):
                    st.error("Preencha todos os campos obrigatórios (*)")
                elif ' ' in login:
                    st.error("O nome para login não pode conter espaços")
                else:
                    novo_jogador = {
                        "nome": nome_completo,
                        "login": login.lower(),
                        "posicao": posicao,
                        "nr_camisola": nr_camisola,
                        "idade": idade,
                        "altura": altura,
                        "peso": peso,
                        "ultimo_clube": ultimo_clube,
                        "telefone": telefone,
                        "email": email,
                        "pontos_fortes": pontos_fortes,
                        "senha_hash": auth.hash_password(f"jogador_{login.lower()}"),
                        "foto": None
                    }
                    
                    if foto:
                        try:
                            os.makedirs("data/fotos", exist_ok=True)
                            img = ImageOps.fit(Image.open(foto), (300, 300))
                            foto_path = f"data/fotos/{login.lower().replace(' ', '_')}.png"
                            img.save(foto_path)
                            novo_jogador["foto"] = foto_path
                        except Exception as e:
                            st.error(f"Erro ao salvar foto: {str(e)}")
                    
                    data['jogadores'].append(novo_jogador)
                    DataManager.save_data(data)
                    st.success("Jogador adicionado com sucesso!")
                    st.rerun()

    st.subheader(f"🏃‍♂️ Elenco ({len(filtered_players)} jogadores)")
    
    if not paginated_players:
        st.warning("Nenhum jogador encontrado com os filtros atuais")
    else:
        for jogador in paginated_players:
            show_player_card(
                jogador,
                edit_callback=lambda j: st.session_state.update({'edit_player': j}),
                delete_callback=lambda j: delete_player(j),
                read_only=False
            )
    
    if 'edit_player' in st.session_state:
        edit_player_form(st.session_state['edit_player'])

    # DEBUG: Verificação de persistência
    if st.session_state.get('tipo_usuario') == 'treinador':
        with st.expander("🔍 DEBUG - Ver dados atuais", expanded=False):
            st.write("Caminho do arquivo:", os.path.abspath(DataManager.DATA_FILE))
            if os.path.exists(DataManager.DATA_FILE):
                st.write(f"Tamanho do arquivo: {os.path.getsize(DataManager.DATA_FILE)} bytes")
                with open(DataManager.DATA_FILE, 'r') as f:
                    st.code(f.read())

def player_view_page():
    st.title("👤 Meu Perfil")
    data = DataManager.load_data()
    jogador = st.session_state.get('jogador_info')
    
    if not jogador:
        st.warning("Informações do jogador não disponíveis")
        return
    
    show_player_card(jogador, read_only=True)
    
    st.subheader("📅 Meus Próximos Treinos")
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

def reports_page() -> None:
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
                pdf = PDFReport()
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

def settings_page() -> None:
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
        
    st.title("⚙️ Configurações do Sistema")
    
    st.subheader("Backup de Dados")
    if st.button("🔄 Criar Backup Agora"):
        backup_file = DataManager.create_backup()
        if backup_file:
            st.success(f"Backup criado com sucesso: {backup_file}")
    
    st.subheader("Restaurar Backup")
    backups = []
    if os.path.exists(DataManager.BACKUP_DIR):
        backups = sorted([f for f in os.listdir(DataManager.BACKUP_DIR) if f.startswith('backup_')], reverse=True)
    
    if backups:
        backup_selecionado = st.selectbox("Selecione um backup", backups)
        
        if st.button("🔄 Restaurar Backup Selecionado"):
            with open(os.path.join(DataManager.BACKUP_DIR, backup_selecionado), 'r') as f:
                data = json.load(f)
            DataManager.save_data(data)
            st.success("Backup restaurado com sucesso!")
            st.rerun()
    else:
        st.warning("Nenhum backup disponível")

# --- Main App ---
def main() -> None:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "check"])
    except subprocess.CalledProcessError:
        st.error("⚠️ Ambiente corrompido! Execute:")
        st.code("pip install --force-reinstall -r requirements.txt")
        st.stop()
    
    if st.button("💾 Fazer backup agora"):
        if backup_data():
            st.success("Backup criado com sucesso!")
        else:
            st.error("Erro ao criar backup.")
    
    auth = Authentication()
    
    data = DataManager.load_data()
    needs_save = False
    for jogador in data['jogadores']:
        if 'login' not in jogador:
            jogador['login'] = jogador['nome'].lower().replace(' ', '_')
            needs_save = True
        if 'senha_hash' not in jogador:
            jogador['senha_hash'] = auth.hash_password(f"jogador_{jogador['login']}")
            needs_save = True
        if 'altura' not in jogador:
            jogador['altura'] = 1.75
            needs_save = True
        if 'peso' not in jogador:
            jogador['peso'] = 70
            needs_save = True
        if 'ultimo_clube' not in jogador:
            jogador['ultimo_clube'] = 'Desconhecido'
            needs_save = True
    
    if needs_save:
        DataManager.save_data(data)
    
    if not st.session_state.get('autenticado'):
        login_page(auth)
        return
    
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Team+Manager", use_container_width=True)
        st.title(f"Olá, {st.session_state.get('user', 'Treinador')}")
        
        if st.session_state.get('tipo_usuario') == 'treinador':
            menu_options = ["🏠 Dashboard", "👥 Jogadores", "📅 Treinos", "⚽ Jogos", "📐 Táticas", "📊 Relatórios", "⚙️ Configurações"]
        else:
            menu_options = ["🏠 Meu Perfil"]
            
        selected = st.radio("Menu", menu_options)
        
        if st.button("🚪 Sair"):
            st.session_state.clear()
            st.rerun()
    
    if selected == "🏠 Dashboard":
        dashboard_page()
    elif selected == "👥 Jogadores":
        players_page()
    elif selected == "📅 Treinos":
        training_page()
    elif selected == "⚽ Jogos":
        games_page()
    elif selected == "📐 Táticas":
        tactics_page()
    elif selected == "📊 Relatórios":
        reports_page()
    elif selected == "⚙️ Configurações":
        settings_page()
    elif selected == "🏠 Meu Perfil":
        player_view_page()

if __name__ == "__main__":
    main()
