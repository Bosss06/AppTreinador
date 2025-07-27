import os
import json
import logging
import uuid
import zipfile
import tempfile
from datetime import datetime, timedelta
import dropbox
from dropbox.exceptions import AuthError, ApiError, HttpError
import shutil
import requests
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constantes
DATA_FILE = "data/dados_treino.json"
BACKUP_DIR = "data/backups/"

class DataManager:
    @staticmethod
    def _initialize_data() -> dict:
        """Retorna uma cópia dos dados padrão"""
        return {
            "jogadores": [],
            "treinos": {},
            "exercicios": {},
            "taticas": [],
            "jogos": []
        }

    @staticmethod
    def refresh_dropbox_token():
        """Atualiza o token do Dropbox automaticamente usando refresh token"""
        try:
            refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
            app_key = os.getenv('DROPBOX_APP_KEY')
            app_secret = os.getenv('DROPBOX_APP_SECRET')
            
            if not all([refresh_token, app_key, app_secret]):
                logger.warning("Configurações do Dropbox incompletas para refresh automático")
                return False
            
            # Requisição para renovar o token
            url = "https://api.dropboxapi.com/oauth2/token"
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': app_key,
                'client_secret': app_secret
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                new_access_token = token_data.get('access_token')
                
                # Atualizar variável de ambiente (temporariamente na sessão)
                os.environ['DROPBOX_ACCESS_TOKEN'] = new_access_token
                
                # Salvar em arquivo de configuração local (opcional)
                config_file = "data/dropbox_config.json"
                os.makedirs("data", exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump({
                        'access_token': new_access_token,
                        'updated_at': datetime.now().isoformat()
                    }, f)
                
                logger.info("Token do Dropbox renovado com sucesso")
                return True
            else:
                logger.error(f"Erro ao renovar token: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao renovar token do Dropbox: {str(e)}")
            return False

    @staticmethod
    def get_dropbox_client():
        """Obtém cliente Dropbox com renovação automática de token"""
        try:
            # Tentar carregar token do arquivo local primeiro
            config_file = "data/dropbox_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    token = config.get('access_token')
                    updated_at = datetime.fromisoformat(config.get('updated_at', '2020-01-01'))
                    
                    # Se o token tem menos de 3 horas, usar ele
                    if datetime.now() - updated_at < timedelta(hours=3):
                        os.environ['DROPBOX_ACCESS_TOKEN'] = token
            
            # Tentar usar token atual
            token = os.getenv('DROPBOX_ACCESS_TOKEN')
            if token:
                dbx = dropbox.Dropbox(token)
                # Testar conexão
                try:
                    dbx.users_get_current_account()
                    return dbx
                except AuthError:
                    # Token expirado, tentar renovar
                    if DataManager.refresh_dropbox_token():
                        new_token = os.getenv('DROPBOX_ACCESS_TOKEN')
                        return dropbox.Dropbox(new_token)
                    else:
                        return None
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter cliente Dropbox: {str(e)}")
            return None

    @staticmethod
    def create_photos_backup():
        """Cria um arquivo ZIP com todas as fotos dos jogadores"""
        try:
            photos_dir = "data/fotos"
            if not os.path.exists(photos_dir):
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"backups/fotos_backup_{timestamp}.zip"
            os.makedirs("backups", exist_ok=True)
            
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for root, dirs, files in os.walk(photos_dir):
                    for file in files:
                        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, photos_dir)
                            zipf.write(file_path, arcname)
            
            return zip_filename if os.path.exists(zip_filename) else None
            
        except Exception as e:
            logger.error(f"Erro ao criar backup de fotos: {str(e)}")
            return None

    @staticmethod
    def restore_photos_from_backup(zip_file_path):
        """Restaura fotos a partir de um arquivo ZIP"""
        try:
            photos_dir = "data/fotos"
            os.makedirs(photos_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_file_path, 'r') as zipf:
                zipf.extractall(photos_dir)
            
            logger.info(f"Fotos restauradas de {zip_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao restaurar fotos: {str(e)}")
            return False

    @staticmethod
    def load_data() -> dict:
        """Carrega dados com verificação de integridade"""
        DEFAULT_DATA = DataManager._initialize_data()
        
        try:
            os.makedirs('data', exist_ok=True)
            
            # Se arquivo não existe ou está vazio
            if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_DATA, f)
                return DEFAULT_DATA
            
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Verifica estrutura básica
                for key in DEFAULT_DATA:
                    if key not in data:
                        data[key] = DEFAULT_DATA[key]
                
                # Verifica jogadores
                if isinstance(data['jogadores'], list):
                    for jogador in data['jogadores']:
                        if 'id' not in jogador:
                            jogador['id'] = str(uuid.uuid4())
                
                return data
                
        except json.JSONDecodeError:
            logger.error("Arquivo de dados corrompido - retornando estrutura padrão")
            return DEFAULT_DATA
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}")
            return DEFAULT_DATA

    @staticmethod
    def save_data(data: dict) -> bool:
        """Salva os dados no arquivo JSON"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {str(e)}")
            return False

    @staticmethod
    def create_secure_backup(local_only=False, dropbox_only=False):
        """Cria um backup completo dos dados e fotos (local, Dropbox ou ambos)"""
        try:
            # Criar diretório de backups se não existir
            os.makedirs('backups', exist_ok=True)
            
            # Carregar dados atuais
            data = DataManager.load_data()
            
            # Nome do arquivo de backup com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.json"
            backup_path = os.path.join('backups', backup_filename)
            
            # Criar backup de fotos
            photos_backup = DataManager.create_photos_backup()
            
            # Salvar backup local se não for só Dropbox
            if not dropbox_only:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                logger.info(f"Backup local criado: {backup_path}")
            
            # Tentar fazer upload para o Dropbox se configurado e não for só local
            if not local_only:
                dbx = DataManager.get_dropbox_client()
                if dbx:
                    try:
                        # Upload do arquivo de dados
                        if not dropbox_only:
                            with open(backup_path, 'rb') as f:
                                dbx.files_upload(f.read(), f'/backups/{backup_filename}', mode=dropbox.files.WriteMode.overwrite)
                        else:
                            # Se só Dropbox, faz upload direto dos dados atuais
                            data_content = json.dumps(data, ensure_ascii=False, indent=4).encode('utf-8')
                            dbx.files_upload(data_content, f'/backups/{backup_filename}', mode=dropbox.files.WriteMode.overwrite)
                        
                        # Upload do backup de fotos se existir
                        if photos_backup:
                            photos_filename = os.path.basename(photos_backup)
                            with open(photos_backup, 'rb') as f:
                                dbx.files_upload(f.read(), f'/backups/{photos_filename}', mode=dropbox.files.WriteMode.overwrite)
                            logger.info(f"Backup de fotos enviado para Dropbox: {photos_filename}")
                        
                        logger.info(f"Backup enviado para Dropbox: {backup_filename}")
                        
                    except Exception as e:
                        logger.error(f"Erro ao enviar para Dropbox: {str(e)}")
                        return False
                else:
                    logger.warning("Não foi possível conectar ao Dropbox")
                    if local_only:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar backup: {str(e)}")
            return False
            

    @staticmethod
    def restore_backup(backup_file: str, photos_zip_file: str = None) -> bool:
        """Restaura dados a partir de um backup (dados + fotos opcionais)"""
        try:
            # Verifica se o arquivo existe
            if not os.path.exists(backup_file):
                logger.error(f"Arquivo de backup não encontrado: {backup_file}")
                return False
                
            # Cria backup antes de restaurar
            DataManager.create_secure_backup()
            
            # Restaura os dados
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Restaura fotos se fornecido
            if photos_zip_file and os.path.exists(photos_zip_file):
                DataManager.restore_photos_from_backup(photos_zip_file)
                logger.info("Fotos restauradas com sucesso")
            
            success = DataManager.save_data(backup_data)
            if success:
                logger.info("Backup restaurado com sucesso")
            return success
            
        except Exception as e:
            logger.error(f"Erro ao restaurar backup: {str(e)}")
            return False

    @staticmethod
    def restore_from_dropbox(backup_name: str, restore_photos: bool = True) -> bool:
        """Restaura backup diretamente do Dropbox"""
        try:
            dbx = DataManager.get_dropbox_client()
            if not dbx:
                logger.error("Não foi possível conectar ao Dropbox")
                return False
            
            # Fazer backup atual antes de restaurar
            DataManager.create_secure_backup()
            
            # Baixar arquivo de dados
            temp_data_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
            try:
                _, response = dbx.files_download(f'/backups/{backup_name}')
                temp_data_file.write(response.content)
                temp_data_file.close()
                
                # Restaurar dados
                with open(temp_data_file.name, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                success = DataManager.save_data(backup_data)
                
                # Tentar restaurar fotos se solicitado
                if restore_photos and success:
                    photos_backup_name = backup_name.replace('backup_', 'fotos_backup_').replace('.json', '.zip')
                    try:
                        temp_photos_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
                        _, photos_response = dbx.files_download(f'/backups/{photos_backup_name}')
                        temp_photos_file.write(photos_response.content)
                        temp_photos_file.close()
                        
                        DataManager.restore_photos_from_backup(temp_photos_file.name)
                        os.unlink(temp_photos_file.name)
                        logger.info("Fotos restauradas do Dropbox")
                        
                    except Exception as e:
                        logger.warning(f"Não foi possível restaurar fotos do Dropbox: {str(e)}")
                
                os.unlink(temp_data_file.name)
                return success
                
            except Exception as e:
                if temp_data_file:
                    os.unlink(temp_data_file.name)
                raise e
                
        except Exception as e:
            logger.error(f"Erro ao restaurar do Dropbox: {str(e)}")
            return False

    @staticmethod
    def list_dropbox_backups():
        """Lista backups disponíveis no Dropbox"""
        try:
            dbx = DataManager.get_dropbox_client()
            if not dbx:
                return []
            
            files = dbx.files_list_folder("/backups").entries
            backups = []
            
            for file in files:
                if isinstance(file, dropbox.files.FileMetadata) and file.name.startswith('backup_') and file.name.endswith(".json"):
                    backups.append({
                        'name': file.name,
                        'modified': file.server_modified,
                        'size': file.size
                    })
            
            return sorted(backups, key=lambda x: x['modified'], reverse=True)
            
        except Exception as e:
            logger.error(f"Erro ao listar backups do Dropbox: {str(e)}")
            return []

    @staticmethod
    def list_backups() -> list:
        """Lista todos os backups disponíveis"""
        try:
            if not os.path.exists(BACKUP_DIR):
                return []
                
            backups = []
            for f in os.listdir(BACKUP_DIR):
                if f.startswith('backup_') and f.endswith('.json'):
                    backups.append(f)
                    
            return sorted(backups, reverse=True)
        except Exception as e:
            logger.error(f"Erro ao listar backups: {str(e)}")
            return []
