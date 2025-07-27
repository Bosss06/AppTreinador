# Configuração do Dropbox para o App do Treinador

## Configuração Inicial

Para usar o Dropbox com renovação automática de token, configure as seguintes variáveis de ambiente:

### 1. Obter App Key e App Secret
1. Acesse https://www.dropbox.com/developers/apps
2. Crie uma nova app
3. Anote o App Key e App Secret

### 2. Obter Refresh Token
Execute este script Python uma vez:

```python
import dropbox
import webbrowser
import urllib.parse

APP_KEY = "sua_app_key"
APP_SECRET = "seu_app_secret"

# 1. Gerar URL de autorização
auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
authorize_url = auth_flow.start()

print("1. Vá para: " + authorize_url)
print("2. Clique em 'Allow' (você pode ter que fazer login primeiro)")
print("3. Copie o código de autorização:")

auth_code = input("Digite o código de autorização aqui: ").strip()

try:
    oauth_result = auth_flow.finish(auth_code)
    print(f"Access Token: {oauth_result.access_token}")
    print(f"Refresh Token: {oauth_result.refresh_token}")
    print("IMPORTANTE: Salve o Refresh Token - ele não expira!")
except Exception as e:
    print(f"Erro: {e}")
```

### 3. Configurar Variáveis de Ambiente

#### Para desenvolvimento local (.env):
```
DROPBOX_ACCESS_TOKEN=seu_access_token_inicial
DROPBOX_REFRESH_TOKEN=seu_refresh_token
DROPBOX_APP_KEY=sua_app_key
DROPBOX_APP_SECRET=seu_app_secret
```

#### Para Streamlit Cloud (Secrets):
```toml
[default]
DROPBOX_ACCESS_TOKEN = "seu_access_token_inicial"
DROPBOX_REFRESH_TOKEN = "seu_refresh_token"
DROPBOX_APP_KEY = "sua_app_key"
DROPBOX_APP_SECRET = "seu_app_secret"
```

## Funcionalidades Implementadas

### 1. Renovação Automática de Token
- O sistema tenta renovar automaticamente tokens expirados
- Usa refresh token para obter novos access tokens
- Salva tokens atualizados em arquivo local

### 2. Backup Completo com Fotos
- Backup de dados em JSON
- Backup de fotos dos jogadores em ZIP
- Upload automático para Dropbox
- Opções: Local, Dropbox ou Ambos

### 3. Restore Inteligente
- Restaura dados e fotos automaticamente
- Suporte a upload manual
- Restauração do Dropbox com lista de backups
- Verifica backups correspondentes de fotos

### 4. Prevenção de Reboot
- JavaScript injected para manter sessão ativa
- Ping automático a cada 5 minutos
- Detecção de atividade do usuário
- Operações em background para manter conexão

## Troubleshooting

### Token Expirado
Se aparecer erro de token expirado:
1. Vá para Configurações
2. Clique em "Tentar Renovar Token"
3. Se não funcionar, gere novo refresh token

### Backup Falhando
- Verifique conexão com internet
- Confirme que as credenciais estão corretas
- Verifique espaço disponível no Dropbox

### App Reiniciando
- O sistema de prevenção de reboot está ativo
- Mantenha a aba do navegador aberta
- Interaja com a app periodicamente
