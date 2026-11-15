# CONTEXTO COMPLETO — Clone do "Agente Vendedor" (LeadHunter AI)

> **Cole este arquivo inteiro no início de um chat novo com o Claude.** Ele resume tudo o que foi feito até 15/11/2026, como cada peça funciona, onde paramos e o que falta.

---

## 0. Instruções para o Claude que vai ler isto

- **Fale comigo em português do Brasil, simples e direto.** Não sou programador. Uso muito o **celular**, mas tenho acesso a um computador.
- **Não fique corrigindo detalhes cosméticos** (ex.: `**` aparecendo no Telegram). É para uso pessoal. Corrija só o que trava ou quebra.
- **Nunca peça para eu colar tokens/chaves no chat.** Elas ficam nas variáveis de ambiente da Shard Cloud.
- **Regra fixa do projeto: nada de envio automático de DMs, comentários ou curtidas.** O agente encontra, analisa e deixa a mensagem pronta; **eu** reviso e envio, um por um. (Foi decidido assim para não ter a conta do Instagram bloqueada e por ser spam. O próprio agente original da Base44 também só gera rascunhos.)
- O código está no GitHub: repositório **`adrynbr/Ahaha`**, branch **`claude/sales-agent-ai-clone-68u4xu`**. Leia o `README.md` e este arquivo antes de mexer.
- Sempre que mudar o código: rode os testes (`python -m pytest -q` e `node extensao/testes/parser.test.js`), gere os zips de novo em `dist/` e faça commit + push nessa branch.

---

## 1. O objetivo

Estou fazendo o curso **"Cansei Dessa Vida"**, que ensina a usar um **"Agente Vendedor"** feito na plataforma **Base44**. Ele faz prospecção ativa:

- procura nas redes sociais (Instagram, TikTok, Facebook) e na **Biblioteca de Anúncios da Meta** criativos e anúncios de produtos físicos que estão vendendo;
- lê comentários procurando **intenção de compra** ("quero", "manda o link", "quanto custa?");
- entrega os **leads quentes** com uma **mensagem pronta** (com link de checkout/desconto);
- tem uma **extensão do Chrome ("Superagent")** que abre os links em abas com a mensagem pronta para eu só enviar.

**Não confundir com o Ofertize**, que era só um gerador de copy/landing page.

**Problema:** não tenho dinheiro para assinar a Base44 (o plano grátis tem só 25 créditos de mensagem e 100 de integração). Então **criamos um clone próprio** que faz a mesma coisa sem a Base44.

---

## 2. O que descobrimos do agente original (Base44)

Mandei para o agente original um prompt pedindo as instruções dele (sem executar ferramentas, gastou 1 crédito). Ele revelou:

- Chama-se **"LeadHunter AI"**, com dois arquivos de regras: **Complemento 5.0 ("Radar Social")** e **Complemento 6.0 (núcleo operacional)**.
- **Não tem integração especial** com Meta/TikTok: usa só **busca no Google** e um **navegador automatizado (Browserbase)** que abre páginas públicas.
- **Só gera rascunhos.** Regra explícita: "Nunca enviar DM, comentário ou curtida automaticamente."
- Comandos: `CAÇAR CLIENTES`, `VARREDURA TOTAL 360`, `RADAR SOCIAL`, `RADAR META`, `CLIENTES QUENTES`, `BUSCAR MAIS`, `MINHA MENSAGEM`, `TROCAR PRODUTO`, `MEUS RESULTADOS`.
- Onboarding curto: pergunta o produto → link de venda (exato, com rastreamento) → país (Brasil padrão) → confirma → executa.
- Seis frentes da Varredura 360: Biblioteca de Anúncios, Facebook orgânico, Instagram Reels (24–72h primeiro), TikTok, X/Twitter, leads consentidos.
- **Recência é prioridade**: 24h > 48h > 72h > 7 dias. Separa data da publicação e data do comentário.
- Sinais: Intenção direta, Preço, Confiança, Compatibilidade, Logística, Comparação, Objeção. Nota 0–100. "Perguntar não é comprar."
- Entrega por oportunidade: fonte, link, trecho exato, data, sinal, nota, abordagem personalizada, link de venda.
- Relatório de execução obrigatório (fontes, quantidades, limitações). Nunca inventar perfil, data ou URL.
- Entrega diária por volta das 7h (fuso America/Sao_Paulo).

