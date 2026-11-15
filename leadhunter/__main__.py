"""Inicia o bot do Telegram e o servidor de webhooks da Meta no mesmo processo."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from .agent import LeadHunter
from .config import settings
from .storage import Storage
from .telegram_bot import criar_aplicacao


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx registra a URL de cada chamada, e a URL do Telegram contém o token do bot.
    # Silencia esses logs (também evita uma linha a cada 10 segundos).
    for nome in ("httpx", "httpx2", "httpcore", "apscheduler"):
        logging.getLogger(nome).setLevel(logging.WARNING)
    faltando = [n for n, v in [("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY")),
                               ("TELEGRAM_BOT_TOKEN", settings.telegram_token)] if not v]
    if faltando:
        sys.exit(f"Faltam variáveis no .env: {', '.join(faltando)}")

    storage = Storage(settings.db_path)
    bot = criar_aplicacao(storage, LeadHunter(storage))
    # O servidor web só sobe para a extensão do Chrome (WEB_ATIVO) ou o "comente QUERO".
    # Sem ele, o bot do Telegram roda sozinho e não precisa de porta nem link público.
    servidor = None
    if settings.web_ativo or settings.meta_page_token:
        import uvicorn

        from .meta_webhook import criar_app

        servidor = uvicorn.Server(uvicorn.Config(criar_app(settings, storage), host="0.0.0.0",
                                                 port=settings.port, log_level="info"))
    async with bot:
        await bot.start()
        await bot.updater.start_polling()
        logging.info("LeadHunter rodando. Abra o bot no Telegram e mande /start.")
        if servidor:
            logging.info("Servidor web ligado na porta %s (extensão / webhooks).", settings.port)
        try:
            if servidor:
                await servidor.serve()  # bloqueia até Ctrl+C
            else:
                await asyncio.Event().wait()
        finally:
            await bot.updater.stop()
            await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
