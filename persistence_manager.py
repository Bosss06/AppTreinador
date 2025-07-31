"""
Gerenciador de Persistência Avançado para a App do Treinador
Garante que os dados e fotos persistam mesmo com resets do Streamlit Cloud
"""

import os
import time
import json
import uuid
import streamlit as st
from data_manager import DataManager
from datetime import datetime, timedelta

class PersistenceManager:
    """Gerencia a persistência robusta de dados"""
    
    @staticmethod
    def init_session_persistence():
        """Inicializa sistema de persistência da sessão"""
        if 'persistence_initialized' not in st.session_state:
            st.session_state.persistence_initialized = True
            st.session_state.last_data_backup = 0
            st.session_state.data_validation_count = 0
            
    @staticmethod
    def validate_data_integrity():
        """Valida a integridade dos dados carregados"""
        try:
            data = DataManager.load_data()
            
            # Verificações básicas
            if not isinstance(data, dict):
                return False
            
            # Verificar estruturas essenciais
            required_keys = ['jogadores', 'treinos', 'jogos']
            for key in required_keys:
                if key not in data:
                    data[key] = [] if key in ['jogadores', 'jogos'] else {}
            
            # Verificar se jogadores têm IDs
            needs_save = False
            for jogador in data.get('jogadores', []):
                if 'id' not in jogador:
                    jogador['id'] = str(uuid.uuid4())
                    needs_save = True
            
            if needs_save:
                DataManager.save_data(data)
            
            return True
            
        except Exception as e:
            st.error(f"❌ Erro na validação de dados: {str(e)}")
            return False
    
    @staticmethod
    def schedule_auto_backup():
        """Agenda backup automático"""
        current_time = time.time()
        
        # Backup a cada 30 minutos
        if (current_time - st.session_state.get('last_data_backup', 0)) > 1800:
            try:
                from APP_FINAL import create_backup_with_auto_retry, is_streamlit_cloud
                
                if is_streamlit_cloud():
                    success = create_backup_with_auto_retry(dropbox_only=True)
                else:
                    success = create_backup_with_auto_retry()
                
                if success:
                    st.session_state.last_data_backup = current_time
                    st.sidebar.success("✅ Backup automático realizado")
                
            except Exception as e:
                st.sidebar.warning(f"⚠️ Erro no backup automático: {str(e)}")
    
    @staticmethod
    def emergency_data_recovery():
        """Recuperação de emergência dos dados"""
        try:
            from APP_FINAL import auto_restore_from_backup, is_streamlit_cloud
            
            st.warning("🚨 Iniciando recuperação de emergência...")
            
            if is_streamlit_cloud():
                # No cloud, tentar restaurar do Dropbox
                auto_restore_from_backup()
            else:
                # Localmente, verificar backups
                backup_dir = "data/backups"
                if os.path.exists(backup_dir):
                    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]
                    if backup_files:
                        latest_backup = max(backup_files, key=lambda x: os.path.getctime(os.path.join(backup_dir, x)))
                        st.info(f"📁 Backup local encontrado: {latest_backup}")
                        # Implementar restauração local se necessário
            
            # Revalidar após recuperação
            if PersistenceManager.validate_data_integrity():
                st.success("✅ Recuperação concluída com sucesso!")
                return True
            else:
                st.error("❌ Falha na recuperação de dados")
                return False
                
        except Exception as e:
            st.error(f"❌ Erro na recuperação de emergência: {str(e)}")
            return False
    
    @staticmethod
    def create_session_checkpoint():
        """Cria checkpoint da sessão atual"""
        try:
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'session_state': {
                    'autenticado': st.session_state.get('autenticado', False),
                    'tipo_usuario': st.session_state.get('tipo_usuario'),
                    'user': st.session_state.get('user'),
                    'jogador_info': st.session_state.get('jogador_info')
                },
                'data_integrity': PersistenceManager.validate_data_integrity()
            }
            
            # Salvar checkpoint em arquivo temporário
            checkpoint_file = "session_checkpoint.json"
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            return False
    
    @staticmethod
    def restore_session_checkpoint():
        """Restaura checkpoint da sessão"""
        try:
            checkpoint_file = "session_checkpoint.json"
            if os.path.exists(checkpoint_file):
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                
                # Verificar se checkpoint é recente (últimas 2 horas)
                checkpoint_time = datetime.fromisoformat(checkpoint_data['timestamp'])
                if datetime.now() - checkpoint_time < timedelta(hours=2):
                    
                    session_data = checkpoint_data.get('session_state', {})
                    for key, value in session_data.items():
                        if value is not None:
                            st.session_state[key] = value
                    
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    @staticmethod
    def run_persistence_checks():
        """Executa todas as verificações de persistência"""
        try:
            # Inicializar se necessário
            PersistenceManager.init_session_persistence()
            
            # Validar integridade dos dados
            if not PersistenceManager.validate_data_integrity():
                st.warning("⚠️ Problemas de integridade detectados")
                
                # Tentar recuperação automática
                if not PersistenceManager.emergency_data_recovery():
                    st.error("❌ Não foi possível recuperar dados automaticamente")
            
            # Agendar backup automático
            PersistenceManager.schedule_auto_backup()
            
            # Criar checkpoint da sessão
            PersistenceManager.create_session_checkpoint()
            
            # Incrementar contador de validações
            st.session_state.data_validation_count = st.session_state.get('data_validation_count', 0) + 1
            
            return True
            
        except Exception as e:
            st.error(f"❌ Erro nas verificações de persistência: {str(e)}")
            return False
    
    @staticmethod
    def show_persistence_dashboard():
        """Mostra dashboard de status da persistência"""
        try:
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔒 Sistema de Persistência")
            
            # Status geral
            data = DataManager.load_data()
            if data and data.get('jogadores'):
                st.sidebar.success(f"✅ Sistema Ativo ({len(data['jogadores'])} jogadores)")
            else:
                st.sidebar.error("❌ Dados não encontrados")
            
            # Informações de backup
            last_backup = st.session_state.get('last_data_backup', 0)
            if last_backup > 0:
                time_since_backup = (time.time() - last_backup) / 60  # minutos
                if time_since_backup < 60:
                    st.sidebar.info(f"💾 Último backup: {int(time_since_backup)}min atrás")
                else:
                    st.sidebar.warning(f"💾 Último backup: {int(time_since_backup/60)}h atrás")
            else:
                st.sidebar.warning("💾 Nenhum backup registrado")
            
            # Validações realizadas
            validations = st.session_state.get('data_validation_count', 0)
            st.sidebar.caption(f"🔍 Validações: {validations}")
            
            # Botões de ação
            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("🔄", help="Backup Manual"):
                    PersistenceManager.schedule_auto_backup()
            with col2:
                if st.button("🚨", help="Recuperação"):
                    PersistenceManager.emergency_data_recovery()
            
        except Exception as e:
            st.sidebar.error(f"❌ Erro no dashboard: {str(e)}")

# Função principal para integração
def init_robust_persistence():
    """Função principal para inicializar persistência robusta"""
    return PersistenceManager.run_persistence_checks()

def show_persistence_status():
    """Função para mostrar status na sidebar"""
    PersistenceManager.show_persistence_dashboard()
