"""Inicia o bot do Telegram e o servidor de webhooks da Meta no mesmo processo."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import uvicorn

from .agent import LeadHunter
from .config import settings
from .meta_webhook import criar_app
from .storage import Storage
from .telegram_bot import criar_aplicacao


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    faltando = [n for n, v in [("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY")),
                               ("TELEGRAM_BOT_TOKEN", settings.telegram_token)] if not v]
    if faltando:
        sys.exit(f"Faltam variáveis no .env: {', '.join(faltando)}")

    storage = Storage(settings.db_path)
    bot = criar_aplicacao(storage, LeadHunter(storage))
    # O servidor de webhooks só sobe se o "comente QUERO" estiver configurado.
    # Sem ele, o bot do Telegram roda sozinho e não precisa de porta nem link público.
    servidor = None
    if settings.meta_page_token:
        servidor = uvicorn.Server(uvicorn.Config(criar_app(settings, storage), host="0.0.0.0",
                                                 port=settings.port, log_level="info"))
    async with bot:
        await bot.start()
        await bot.updater.start_polling()
        logging.info("LeadHunter rodando. Abra o bot no Telegram e mande /start.")
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
