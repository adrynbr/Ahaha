"""Lê as oportunidades do texto que o agente entregou no chat.

Garante que tudo o que o usuário viu fica salvo (para MEUS RESULTADOS e para a
extensão), mesmo quando o modelo esquece de chamar registrar_oportunidade.
Mesmo formato que extensao/parser.js entende.
"""

from __future__ import annotations

import re

_CAB = re.compile(r"^\s*\**#(\d+)\s*·([^\n]*)")
_LINK = re.compile(r"🔗\s*(https?://\S+)")
_FALA = re.compile(r"💬\s*([^\n]+)")
_SUG = re.compile(r"✍️\s*(?:\**\s*Sugest[aã]o de resposta:?\s*\**)?\s*([\s\S]*)", re.I)
_DATA = re.compile(r"\((\d{1,2}/\d{1,2}/\d{2,4}|não verificada)\)\s*$", re.I)
_PONT = re.compile(r"(\d{1,3})\s*/\s*100")


def _limpar(t: str) -> str:
    return t.replace("**", "").replace("__", "").strip()


def rede_do_link(link: str) -> str:
    if "instagram.com" in link:
        return "Instagram"
    if "facebook.com" in link or "fb.com" in link:
        return "Facebook"
    if "tiktok.com" in link:
        return "TikTok"
    if re.search(r"(^|[/.])(x|twitter)\.com", link):
        return "X"
    return "Web"


def extrair(texto: str) -> list[dict]:
    itens = []
    for parte in re.split(r"\n(?=\s*\**#\d+\s*·)", texto.replace("\r", "")):
        cab = _CAB.match(parte)
        link = _LINK.search(parte)
        if not cab or not link:
            continue
        fala = _limpar((_FALA.search(parte) or [None, ""])[1])
        data = ""
        m = _DATA.search(fala)
        if m:
            data, fala = m.group(1), fala[:m.start()].strip()
        fala = fala.strip("“”\"")
        sug = _SUG.search(parte)
        sugestao = _limpar(re.split(r"\n\s*(?:📌|📎|📩)", sug.group(1))[0]) if sug else ""
        titulo = _limpar(cab.group(2))
        usuario = (re.search(r"@([A-Za-z0-9._]+)", titulo) or [None, ""])[1]
        pont = _PONT.search(titulo)
        partes_tit = [p.strip() for p in titulo.split("·") if p.strip()]
        url = link.group(1).rstrip(").],")
        itens.append({
            "fonte": rede_do_link(url),
            "link": url,
            "trecho": fala,
            "data": data or "não verificada",
            "sinal": partes_tit[-1] if len(partes_tit) >= 2 else "",
            "pontuacao": int(pont.group(1)) if pont else 0,
            "sugestao": sugestao,
            "usuario": usuario,
        })
    return itens
