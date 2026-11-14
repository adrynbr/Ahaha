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
        if any(t.get("name") == "web_search" for t in corpo.get("tools", [])):
            return httpx2.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": "unsupported tool"}})
        return httpx2.Response(200, json=RESPOSTA_OK)

    lh = agent_mod.LeadHunter(Storage(str(tmp_path / "t.db")), _cliente(handler))
    assert lh.responder(1, "oi") == "ok"
    assert lh.compat is True
    segundo = corpos[1]
    assert "tools" not in segundo, "modo compatível não envia ferramentas nativas"
    assert "<<ferramenta NOME>>" in segundo["system"] and "buscar_web(" in segundo["system"]
    assert segundo["stop_sequences"] == ["<<fim>>"]
    assert "fallbacks" not in segundo and "cache_control" not in segundo
    # Próximas mensagens já vão direto no modo compatível
    lh.responder(1, "de novo")
    assert len(corpos) == 3 and "tools" not in corpos[2]


def _resposta(texto, stop="end_turn"):
    return {**RESPOSTA_OK, "content": [{"type": "text", "text": texto}], "stop_reason": stop}


def test_loop_de_ferramentas_por_texto(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "settings", replace(agent_mod.settings, modo_compativel="sim"))
    monkeypatch.setattr(agent_mod.web, "buscar", lambda consulta: f"resultados para {consulta}")
    respostas = iter([
        _resposta('Vou pesquisar.\n<<ferramenta buscar_web>>{"consulta": "caneta depiladora"}', "stop_sequence"),
        _resposta('<<ferramenta salvar_nota>>{"texto": "gosta de SP"}', "stop_sequence"),
        _resposta("Achei 3 oportunidades."),
    ])
    corpos = []

    def handler(req):
        corpos.append(json.loads(req.content))
        return httpx2.Response(200, json=next(respostas))

    s = Storage(str(tmp_path / "t.db"))
    lh = agent_mod.LeadHunter(s, _cliente(handler))
    assert lh.responder(1, "CAÇAR CLIENTES") == "Achei 3 oportunidades."
    ultimo = corpos[-1]["messages"]
    papeis = [m["role"] for m in ultimo]
    assert papeis == ["user", "assistant", "user", "assistant", "user"]
    assert all(isinstance(m["content"], str) for m in ultimo), "só texto, sem blocos de ferramenta"
    assert ultimo[2]["content"] == "[resultado buscar_web]\nresultados para caneta depiladora"
    assert ultimo[4]["content"] == "[resultado salvar_nota]\nNota salva."
    assert s.notas(1) == ["gosta de SP"]


def test_extrair_chamada():
    assert agent_mod.extrair_chamada("oi") is None
    assert agent_mod.extrair_chamada('a\n<<ferramenta ler_pagina>>{"url": "https://x"}<<fim>>') == (
        "a", "ler_pagina", {"url": "https://x"})
    assert agent_mod.extrair_chamada("<<ferramenta trocar_produto>>") == ("", "trocar_produto", {})
    assert agent_mod.extrair_chamada("<<ferramenta buscar_web>>{quebrado}")[2] == {"__erro__": "{quebrado}"}
    # Caso real da KPA: final malformado depois do JSON
    real = ('Vou testar buscas.\n\n<<ferramenta buscar_web>>{"consulta":"caneta depiladora '
            'preço Mercado Livre comprar R$"}<<fim><<fim><<fim>>')
    assert agent_mod.extrair_chamada(real) == (
        "Vou testar buscas.", "buscar_web",
        {"consulta": "caneta depiladora preço Mercado Livre comprar R$"})
    # Pega a primeira chamada e ignora resultados inventados depois
    dupla = '<<ferramenta ler_pagina>>{"url": "a"}<<fim>>\n[resultado ler_pagina] x\n<<ferramenta buscar_web>>{}'
    assert agent_mod.extrair_chamada(dupla)[1:] == ("ler_pagina", {"url": "a"})


def test_limpar_marcacoes():
    assert agent_mod.limpar_marcacoes("Pronto!<<fim><<fim>>") == "Pronto!"


def test_sem_base_url_nao_troca(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_mod, "settings", replace(agent_mod.settings, base_url=""))

    def handler(req):
        return httpx2.Response(400, json={"type": "error", "error": {
            "type": "invalid_request_error", "message": "bad"}})

    lh = agent_mod.LeadHunter(Storage(str(tmp_path / "t.db")), _cliente(handler))
    r = lh.responder(1, "oi")
    assert "Erro no serviço de IA (400" in r and "bad" in r
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
