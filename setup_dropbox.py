#!/usr/bin/env python3
"""
Script para configuração inicial do Dropbox
Execute este script uma vez para obter refresh token
"""

import dropbox
import webbrowser
import os
from dotenv import load_dotenv

def setup_dropbox():
    """Configuração inicial do Dropbox"""
    load_dotenv()
    
    APP_KEY = input("Digite sua App Key do Dropbox: ").strip()
    APP_SECRET = input("Digite sua App Secret do Dropbox: ").strip()
    
    if not APP_KEY or not APP_SECRET:
        print("❌ App Key e App Secret são obrigatórios!")
        return
    
    try:
        # Iniciar fluxo OAuth2
        auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
        authorize_url = auth_flow.start()
        
        print("\n" + "="*60)
        print("🔗 AUTORIZAÇÃO NECESSÁRIA")
        print("="*60)
        print(f"1. Abra este link no seu navegador:")
        print(f"   {authorize_url}")
        print("\n2. Faça login na sua conta Dropbox")
        print("3. Clique em 'Allow' para autorizar a aplicação")
        print("4. Copie o código de autorização que aparecerá")
        print("="*60)
        
        # Abrir automaticamente no navegador
        try:
            webbrowser.open(authorize_url)
            print("✅ Link aberto automaticamente no navegador")
        except:
            print("⚠️  Não foi possível abrir automaticamente. Copie o link acima.")
        
        print("\n")
        auth_code = input("📋 Cole o código de autorização aqui: ").strip()
        
        if not auth_code:
            print("❌ Código de autorização não fornecido!")
            return
        
        # Finalizar autorização
        oauth_result = auth_flow.finish(auth_code)
        
        print("\n" + "="*60)
        print("✅ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print("📝 Adicione estas variáveis ao seu arquivo .env:")
        print("")
        print(f"DROPBOX_APP_KEY={APP_KEY}")
        print(f"DROPBOX_APP_SECRET={APP_SECRET}")
        print(f"DROPBOX_ACCESS_TOKEN={oauth_result.access_token}")
        print(f"DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}")
        print("")
        print("💡 IMPORTANTE:")
        print("   • O REFRESH_TOKEN não expira - guarde-o com segurança!")
        print("   • O ACCESS_TOKEN será renovado automaticamente")
        print("   • Para Streamlit Cloud, adicione também ao secrets.toml")
        print("="*60)
        
        # Salvar em arquivo .env automaticamente
        try:
            with open('.env', 'a') as f:
                f.write(f"\n# Configurações do Dropbox (geradas em {os.path.basename(__file__)})\n")
                f.write(f"DROPBOX_APP_KEY={APP_KEY}\n")
                f.write(f"DROPBOX_APP_SECRET={APP_SECRET}\n")
                f.write(f"DROPBOX_ACCESS_TOKEN={oauth_result.access_token}\n")
                f.write(f"DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}\n")
            
            print("✅ Configurações salvas automaticamente no arquivo .env")
            
        except Exception as e:
            print(f"⚠️  Não foi possível salvar automaticamente: {e}")
            print("   Por favor, adicione manualmente as variáveis acima")
        
        # Testar conexão
        print("\n🧪 Testando conexão...")
        try:
            dbx = dropbox.Dropbox(oauth_result.access_token)
            account = dbx.users_get_current_account()
            print(f"✅ Conectado com sucesso como: {account.name.display_name}")
            print(f"📧 Email: {account.email}")
            
            # Criar pasta de backups se não existir
            try:
                dbx.files_create_folder_v2("/backups")
                print("📁 Pasta /backups criada no Dropbox")
            except dropbox.exceptions.ApiError as e:
                if e.error.is_path() and e.error.get_path().is_conflict():
                    print("📁 Pasta /backups já existe no Dropbox")
                else:
                    print(f"⚠️  Não foi possível criar pasta /backups: {e}")
            
        except Exception as e:
            print(f"❌ Erro ao testar conexão: {e}")
            return
        
        print("\n🎉 Configuração concluída! Agora você pode usar o backup no Dropbox.")
        
    except Exception as e:
        print(f"❌ Erro durante configuração: {e}")
        return

if __name__ == "__main__":
    print("🔧 CONFIGURAÇÃO INICIAL DO DROPBOX")
    print("="*40)
    print("Este script irá configurar o acesso ao Dropbox para backup automático.")
    print("")
    print("📋 Você precisará de:")
    print("   • App Key do Dropbox")
    print("   • App Secret do Dropbox")
    print("   • Acesso ao navegador para autorização")
    print("")
    
    continuar = input("Deseja continuar? (s/N): ").strip().lower()
    if continuar in ['s', 'sim', 'y', 'yes']:
        setup_dropbox()
    else:
        print("❌ Configuração cancelada.")
