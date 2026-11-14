from fastapi import FastAPI
from fastapi.testclient import TestClient

from leadhunter.api_extensao import registrar_rotas
from leadhunter.oportunidades import extrair
from leadhunter.storage import Storage

RESPOSTA = """🔎 **3 oportunidades verificadas.**

#1 · Instagram Reels — @sonia_soarees · 92/100 · Intenção direta
🔗 https://www.instagram.com/p/DflB-VRguIO/c/17879664798573081
💬 “Que maravilha eu quero” (14/11/2026)
✍️ Sugestão de resposta: Oi, Sonia! R$ 119,90 com frete grátis: https://pratikasa.vercel.app/migazero

#2 · Facebook — Talia Biasini · 98/100 · Pediu o link
🔗 https://www.facebook.com/reel/2031045924249145/?comment_id=1774755707154460
💬 “Manda o link do aspirador” (10/11/2026)
✍️ Sugestão de resposta: Oi, Talia! Segue o link: https://pratikasa.vercel.app/migazero

📌 **Resumo de mercado**
- Demanda forte."""


def test_extrair_da_resposta_do_chat():
    itens = extrair(RESPOSTA)
    assert len(itens) == 2
    a, b = itens
    assert a == {"fonte": "Instagram", "link": "https://www.instagram.com/p/DflB-VRguIO/c/17879664798573081",
                 "trecho": "Que maravilha eu quero", "data": "14/11/2026", "sinal": "Intenção direta",
                 "pontuacao": 92, "sugestao": "Oi, Sonia! R$ 119,90 com frete grátis: https://pratikasa.vercel.app/migazero",
                 "usuario": "sonia_soarees"}
    assert b["usuario"] == "" and b["fonte"] == "Facebook" and "Resumo" not in b["sugestao"]


def _api(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    app = FastAPI()
    registrar_rotas(app, s)
    return s, TestClient(app)


def test_fluxo_pedido_abrir_confirmar(tmp_path):
    s, c = _api(tmp_path)
    for item in extrair(RESPOSTA):
        s.registrar_oportunidade(1, item)
    assert c.get("/api/extensao/pendente").status_code == 401
    token = s.gerar_token_extensao(1)
    h = {"Authorization": f"Bearer {token}"}
    assert c.get("/api/extensao/status", headers=h).json() == {"ok": True, "pendentes": 2}
    # Sem pedido no Telegram: nada para abrir
    assert c.get("/api/extensao/pendente", headers=h).json() == {"abrir": False, "itens": []}
    s.pedir_abertura(1, 10)
    r = c.get("/api/extensao/pendente", headers=h).json()
    assert r["abrir"] and len(r["itens"]) == 2 and r["itens"][0]["sugestao"]
    ids = [i["id"] for i in r["itens"]]
    assert c.post("/api/extensao/confirmar", headers=h, json={"ids": ids}).json() == {"ok": True}
    assert c.get("/api/extensao/pendente", headers=h).json() == {"abrir": False, "itens": []}
    assert c.get("/api/extensao/status", headers=h).json()["pendentes"] == 0
    # Novo /conectar invalida o código antigo
    s.gerar_token_extensao(1)
    assert c.get("/api/extensao/status", headers=h).status_code == 401


def test_isolamento_entre_usuarios(tmp_path):
    s, c = _api(tmp_path)
    for item in extrair(RESPOSTA):
        s.registrar_oportunidade(1, item)
    t2 = s.gerar_token_extensao(2)
    r = c.get("/api/extensao/oportunidades", headers={"Authorization": f"Bearer {t2}"}).json()
    assert r == {"itens": []}


def test_cors_para_extensao(tmp_path):
    s, c = _api(tmp_path)
    r = c.options("/api/extensao/status", headers={
        "Origin": "chrome-extension://abc", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"})
    assert r.headers.get("access-control-allow-origin") == "chrome-extension://abc"
    r2 = c.options("/api/extensao/status", headers={
        "Origin": "https://site-malicioso.com", "Access-Control-Request-Method": "GET"})
    assert r2.headers.get("access-control-allow-origin") is None
