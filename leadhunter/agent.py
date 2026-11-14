"""O agente: Claude + busca na web + Apify + memória por usuário."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
from anthropic import beta_tool

from . import apify, web
from .config import settings
from .prompts import SYSTEM_PROMPT, contexto_usuario
from .storage import Storage

log = logging.getLogger(__name__)

SERVER_TOOLS = [
    {
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": 20,
        "user_location": {"type": "approximate", "country": "BR", "timezone": "America/Sao_Paulo"},
    },
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 20},
]


def _ferramentas_web() -> list:
    """Busca própria, para provedores sem a busca na web da Anthropic."""

    @beta_tool
    def buscar_web(consulta: str) -> str:
        """Pesquisa na web e devolve até 10 resultados (título, link, trecho).

        Args:
            consulta: Termos de busca. Aceita operadores como site:instagram.com.
        """
        return web.buscar(consulta)

    @beta_tool
    def ler_pagina(url: str) -> str:
        """Abre uma página pública e devolve o texto dela.

        Args:
            url: Endereço completo da página (https://...).
        """
        return web.ler_pagina(url)

    return [buscar_web, ler_pagina]


def _ferramentas(storage: Storage, user_id: int) -> list:
    @beta_tool
    def salvar_produto(
        nome: str = "",
        descricao: str = "",
        preco: str = "",
        link_venda: str = "",
        desconto: str = "",
        pais: str = "",
        publico: str = "",
        concorrentes: str = "",
    ) -> str:
        """Salva ou atualiza o produto do usuário. Envie só os campos que mudaram.

        Args:
            nome: Nome do produto.
            descricao: Descrição curta.
            preco: Preço e parcelamento.
            link_venda: Link de checkout EXATO, com parâmetros de rastreamento.
            desconto: Cupom ou condição especial.
            pais: País de venda (padrão Brasil).
            publico: Público-alvo.
            concorrentes: Concorrentes conhecidos, separados por vírgula.
        """
        storage.salvar_produto(user_id, dict(
            nome=nome, descricao=descricao, preco=preco, link_venda=link_venda,
            desconto=desconto, pais=pais, publico=publico, concorrentes=concorrentes,
        ))
        return "Produto salvo: " + json.dumps(storage.obter_produto(user_id), ensure_ascii=False)

    @beta_tool
    def trocar_produto() -> str:
        """Apaga o produto atual para cadastrar outro (comando TROCAR PRODUTO)."""
        storage.apagar_produto(user_id)
        return "Produto apagado. Pergunte qual é o novo produto."

    @beta_tool
    def salvar_nota(texto: str) -> str:
        """Guarda uma preferência ou feedback do usuário (ex.: 'prefere leads de SP').

        Args:
            texto: A preferência ou aprendizado, em uma frase.
        """
        storage.salvar_nota(user_id, texto)
        return "Nota salva."

    @beta_tool
    def registrar_oportunidade(
        fonte: str, link: str, trecho: str, data: str, sinal: str, pontuacao: int, sugestao: str
    ) -> str:
        """Registra uma oportunidade antes de entregá-la. Recusa duplicadas já entregues antes.

        Args:
            fonte: Instagram, TikTok, Facebook, Meta Ads, X, etc.
            link: Link verificável da publicação ou comentário.
            trecho: Texto exato da manifestação da pessoa.
            data: Data do comentário, ou 'não verificada'.
            sinal: Intenção direta, Preço, Confiança, Compatibilidade, Logística, Comparação ou Objeção.
            pontuacao: 0 a 100.
            sugestao: Rascunho de resposta personalizado com o link do usuário.
        """
        dados = dict(fonte=fonte, link=link, trecho=trecho, data=data, sinal=sinal,
                     pontuacao=pontuacao, sugestao=sugestao)
        if not storage.registrar_oportunidade(user_id, dados):
            return "DUPLICADA: já foi entregue antes. Não entregue de novo."
        op_id = storage.oportunidades(user_id, limite=1)[0]["id"]
        return f"Registrada com id #{op_id}."

    @beta_tool
    def listar_oportunidades(limite: int = 20) -> str:
        """Lista oportunidades já entregues ao usuário (comando MEUS RESULTADOS).

        Args:
            limite: Quantas mostrar, das mais recentes.
        """
        ops = storage.oportunidades(user_id, limite=limite)
        if not ops:
            return "Nenhuma oportunidade entregue ainda."
        return json.dumps(ops, ensure_ascii=False)

    @beta_tool
    def marcar_oportunidade(op_id: int, status: str) -> str:
        """Marca o resultado de uma oportunidade (feedback do usuário).

        Args:
            op_id: Número da oportunidade (#id).
            status: 'comprou', 'nao_qualificado', 'respondeu' ou 'sem_resposta'.
        """
        ok = storage.marcar_oportunidade(user_id, op_id, status)
        return "Atualizado." if ok else "Oportunidade não encontrada."

    tools = [salvar_produto, trocar_produto, salvar_nota, registrar_oportunidade,
             listar_oportunidades, marcar_oportunidade]

    if settings.apify_token:
        @beta_tool
        def apify_rodar(ator: str, entrada_json: str) -> str:
            """Roda um coletor da Apify em dados públicos. Custa dinheiro: use com limites baixos.

            Atores e exemplos de entrada:
            - instagram_comentarios: {"directUrls": ["https://www.instagram.com/reel/..."], "resultsLimit": 40}
            - instagram_posts: {"search": "caneta depiladora", "searchType": "hashtag", "resultsLimit": 20}
            - tiktok_comentarios: {"postURLs": ["https://www.tiktok.com/@x/video/..."], "commentsPerPost": 40}
            - tiktok_busca: {"searchQueries": ["caneta depiladora"], "resultsPerPage": 20}
            - biblioteca_anuncios: {"urls": [{"url": "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q=TERMO&search_type=keyword_unordered"}], "count": 30}
            - facebook_comentarios: {"startUrls": [{"url": "https://www.facebook.com/..."}], "resultsLimit": 40}

            Args:
                ator: Um dos apelidos acima.
                entrada_json: Objeto JSON de entrada do ator, como texto.
            """
            try:
                entrada = json.loads(entrada_json)
            except json.JSONDecodeError as e:
                return f"JSON inválido: {e}"
            return apify.rodar_ator(settings.apify_token, ator, entrada)

        tools.append(apify_rodar)
    return tools


def _texto_final(msg) -> str:
    if msg.stop_reason == "refusal":
        return "⚠️ Não consegui completar esse pedido. Tente reformular."
    partes = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
    texto = "\n".join(p for p in partes if p.strip()).strip()
    if msg.stop_reason == "pause_turn" and not texto:
        return "⏳ A busca ficou longa demais. Mande BUSCAR MAIS para continuar."
    return texto or "(sem resposta)"


class LeadHunter:
    def __init__(self, storage: Storage, client: anthropic.Anthropic | None = None):
        self.storage = storage
        self.client = client or anthropic.Anthropic(base_url=settings.base_url or None)
        # Modo compatível: sem recursos exclusivos da API oficial (busca da Anthropic,
        # fallbacks, cache). Usado em provedores como a KPA Labz.
        self.compat = settings.modo_compativel in ("sim", "1", "true")

    def _chamar(self, user_id: int, mensagens: list[dict]):
        comum = dict(
            model=settings.anthropic_model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=mensagens,
            max_iterations=40,
        )
        if self.compat:
            tools = _ferramentas_web() + _ferramentas(self.storage, user_id)
            return self.client.beta.messages.tool_runner(tools=tools, **comum).until_done()
        return self.client.beta.messages.tool_runner(
            tools=SERVER_TOOLS + _ferramentas(self.storage, user_id),
            thinking={"type": "adaptive"},
            output_config={"effort": settings.effort},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **comum,
        ).until_done()

    def responder(self, user_id: int, mensagem: str) -> str:
        hoje = datetime.now(ZoneInfo(settings.timezone)).strftime("%d/%m/%Y %H:%M (%A)")
        contexto = contexto_usuario(
            self.storage.obter_produto(user_id), self.storage.notas(user_id), hoje
        )
        mensagens = self.storage.historico(user_id) + [
            {"role": "user", "content": f"{contexto}\n\n{mensagem}"}
        ]

        try:
            try:
                final = self._chamar(user_id, mensagens)
            except anthropic.BadRequestError:
                pode_trocar = settings.modo_compativel == "auto" and settings.base_url
                if self.compat or not pode_trocar:
                    raise
                log.warning("Provedor recusou recursos da API oficial; ativando modo compatível.")
                self.compat = True
                final = self._chamar(user_id, mensagens)
        except anthropic.AuthenticationError:
            return "🔑 Chave da API inválida ou vencida. Confira ANTHROPIC_API_KEY."
        except anthropic.NotFoundError:
            return (f"⚠️ O provedor não tem o modelo '{settings.anthropic_model}'. "
                    "Troque a variável ANTHROPIC_MODEL (ex.: claude-sonnet-5-5).")
        except anthropic.RateLimitError:
            return "⏳ Limite de uso atingido. Tente de novo mais tarde."
        except anthropic.APIStatusError as e:
            log.exception("Erro da API Claude")
            return f"⚠️ Erro no serviço de IA ({e.status_code}). Tente de novo mais tarde."
        except anthropic.APIConnectionError:
            return "⚠️ Sem conexão com o serviço de IA. Tente de novo."

        resposta = _texto_final(final)
        # Histórico só com texto (barato e simples). Dados importantes ficam nas tabelas.
        self.storage.adicionar_historico(user_id, "user", mensagem)
        self.storage.adicionar_historico(user_id, "assistant", resposta)
        return resposta
