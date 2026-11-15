"""Cliente mínimo da Apify (execução síncrona de actors públicos)."""

from __future__ import annotations

import json

import httpx

# Apelidos -> actor ID na Apify. Confira o formato de entrada de cada um na página do actor.
ATORES = {
    "instagram_comentarios": "apify~instagram-comment-scraper",
    "instagram_posts": "apify~instagram-scraper",
    "tiktok_comentarios": "clockworks~tiktok-comments-scraper",
    "tiktok_busca": "clockworks~tiktok-scraper",
    "biblioteca_anuncios": "curious_coder~facebook-ads-library-scraper",
    "facebook_comentarios": "apify~facebook-comments-scraper",
}

MAX_ITENS = 100
MAX_CHARS = 60_000


def rodar_ator(token: str, apelido: str, entrada: dict, timeout: float = 240) -> str:
    ator = ATORES.get(apelido)
    if not ator:
        return f"Erro: ator desconhecido '{apelido}'. Opções: {', '.join(ATORES)}"
    url = f"https://api.apify.com/v2/acts/{ator}/run-sync-get-dataset-items"
    try:
        resp = httpx.post(
            url,
            params={"limit": MAX_ITENS},
            headers={"Authorization": f"Bearer {token}"},
            json=entrada,
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        return f"Erro de rede na Apify: {e}"
    if resp.status_code >= 400:
        return f"Erro Apify {resp.status_code}: {resp.text[:500]}"
    itens = resp.json()
    texto = json.dumps(itens[:MAX_ITENS], ensure_ascii=False)
    if len(texto) > MAX_CHARS:
        texto = texto[:MAX_CHARS] + " …[cortado]"
    return f"{len(itens)} itens: {texto}"
