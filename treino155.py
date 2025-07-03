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

# Backup automático ao iniciar
if not os.path.exists("backups/latest.zip"):
    import subprocess
    subprocess.run(["python", "scripts/backup.py"])

def check_environment():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "check"])
    except subprocess.CalledProcessError:
        st.error("⚠️ Ambiente corrompido! Execute:")
        st.code("pip install --force-reinstall -r requirements.txt")
        st.stop()

check_environment()

# Configurações iniciais
load_dotenv()
st.set_page_config(page_title="App do Treinador PRO ⚽", layout="wide")

# --- Classes de Apoio ---
class PDFReport(FPDF, HTMLMixin):
    """Classe para geração de relatórios em PDF"""
    def header(self):
        self.image("assets/logo.png", 10, 8, 25)
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
        """Gera hash seguro da senha"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    def login(self, username: str, password: str) -> bool:
        """Verifica login pelo campo 'login' em vez de 'nome'"""
        try:
            # Verificação do administrador
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

            # Verificação de jogadores (agora pelo campo 'login')
            data = DataManager.load_data()
            for jogador in data.get('jogadores', []):
                if jogador.get('login', '').lower() == username.lower() and jogador.get('senha_hash'):
                    if bcrypt.checkpw(password.encode(), jogador['senha_hash'].encode()):
                        st.session_state.update({
                            'autenticado': True,
                            'tipo_usuario': 'jogador',
                            'user': jogador['nome'],  # Mostra o nome completo na sessão
                            'jogador_info': jogador
                        })
                        return True
            return False
        except Exception as e:
            st.error(f"Erro na autenticação: {str(e)}")
            return False

    def reset_password(self, username: str, nova_senha: str) -> bool:
        """Redefine a senha de um jogador"""
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
        """Carrega os dados do arquivo JSON"""
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
        """Inicializa a estrutura de dados padrão"""
        return {
            'treinos': {},
            'jogos': [],
            'jogadores': [],
            'taticas': [],
            'exercicios': {
                "Técnica": {"Domínio de bola": 20, "Passe curto": 15, "Finalização": 30},
                "Física": {"Velocidade": 25, "Resistência": 40, "Força": 30},
                "Tática": {"Posicionamento": 35, "Transição": 25, "Marcação": 20}
            }
        }
    
    @staticmethod
    def save_data(data: Dict) -> None:
        """Salva os dados no arquivo JSON"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(DataManager.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            st.error(f"Erro ao salvar dados: {str(e)}")
    
    @staticmethod
    def create_backup() -> str:
        """Cria um backup dos dados"""
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
    """Classe para envio de e-mails"""
    @staticmethod
    def enviar_treino(destinatario: str, assunto: str, corpo: str) -> bool:
        """Envia e-mail com informações de treino"""
        try:
            remetente = os.getenv("EMAIL_USER")
            senha = os.getenv("EMAIL_PASSWORD")
            
            if not remetente or not senha:
                st.error("Configurações de e-mail não encontradas no .env!")
                return False

            # Criar mensagem
            msg = MIMEMultipart()
            msg['From'] = remetente
            msg['To'] = destinatario
            msg['Subject'] = assunto
            msg.attach(MIMEText(corpo, 'html'))

            # Conexão SMTP segura
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
    """Componente de cartão de jogador"""
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if jogador.get('foto') and os.path.exists(jogador['foto']):
            st.image(jogador['foto'], use_container_width=True)
        else:
            avatar_url = f"https://ui-avatars.com/api/?name={jogador['nome'].replace(' ', '+')}&size=150"
            st.image(avatar_url, use_container_width=True)
    
    with col2:
        st.subheader(f"#{jogador.get('nr_camisola', '')} {jogador['nome']}")
        st.caption(f"Posição: {jogador['posicao']} | Idade: {jogador['idade']}")
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