Essas regras foram copiadas e adaptadas no arquivo `leadhunter/prompts.py`.

---

## 3. O que foi construído (visão geral)

```
┌─────────────────────┐        ┌──────────────────────────────┐
│  Telegram (celular) │◄──────►│  Bot LeadHunter (Python)     │
│  botões e comandos  │        │  rodando na Shard Cloud      │
└─────────────────────┘        │  - IA: KPA Labz (Claude)     │
                               │  - Busca: Serper (Google)    │
                               │    → reserva: DuckDuckGo     │
                               │  - Comentários: Apify        │
                               │  - Memória: SQLite           │
                               │  - API p/ extensão (FastAPI) │
                               └──────────────┬───────────────┘
                                              │ internet (subdomínio da Shard)
                               ┌──────────────▼───────────────┐
                               │ Extensão Chrome (no PC)      │
                               │ "LeadHunter Abridor"         │
                               │ abre abas + mensagem pronta  │
                               │ EU reviso e envio            │
                               └──────────────────────────────┘
```

Também existe uma **Skill para o app do Claude** (`skill/leadhunter/SKILL.md`, zip em `dist/leadhunter-skill.zip`) — versão sem servidor, que roda dentro do meu Claude Pro com a busca do próprio Claude. Não roda sozinha nem tem extensão, mas é grátis.

---

## 4. Estrutura do repositório

```
main.py                    arquivo principal (Shard Cloud executa "python main.py")
requirements.txt           anthropic, python-telegram-bot[job-queue], httpx, python-dotenv, fastapi, uvicorn
.env.example               todas as variáveis com explicação
Procfile                   "web: python -m leadhunter" (Railway, alternativa)
README.md                  guia de instalação
CONTEXTO-PARA-NOVO-CHAT.md este arquivo

leadhunter/
  __main__.py      liga o bot do Telegram e (se WEB_ATIVO=1 ou Meta configurada) o servidor web
  config.py        lê as variáveis de ambiente (Settings)
  prompts.py       system prompt (regras do LeadHunter 5.0 + 6.0 adaptadas)
  agent.py         o agente: modo oficial (API Anthropic) e MODO COMPATÍVEL (KPA Labz)
  web.py           busca (Serper → DuckDuckGo) e leitura de páginas
  apify.py         coletores da Apify (comentários IG/TikTok/FB, Biblioteca de Anúncios)
  storage.py       SQLite: produto, notas, oportunidades (sem duplicar), histórico, extensão
  oportunidades.py lê as oportunidades do texto que o bot entregou e salva no banco
  telegram_bot.py  conversa, botões, /conectar, ABRIR NA EXTENSÃO, varredura das 7h
  api_extensao.py  API que a extensão consulta (código por Bearer, CORS só chrome-extension://)
  meta_webhook.py  "comente QUERO" nos MEUS posts (API oficial da Meta) — pronto, mas desligado

extensao/          extensão do Chrome "LeadHunter Abridor" (Manifest V3)
  manifest.json, popup.html, popup.js, background.js, cartao.js, parser.js
  testes/parser.test.js

skill/leadhunter/SKILL.md   versão Skill para o app do Claude
tests/                      testes Python (pytest): 39 testes passando
dist/                       zips prontos:
  leadhunter-shardcloud.zip   → enviar na Shard Cloud
  leadhunter-extensao.zip     → instalar no Chrome
  leadhunter-skill.zip        → enviar no app do Claude (Skills)
```

---

## 5. Hospedagem: Shard Cloud

- Plataforma: **shardcloud.app** (já uso para 2 bots de Discord).
- App: **`agente-vendedor`**, Python, **256 MB de RAM** (usa ~100–150 MB; 512 não cabia junto com os outros bots).
- Arquivo principal: **`main.py`**. A Shard instala o `requirements.txt` sozinha no primeiro início (o pico de memória nessa hora é normal).
- **Logs:** a tela "Mostrar Logs" às vezes mostra só a primeira execução. Por isso o bot mostra o **motivo dos erros direto no Telegram** ("Detalhe: ...").
- Atualizar: enviar o zip novo (`dist/leadhunter-shardcloud.zip`) e tocar em **Reiniciar**.

