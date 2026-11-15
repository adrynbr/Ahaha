import json
import subprocess
import threading
import time

import anthropic
import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from leadhunter import video
from leadhunter.agent import LeadHunter, _ferramentas, ler_via_extensao
from leadhunter.api_extensao import registrar_rotas
from leadhunter.storage import Storage


def _nomes(s, uid=1):
    return {t.name: t for t in _ferramentas(s, uid)}


# --- rotinas ("fluxos de trabalho") ---

def test_rotinas_vencem_uma_vez_por_dia(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    s.criar_rotina(1, 6, 0, "varrer TikTok", "2026-11-14", ja_passou=False)
    s.criar_rotina(1, 5, 0, "criada depois das 5h", "2026-11-14", ja_passou=True)
    assert s.rotinas_vencidas("2026-11-14", 5, 59) == []
    [r] = s.rotinas_vencidas("2026-11-14", 6, 0)
    assert r["pedido"] == "varrer TikTok"
    assert s.rotinas_vencidas("2026-11-14", 23, 0) == []  # não repete no mesmo dia
    assert len(s.rotinas_vencidas("2026-11-15", 7, 0)) == 2  # dia seguinte: as duas


def test_ferramentas_de_rotina(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    f = _nomes(s)
    assert "criada" in f["criar_rotina"].call({"hora": 6, "pedido": "trazer comentários quero"})
    assert "Horário inválido" in f["criar_rotina"].call({"hora": 25, "pedido": "x"})
    assert "06:00" in f["listar_rotinas"].call({})
    rid = s.rotinas(1)[0]["id"]
    assert not s.apagar_rotina(2, rid)  # outro usuário não apaga
    assert f["apagar_rotina"].call({"rotina_id": rid}) == "Rotina apagada."
    assert f["listar_rotinas"].call({}) == "Nenhuma rotina agendada."


# --- leitura de páginas pela extensão ---

def test_ler_no_navegador_so_com_extensao_online(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    assert "ler_no_navegador" not in _nomes(s)
    s.registrar_visto(1, leitura=True)
    assert "ler_no_navegador" in _nomes(s)
    s.registrar_visto(1, leitura=False)  # usuário desligou no popup
    assert "ler_no_navegador" not in _nomes(s)


def test_fluxo_leitura_pela_api(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    app = FastAPI()
    registrar_rotas(app, s)
    c = TestClient(app)
    h = {"Authorization": f"Bearer {s.gerar_token_extensao(1)}"}
    assert c.get("/api/extensao/tarefas").status_code == 401

    def extensao_falsa():
        for _ in range(50):
            ts = c.get("/api/extensao/tarefas", headers=h).json()["tarefas"]
            if ts:
                [t] = ts
                assert t["url"].startswith("https://www.tiktok.com/")
                c.post(f"/api/extensao/tarefa/{t['id']}", headers=h,
                       json={"texto": "agtha mendes: ela vem com carregador?"})
                return
            time.sleep(0.05)

    th = threading.Thread(target=extensao_falsa)
    th.start()
    r = ler_via_extensao(s, 1, "https://www.tiktok.com/@x/video/1", espera=5, intervalo=0.05)
    th.join()
    assert "carregador" in r
    # Outro usuário não conclui tarefa alheia
    tid = s.criar_tarefa_navegador(1, "https://www.instagram.com/p/x")
    h2 = {"Authorization": f"Bearer {s.gerar_token_extensao(2)}"}
    assert c.post(f"/api/extensao/tarefa/{tid}", headers=h2, json={"texto": "x"}).status_code == 404
    # leitura=0: não entrega tarefas
    assert c.get("/api/extensao/tarefas?leitura=0", headers=h).json() == {"tarefas": []}


def test_ler_via_extensao_recusa_sites_e_expira(tmp_path):
    s = Storage(str(tmp_path / "t.db"))
    assert "só lê redes sociais" in ler_via_extensao(s, 1, "https://banco.com.br/login")
    assert "só lê redes sociais" in ler_via_extensao(s, 1, "https://instagram.com.malicioso.net/")
    r = ler_via_extensao(s, 1, "https://www.instagram.com/p/1", espera=1, intervalo=0.05, sem_resposta=0.2)
    assert "não respondeu" in r
    assert s.pegar_tarefas_navegador(1) == []  # tarefa expirada não é entregue depois


# --- imagens para a IA ---

def test_responder_envia_imagens(tmp_path):
    enviados = []

    def handler(req):
        corpo = json.loads(req.content)
        enviados.append(corpo)
        return httpx2.Response(200, json={
            "id": "m", "type": "message", "role": "assistant", "model": corpo["model"],
            "content": [{"type": "text", "text": "Nota 7/10"}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

    client = anthropic.Anthropic(api_key="t", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    s = Storage(str(tmp_path / "t.db"))
    LeadHunter(s, client).responder(1, "analisa", [("image/jpeg", "QUJD")])
    conteudo = enviados[0]["messages"][-1]["content"]
    assert conteudo[0]["type"] == "image" and conteudo[0]["source"]["data"] == "QUJD"
    assert conteudo[-1]["type"] == "text" and "analisa" in conteudo[-1]["text"]
    assert s.historico(1)[0]["content"].startswith("[1 imagem(ns) enviada(s)]")


# --- vídeo ---

def test_comando_juntar_poe_silencio_em_video_mudo():
    cmd = video.comando_juntar("ffmpeg", ["a.mp4", "b.mp4"], "out.mp4", [True, False], [3.0, 2.5])
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "anullsrc=r=44100:cl=stereo" in cmd and "2.50" in cmd
    assert "[2:a]aresample" in fc and "[0:a]aresample" in fc
    assert fc.endswith("[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    assert video.duracao("  Duration: 00:01:02.50, start") == 62.5
    assert video.tem_audio("Stream #0:1(und): Audio: aac") and not video.tem_audio("Video: h264")


@pytest.mark.skipif(not video.ffmpeg_exe(), reason="sem ffmpeg")
def test_juntar_e_quadros_de_verdade(tmp_path):
    exe = video.ffmpeg_exe()
    a, b = str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")
    subprocess.run([exe, "-y", "-f", "lavfi", "-i", "testsrc=s=320x240:d=1", "-f", "lavfi", "-i",
                    "sine=d=1", "-shortest", "-pix_fmt", "yuv420p", a], check=True, capture_output=True)
    subprocess.run([exe, "-y", "-f", "lavfi", "-i", "testsrc=s=240x426:d=1", "-pix_fmt", "yuv420p", b],
                   check=True, capture_output=True)  # sem áudio
    out = str(tmp_path / "out.mp4")
    assert video.juntar([a, b], out) is None
    info = video._info(exe, out)
    assert "720x1280" in info and video.tem_audio(info) and 1.8 < video.duracao(info) < 2.5
    jpg = str(tmp_path / "q.jpg")
    assert video.quadros(out, jpg) is None
    assert (tmp_path / "q.jpg").stat().st_size > 1000


# --- provedor instável (503) ---

def _cliente(respostas):
    def handler(req):
        st = respostas.pop(0)
        if st != 200:
            return httpx2.Response(st, json={"type": "error", "error": {"type": "api_error", "message": "indisponível"}})
        corpo = json.loads(req.content)
        return httpx2.Response(200, json={
            "id": "m", "type": "message", "role": "assistant", "model": corpo["model"],
            "content": [{"type": "text", "text": "Achei 3 anunciantes."}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})
    return anthropic.Anthropic(api_key="t", max_retries=0,
                               http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def test_503_espera_e_tenta_de_novo(tmp_path, monkeypatch):
    monkeypatch.setattr(LeadHunter, "ESPERAS_INSTAVEL", (0, 0, 0))
    s = Storage(str(tmp_path / "t.db"))
    lh = LeadHunter(s, _cliente([503, 529, 200]))
    lh.compat = True
    assert lh.responder(1, "RADAR META") == "Achei 3 anunciantes."


def test_503_persistente_mensagem_clara(tmp_path, monkeypatch):
    monkeypatch.setattr(LeadHunter, "ESPERAS_INSTAVEL", (0, 0, 0))
    s = Storage(str(tmp_path / "t.db"))
    lh = LeadHunter(s, _cliente([503] * 4))
    lh.compat = True
    r = lh.responder(1, "RADAR META")
    assert "fora do ar" in r and "MEUS RESULTADOS" in r