def tactic_editor() -> None:
    """Editor de táticas interativo"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta funcionalidade")
        return
        
    st.subheader("Editor Tático")
    
    formacao = st.selectbox("Formação", ["4-4-2", "4-3-3", "3-5-2", "5-3-2"])
    cor_time = st.color_picker("Cor do Time", "#1E90FF")
    
    data = DataManager.load_data()
    jogadores = [j for j in data['jogadores'] if j.get('posicao')]
    
    st.info("Editor tático interativo será implementado aqui")
    st.write(f"Formação selecionada: {formacao}")
    st.write(f"Cor do time: {cor_time}")
    st.write(f"Jogadores disponíveis: {len(jogadores)}")

# --- Páginas da Aplicação ---
def login_page(auth: Authentication) -> None:
    """Página de login"""
    st.title("🔐 Acesso Restrito")
    
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Entrar"):
            if auth.login(username, password):
                st.rerun()
            else:
                st.error("Credenciais inválidas")

def dashboard_page() -> None:
    """Página inicial do dashboard"""
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

def players_page() -> None:
    """Página de gerenciamento de jogadores"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        player_view_page()
        return
        
    st.title("👥 Gestão de Jogadores")
    data = DataManager.load_data()
    auth = Authentication()
    
    # Filtros e busca
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
    
    # Formulário de novo jogador - ESTRUTURA CORRIGIDA
    with st.expander("➕ Adicionar Novo Jogador", expanded=False):
        form_novo_jogador = st.form(key="form_novo_jogador", clear_on_submit=True)
        with form_novo_jogador:
            cols = st.columns(2)
            with cols[0]:
                nome_completo = st.text_input("Nome Completo*")
                login = st.text_input("Nome para Login* (sem espaços, minúsculas)", 
                                    help="Será usado para acessar o sistema")
                posicao = st.selectbox("Posição*", ["Goleiro", "Defesa", "Meio-Campo", "Ataque"])
                nr_camisola = st.number_input("Nº Camisola", min_value=1, max_value=99)
            
            with cols[1]:
                idade = st.number_input("Idade*", min_value=16, max_value=50)
                telefone = st.text_input("Telefone*", placeholder="912345678")
                email = st.text_input("E-mail*", placeholder="atleta@clube.com")
                foto = st.file_uploader("Foto (opcional)", type=["jpg", "png", "jpeg"])
            
            pontos_fortes = st.multiselect("Pontos Fortes", ["Finalização", "Velocidade", "Força", "Visão de Jogo", "Cabeceamento"])
            
            submitted = st.form_submit_button("💾 Salvar Jogador")
            
            if submitted:
                if not nome_completo or not login or not posicao or not idade or not telefone or not email:
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
    # Listagem de jogadores
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
    
    # Formulário de edição
    if 'edit_player' in st.session_state:
        edit_player_form(st.session_state['edit_player'])

def player_view_page():
    """Página completa de visualização para jogadores"""
    st.title("👤 Meu Perfil")
    data = DataManager.load_data()
    jogador = st.session_state.get('jogador_info')
    
    if not jogador:
        st.warning("Informações do jogador não disponíveis")
        return
    
    # Abas para organizar as informações
    tab1, tab2, tab3 = st.tabs(["📋 Perfil", "📅 Treinos", "⚽ Jogos"])
    
    with tab1:
        # Mostrar informações do jogador
        show_player_card(jogador, read_only=True)
    
    with tab2:
        # Mostrar treinos do jogador
        st.subheader("Meus Próximos Treinos")
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
    
    with tab3:
        # Mostrar jogos do jogador
        st.subheader("Meus Próximos Jogos")
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

