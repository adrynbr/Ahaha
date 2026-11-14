# LeadHunter AI — clone do Agente Vendedor

Agente de prospecção que:

- busca anúncios e produtos escalando (Biblioteca de Anúncios da Meta, Instagram, TikTok, Facebook, X)
- lê comentários e separa quem quer comprar ou tem dúvida sem resposta
- te entrega uma lista com **link do comentário + sugestão de resposta com seu link e desconto**, e **você** envia
- todo dia às 7h faz a varredura sozinho e te manda no Telegram
- responde sozinho o **"comente QUERO"** nos **seus** posts e anúncios (API oficial da Meta)

O agente nunca manda mensagem para concorrente ou desconhecido sozinho. Isso protege sua conta de bloqueio.

---

## Opção 1: usar hoje, sem servidor (app do Claude)

1. Baixe o arquivo [`dist/leadhunter-skill.zip`](dist/leadhunter-skill.zip).
2. No Claude (site ou app): **Configurações → Capacidades → Skills → Enviar skill** e escolha o zip.
3. Confira se a **busca na web** está ligada.
4. Abra uma conversa e escreva: `CAÇAR CLIENTES`.

Limites dessa versão: não roda sozinha de madrugada e não lê comentários que exigem login (por exemplo, TikTok).

## Opção 2: versão completa (Telegram + automático + comente QUERO)

Você precisa de:

| O quê | Onde conseguir | Custo |
|---|---|---|
| Chave da API do Claude | console.anthropic.com | por uso |
| Bot do Telegram | fale com o **@BotFather** no Telegram → `/newbot` | grátis |
| Seu ID do Telegram | fale com o **@userinfobot** | grátis |
| Apify (opcional, comentários IG/TikTok/Biblioteca) | apify.com | tem plano grátis |
| Servidor | Railway, Render ou uma VPS | ~US$5/mês |

### Subir na Shard Cloud (ou Square Cloud / Discloud)
1. Baixe [`dist/leadhunter-shardcloud.zip`](dist/leadhunter-shardcloud.zip) e envie como um novo app **Python**.
2. Arquivo principal: `main.py`. Memória: 256 MB é suficiente (o bot usa ~100 MB).
3. Coloque as variáveis do [`.env.example`](.env.example) no painel de variáveis de ambiente do app. Se não houver painel, renomeie `.env.example` para `.env` dentro do zip e preencha.
4. Inicie o app e mande `/start` para o seu bot no Telegram.

O bot do Telegram não precisa de porta nem link público. O "comente QUERO" só liga se você preencher as variáveis `META_*`, e aí precisa de um link público (plano com site/domínio).

### Subir no Railway (sem precisar de computador)
1. Entre em railway.app com sua conta do GitHub → **New Project → Deploy from GitHub repo** → escolha este repositório.
2. Em **Variables**, cole as variáveis do arquivo [`.env.example`](.env.example) com os seus valores (no mínimo `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`).
3. Em **Start Command**, coloque `python -m leadhunter`.
4. Para não perder a memória quando o servidor reiniciar, adicione um **Volume** montado em `/data` e a variável `DB_PATH=/data/leadhunter.db`.
5. Abra seu bot no Telegram e mande `/start`.

### Rodar no computador
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # e preencha
python -m leadhunter
```

### Comandos no Telegram
Botões prontos: `CAÇAR CLIENTES`, `CLIENTES QUENTES`, `VARREDURA TOTAL 360`, `BUSCAR MAIS`, `RADAR META`, `RADAR SOCIAL`, `MINHA MENSAGEM`, `MEUS RESULTADOS`, `TROCAR PRODUTO`.
Também: `ESSE COMPROU #3`, `ESSE NÃO ERA #5`, `/relatorio off` (desliga as 7h), `/limpar` (reinicia a conversa).

### "Comente QUERO" (opcional)
Precisa de um app na Meta (developers.facebook.com) ligado à sua Página e ao Instagram profissional, com permissões `instagram_manage_comments`, `instagram_manage_messages`, `pages_manage_engagement`, `pages_messaging`.
- URL do webhook: `https://SEU-SERVIDOR/meta/webhook`
- Token de verificação: o valor de `META_VERIFY_TOKEN`
- Assine os campos `comments` (Instagram) e `feed` (Página).
Quando alguém comenta uma palavra de `AUTO_REPLY_KEYWORDS`, o bot manda a DM com `AUTO_REPLY_DM` e responde o comentário com `AUTO_REPLY_PUBLIC`. É uma vez por comentário, como a Meta exige.

---

## Estrutura

```
leadhunter/
  prompts.py       regras do agente (baseadas no LeadHunter original 5.0 + 6.0)
  agent.py         Claude + busca na web + Apify + ferramentas de memória
  storage.py       memória por usuário (SQLite): produto, notas, oportunidades sem duplicar
  apify.py         coletores públicos (comentários IG/TikTok, Biblioteca de Anúncios)
  telegram_bot.py  conversa pelo celular + varredura diária às 7h
  meta_webhook.py  "comente QUERO" → DM nos seus posts (API oficial)
skill/leadhunter/  versão Skill para o app do Claude
tests/             testes (python -m pytest)
```
