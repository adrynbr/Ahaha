from leadhunter.storage import Storage


def test_produto_merge_e_apagar(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    s.salvar_produto(1, {"nome": "Caneta", "preco": "79,90"})
    s.salvar_produto(1, {"link_venda": "https://x.com/?utm=1", "preco": ""})
    assert s.obter_produto(1) == {"nome": "Caneta", "preco": "79,90", "link_venda": "https://x.com/?utm=1"}
    assert s.obter_produto(2) is None
    assert s.usuarios_com_produto() == [1]
    s.definir_digest(1, False)
    assert s.usuarios_com_produto() == []
    s.apagar_produto(1)
    assert s.obter_produto(1) is None


def test_oportunidade_sem_duplicar_e_isolada_por_usuario(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    op = {"link": "https://ig.com/p/1", "trecho": "Quero comprar!"}
    assert s.registrar_oportunidade(1, op) is True
    assert s.registrar_oportunidade(1, {"link": "https://IG.com/p/1 ", "trecho": "quero comprar!"}) is False
    assert s.registrar_oportunidade(2, op) is True
    [o] = s.oportunidades(1)
    assert s.marcar_oportunidade(1, o["id"], "comprou")
    assert not s.marcar_oportunidade(2, o["id"], "comprou")
    assert s.oportunidades(1)[0]["status"] == "comprou"


def test_historico_e_resposta_auto(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    for i in range(12):
        s.adicionar_historico(1, "user" if i % 2 == 0 else "assistant", str(i))
    h = s.historico(1, limite=4)
    assert [m["content"] for m in h] == ["8", "9", "10", "11"]
    assert s.marcar_resposta_auto("c1") and not s.marcar_resposta_auto("c1")