def edit_player_form(jogador: Dict) -> None:
    """Formulário completo de edição de jogador com campo de login"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem editar jogadores")
        return

    st.title(f"✏️ Editando: {jogador['nome']}")
    data = DataManager.load_data()
    nome_original = jogador['nome']
    login_original = jogador.get('login', jogador['nome'].lower().replace(' ', '_'))

    with st.form(key=f"form_edicao_{login_original}"):
        cols = st.columns(2)
        with cols[0]:
            novo_nome = st.text_input("Nome Completo*", value=jogador['nome'])
            novo_login = st.text_input(
                "Nome para Login*",
                value=login_original,
                help="Usado para acessar o sistema (sem espaços, minúsculas)"
            )
            nova_posicao = st.selectbox(
                "Posição*",
                ["Goleiro", "Defesa", "Meio-Campo", "Ataque"],
                index=["Goleiro", "Defesa", "Meio-Campo", "Ataque"].index(jogador['posicao'])
            )
            novo_numero = st.number_input(
                "Nº Camisola*",
                value=jogador.get('nr_camisola', 1),
                min_value=1,
                max_value=99
            )

        with cols[1]:
            nova_idade = st.number_input("Idade*", value=jogador['idade'])
            novo_telefone = st.text_input(
                "Telefone*",
                value=jogador.get('telefone', '')
            )
            novo_email = st.text_input(
                "E-mail*",
                value=jogador.get('email', '')
            )
            nova_foto = st.file_uploader(
                "Atualizar Foto",
                type=["jpg", "png", "jpeg"],
                help="Deixe em branco para manter a foto atual"
            )

        novos_pontos = st.multiselect(
            "Pontos Fortes",
            ["Finalização", "Velocidade", "Força", "Visão de Jogo", "Cabeceamento"],
            default=jogador.get('pontos_fortes', [])
        )

        col1, col2, _ = st.columns([1, 1, 2])
        with col1:
            btn_salvar = st.form_submit_button("💾 Salvar Alterações")
        with col2:
            btn_cancelar = st.form_submit_button("❌ Cancelar")

        if btn_salvar:
            try:
                # Validações
                if not all([novo_nome, novo_login, nova_posicao, novo_email]):
                    st.error("Preencha todos os campos obrigatórios (*)")
                elif ' ' in novo_login:
                    st.error("O nome para login não pode conter espaços")
                elif '@' not in novo_email:
                    st.error("Por favor, insira um e-mail válido")
                else:
                    # Prepara os dados atualizados
                    jogador_atualizado = {
                        'nome': novo_nome,
                        'login': novo_login.lower().strip(),
                        'posicao': nova_posicao,
                        'nr_camisola': novo_numero,
                        'idade': nova_idade,
                        'telefone': novo_telefone,
                        'email': novo_email,
                        'pontos_fortes': novos_pontos,
                        'senha_hash': jogador.get('senha_hash')  # Mantém a senha
                    }

                    # Tratamento da foto
                    if nova_foto:
                        # Remove a foto antiga se existir
                        if jogador.get('foto') and os.path.exists(jogador['foto']):
                            os.remove(jogador['foto'])
                        
                        # Salva a nova foto
                        os.makedirs("data/fotos", exist_ok=True)
                        img = ImageOps.fit(Image.open(nova_foto), (300, 300))
                        foto_path = f"data/fotos/{novo_login}.png"
                        img.save(foto_path)
                        jogador_atualizado["foto"] = foto_path
                    else:
                        jogador_atualizado["foto"] = jogador.get('foto')

                    # Atualiza na lista principal
                    for i, j in enumerate(data['jogadores']):
                        if j.get('login', j['nome'].lower().replace(' ', '_')) == login_original:
                            data['jogadores'][i] = jogador_atualizado
                            break

                    DataManager.save_data(data)
                    
                    # Atualiza a sessão se for o próprio jogador
                    if st.session_state.get('jogador_info', {}).get('login') == login_original:
                        st.session_state['jogador_info'] = jogador_atualizado
                    
                    st.success("Dados atualizados com sucesso!")
                    time.sleep(1)  # Pequeno delay para visualização
                    del st.session_state['edit_player']
                    st.rerun()

            except Exception as e:
                st.error(f"Erro crítico ao salvar: {str(e)}")

        elif btn_cancelar:
            del st.session_state['edit_player']
            st.rerun()

def delete_player(jogador: Dict) -> None:
    """Excluir jogador com confirmação"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem remover jogadores")
        return
        
    if st.checkbox(f"Confirmar exclusão de {jogador['nome']}?"):
        data = DataManager.load_data()
        data['jogadores'] = [j for j in data['jogadores'] if j['nome'] != jogador['nome']]
        DataManager.save_data(data)
        st.success(f"Jogador {jogador['nome']} removido!")
        st.rerun()

