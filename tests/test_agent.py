import json

import anthropic
import httpx2

from leadhunter.agent import LeadHunter, _ferramentas
from leadhunter.storage import Storage
from leadhunter.telegram_bot import dividir


def _ferr(storage, uid=1):
    return {t.name: t for t in _ferramentas(storage, uid)}


def test_ferramentas_salvam_por_usuario(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    f = _ferr(s, 1)
    f["salvar_produto"].call({"nome": "Caneta", "link_venda": "https://k.com/?utm=a"})
    assert s.obter_produto(1) == {"nome": "Caneta", "link_venda": "https://k.com/?utm=a"}
    assert s.obter_produto(2) is None
    args = dict(fonte="Instagram", link="https://ig/p/1", trecho="quero", data="hoje",
                sinal="Intenção direta", pontuacao=90, sugestao="oi")
    assert f["registrar_oportunidade"].call(args).startswith("Registrada com id #")
    assert f["registrar_oportunidade"].call(args).startswith("DUPLICADA")


def test_dividir_respeita_limite():
    texto = "\n".join(["x" * 30] * 50) + "\n" + "y" * 250
    partes = dividir(texto, limite=100)
    assert all(len(p) <= 100 for p in partes)
    assert "".join(partes).replace("\n", "") == texto.replace("\n", "")


def test_responder_monta_requisicao_e_salva_historico(tmp_path):
    enviados = []

    def handler(req: httpx2.Request):
        corpo = json.loads(req.content)
        enviados.append((req, corpo))
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"],
            "content": [{"type": "text", "text": "🚀 Bem-vindo! QUAL PRODUTO VOCÊ QUER VENDER?"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })

    client = anthropic.Anthropic(api_key="test", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    s = Storage(str(tmp_path / "t.db"))
    resposta = LeadHunter(s, client).responder(7, "Olá!")
    assert "QUAL PRODUTO" in resposta
    req, corpo = enviados[0]
    assert corpo["model"] == "claude-opus-5-5"
    assert corpo["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in req.headers["anthropic-beta"]
    nomes = [t["name"] for t in corpo["tools"]]
    assert nomes[:2] == ["web_search", "web_fetch"] and "registrar_oportunidade" in nomes
    assert "Nenhum produto salvo" in corpo["messages"][-1]["content"]
    assert [m["content"] for m in s.historico(7)] == ["Olá!", resposta]
