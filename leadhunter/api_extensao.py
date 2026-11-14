"""API que a extensão do Chrome consulta (ponte bot ↔ navegador).

Fluxo: no Telegram o usuário toca em ABRIR NA EXTENSÃO → o bot registra um pedido →
a extensão (que consulta a cada ~30s) recebe as oportunidades, abre as abas e confirma.
Autenticação: código gerado com /conectar no Telegram (cabeçalho Authorization: Bearer).
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .storage import Storage


class Confirmacao(BaseModel):
    ids: list[int]


def _item(o: dict) -> dict:
    return {k: o.get(k, "") for k in
            ("id", "fonte", "link", "trecho", "data", "sinal", "pontuacao", "sugestao", "usuario")}


def registrar_rotas(app: FastAPI, storage: Storage) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"chrome-extension://.*",
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def usuario(authorization: str | None) -> int:
        token = (authorization or "").removeprefix("Bearer ").strip()
        uid = storage.usuario_do_token(token)
        if uid is None:
            raise HTTPException(401, "Código inválido. Gere outro com /conectar no Telegram.")
        return uid

    @app.get("/api/extensao/status")
    def status(authorization: str | None = Header(default=None)):
        uid = usuario(authorization)
        return {"ok": True, "pendentes": len(storage.oportunidades_pendentes(uid, 200))}

    @app.get("/api/extensao/pendente")
    def pendente(authorization: str | None = Header(default=None)):
        """A extensão chama isto periodicamente. Só devolve itens se houver pedido."""
        uid = usuario(authorization)
        limite = storage.pedido_abertura(uid)
        if not limite:
            return {"abrir": False, "itens": []}
        itens = [_item(o) for o in storage.oportunidades_pendentes(uid, limite)]
        return {"abrir": True, "itens": itens}

    @app.get("/api/extensao/oportunidades")
    def listar(limite: int = 10, authorization: str | None = Header(default=None)):
        """Botão 'Buscar do bot agora' na extensão (sem precisar do pedido no Telegram)."""
        uid = usuario(authorization)
        return {"itens": [_item(o) for o in storage.oportunidades_pendentes(uid, min(limite, 20))]}

    @app.post("/api/extensao/confirmar")
    def confirmar(dados: Confirmacao, authorization: str | None = Header(default=None)):
        uid = usuario(authorization)
        storage.marcar_varias(uid, dados.ids, "aberta")
        storage.limpar_pedido(uid)
        return {"ok": True}