def training_page() -> None:
    """Página de gerenciamento de treinos"""
    if st.session_state.get('tipo_usuario') == 'jogador':
        st.title("📅 Meus Treinos")
        player_view_page()
        return
        
    st.title("📅 Gestão de Treinos")
    data = DataManager.load_data()
    
    tab1, tab2 = st.tabs(["Agendar Treino", "Treinos Agendados"])
    
    with tab1:
        with st.form("novo_treino"):
            cols = st.columns(2)
            with cols[0]:
                data_treino = st.date_input("Data*", datetime.now())
                objetivo = st.text_input("Objetivo*", "Melhorar finalização")
                categoria = st.selectbox("Categoria*", list(data['exercicios'].keys()))
            
            with cols[1]:
                duracao = st.number_input("Duração (min)*", min_value=30, max_value=180, value=90)
                local = st.text_input("Local*", "Campo Principal")
            
            exercicios = data['exercicios'][categoria]
            selecionados = st.multiselect(
                "Exercícios*", 
                list(exercicios.keys()),
                default=list(exercicios.keys())[:2],
                format_func=lambda x: f"{x} ({exercicios[x]}min)"
            )
            
            if st.form_submit_button("💾 Salvar Treino"):
                data['treinos'][str(data_treino)] = {
                    "objetivo": objetivo,
                    "categoria": categoria,
                    "duracao": duracao,
                    "local": local,
                    "exercicios": selecionados,
                    "participantes": [j['nome'] for j in data['jogadores']]
                }
                DataManager.save_data(data)
                st.success("Treino salvo com sucesso!")
                st.rerun()
    
    with tab2:
        if not data['treinos']:
            st.warning("Nenhum treino agendado")
        else:
            for data_treino, detalhes in sorted(data['treinos'].items(), reverse=True):
                with st.expander(f"📅 {data_treino} - {detalhes['objetivo']}", expanded=False):
                    cols = st.columns(3)
                    cols[0].write(f"**Categoria:** {detalhes['categoria']}")
                    cols[1].write(f"**Duração:** {detalhes['duracao']} min")
                    cols[2].write(f"**Local:** {detalhes['local']}")
                    
                    st.write("**Exercícios:**")
                    for exercicio in detalhes['exercicios']:
                        st.write(f"- {exercicio} ({data['exercicios'][detalhes['categoria']][exercicio]}min)")
                    
                    st.write(f"**Participantes:** {len(detalhes['participantes'])} jogadores")
                    
                    # Seção de envio de e-mail (apenas para treinadores)
                    if st.session_state.get('tipo_usuario') == 'treinador':
                        st.divider()
                        st.subheader("Enviar Treino por E-mail")
                        
                        jogadores_com_email = [j for j in data['jogadores'] 
                                             if j.get('email') and '@' in j['email']]
                        
                        if not jogadores_com_email:
                            st.warning("Nenhum jogador com e-mail válido cadastrado")
                        else:
                            with st.form(f"form_email_{data_treino}"):
                                jogador_selecionado = st.selectbox(
                                    "Destinatário",
                                    jogadores_com_email,
                                    format_func=lambda x: f"{x['nome']} ({x['email']})",
                                    key=f"jogador_{data_treino}"
                                )
                                
                                if st.form_submit_button("Enviar"):
                                    corpo_email = f"""
                                    <h3>Treino Agendado - {data_treino}</h3>
                                    <p><strong>Objetivo:</strong> {detalhes['objetivo']}</p>
                                    <p><strong>Local:</strong> {detalhes['local']}</p>
                                    <p><strong>Duração:</strong> {detalhes['duracao']} minutos</p>
                                    <p><strong>Exercícios:</strong></p>
                                    <ul>
                                        {''.join(f'<li>{ex}</li>' for ex in detalhes['exercicios'])}
                                    </ul>
                                    """
                                    
                                    if EmailSender.enviar_treino(
                                        destinatario=jogador_selecionado['email'],
                                        assunto=f"⚽ Treino {data_treino}",
                                        corpo=corpo_email
                                    ):
                                        st.success(f"E-mail enviado para {jogador_selecionado['nome']}!")
                                    else:
                                        st.error("Falha no envio do e-mail")

def tactics_page() -> None:
    """Página de táticas"""
    if st.session_state.get('tipo_usuario') != 'treinador':
        st.warning("Apenas treinadores podem acessar esta página")
        return
        
    st.title("📐 Táticas do Time")
    
    tab1, tab2 = st.tabs(["Editor Tático", "Táticas Salvas"])
    
    with tab1:
        tactic_editor()
    
    with tab2:
        data = DataManager.load_data()
        if not data.get('taticas'):
            st.warning("Nenhuma tática salva ainda")
        else:
            for i, tatica in enumerate(data['taticas']):
                st.write(f"### {tatica['nome']} ({tatica['formacao']})")
                if tatica.get('imagem') and os.path.exists(tatica['imagem']):
                    st.image(tatica['imagem'], width=300)
                st.caption(tatica['descricao'])