### Variáveis de ambiente (NÃO colocar os valores em chat)

| Variável | Para quê | Situação |
|---|---|---|
| `ANTHROPIC_API_KEY` | chave da KPA Labz (`sk-kpa-...`) | ✅ configurada |
| `ANTHROPIC_BASE_URL` | `https://api.kpalabz.com` | ✅ |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | ✅ |
| `TELEGRAM_BOT_TOKEN` | token do @BotFather (já foi trocado com /revoke depois de vazar num log) | ✅ |
| `TELEGRAM_ALLOWED_USERS` | meu ID numérico do Telegram (@userinfobot) | ✅/verificar |
| `SERPER_API_KEY` | busca Google (serper.dev) | ✅ |
| `APIFY_TOKEN` | comentários e anúncios (apify.com) | ✅ |
| `MODO_COMPATIVEL` | `auto` (padrão) | opcional |
| `WEB_ATIVO` | `1` liga o servidor web para a extensão | ⏳ falta |
| `PORT` | `80` (palpite; usar a porta que a Shard indicar) | ⏳ falta |
| `URL_PUBLICA` | endereço do subdomínio da Shard | ⏳ falta |
| `DB_PATH`, `TIMEZONE`, `DIGEST_HOUR` | ajustes (padrão: leadhunter.db, America/Sao_Paulo, 7) | opcional |
| `META_*`, `AUTO_REPLY_*` | "comente QUERO" (só quando eu tiver vídeos próprios) | desligado |

---

## 6. A IA: KPA Labz (e por que existe o "modo compatível")

- Não tenho API oficial da Anthropic (é paga à parte do Claude Pro). Uso a **KPA Labz** (kpalabz.com), que diz ser **compatível com a API Anthropic**, plano "Pro".
- **Vencimento da chave:** 23/11/2026. A KPA prometeu **+4 dias** (→ ~27/11) e 1 reset semanal como compensação de uma queda, mas o **resgate é pelo app "KPA Networking"** e ainda não tinha sido liberado. Depois de vencer, o bot para até renovar (chave nova vai em `ANTHROPIC_API_KEY`).
- Esse tipo de serviço não é oficial e pode parar de funcionar.

### Problemas que a KPA causou e como foram resolvidos (em `leadhunter/agent.py`)
1. **Recusa a busca na web oficial da Anthropic** (400) → o bot troca sozinho para o **modo compatível** (`MODO_COMPATIVEL=auto`).
2. **Recusa o formato nativo de ferramentas** (`unpaired tool_use/tool_result block`) → no modo compatível o modelo pede ferramentas **em texto**: `<<ferramenta NOME>>{"param": "valor"}<<fim>>`, e o resultado volta como mensagem comum `[resultado NOME]`. Nenhum bloco tool_use atravessa a KPA.
3. **O modelo escrevia o comando de jeitos variados** (`<<fim><<fim>>`, `<tool_call>agente>ler_pagina{...}`, `<<ferroughta?>>{"consulta": ...}`) → o leitor (`extrair_chamada`) é tolerante: pega a primeira chamada, aceita qualquer nome de ferramenta seguido de JSON e, se o nome vier embaralhado, **deduz a ferramenta pelos campos do JSON**.
4. **Autocorreção:** se a resposta parece uma chamada que não deu para entender, o bot pede ao modelo "repita no formato certo" (até 2 vezes) em vez de mostrar texto cru. Restos de marcação são limpos da resposta final.
5. Com o modelo `claude-sonnet-5-5` funcionou bem e em português.

O **modo oficial** (API Anthropic de verdade) continua no código: usa `web_search`/`web_fetch` da Anthropic, `fallbacks`, cache, etc. É só tirar `ANTHROPIC_BASE_URL` e usar uma chave oficial.

---

## 7. Busca e coleta de dados

