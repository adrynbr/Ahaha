"""Interface pelo Telegram + relatório diário automático."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import tempfile
import zipfile
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InputFile, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import video
from .agent import LeadHunter
from .config import settings
from .storage import Storage

log = logging.getLogger(__name__)

TECLADO = ReplyKeyboardMarkup(
    [["CAÇAR CLIENTES", "CLIENTES QUENTES"],
     ["VARREDURA TOTAL 360", "BUSCAR MAIS"],
     ["RADAR META", "RADAR SOCIAL"],
     ["CRIATIVOS CAMPEÕES", "MONTAR CAMPANHA"],
     ["MINHA MENSAGEM", "MEUS RESULTADOS"],
     ["ABRIR NA EXTENSÃO", "MAIS FUNÇÕES"]],
    resize_keyboard=True,
)
LIMITE_TELEGRAM = 4000
MAX_VIDEOS = 6
PASTA_EXTENSAO = Path(__file__).resolve().parent.parent / "extensao"

MENU = """🧰 Tudo o que eu faço (toque ou escreva):

🎯 Clientes
• CAÇAR CLIENTES / CLIENTES QUENTES / BUSCAR MAIS
• VARREDURA TOTAL 360 / RADAR SOCIAL / RADAR META
• Pedido livre: "preciso de 50 clientes para hoje"
• MINHA MENSAGEM: modelo de abordagem (mande o seu, eu sigo o estilo)
• ABRIR NA EXTENSÃO: abre os leads no Chrome com a mensagem pronta

📊 Anúncios e criativos
• CRIATIVOS CAMPEÕES: minera a Biblioteca de Anúncios (dias rodando, cópias, copy vencedora)
• ROTEIRO DE CRIATIVO: roteiro cena a cena para gravar ou gerar em IA
• MONTAR CAMPANHA: campanha da Meta pronta para copiar e colar
• Mande PRINT das métricas ou do anúncio que eu analiso

🎬 Vídeos (mande os vídeos aqui, até 20 MB cada)
• ANALISAR VÍDEO: nota e melhorias do criativo
• JUNTAR VÍDEOS: junto na ordem enviada, formato 9:16
• ESQUECER VÍDEOS: limpa a lista

🛒 Vendas
• ATENDIMENTO: respostas para preço, frete, "é golpe?", etc.
• ANALISAR MINHA PÁGINA: o que está travando a venda
• ACHAR PRODUTO: produtos com potencial
• CONTEÚDO: 7 dias de posts para Instagram/TikTok

⏰ Rotinas
• "Todo dia às 6h, traga comentários 'quero' do TikTok das últimas 24h"
• MINHAS ROTINAS / "cancele a rotina #id"

