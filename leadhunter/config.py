"""Configuração lida do ambiente (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    effort: str = os.getenv("ANTHROPIC_EFFORT", "high")
    # Provedores "compatíveis com a API Anthropic" (ex.: KPA Labz) usam ANTHROPIC_BASE_URL.
    base_url: str = os.getenv("ANTHROPIC_BASE_URL", "")
    # auto = tenta a busca oficial da Anthropic e, se o provedor recusar, usa a busca própria.
    # sim = sempre busca própria; nao = sempre busca oficial.
    modo_compativel: str = os.getenv("MODO_COMPATIVEL", "auto").lower()

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_allowed_users: list[int] = field(
        default_factory=lambda: [int(u) for u in _list("TELEGRAM_ALLOWED_USERS")]
    )

    apify_token: str = os.getenv("APIFY_TOKEN", "")
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")

    meta_verify_token: str = os.getenv("META_VERIFY_TOKEN", "")
    meta_app_secret: str = os.getenv("META_APP_SECRET", "")
    meta_page_token: str = os.getenv("META_PAGE_ACCESS_TOKEN", "")
    meta_page_id: str = os.getenv("META_PAGE_ID", "")
    meta_ig_user_id: str = os.getenv("META_IG_USER_ID", "")
    meta_graph_version: str = os.getenv("META_GRAPH_VERSION", "v21.0")
    auto_reply_keywords: list[str] = field(
        default_factory=lambda: [k.lower() for k in _list("AUTO_REPLY_KEYWORDS", "quero")]
    )
    auto_reply_dm: str = os.getenv(
        "AUTO_REPLY_DM", "Oi! Aqui está o link com seu desconto: {link}"
    )
    auto_reply_public: str = os.getenv("AUTO_REPLY_PUBLIC", "Te chamei no direct! 💌")
    auto_reply_link: str = os.getenv("AUTO_REPLY_LINK", "")

    # Liga o servidor web (extensão do Chrome). Precisa da "Publicação na Web" na hospedagem.
    web_ativo: bool = os.getenv("WEB_ATIVO", "").lower() in ("1", "sim", "true")
    url_publica: str = os.getenv("URL_PUBLICA", "").rstrip("/")

    timezone: str = os.getenv("TIMEZONE", "America/Sao_Paulo")
    digest_hour: int = int(os.getenv("DIGEST_HOUR", "7"))
    db_path: str = os.getenv("DB_PATH", "leadhunter.db")
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