- **Serper.dev** (`SERPER_API_KEY`): busca no Google, região BR, filtro de período (`dia`, `semana`, `mes`, `ano`), mostra a data dos resultados. Conta grátis ~2.500 buscas; cada CAÇAR CLIENTES usa ~10–25.
- **DuckDuckGo**: reserva automática se o Serper falhar ou não tiver chave (resultados fracos a partir de servidor).
- **Apify** (`APIFY_TOKEN`): ferramenta `apify_rodar` com atores: `instagram_comentarios`, `instagram_posts`, `tiktok_comentarios`, `tiktok_busca`, `biblioteca_anuncios`, `facebook_comentarios`. Plano grátis ~US$5/mês de crédito.
- **Limites reais:** Instagram/TikTok/Facebook bloqueiam leitura sem login; Mercado Livre bloqueia robôs (403). O bot declara essas limitações em vez de inventar.

### Resultado real que já saiu (prova de que funciona)
Com Serper + Apify, o CAÇAR CLIENTES para o MigaZero trouxe **10 oportunidades verificadas** (7 Instagram, 3 Facebook), comentários de 10 a 14/11/2026 como "Quero link", "Manda o link do aspirador", cada um com link do comentário, nota e mensagem pronta. Observações do bot: concorrente na Shopee a ~R$ 33; vários comentários no mesmo Reel de outra pessoa (cuidado para não ser bloqueado pela dona do vídeo: preferir DM, no máximo 1–2 respostas por vídeo, 15–30 abordagens por dia).

> Eu disse que **não vou usar essa lista agora**; foi só para validar que o agente funciona.

---

## 8. Produto cadastrado no bot

- **MigaZero** — aspirador portátil sem fio para carro, bico de frestas e escova, recarga USB.
- **R$ 119,90**, frete grátis para todo o Brasil.
- Link de venda: **https://pratikasa.vercel.app/migazero**

---

## 9. Telegram: como usar

- Bot: "Agente vendedor" (criado no @BotFather).
- Botões: `CAÇAR CLIENTES`, `CLIENTES QUENTES`, `VARREDURA TOTAL 360`, `BUSCAR MAIS`, `RADAR META`, `RADAR SOCIAL`, `MINHA MENSAGEM`, `MEUS RESULTADOS`, `ABRIR NA EXTENSÃO`, `TROCAR PRODUTO`.
- Comandos: `/start`, `/limpar` (reinicia a conversa, mantém produto e resultados), `/relatorio on|off` (varredura automática das 7h — **eu desliguei** para não gastar créditos), `/conectar` (gera o código da extensão).
- Feedback: "ESSE COMPROU #id", "ESSE NÃO ERA #id".
- Toda oportunidade entregue no chat é salva no banco automaticamente (lida do próprio texto da resposta), sem repetir o mesmo link.

---

## 10. Extensão do Chrome: "LeadHunter Abridor"

Faz o papel da "Superagent" da Base44. **Só no computador** (Chrome do celular não aceita extensões).

### Instalar
1. Baixar `dist/leadhunter-extensao.zip` e descompactar.
2. Chrome → `chrome://extensions` → ligar **Modo do desenvolvedor** → **Carregar sem compactação** → escolher a pasta `extensao`.
3. Fixar o ícone (quebra-cabeça 🧩). Sugestão: usar um **perfil separado do Chrome**.

### Modo manual (funciona sem servidor)
Copiar a resposta do CAÇAR CLIENTES no Telegram → colar na extensão → **Ler oportunidades** → **Abrir abas** (lotes de 5, ajustável). Em cada aba aparece um cartão com:
- **Copiar** (copia a mensagem)
- **Colar na caixa** (coloca o texto na caixa de comentário; se não achar, copia e avisa)
- **Abrir perfil (DM)** (abre o perfil com a mensagem copiada)

### Modo conectado ao bot (automático)
1. Shard Cloud: habilitar subdomínio + variáveis `WEB_ATIVO=1`, `PORT=80`, `URL_PUBLICA`. Reiniciar. Abrir o endereço no navegador: deve aparecer `{"ok":true}`.
2. Telegram: `/conectar` → bot dá um código (um novo `/conectar` invalida o antigo).
3. Extensão: **🔌 Conexão com o bot** → endereço + código → **Salvar e testar** → "✅ Conectada!".
4. Uso diário: CAÇAR CLIENTES → **ABRIR NA EXTENSÃO** → com o Chrome aberto, as abas abrem em até 1 minuto (a extensão consulta a cada 30 s). Também tem o botão **📥 Buscar do bot agora** na extensão.
5. O que já foi aberto não reabre (status "aberta" no banco).

