import hashlib
import hmac
import json
from dataclasses import replace

import httpx
from fastapi.testclient import TestClient

from leadhunter.config import Settings
from leadhunter.meta_webhook import (MetaResponder, assinatura_valida, criar_app,
                                     extrair_comentarios, tem_palavra_chave)
from leadhunter.storage import Storage

CFG = replace(Settings(), meta_verify_token="vt", meta_app_secret="seg", meta_page_token="tok",
              meta_page_id="PAGE", meta_ig_user_id="IG", auto_reply_keywords=["quero", "link"],
              auto_reply_link="https://loja.com/?c=QUERO", auto_reply_dm="Link: {link}",
              auto_reply_public="Te chamei no direct!")

IG_PAYLOAD = {"object": "instagram", "entry": [{"changes": [
    {"field": "comments", "value": {"id": "c1", "text": "QUERO!!", "from": {"id": "u1"}}},
    {"field": "comments", "value": {"id": "c2", "text": "lindo", "from": {"id": "u2"}}},
    {"field": "comments", "value": {"id": "c3", "text": "quero", "from": {"id": "IG"}}},
]}]}
FB_PAYLOAD = {"object": "page", "entry": [{"changes": [
    {"field": "feed", "value": {"item": "comment", "verb": "add", "comment_id": "f1",
                                "message": "manda o link", "from": {"id": "u9"}}},
    {"field": "feed", "value": {"item": "reaction", "verb": "add"}},
]}]}


def test_palavra_chave():
    assert tem_palavra_chave("Eu QUÉRO sim", ["quero"])
    assert not tem_palavra_chave("queroquero", ["quero"])


def test_assinatura():
    corpo = b'{"a":1}'
    sig = "sha256=" + hmac.new(b"seg", corpo, hashlib.sha256).hexdigest()
    assert assinatura_valida(corpo, sig, "seg")
    assert not assinatura_valida(corpo, "sha256=00", "seg")
    assert not assinatura_valida(corpo, None, "seg")


def test_extrair_ignora_propria_conta():
    ig = extrair_comentarios(IG_PAYLOAD, "PAGE", "IG")
    assert [c["comment_id"] for c in ig] == ["c1", "c2"]
    fb = extrair_comentarios(FB_PAYLOAD, "PAGE", "IG")
    assert fb == [{"canal": "facebook", "comment_id": "f1", "texto": "manda o link", "autor_id": "u9"}]


def _app(tmp_path):
    chamadas = []

    def handler(req: httpx.Request):
        chamadas.append((req.url.path, json.loads(req.content)))
        return httpx.Response(200, json={"id": "ok"})

    storage = Storage(str(tmp_path / "t.db"))
    resp = MetaResponder(CFG, storage, http=httpx.Client(transport=httpx.MockTransport(handler)))
    return TestClient(criar_app(CFG, storage, resp)), chamadas


def _post(client, payload):
    corpo = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"seg", corpo, hashlib.sha256).hexdigest()
    return client.post("/meta/webhook", content=corpo,
                       headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})


def test_verificacao(tmp_path):
    client, _ = _app(tmp_path)
    ok = client.get("/meta/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "vt",
                                             "hub.challenge": "123"})
    assert ok.status_code == 200 and ok.text == "123"
    assert client.get("/meta/webhook", params={"hub.mode": "subscribe",
                                               "hub.verify_token": "x"}).status_code == 403


def test_responde_instagram_uma_vez(tmp_path):
    client, chamadas = _app(tmp_path)
    r = _post(client, IG_PAYLOAD)
    assert r.json() == {"resultados": ["respondido", "ignorado"]}
    assert chamadas[0] == ("/v21.0/IG/messages", {"recipient": {"comment_id": "c1"},
                                                  "message": {"text": "Link: https://loja.com/?c=QUERO"}})
    assert chamadas[1] == ("/v21.0/c1/replies", {"message": "Te chamei no direct!"})
    assert _post(client, IG_PAYLOAD).json() == {"resultados": ["duplicado", "ignorado"]}


def test_responde_facebook(tmp_path):
    client, chamadas = _app(tmp_path)
    assert _post(client, FB_PAYLOAD).json() == {"resultados": ["respondido"]}
    assert chamadas[0][0] == "/v21.0/PAGE/messages"
    assert chamadas[1][0] == "/v21.0/f1/comments"


def test_assinatura_invalida_rejeitada(tmp_path):
    client, _ = _app(tmp_path)
    r = client.post("/meta/webhook", json=IG_PAYLOAD, headers={"X-Hub-Signature-256": "sha256=00"})
    assert r.status_code == 401
