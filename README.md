# 🤖 Bot WhatsApp - Afiliados Multi-Plataforma

Bot automatizado que monitora grupos do WhatsApp e converte links de produtos em links de afiliado de múltiplas plataformas.

## 📋 Plataformas Suportadas

- ✅ **Mercado Livre** (com geração automática de links /sec/)
- ✅ **Amazon** (adiciona tag de afiliado)
- ✅ **AliExpress** (adiciona parâmetros de tracking)
- ✅ **Shopee** (adiciona af_siteid)
- ✅ **Magazine Luiza** (Magalu)
- ✅ **Outras lojas** (modo genérico)

## 🚀 Como Configurar

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configurar IDs de Afiliado

Edite o arquivo `config.py`:

```python
# ========== GRUPOS DO WHATSAPP ==========
SOURCE_GROUP = "Nome do Grupo Origem"  # Grupo que o bot monitora
TARGET_GROUP = "Nome do Grupo Destino" # Grupo para onde envia

# ========== CONFIGURAÇÕES DE AFILIADOS ==========
# Mercado Livre
MELI_AFFILIATE_TAG = "seu-id-mercadolivre"
MELI_ENABLED = True  # True = ativa / False = desativa

# Amazon
AMAZON_AFFILIATE_TAG = "seu-id-amazon-20"
AMAZON_ENABLED = True

# Outras plataformas
GENERIC_AFFILIATE_TAG = "seu-id-generico"
GENERIC_ENABLED = True

# ========== PERFIL DO CHROME ==========
CHROME_USER_DATA_DIR = r"C:\Users\SEU_USUARIO\AppData\Local\BotChromeProfile"
```

### 3. Obter Tags de Afiliado

#### **Mercado Livre:**
1. Acesse: https://www.mercadolivre.com.br/afiliados
2. Crie uma conta de afiliado
3. Vá em "Configurações" ou "Etiquetas"
4. Copie seu ID de afiliado

#### **Amazon:**
1. Acesse: https://associados.amazon.com.br/
2. Cadastre-se no programa de afiliados
3. Seu ID será algo como: `seusite-20`

#### **AliExpress, Shopee, etc:**
- Consulte os programas de afiliados de cada plataforma

### 4. Ajustar Caminho do Chrome

Mude para seu usuário Windows:
```python
CHROME_USER_DATA_DIR = r"C:\Users\SEU_USUARIO_AQUI\AppData\Local\BotChromeProfile"
```

## ▶️ Como Rodar

```bash
python main.py
```

### Primeiro Uso:
1. O bot abrirá o Chrome automaticamente
2. Faça login no **WhatsApp Web** (escanear QR code)
3. Faça login no **Mercado Livre** (conta de afiliado)
4. O bot começará a monitorar automaticamente

## 🔧 Como Funciona

1. **Monitora** o grupo de origem (SOURCE_GROUP) a cada 2 segundos
2. **Detecta** mensagens com links de produtos
3. **Identifica** a plataforma (Mercado Livre, Amazon, etc)
4. **Gera** link de afiliado automaticamente
5. **Copia** a imagem da mensagem original (Ctrl+C)
6. **Cola** a imagem no grupo destino (Ctrl+V)
7. **Envia** com o link de afiliado na legenda

## ⚙️ Ativar/Desativar Plataformas

No arquivo `config.py`, altere:

```python
MELI_ENABLED = True     # True = processa / False = ignora
AMAZON_ENABLED = False  # Desativa Amazon
GENERIC_ENABLED = True  # Outras plataformas
```

## 📝 Observações Importantes

- O bot **sempre pega a última mensagem** do chat (scroll automático)
- Funciona com **imagens e textos**
- Usa **Ctrl+C/Ctrl+V** para copiar/colar imagens
- Salva o ID da última mensagem em `state_last_seen.txt`
- Não processa a mesma mensagem duas vezes

## 🛠️ Arquivos do Projeto

```
Bot/
├── main.py                      # Arquivo principal
├── config.py                    # Configurações (EDITE AQUI)
├── watcher.py                   # Monitora mensagens do WhatsApp
├── sender_whatsapp.py           # Envia mensagens
├── extractor.py                 # Detecta URLs e plataformas
├── affiliate.py                 # Gera links Mercado Livre
├── affiliate_multi_platform.py  # Gera links outras plataformas
├── storage.py                   # Salva estado
├── requirements.txt             # Dependências
└── state_last_seen.txt          # Última mensagem processada
```

## 🐛 Solução de Problemas

**Bot não detecta mensagens:**
- Verifique se o nome do grupo está EXATO (case-sensitive)
- Pressione `End` no WhatsApp para rolar até o fim

**Link de afiliado não é gerado:**
- Verifique se o ID de afiliado está correto
- Confirme que fez login na plataforma (Mercado Livre, Amazon)
- Veja os logs no terminal

**Imagem não é copiada:**
- Certifique-se que a mensagem tem imagem
- O bot usa Ctrl+C para copiar (pode falhar em alguns casos)

## 📊 Exemplo de Log

```
📨 NOVA MENSAGEM DETECTADA!
──────────────────────────────────────────────────────────────
ID: a7f3e2c9b1d4...

📊 URLs detectadas por plataforma:
   • MERCADOLIVRE: 1 link(s)
   • AMAZON: 1 link(s)

>> [MERCADO LIVRE] Gerando link afiliado: https://mercadolivre.com/sec/XYZ...
   ✓ Link afiliado gerado: https://mercadolivre.com/sec/ABC...

>> [AMAZON] Gerando link afiliado: https://amazon.com.br/produto...
   ✓ Link afiliado gerado: https://amazon.com.br/produto?tag=seu-id-20...

>> Mensagem tem IMAGEM
   → Copiando imagem (Ctrl+C)...
   ✓ Imagem copiada para área de transferência

>> Enviando IMAGEM COPIADA + LEGENDA para: Teste
   ✅ Imagem + Legenda enviadas com Ctrl+V!
```

## 🔐 Segurança

- Nunca compartilhe seu arquivo `config.py` (contém IDs de afiliado)
- O bot usa seu perfil do Chrome para manter login

## 📄 Licença

Projeto pessoal - Use por sua conta e risco.