⚙️ /extensao (baixar a extensão) · /conectar · /limpar · TROCAR PRODUTO"""


def dividir(texto: str, limite: int = LIMITE_TELEGRAM) -> list[str]:
    partes, atual = [], ""
    for linha in texto.split("\n"):
        while len(linha) > limite:
            if atual:
                partes.append(atual)
                atual = ""
            partes.append(linha[:limite])
            linha = linha[limite:]
        if len(atual) + len(linha) + 1 > limite:
            partes.append(atual)
            atual = linha
        else:
            atual = f"{atual}\n{linha}" if atual else linha
    if atual:
        partes.append(atual)
    return partes or [""]


def _permitido(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return not settings.telegram_allowed_users or uid in settings.telegram_allowed_users


async def _enviar(context: ContextTypes.DEFAULT_TYPE, chat_id: int, texto: str) -> None:
    for parte in dividir(texto):
        await context.bot.send_message(chat_id, parte, reply_markup=TECLADO,
                                       disable_web_page_preview=True)


async def _digitando(context, chat_id: int, parar: asyncio.Event) -> None:
    while not parar.is_set():
        try:
            await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:  # noqa: BLE001 - indicador visual, falha não importa
            pass
        try:
            await asyncio.wait_for(parar.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            pass


async def _rodar_agente(context, chat_id: int, user_id: int, texto: str,
                        imagens: list[tuple[str, str]] | None = None) -> None:
    agente: LeadHunter = context.application.bot_data["agente"]
    parar = asyncio.Event()
    tarefa = asyncio.create_task(_digitando(context, chat_id, parar))
    try:
        resposta = await asyncio.to_thread(agente.responder, user_id, texto, imagens)
    finally:
        parar.set()
        await tarefa
    await _enviar(context, chat_id, resposta)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _permitido(update):
        await update.message.reply_text(f"Acesso não autorizado. Seu ID: {update.effective_user.id}")
        return
    await _rodar_agente(context, update.effective_chat.id, update.effective_user.id, "Olá!")


async def mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _permitido(update):
        await update.message.reply_text(f"Acesso não autorizado. Seu ID: {update.effective_user.id}")
        return
    texto = update.message.text or ""
    cima = texto.strip().upper()
    if cima.startswith(("ABRIR NA EXTENS", "ABRIR NA EXTENÇ")):
        await abrir_na_extensao(update, context)
        return
    if cima.startswith(("MAIS FUN", "MENU", "AJUDA")):
        await update.message.reply_text(MENU, reply_markup=TECLADO)
        return
    if cima.startswith(("JUNTAR V", "JUNTAR OS V", "JUNTA OS V", "JUNTA ESSES")):
        await juntar_videos(update, context)
        return
    if cima.startswith(("ANALISAR V", "ANALISA O V", "ANALISA ESSE V", "ANALISAR O V", "ANALISAR OS V")):
        await analisar_videos(update, context, texto)
        return
    if cima.startswith(("ESQUECER V", "LIMPAR V")):
        context.user_data["videos"] = []
        await update.message.reply_text("🧹 Lista de vídeos limpa.", reply_markup=TECLADO)
        return
    if cima.startswith(("VARREDURA", "CAÇAR", "CACAR", "RADAR", "CLIENTES", "BUSCAR", "CRIATIVOS",
                        "MONTAR CAMPANHA", "ACHAR PRODUTO", "ROTEIRO")):
        await update.message.reply_text("🔎 Começando a busca. Pode levar alguns minutos…")
    await _rodar_agente(context, update.effective_chat.id, update.effective_user.id, texto)


async def conectar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gera o código que liga a extensão do Chrome a este bot."""
    if not _permitido(update):
        return
    if not settings.web_ativo:
        await update.message.reply_text(
            "A ponte com a extensão está desligada. Na hospedagem, ligue a Publicação na Web "
            "e crie as variáveis WEB_ATIVO=1 e URL_PUBLICA (o endereço do seu app).")
        return
    storage: Storage = context.application.bot_data["storage"]
    token = storage.gerar_token_extensao(update.effective_user.id)
    url = settings.url_publica or "(o endereço do seu app na hospedagem)"
    await update.message.reply_text(
        "🔌 Conectar a extensão:\n"
        "1. No Chrome, clique na extensão LeadHunter → Conexão com o bot.\n"
        f"2. Endereço: {url}\n"
        f"3. Código: {token}\n"
        "4. Clique em Salvar.\n\n"
        "Não mostre esse código a ninguém. Mandar /conectar de novo gera outro e desliga o antigo.",
        reply_markup=TECLADO)


async def abrir_na_extensao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    uid = update.effective_user.id
    if not storage.extensao_conectada(uid):
        await update.message.reply_text("A extensão ainda não está conectada. Mande /conectar primeiro.",
                                        reply_markup=TECLADO)
        return
    pendentes = len(storage.oportunidades_pendentes(uid, 200))
    if not pendentes:
        await update.message.reply_text("Nenhuma oportunidade nova para abrir. Toque em CAÇAR CLIENTES antes.",
                                        reply_markup=TECLADO)
        return
    n = min(pendentes, 10)
    storage.pedir_abertura(uid, n)
    await update.message.reply_text(
        f"🧭 Pronto! Com o Chrome aberto, a extensão vai abrir {n} oportunidade(s) em até 1 minuto, "
        "cada uma com a mensagem pronta. Você revisa e envia.", reply_markup=TECLADO)


# --- Fotos e vídeos ---------------------------------------------------------------------