### API (leadhunter/api_extensao.py)
- `GET /api/extensao/status` → `{ok, pendentes}`
- `GET /api/extensao/pendente` → `{abrir, itens}` (só com pedido do Telegram)
- `GET /api/extensao/oportunidades?limite=N`
- `POST /api/extensao/confirmar {"ids": [...]}`
- Autenticação: `Authorization: Bearer <código do /conectar>`. CORS só para `chrome-extension://`.

### Testes feitos
Testado num Chromium com páginas falsas do Instagram/Facebook e o servidor real: conexão com código errado recusada, certo aceita, pedido abriu as abas com cartão e mensagem, "Colar na caixa" preencheu a caixa, nada reabriu depois de confirmado. **Ainda não testado no Instagram/Facebook de verdade** (o "Colar na caixa" pode precisar de ajuste no site real).

---

## 11. ONDE PARAMOS (próximos passos)

1. ⏳ **Shard Cloud → Configurações → Rede e Website:** digitar um subdomínio (ex.: `leadhunter-adryan`) e tocar em **Habilitar**. O plano libera (só a página de erro personalizada pede Pro).
2. ⏳ Criar as variáveis `WEB_ATIVO=1`, `PORT=80`, `URL_PUBLICA=<endereço>` e reiniciar. Conferir `{"ok":true}` no navegador. Se não abrir, ver o log e testar outra porta.
3. ⏳ Enviar o **zip mais recente do bot** (com a ponte da extensão) se ainda não enviou.
4. ⏳ No PC: instalar a **extensão mais recente**, mandar `/conectar`, conectar e testar **ABRIR NA EXTENSÃO** com o Instagram/Facebook reais.
5. ⏳ Se o "Colar na caixa" falhar no site real: ajustar os seletores em `extensao/cartao.js`.
6. 🔜 Quando eu começar a postar vídeos: ligar o **"comente QUERO"** (`leadhunter/meta_webhook.py`, precisa de app na Meta com `instagram_manage_comments`, `instagram_manage_messages`, `pages_manage_engagement`, `pages_messaging`; webhook `https://<URL_PUBLICA>/meta/webhook`).
7. 📅 Renovar/resgatar a KPA antes de 23/11 (ou 27/11 com o bônus).

### Coisas que ficaram em aberto
- A aula do curso sobre a extensão: tentei ver o vídeo (557 MB no Google Drive, grande demais; MediaFire bloqueado). Vi só um trecho curto (instalação da Superagent + chat da Base44). Pela minha explicação, a Superagent **abre os links que o agente achou em abas com a mensagem pronta e eu só envio** — foi isso que a nossa extensão copiou.
- Não sei o que o professor pede para "mandar para ele" no curso.

---

## 12. Histórico de decisões importantes

- **Arquitetura escolhida:** serviço Python com agendador (núcleo) + extensão do navegador, em vez de MCP puro (MCP não roda sozinho de madrugada).
- **Telegram** como interface (eu gostei; funciona no celular).
- **Shard Cloud** em vez de Railway (já tenho assinatura).
- **Sem DM automática / sem driblar bloqueio** de redes sociais (risco de banimento e spam). Abordagem em posts de concorrentes só manual, poucas por dia.
- **Token do Telegram vazou num log** → trocado com /revoke e o código passou a esconder os logs do httpx.
- **Erros aparecem no próprio Telegram** porque os logs da Shard são difíceis de ver no celular.
- **Instalação leve** foi testada, mas o fastapi/uvicorn voltaram ao requirements por causa da ponte com a extensão.
- **Cosméticos não são prioridade** (pedido meu).

---

## 13. Comandos úteis para quem for mexer no código

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q                       # 39 testes
node extensao/testes/parser.test.js       # teste do leitor da extensão
python main.py                            # roda local (precisa do .env)

