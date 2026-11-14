"""Busca e leitura de páginas feitas pelo próprio bot.

Usadas quando o provedor da API não oferece a busca na web da Anthropic
(caso comum em plataformas "compatíveis com a API Anthropic").
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

UA = ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36")
MAX_CHARS = 20_000

_RESULTADO = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
    r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
    re.S,
)
_TAG = re.compile(r"<[^>]+>")


def _limpar(html: str) -> str:
    return " ".join(unescape(_TAG.sub(" ", html)).split())


def _url_real(href: str) -> str:
    if "duckduckgo.com/l/" in href:
        uddg = parse_qs(urlparse(href if href.startswith("http") else "https:" + href).query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return href


def analisar_busca(html: str, limite: int = 10) -> list[dict]:
    saida = []
    for href, titulo, trecho in _RESULTADO.findall(html):
        saida.append({"titulo": _limpar(titulo), "link": _url_real(unescape(href)),
                      "trecho": _limpar(trecho)})
        if len(saida) >= limite:
            break
    return saida


def buscar(consulta: str, http: httpx.Client | None = None, limite: int = 10) -> str:
    http = http or httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True)
    try:
        r = http.post("https://html.duckduckgo.com/html/", data={"q": consulta, "kl": "br-pt"})
    except httpx.HTTPError as e:
        return f"Erro na busca: {e}"
    if r.status_code >= 400:
        return f"Busca indisponível ({r.status_code}). Tente outra consulta mais tarde."
    resultados = analisar_busca(r.text, limite)
    if not resultados:
        return "Nenhum resultado."
    return "\n".join(f"- {x['titulo']}\n  {x['link']}\n  {x['trecho']}" for x in resultados)


class _Texto(HTMLParser):
    IGNORAR = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.partes: list[str] = []
        self._pular = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._pular += 1

    def handle_endtag(self, tag):
        if tag in self.IGNORAR and self._pular:
            self._pular -= 1

    def handle_data(self, data):
        if not self._pular and data.strip():
            self.partes.append(data.strip())


def extrair_texto(html: str) -> str:
    p = _Texto()
    p.feed(html)
    return " ".join(p.partes)


def ler_pagina(url: str, http: httpx.Client | None = None) -> str:
    if not url.startswith(("http://", "https://")):
        return "URL inválida."
    http = http or httpx.Client(timeout=25, headers={"User-Agent": UA}, follow_redirects=True)
    try:
        r = http.get(url)
    except httpx.HTTPError as e:
        return f"Erro ao abrir a página: {e}"
    if r.status_code >= 400:
        return f"Página indisponível ({r.status_code}). Pode exigir login."
    texto = extrair_texto(r.text) if "html" in r.headers.get("content-type", "html") else r.text
    if len(texto) > MAX_CHARS:
        texto = texto[:MAX_CHARS] + " …[cortado]"
    return texto or "Página sem texto legível (pode exigir login)."