def games_page() -> None:
    """Página de gerenciamento de jogos"""
    if st.session_state.get('tipo_usuario') == 'jogador':
        st.title("⚽ Meus Jogos")
        player_view_page()
        return
        
    st.title("⚽ Gestão de Jogos")
    data = DataManager.load_data()
    
    tab1, tab2 = st.tabs(["Novo Jogo", "Histórico"])
    
    with tab1:
        with st.form("novo_jogo"):
            cols = st.columns(2)
            with cols[0]:
                data_jogo = st.date_input("Data*", datetime.now())
                hora = st.time_input("Hora*", datetime.strptime("15:00", "%H:%M").time())
                adversario = st.text_input("Adversário*")
                tipo_jogo = st.selectbox("Tipo de Jogo*", ["Amistoso", "Campeonato", "Copa", "Treino"])
            
            with cols[1]:
                local = st.text_input("Local*", "Estádio Principal")
                escalacao = st.multiselect(
                    "Convocados*", 
                    [j['nome'] for j in data['jogadores']],
                    default=[j['nome'] for j in data['jogadores'][:11]]
                )
                tatica = st.selectbox(
                    "Tática Recomendada", 
                    ["4-4-2", "4-3-3", "3-5-2", "5-3-2"]
                )
            
            if st.form_submit_button("📅 Agendar Jogo"):
                novo_jogo = {
                    "data": str(data_jogo),
                    "hora": str(hora),
                    "adversario": adversario,
                    "tipo": tipo_jogo,
                    "local": local,
                    "convocados": escalacao,
                    "tatica": tatica,
                    "resultado": None
                }
                data.setdefault('jogos', []).append(novo_jogo)
                DataManager.save_data(data)
                st.success(f"Jogo contra {adversario} agendado para {data_jogo}!")
                st.rerun()
    
    with tab2:
         st.subheader("Próximos Jogos")
    proximos = [j for j in data.get('jogos', []) if not j.get('resultado')]
    
    if not proximos:
        st.warning("Nenhum jogo agendado")
    else:
        for i, jogo in enumerate(sorted(proximos, key=lambda x: x['data'])):
            with st.expander(f"📅 {jogo['data']} - {jogo['adversario']} ({jogo['tipo']})", expanded=False):
                cols = st.columns(3)
                cols[0].write(f"**Local:** {jogo['local']}")
                cols[1].write(f"**Hora:** {jogo['hora']}")
                cols[2].write(f"**Tática:** {jogo.get('tatica', 'A definir')}")
                
                st.write("**Convocados:**")
                for jogador in jogo['convocados']:
                    st.write(f"- {jogador}")
                
                if st.session_state.get('tipo_usuario') == 'treinador':
                    # Adicione o índice 'i' para tornar a chave única
                    if st.button(f"Registrar Resultado", key=f"result_{jogo['data']}_{i}"):
                        st.session_state['edit_game'] = jogo

def reports_page() -> None:
    """Página de relatórios"""
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
                    pdf.cell(0, 10, f"Idade: {jogador['idade']} | Contato: {jogador.get('telefone', 'N/A')}", 0, 1)
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
    """Página de configurações"""
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
    """Função principal da aplicação"""
    auth = Authentication()
    
    if not st.session_state.get('autenticado'):
        login_page(auth)
        return
    
    # Sidebar com menu
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Team+Manager", use_container_width=True)
        st.title(f"Olá, {st.session_state.get('user', 'Treinador')}")
        
        # Menu diferente para treinadores e jogadores
        if st.session_state.get('tipo_usuario') == 'treinador':
            menu_options = ["🏠 Dashboard", "👥 Jogadores", "📅 Treinos", "⚽ Jogos", "📐 Táticas", "📊 Relatórios", "⚙️ Configurações"]
        else:
            menu_options = ["🏠 Meu Perfil"]  # Menu simplificado para jogadores
            
        selected = st.radio("Menu", menu_options)
        
        if st.button("🚪 Sair"):
            st.session_state.clear()
            st.rerun()
    
    # Navegação entre páginas (simplificada para jogadores)
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
    elif selected == "🏠 Meu Perfil":  # Única opção para jogadores
        player_view_page()

if __name__ == "__main__":
    main()
