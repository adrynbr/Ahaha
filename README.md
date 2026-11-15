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
| Serper (opcional, busca no Google) | serper.dev | 2.500 buscas grátis |
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
Botões prontos: `CAÇAR CLIENTES`, `CLIENTES QUENTES`, `VARREDURA TOTAL 360`, `BUSCAR MAIS`, `RADAR META`, `RADAR SOCIAL`, `CRIATIVOS CAMPEÕES`, `MONTAR CAMPANHA`, `MINHA MENSAGEM`, `MEUS RESULTADOS`, `ABRIR NA EXTENSÃO`, `MAIS FUNÇÕES` (mostra o menu completo).
Também: `ROTEIRO DE CRIATIVO`, `ATENDIMENTO`, `ANALISAR MINHA PÁGINA`, `ACHAR PRODUTO`, `CONTEÚDO`, `MINHAS ROTINAS`, `TROCAR PRODUTO`, `ESSE COMPROU #3`, `ESSE NÃO ERA #5`, `/relatorio off` (desliga as 7h), `/limpar` (reinicia a conversa), `/extensao` (manda o zip da extensão), `/menu`.

- **Pedidos livres:** "preciso de 50 clientes para hoje", "procure no X quem quer comprar".
- **Rotinas (fluxos de trabalho):** "todo dia às 6h traga comentários 'quero' do TikTok das últimas 24h". Cancelar: "cancele a rotina #2".
- **Prints:** mande foto de um anúncio, das métricas ou de uma página e peça a análise.
- **Vídeos (até 20 MB cada):** mande os vídeos e toque/escreva `ANALISAR VÍDEO` (nota e melhorias) ou `JUNTAR VÍDEOS` (junta em 9:16 e devolve). Legenda automática: CapCut. Áudio/voz ainda não é ouvido.

### "Comente QUERO" (opcional)
Precisa de um app na Meta (developers.facebook.com) ligado à sua Página e ao Instagram profissional, com permissões `instagram_manage_comments`, `instagram_manage_messages`, `pages_manage_engagement`, `pages_messaging`.
- URL do webhook: `https://SEU-SERVIDOR/meta/webhook`
- Token de verificação: o valor de `META_VERIFY_TOKEN`
- Assine os campos `comments` (Instagram) e `feed` (Página).
Quando alguém comenta uma palavra de `AUTO_REPLY_KEYWORDS`, o bot manda a DM com `AUTO_REPLY_DM` e responde o comentário com `AUTO_REPLY_PUBLIC`. É uma vez por comentário, como a Meta exige.

---

## Extensão do Chrome: LeadHunter Abridor

Faz o papel da "Superagent": abre cada oportunidade numa aba, com a mensagem pronta. **Você revisa e envia.** Ela nunca envia nada sozinha.

1. No **computador**, baixe [`dist/leadhunter-extensao.zip`](dist/leadhunter-extensao.zip) e descompacte.
2. No Chrome, abra `chrome://extensions` e ligue o **Modo do desenvolvedor**, no canto superior direito.
3. Clique em **Carregar sem compactação** e escolha a pasta `extensao`.
4. Fixe o ícone 🧩 → LeadHunter Abridor.

Uso manual: copie a resposta do **CAÇAR CLIENTES** no Telegram, cole na extensão, clique em **Ler oportunidades** e depois em **Abrir abas**. Em cada aba aparece um cartão com **Copiar**, **Colar na caixa** e **Abrir perfil (DM)**.

### Conectar a extensão ao bot (abre sozinha)
1. Na hospedagem, ligue a **Publicação na Web** e crie as variáveis `WEB_ATIVO=1`, `PORT=80` (ou a porta indicada) e `URL_PUBLICA` (o endereço do app). Reinicie.
2. No Telegram, mande `/conectar` e copie o código.
3. Na extensão, abra **🔌 Conexão com o bot**, cole o endereço e o código e clique em **Salvar e testar**.
4. Depois de cada varredura, toque em **ABRIR NA EXTENSÃO** no Telegram: com o Chrome aberto, as abas abrem em até 1 minuto.

### O bot lendo páginas no seu Chrome (como a Superagent)
Com a extensão conectada e o Chrome aberto (logado no Instagram/TikTok/Facebook), o agente ganha a ferramenta `ler_no_navegador`: durante a busca ele pede uma página, a extensão abre numa aba de fundo, rola os comentários, copia o texto e fecha a aba. Assim ele lê comentários que sem login não aparecem. **Só leitura**: nada é curtido, comentado ou enviado. Dá para desligar na extensão (caixa "Deixar o bot ler páginas aqui"). Sites permitidos: redes sociais, Mercado Livre, Shopee, Reclame Aqui.

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
extensao/          extensão do Chrome (abre as oportunidades com a mensagem pronta)
tests/             testes (python -m pytest)
```