async def foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Print de anúncio, métricas, página ou comentários: a IA analisa a imagem."""
    if not _permitido(update):
        return
    msg = update.message
    if msg.photo:
        arquivo = await msg.photo[-1].get_file()
        tipo = "image/jpeg"
    else:  # imagem enviada como arquivo
        doc = msg.document
        if (doc.file_size or 0) > 5_000_000:
            await msg.reply_text("Imagem grande demais (máx. 5 MB). Mande como foto.", reply_markup=TECLADO)
            return
        arquivo = await doc.get_file()
        tipo = doc.mime_type if doc.mime_type in ("image/png", "image/jpeg", "image/webp", "image/gif") else "image/jpeg"
    dados = bytes(await arquivo.download_as_bytearray())
    pedido = msg.caption or ("Analise esta imagem no contexto do meu produto e me diga o que "
                             "ela mostra e o que eu devo fazer.")
    await _rodar_agente(context, update.effective_chat.id, update.effective_user.id, pedido,
                        [(tipo, base64.b64encode(dados).decode())])


async def receber_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _permitido(update):
        return
    msg = update.message
    v = msg.video or msg.video_note or msg.animation or msg.document
    if (getattr(v, "file_size", 0) or 0) > 20_000_000:
        await msg.reply_text("⚠️ Esse vídeo passa de 20 MB, o limite do Telegram para bots. "
                             "Comprima (ex.: no CapCut, exportar em 720p) e mande de novo.",
                             reply_markup=TECLADO)
        return
    videos = context.user_data.setdefault("videos", [])
    if len(videos) >= MAX_VIDEOS:
        videos.pop(0)
    videos.append(v.file_id)
    if msg.caption:
        await analisar_videos(update, context, msg.caption, so_ultimo=True)
        return
    await msg.reply_text(
        f"🎬 Vídeo {len(videos)} recebido.\n"
        "• ANALISAR VÍDEO: eu olho os quadros e dou nota e melhorias\n"
        "• JUNTAR VÍDEOS: junto todos na ordem enviada (9:16)\n"
        "• ESQUECER VÍDEOS: limpa a lista\n"
        "Pode mandar mais vídeos antes.", reply_markup=TECLADO)


async def _baixar(context, file_id: str, destino: str) -> None:
    arquivo = await context.bot.get_file(file_id)
    await arquivo.download_to_drive(destino)


async def analisar_videos(update: Update, context: ContextTypes.DEFAULT_TYPE, pedido: str,
                          so_ultimo: bool = False) -> None:
    videos = context.user_data.get("videos", [])
    if not videos:
        await update.message.reply_text("Mande o vídeo aqui no chat primeiro.", reply_markup=TECLADO)
        return
    alvo = videos[-1:] if so_ultimo else videos[-4:]
    await update.message.reply_text("🎞️ Olhando o(s) vídeo(s)…")
    imagens = []
    with tempfile.TemporaryDirectory() as pasta:
        for i, fid in enumerate(alvo, 1):
            entrada, saida = f"{pasta}/v{i}.mp4", f"{pasta}/q{i}.jpg"
            try:
                await _baixar(context, fid, entrada)
            except Exception as e:  # noqa: BLE001
                await update.message.reply_text(f"Não consegui baixar o vídeo {i}. Detalhe: {e}")
                return
            erro = await asyncio.to_thread(video.quadros, entrada, saida)
            if erro:
                await update.message.reply_text(f"Não consegui ler o vídeo {i}. Detalhe: {erro}")
                return
            imagens.append(("image/jpeg", base64.b64encode(Path(saida).read_bytes()).decode()))
    texto = (f"{pedido}\n\n[Recebeu {len(imagens)} vídeo(s); cada imagem é uma grade 3x3 com 9 quadros "
             "em ordem (esquerda→direita, cima→baixo). Sem áudio.]")
    await _rodar_agente(context, update.effective_chat.id, update.effective_user.id, texto, imagens)


async def juntar_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    videos = context.user_data.get("videos", [])
    if len(videos) < 2:
        await update.message.reply_text("Mande pelo menos 2 vídeos aqui no chat, depois JUNTAR VÍDEOS.",
                                        reply_markup=TECLADO)
        return
    await update.message.reply_text(f"✂️ Juntando {len(videos)} vídeos… pode levar alguns minutos.")
    chat_id = update.effective_chat.id
    with tempfile.TemporaryDirectory() as pasta:
        entradas = []
        for i, fid in enumerate(videos, 1):
            caminho = f"{pasta}/v{i}.mp4"
            try:
                await _baixar(context, fid, caminho)
            except Exception as e:  # noqa: BLE001
                await update.message.reply_text(f"Não consegui baixar o vídeo {i}. Detalhe: {e}")
                return
            entradas.append(caminho)
        saida = f"{pasta}/criativo_final.mp4"
        erro = await asyncio.to_thread(video.juntar, entradas, saida)
        if erro:
            await update.message.reply_text(f"⚠️ Não consegui juntar. Detalhe: {erro}", reply_markup=TECLADO)
            return
        tamanho = Path(saida).stat().st_size
        if tamanho > 49_000_000:
            await update.message.reply_text("O vídeo final passou de 50 MB (limite do Telegram). "
                                            "Mande vídeos mais curtos ou em 720p.", reply_markup=TECLADO)
            return
        with open(saida, "rb") as f:
            await context.bot.send_video(
                chat_id, video=f, supports_streaming=True, read_timeout=180, write_timeout=180,
                caption="✅ Pronto (9:16). Para legendas automáticas: CapCut → Legendas → Gerar.",
                reply_markup=TECLADO)
    context.user_data["videos"] = []


async def audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _permitido(update):
        return
    await update.message.reply_text(
        "🎙️ Ainda não ouço áudios. Escreva o pedido (dica: o teclado do celular tem o microfone "
        "que transforma fala em texto).", reply_markup=TECLADO)


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _permitido(update):
        await update.message.reply_text(MENU, reply_markup=TECLADO)


async def extensao_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manda a extensão do Chrome em .zip, com o passo a passo (no computador)."""
    if not _permitido(update):
        return
    arquivos = [p for p in sorted(PASTA_EXTENSAO.glob("*")) if p.is_file()]
    if not arquivos:
        await update.message.reply_text("A pasta da extensão não veio no servidor. Use o zip do GitHub.")
        return
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in arquivos:
            z.write(p, f"extensao/{p.name}")
    buf.seek(0)
    await update.message.reply_document(
        InputFile(buf, filename="leadhunter-extensao.zip"),
        caption=("🧩 Extensão LeadHunter (só no computador):\n"
                 "1. Baixe e descompacte este arquivo.\n"
                 "2. Chrome → chrome://extensions → ligue Modo do desenvolvedor.\n"
                 "3. Carregar sem compactação → escolha a pasta extensao.\n"
                 "4. Fixe o ícone (🧩) e mande /conectar aqui.\n"
                 "Deixe o Chrome logado no Instagram/TikTok/Facebook: a extensão lê os comentários "
                 "por lá. Ela nunca comenta, curte ou envia nada sozinha."),
        reply_markup=TECLADO)


