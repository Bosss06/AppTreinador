# === DATA MANAGER SIMPLIFICADO ===
import os
import json
from datetime import datetime

class DataManager:
    """Gerenciador de dados simplificado e eficiente"""
    
    DATA_FILE = "data/dados_treino.json"
    
    @staticmethod
    def _get_default_data():
        """Retorna estrutura padrão de dados"""
        return {
            "jogadores": [],
            "treinos": {},
            "exercicios": {},
            "taticas": [],
            "jogos": []
        }
    
    @staticmethod
    def ensure_data_dir():
        """Garante que o diretório de dados existe"""
        os.makedirs("data", exist_ok=True)
    
    @staticmethod
    def load_data():
        """Carrega dados do arquivo JSON"""
        DataManager.ensure_data_dir()
        
        try:
            if os.path.exists(DataManager.DATA_FILE):
                with open(DataManager.DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Garantir estrutura padrão
                default_data = DataManager._get_default_data()
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                
                return data
            else:
                # Criar arquivo inicial
                data = DataManager._get_default_data()
                DataManager.save_data(data)
                return data
                
        except Exception as e:
            print(f"Erro ao carregar dados: {str(e)}")
            return DataManager._get_default_data()
    
    @staticmethod
    def save_data(data):
        """Salva dados no arquivo JSON"""
        try:
            DataManager.ensure_data_dir()
            
            # Backup do arquivo atual antes de salvar
            if os.path.exists(DataManager.DATA_FILE):
                backup_name = f"{DataManager.DATA_FILE}.backup"
                try:
                    with open(DataManager.DATA_FILE, 'r') as original:
                        with open(backup_name, 'w') as backup:
                            backup.write(original.read())
                except:
                    pass  # Se não conseguir fazer backup, continua
            
            # Salvar novos dados
            with open(DataManager.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Erro ao salvar dados: {str(e)}")
            
            # Tentar restaurar backup se salvamento falhar
            backup_name = f"{DataManager.DATA_FILE}.backup"
            if os.path.exists(backup_name):
                try:
                    with open(backup_name, 'r') as backup:
                        with open(DataManager.DATA_FILE, 'w') as original:
                            original.write(backup.read())
                except:
                    pass
            
            return False
    
    @staticmethod
    def create_simple_backup():
        """Cria backup simples dos dados"""
        try:
            data = DataManager.load_data()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Criar diretório de backup
            backup_dir = "data/backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Salvar backup
            backup_file = f"{backup_dir}/backup_simples_{timestamp}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Manter apenas os 10 backups mais recentes
            backup_files = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.json')]
            if len(backup_files) > 10:
                backup_files.sort()
                for old_backup in backup_files[:-10]:
                    try:
                        os.remove(os.path.join(backup_dir, old_backup))
                    except:
                        pass
            
            return True
            
        except Exception as e:
            print(f"Erro ao criar backup: {str(e)}")
            return False
    
    @staticmethod
    def restore_from_backup(backup_file):
        """Restaura dados de um arquivo de backup"""
        try:
            if not os.path.exists(backup_file):
                return False
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return DataManager.save_data(data)
            
        except Exception as e:
            print(f"Erro ao restaurar backup: {str(e)}")
            return False
