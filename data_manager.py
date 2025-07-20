import os
import json
import logging
from datetime import datetime
import dropbox
from dropbox.exceptions import AuthError

# Configuração do logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class DataManager:
    @staticmethod
    def load_data() -> dict:
        """Carrega os dados do arquivo JSON"""
        DATA_FILE = "data/dados_treino.json"
        try:
            os.makedirs('data', exist_ok=True)
            if not os.path.exists(DATA_FILE):
                return DataManager._initialize_data()
                
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar dados: {str(e)}")
            return DataManager._initialize_data()

    @staticmethod
    def create_backup() -> str:
        """Cria backup e envia para o Dropbox"""
        try:
            # 1. Criar backup local
            os.makedirs("backups", exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"backups/backup_{timestamp}.json"
            
            data = DataManager.load_data()
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            # 2. Upload para Dropbox
            dbx = dropbox.Dropbox(os.getenv('DROPBOX_ACCESS_TOKEN'))
            
            with open(backup_file, 'rb') as f:
                dbx.files_upload(
                    f.read(),
                    f"/backup_app_treinador/{os.path.basename(backup_file)}",
                    mode=dropbox.files.WriteMode.overwrite
                )
            
            # Cria link compartilhado
            link = dbx.sharing_create_shared_link_with_settings(
                f"/backup_app_treinador/{os.path.basename(backup_file)}"
            )
            
            return link.url
        except AuthError:
            logger.error("Erro de autenticação no Dropbox")
            return ""
        except Exception as e:
            logger.error(f"Falha no backup Dropbox: {str(e)}")
            return ""
