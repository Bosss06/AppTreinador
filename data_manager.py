import os
import json
import logging
from datetime import datetime, timedelta
import dropbox
from dropbox.exceptions import AuthError, ApiError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class DataManager:
    # Estrutura padrão dos dados
    DEFAULT_DATA = {
        "jogadores": [],
        "exercicios": [],
        "treinos": [],
        "historico": []
    }

    @staticmethod
    def _initialize_data() -> dict:
        """Retorna uma cópia dos dados padrão"""
        return DataManager.DEFAULT_DATA.copy()

    @staticmethod
    def load_data() -> dict:
        """Carrega dados locais ou restaura do backup se necessário"""
        DATA_FILE = "data/dados_treino.json"
        
        try:
            os.makedirs('data', exist_ok=True)
            
            # Tenta carregar dados locais
            if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Verifica se há jogadores (sinal de dados válidos)
                    if len(data.get('jogadores', [])) > 0:
                        return data
                    
                    # Se não há jogadores, tenta restaurar do backup
                    restored_data = DataManager._restore_backup()
                    if restored_data:
                        return restored_data
            
            # Se chegou aqui, precisa inicializar ou restaurar
            restored_data = DataManager._restore_backup()
            return restored_data if restored_data else DataManager._initialize_data()
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {e}")
            return DataManager._initialize_data()

    @staticmethod
    def _restore_backup() -> dict:
        """Tenta restaurar do backup mais recente"""
        try:
            # 1. Verifica backups locais
            if os.path.exists("backups"):
                backups = sorted(
                    [f for f in os.listdir("backups") if f.startswith("backup_")],
                    reverse=True
                )
                if backups:
                    with open(f"backups/{backups[0]}", 'r') as f:
                        return json.load(f)
            
            # 2. Tenta restaurar do Dropbox
            dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
            if dropbox_token:
                dbx = dropbox.Dropbox(dropbox_token)
                
                # Lista backups no Dropbox (últimos 7 dias)
                try:
                    files = dbx.files_list_folder("/backup_app_treinador").entries
                    backups = sorted(
                        [f.name for f in files if f.name.startswith("backup_")],
                        reverse=True
                    )
                    
                    if backups:
                        # Baixa o mais recente
                        _, res = dbx.files_download(f"/backup_app_treinador/{backups[0]}")
                        data = json.loads(res.content)
                        
                        # Salva localmente
                        DataManager.save_data(data)
                        return data
                        
                except Exception as e:
                    logger.error(f"Erro ao restaurar do Dropbox: {e}")
                    
        except Exception as e:
            logger.error(f"Erro na restauração: {e}")
            
        return None

    @staticmethod
    def save_data(data: dict):
        """Salva dados localmente e cria backup periódico"""
        DATA_FILE = "data/dados_treino.json"
        
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            # Cria backup a cada 24h
            last_backup = getattr(DataManager, '_last_backup', None)
            if not last_backup or (datetime.now() - last_backup) > timedelta(hours=24):
                DataManager.create_backup()
                DataManager._last_backup = datetime.now()
                
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")

    @staticmethod
    def create_backup() -> str:
        """Cria backup local e no Dropbox"""
        try:
            data = DataManager.load_data()
            
            # 1. Backup local
            os.makedirs("backups", exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"backups/backup_{timestamp}.json"
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            # 2. Backup no Dropbox
            dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
            if dropbox_token:
                dbx = dropbox.Dropbox(dropbox_token)
                
                with open(backup_file, 'rb') as f:
                    dbx.files_upload(
                        f.read(),
                        f"/backup_app_treinador/{os.path.basename(backup_file)}",
                        mode=dropbox.files.WriteMode.overwrite
                    )
                
                # Mantém apenas os 5 backups mais recentes no Dropbox
                files = dbx.files_list_folder("/backup_app_treinador").entries
                if len(files) > 5:
                    for file in sorted(files, key=lambda x: x.name)[:-5]:
                        dbx.files_delete_v2(file.path_display)
            
            return backup_file
            
        except Exception as e:
            logger.error(f"Erro no backup: {e}")
            return ""
