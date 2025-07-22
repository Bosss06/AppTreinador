import os
import json
import logging
import uuid
from datetime import datetime
import dropbox
from dropbox.exceptions import AuthError, ApiError, HttpError

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
    def create_secure_backup() -> bool:
        """Cria um backup seguro dos dados"""
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
            
            # Carrega e salva com validação
            data = DataManager.load_data()
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            return True
        except Exception as e:
            logger.error(f"Erro ao criar backup: {str(e)}")
            return False

    @staticmethod
    def restore_backup(backup_file: str) -> bool:
        """Restaura dados a partir de um backup"""
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
            
            return DataManager.save_data(backup_data)
        except Exception as e:
            logger.error(f"Erro ao restaurar backup: {str(e)}")
            return False

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
