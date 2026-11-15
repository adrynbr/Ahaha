""""Comente QUERO que te mando o link na DM" — só nos SEUS posts e anúncios.

Usa a API oficial da Meta (Private Replies). A Meta só permite isso em comentários
de publicações da sua própria Página / conta profissional do Instagram, e uma
mensagem privada por comentário, dentro de 7 dias.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import unicodedata

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from .config import Settings
from .storage import Storage

log = logging.getLogger(__name__)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    so_letras = "".join(ch if ch.isalnum() else " " for ch in sem_acento.lower())
    return " ".join(so_letras.split())


def tem_palavra_chave(texto: str, palavras: list[str]) -> bool:
    t = f" {_normalizar(texto)} "
    return any(f" {_normalizar(p)} " in t for p in palavras if p.strip())


def assinatura_valida(corpo: bytes, cabecalho: str | None, segredo: str) -> bool:
    if not segredo:
        log.warning("META_APP_SECRET vazio: assinatura do webhook NÃO verificada")
        return True
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho.removeprefix("sha256="))


def extrair_comentarios(payload: dict, page_id: str, ig_user_id: str) -> list[dict]:
    """Normaliza eventos de comentário do Instagram e do Facebook.

    Retorna [{canal, comment_id, texto, autor_id}] ignorando comentários da própria conta.
    """
    saida = []
    objeto = payload.get("object")
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            v = change.get("value", {})
            if objeto == "instagram" and change.get("field") == "comments":
                autor = v.get("from", {}).get("id", "")
                if autor and autor == ig_user_id:
                    continue
                saida.append({"canal": "instagram", "comment_id": v.get("id", ""),
                              "texto": v.get("text", ""), "autor_id": autor})
            elif objeto == "page" and change.get("field") == "feed":
                if v.get("item") != "comment" or v.get("verb") != "add":
                    continue
                autor = v.get("from", {}).get("id", "")
                if autor and autor == page_id:
                    continue
                saida.append({"canal": "facebook", "comment_id": v.get("comment_id", ""),
                              "texto": v.get("message", ""), "autor_id": autor})
    return [c for c in saida if c["comment_id"]]


class MetaResponder:
    def __init__(self, cfg: Settings, storage: Storage, http: httpx.Client | None = None):
        self.cfg = cfg
        self.storage = storage
        self.http = http or httpx.Client(timeout=20)
        self.base = f"https://graph.facebook.com/{cfg.meta_graph_version}"

    def _post(self, caminho: str, json: dict) -> bool:
        r = self.http.post(f"{self.base}/{caminho}", json=json,
                           params={"access_token": self.cfg.meta_page_token})
        if r.status_code >= 400:
            log.warning("Graph API %s: %s", r.status_code, r.text[:300])
            return False
        return True

    def responder(self, c: dict) -> str:
        if not tem_palavra_chave(c["texto"], self.cfg.auto_reply_keywords):
            return "ignorado"
        if not self.storage.marcar_resposta_auto(c["comment_id"]):
            return "duplicado"
        dm = self.cfg.auto_reply_dm.format(link=self.cfg.auto_reply_link)
        conta = self.cfg.meta_ig_user_id if c["canal"] == "instagram" else self.cfg.meta_page_id
        ok = self._post(f"{conta}/messages",
                        {"recipient": {"comment_id": c["comment_id"]}, "message": {"text": dm}})
        if ok and self.cfg.auto_reply_public:
            if c["canal"] == "instagram":
                self._post(f"{c['comment_id']}/replies", {"message": self.cfg.auto_reply_public})
            else:
                self._post(f"{c['comment_id']}/comments", {"message": self.cfg.auto_reply_public})
        return "respondido" if ok else "falhou"


def criar_app(cfg: Settings, storage: Storage, responder: MetaResponder | None = None) -> FastAPI:
    app = FastAPI(title="LeadHunter webhooks")
    resp = responder or MetaResponder(cfg, storage)
    from .api_extensao import registrar_rotas

    registrar_rotas(app, storage)

    @app.get("/")
    def saude():
        return {"ok": True}

    @app.get("/meta/webhook")
    def verificar(request: Request):
        q = request.query_params
        if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == cfg.meta_verify_token:
            return PlainTextResponse(q.get("hub.challenge", ""))
        raise HTTPException(403, "token inválido")

    @app.post("/meta/webhook")
    async def receber(request: Request):
        corpo = await request.body()
        if not assinatura_valida(corpo, request.headers.get("X-Hub-Signature-256"),
                                 cfg.meta_app_secret):
            raise HTTPException(401, "assinatura inválida")
        payload = await request.json()
        comentarios = extrair_comentarios(payload, cfg.meta_page_id, cfg.meta_ig_user_id)
        resultados = [await run_in_threadpool(resp.responder, c) for c in comentarios]
        return {"resultados": resultados}

    return app