async def rotinas_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Roda as rotinas diárias que o usuário pediu ("todo dia às 6h faça X")."""
    storage: Storage = context.application.bot_data["storage"]
    agora = datetime.now(ZoneInfo(settings.timezone))
    for r in storage.rotinas_vencidas(agora.date().isoformat(), agora.hour, agora.minute):
        try:
            await context.bot.send_message(r["user_id"], f"⏰ Rotina #{r['id']}: {r['pedido']}")
            await _rodar_agente(context, r["user_id"], r["user_id"],
                                f"(rotina diária automática #{r['id']}) {r['pedido']}")
        except Exception:  # noqa: BLE001 - uma rotina com erro não para as outras
            log.exception("Falha na rotina %s", r["id"])


async def digest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _permitido(update):
        return
    storage: Storage = context.application.bot_data["storage"]
    ligar = (context.args[0].lower() if context.args else "on") not in ("off", "desligar", "nao", "não")
    storage.definir_digest(update.effective_user.id, ligar)
    msg = (f"✅ Relatório diário ligado ({settings.digest_hour}h)." if ligar
           else "🔕 Relatório diário desligado.")
    await update.message.reply_text(msg, reply_markup=TECLADO)


async def limpar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _permitido(update):
        return
    context.application.bot_data["storage"].limpar_historico(update.effective_user.id)
    await update.message.reply_text("🧹 Conversa reiniciada (produto e resultados mantidos).")


async def digest_diario(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Varredura automática: roda CAÇAR CLIENTES para cada usuário com produto salvo."""
    storage: Storage = context.application.bot_data["storage"]
    for user_id in storage.usuarios_com_produto():
        try:
            await context.bot.send_message(user_id, "☀️ Bom dia! Rodando sua varredura diária…")
            await _rodar_agente(context, user_id, user_id,
                                "CAÇAR CLIENTES (varredura diária automática: só o que é das últimas 24-48h)")
        except Exception:  # noqa: BLE001 - um usuário com erro não para os outros
            log.exception("Falha no digest do usuário %s", user_id)


def criar_aplicacao(storage: Storage, agente: LeadHunter) -> Application:
    app = Application.builder().token(settings.telegram_token).concurrent_updates(True).build()
    app.bot_data["storage"] = storage
    app.bot_data["agente"] = agente
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("relatorio", digest_cmd))
    app.add_handler(CommandHandler("limpar", limpar_cmd))
    app.add_handler(CommandHandler("conectar", conectar_cmd))
    app.add_handler(CommandHandler("extensao", extensao_cmd))
    app.add_handler(CommandHandler(["menu", "ajuda"], menu_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, foto))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE | filters.ANIMATION
                                   | filters.Document.VIDEO, receber_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem))
    app.job_queue.run_repeating(rotinas_job, interval=60, first=30, name="rotinas")
    app.job_queue.run_daily(
        digest_diario,
        time=time(hour=settings.digest_hour, minute=3, tzinfo=ZoneInfo(settings.timezone)),
        name="digest_diario",
    )
    return app
