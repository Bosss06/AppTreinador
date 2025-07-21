import os
import json
import logging
from datetime import datetime
import dropbox
from dropbox.exceptions import AuthError, ApiError, HttpError
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
    def load_data() -> dict:
        """Carrega dados com verificação de integridade"""
        DATA_FILE = "data/dados_treino.json"
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
        DATA_FILE = "data/dados_treino.json"
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {str(e)}")
            return False

    @staticmethod
    def create_secure_backup() -> bool:
        """Cria backup com verificação de integridade"""
        try:
            data = DataManager.load_data()
            
            # Verifica se os dados são válidos
            if not isinstance(data, dict) or 'jogadores' not in data:
                raise ValueError("Estrutura de dados inválida para backup")
            
            # Cria backup local
            os.makedirs("backups", exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"backups/backup_{timestamp}.json"
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            # Verifica se o backup foi criado corretamente
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
                if backup_data.get('jogadores') is None:
                    raise ValueError("Backup corrompido")
            
            # Upload para Dropbox (se configurado)
            dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
            if dropbox_token:
                try:
                    dbx = dropbox.Dropbox(dropbox_token)
                    
                    # Verifica conexão com Dropbox
                    dbx.users_get_current_account()
                    
                    with open(backup_file, 'rb') as f:
                        dbx.files_upload(
                            f.read(),
                            f"/backup_app_treinador/{os.path.basename(backup_file)}",
                            mode=dropbox.files.WriteMode.overwrite
                        )
                    
                    logger.info("Backup enviado para Dropbox com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao enviar para Dropbox: {str(e)}")
                    # Continua mesmo com falha no Dropbox
            
            return True
        except Exception as e:
            logger.error(f"Falha no backup seguro: {str(e)}")
            return False

    @staticmethod
    def create_backup() -> str:
        """Mantido para compatibilidade (usa o novo método)"""
        success = DataManager.create_secure_backup()
        return "Backup criado com sucesso" if success else ""
