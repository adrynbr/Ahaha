"""Interface pelo Telegram + relatório diário automático."""

from __future__ import annotations

import asyncio
import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .agent import LeadHunter
from .config import settings
from .storage import Storage

log = logging.getLogger(__name__)

TECLADO = ReplyKeyboardMarkup(
    [["CAÇAR CLIENTES", "CLIENTES QUENTES"],
     ["VARREDURA TOTAL 360", "BUSCAR MAIS"],
     ["RADAR META", "RADAR SOCIAL"],
     ["MINHA MENSAGEM", "MEUS RESULTADOS"],
     ["ABRIR NA EXTENSÃO", "TROCAR PRODUTO"]],
    resize_keyboard=True,
)
LIMITE_TELEGRAM = 4000


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


async def _rodar_agente(context, chat_id: int, user_id: int, texto: str) -> None:
    agente: LeadHunter = context.application.bot_data["agente"]
    parar = asyncio.Event()
    tarefa = asyncio.create_task(_digitando(context, chat_id, parar))
    try:
        resposta = await asyncio.to_thread(agente.responder, user_id, texto)
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
    if texto.upper().startswith(("ABRIR NA EXTENS", "ABRIR NA EXTENÇ")):
        await abrir_na_extensao(update, context)
        return
    if texto.upper().startswith(("VARREDURA", "CAÇAR", "CACAR", "RADAR", "CLIENTES", "BUSCAR")):
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem))
    app.job_queue.run_daily(
        digest_diario,
        time=time(hour=settings.digest_hour, minute=3, tzinfo=ZoneInfo(settings.timezone)),
        name="digest_diario",
    )
    return app