# gerar os zips
python3 -c "
import zipfile,glob
z=zipfile.ZipFile('dist/leadhunter-shardcloud.zip','w',zipfile.ZIP_DEFLATED)
for f in ['main.py','requirements.txt','.env.example']+sorted(glob.glob('leadhunter/*.py'))+['extensao/'+x for x in ['manifest.json','parser.js','popup.html','popup.js','background.js','cartao.js']]: z.write(f)
z.close()
z=zipfile.ZipFile('dist/leadhunter-extensao.zip','w',zipfile.ZIP_DEFLATED)
for f in ['manifest.json','parser.js','popup.html','popup.js','background.js','cartao.js']: z.write('extensao/'+f)
z.close()"
```

Formato que a extensão e o bot entendem nas respostas (não mudar sem atualizar `extensao/parser.js` e `leadhunter/oportunidades.py`):

```
#1 · Instagram Reels — @usuario · 92/100 · Intenção direta
🔗 https://www.instagram.com/p/XXXX/c/123
💬 "Quero o link" (14/11/2026)
✍️ Sugestão de resposta: Oi! ... https://pratikasa.vercel.app/migazero
```

---

## 14. Atualização de 14/11/2026 — funções das aulas 1 e 2 do curso

Assisti (pela transcrição e trechos dos vídeos) as duas aulas do "Agente Vendedor". O que foi copiado:

**Aula 1 (prospecção com a Superagent):**
- **O bot lê páginas no meu Chrome logado** (`ler_no_navegador`): a extensão abre a página em aba de fundo, rola os comentários, devolve o texto e fecha. Só leitura. Só aparece para a IA quando a extensão falou com o bot nos últimos 3 min e a caixa "Deixar o bot ler páginas aqui" está marcada. Sites: redes sociais, Mercado Livre, Shopee, Reclame Aqui. API: `GET /api/extensao/tarefas`, `POST /api/extensao/tarefa/{id}`. A extensão consulta a cada 4 s durante ~25 s a cada alarme de 30 s.
- **Quantidade livre:** "quero 50 leads" funciona (padrão 10, até 50; limite de passos subiu para 40).
- **Abordagem natural** no prompt: nome da pessoa, responder a dúvida exata, cupom com prazo (sem inventar cupom).
- **Rotinas / "workflow"**: "todo dia às 6h faça X" → ferramentas `criar_rotina`, `listar_rotinas`, `apagar_rotina` (tabela `rotinas`, checada a cada minuto, máx. 5).
- **/extensao**: o bot manda o zip da extensão com o passo a passo.
- Áudio: o bot ainda não ouve (responde pedindo texto; o teclado do celular dita).

**Aula 2 (assistente do dia a dia):**
- `CRIATIVOS CAMPEÕES` (Biblioteca: dias ativos, nº de cópias, copy exata, padrões, preço no mapa, 3 roteiros), `ROTEIRO DE CRIATIVO`, `MONTAR CAMPANHA`, `ATENDIMENTO`, `ANALISAR MINHA PÁGINA`, `ACHAR PRODUTO`, `CONTEÚDO`, `MINHAS ROTINAS`. Botão `MAIS FUNÇÕES` mostra o menu.
- **Prints**: foto enviada vai para a IA analisar (anúncio, métricas, página).
- **Vídeos** (`leadhunter/video.py`, ffmpeg via pacote `imageio-ffmpeg`): `ANALISAR VÍDEO` (grade 3x3 de quadros para a IA dar nota) e `JUNTAR VÍDEOS` (junta em 720x1280 e devolve no chat). Limites: 20 MB por vídeo para baixar, 50 MB para enviar.
- **Não feito (difícil/sem chave):** legendas automáticas (precisa transcrever áudio → usar CapCut), editar voz, gerar vídeo com IA, entrar na conta de anúncios/Kaiross (sem login do usuário; mandar print funciona).

**Para usar:** enviar o zip novo na Shard (o `requirements.txt` agora tem `imageio-ffmpeg`, ~30 MB de instalação) e reinstalar a extensão (versão 1.2.0, pede permissão nova "ler e alterar dados" nos sites de redes sociais, necessária para ler os comentários).
