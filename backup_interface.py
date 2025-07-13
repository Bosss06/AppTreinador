import os
import shutil
from datetime import datetime
import json

def backup_data():
    """Função simplificada de backup"""
    try:
        # Cria diretório de backup se não existir
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Define o nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{backup_dir}/backup_{timestamp}.json"
        
        # Copia o arquivo principal para o backup
        shutil.copy2("data/dados_treino.json", backup_file)
        
        return True
    except Exception as e:
        print(f"Erro ao criar backup: {str(e)}")
        return False