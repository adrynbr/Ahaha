import json
from dataclasses import replace

import anthropic
import httpx
import httpx2

from leadhunter import agent as agent_mod
from leadhunter import web
from leadhunter.storage import Storage

RESPOSTA_OK = {
    "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
    "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
    "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
}


def _cliente(handler):
    return anthropic.Anthropic(api_key="sk-kpa-test", base_url="https://api.kpalabz.com",
                               http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def test_auto_troca_para_modo_compativel(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "settings",
                        replace(agent_mod.settings, base_url="https://api.kpalabz.com",
                                modo_compativel="auto"))
    corpos = []

    def handler(req):
        corpo = json.loads(req.content)
        corpos.append(corpo)
        if any(t.get("name") == "web_search" for t in corpo["tools"]):
            return httpx2.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": "unsupported tool"}})
        return httpx2.Response(200, json=RESPOSTA_OK)

    lh = agent_mod.LeadHunter(Storage(str(tmp_path / "t.db")), _cliente(handler))
    assert lh.responder(1, "oi") == "ok"
    assert lh.compat is True
    segundo = corpos[1]
    nomes = [t["name"] for t in segundo["tools"]]
    assert nomes[:2] == ["buscar_web", "ler_pagina"]
    assert "fallbacks" not in segundo and "cache_control" not in segundo
    # Próximas mensagens já vão direto no modo compatível
    lh.responder(1, "de novo")
    assert len(corpos) == 3 and corpos[2]["tools"][0]["name"] == "buscar_web"


def test_sem_base_url_nao_troca(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "settings", replace(agent_mod.settings, base_url=""))

    def handler(req):
        return httpx2.Response(400, json={"type": "error", "error": {
            "type": "invalid_request_error", "message": "bad"}})

    lh = agent_mod.LeadHunter(Storage(str(tmp_path / "t.db")), _cliente(handler))
    assert "Erro no serviço de IA (400)" in lh.responder(1, "oi")
    assert lh.compat is False


def test_modelo_inexistente_mensagem_clara(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "settings", replace(agent_mod.settings, modo_compativel="sim"))

    def handler(req):
        return httpx2.Response(404, json={"type": "error", "error": {
            "type": "not_found_error", "message": "model"}})

    lh = agent_mod.LeadHunter(Storage(str(tmp_path / "t.db")), _cliente(handler))
    assert "ANTHROPIC_MODEL" in lh.responder(1, "oi")


DDG_HTML = """
<div class="result"><h2><a rel="nofollow" class="result__a"
 href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.instagram.com%2Freel%2FABC%2F&amp;rut=x">Caneta &amp; depiladora</a></h2>
<a class="result__snippet" href="#">Quero <b>comprar</b> onde acho?</a></div>
<div class="result"><h2><a rel="nofollow" class="result__a" href="https://x.com/p/1">Post X</a></h2>
<a class="result__snippet" href="#">manda o link</a></div>
"""


def test_analisar_busca():
    r = web.analisar_busca(DDG_HTML)
    assert r[0] == {"titulo": "Caneta & depiladora", "link": "https://www.instagram.com/reel/ABC/",
                    "trecho": "Quero comprar onde acho?"}
    assert r[1]["link"] == "https://x.com/p/1"


def test_buscar_e_ler_pagina_com_http_falso():
    def handler(req):
        if "duckduckgo" in req.url.host:
            return httpx.Response(200, text=DDG_HTML)
        return httpx.Response(200, headers={"content-type": "text/html"},
                              text="<html><head><title>t</title></head><body><script>x()</script>"
                                   "<p>Quanto custa?</p><p>Entrega em SP?</p></body></html>")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert "instagram.com/reel/ABC" in web.buscar("caneta", http=http)
    assert web.ler_pagina("https://loja.com", http=http) == "Quanto custa? Entrega em SP?"
    assert web.ler_pagina("ftp://x") == "URL inválida."
