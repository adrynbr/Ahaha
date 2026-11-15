"""Memória por usuário em SQLite: produto, histórico curto, oportunidades entregues."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    user_id INTEGER PRIMARY KEY,
    dados TEXT NOT NULL,
    atualizado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    texto TEXT NOT NULL,
    criado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oportunidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chave TEXT NOT NULL,
    dados TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'entregue',
    criado TEXT NOT NULL,
    UNIQUE(user_id, chave)
);
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    papel TEXT NOT NULL,
    texto TEXT NOT NULL,
    criado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config_usuario (
    user_id INTEGER PRIMARY KEY,
    digest INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS extensao (
    user_id INTEGER PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    pedido INTEGER
);
CREATE TABLE IF NOT EXISTS respostas_auto (
    comment_id TEXT PRIMARY KEY,
    criado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rotinas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    hora INTEGER NOT NULL,
    minuto INTEGER NOT NULL DEFAULT 0,
    pedido TEXT NOT NULL,
    ultimo TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tarefas_navegador (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'nova',
    resultado TEXT NOT NULL DEFAULT '',
    criado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS extensao_visto (
    user_id INTEGER PRIMARY KEY,
    visto REAL NOT NULL,
    leitura INTEGER NOT NULL DEFAULT 1
);
"""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def chave_oportunidade(link: str, trecho: str = "") -> str:
    """O link do comentário identifica a oportunidade (o mesmo link não é entregue duas vezes)."""
    base = link.strip().lower().rstrip("/")
    return hashlib.sha256(base.encode()).hexdigest()[:32]


class Storage:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    # --- produto ---
    def salvar_produto(self, user_id: int, dados: dict) -> None:
        atual = self.obter_produto(user_id) or {}
        atual.update({k: v for k, v in dados.items() if v not in (None, "")})
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO produtos(user_id, dados, atualizado) VALUES (?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET dados=excluded.dados, atualizado=excluded.atualizado",
                (user_id, json.dumps(atual, ensure_ascii=False), _agora()),
            )

    def obter_produto(self, user_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT dados FROM produtos WHERE user_id=?", (user_id,)
        ).fetchone()
        return json.loads(row["dados"]) if row else None

    def apagar_produto(self, user_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM produtos WHERE user_id=?", (user_id,))

    def usuarios_com_produto(self) -> list[int]:
        rows = self._conn.execute(
            "SELECT p.user_id FROM produtos p LEFT JOIN config_usuario c "
            "ON c.user_id=p.user_id WHERE COALESCE(c.digest,1)=1"
        ).fetchall()
        return [r["user_id"] for r in rows]

    def definir_digest(self, user_id: int, ligado: bool) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO config_usuario(user_id, digest) VALUES (?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET digest=excluded.digest",
                (user_id, int(ligado)),
            )

    # --- notas (preferências, feedback) ---
    def salvar_nota(self, user_id: int, texto: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO notas(user_id, texto, criado) VALUES (?,?,?)",
                (user_id, texto, _agora()),
            )

    def notas(self, user_id: int, limite: int = 30) -> list[str]:
        rows = self._conn.execute(
            "SELECT texto FROM notas WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limite),
        ).fetchall()
        return [r["texto"] for r in reversed(rows)]

    # --- oportunidades ---
    def registrar_oportunidade(self, user_id: int, dados: dict) -> bool:
        """Retorna False se já tinha sido entregue (duplicada)."""
        chave = chave_oportunidade(dados.get("link", ""), dados.get("trecho", ""))
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO oportunidades(user_id, chave, dados, criado) VALUES (?,?,?,?)",
                (user_id, chave, json.dumps(dados, ensure_ascii=False), _agora()),
            )
        return cur.rowcount == 1

    def oportunidades(self, user_id: int, limite: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, dados, status, criado FROM oportunidades WHERE user_id=? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, limite),
        ).fetchall()
        return [
            {"id": r["id"], "status": r["status"], "criado": r["criado"], **json.loads(r["dados"])}
            for r in rows
        ]

    def marcar_oportunidade(self, user_id: int, op_id: int, status: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE oportunidades SET status=? WHERE id=? AND user_id=?",
                (status, op_id, user_id),
            )
        return cur.rowcount == 1

    def oportunidades_pendentes(self, user_id: int, limite: int = 10) -> list[dict]:
        """Entregues no chat e ainda não abertas na extensão (mais recentes primeiro)."""
        return [o for o in self.oportunidades(user_id, limite=200) if o["status"] == "entregue"][:limite]

    def marcar_varias(self, user_id: int, ids: list[int], status: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.executemany(
                "UPDATE oportunidades SET status=? WHERE id=? AND user_id=?",
                [(status, i, user_id) for i in ids],
            )
        return cur.rowcount

    # --- ponte com a extensão do Chrome ---
    def gerar_token_extensao(self, user_id: int) -> str:
        token = secrets.token_urlsafe(18)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO extensao(user_id, token) VALUES (?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET token=excluded.token",
                (user_id, token),
            )
        return token

    def usuario_do_token(self, token: str) -> int | None:
        if not token:
            return None
        row = self._conn.execute("SELECT user_id FROM extensao WHERE token=?", (token,)).fetchone()
        return row["user_id"] if row else None

    def extensao_conectada(self, user_id: int) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM extensao WHERE user_id=?", (user_id,)).fetchone() is not None

    def pedir_abertura(self, user_id: int, limite: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE extensao SET pedido=? WHERE user_id=?", (limite, user_id))

    def pedido_abertura(self, user_id: int) -> int | None:
        row = self._conn.execute("SELECT pedido FROM extensao WHERE user_id=?", (user_id,)).fetchone()
        return row["pedido"] if row else None

    def limpar_pedido(self, user_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE extensao SET pedido=NULL WHERE user_id=?", (user_id,))

    # --- extensão lendo páginas no navegador do usuário (já logado) ---
    def registrar_visto(self, user_id: int, leitura: bool = True) -> None:
        """A extensão acabou de falar com o bot (e se permite leituras)."""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO extensao_visto(user_id, visto, leitura) VALUES (?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET visto=excluded.visto, leitura=excluded.leitura",
                (user_id, time.time(), int(leitura)),
            )

    def extensao_online(self, user_id: int, janela: float = 180) -> bool:
        """Extensão falou com o bot nos últimos `janela` segundos e permite leituras."""
        row = self._conn.execute(
            "SELECT visto, leitura FROM extensao_visto WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["leitura"] and time.time() - row["visto"] <= janela)

    def criar_tarefa_navegador(self, user_id: int, url: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO tarefas_navegador(user_id, url, criado) VALUES (?,?,?)",
                (user_id, url, _agora()),
            )
        return cur.lastrowid

    def pegar_tarefas_navegador(self, user_id: int, limite: int = 3) -> list[dict]:
        """Entrega as tarefas novas à extensão e marca como 'lendo'."""
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT id, url FROM tarefas_navegador WHERE user_id=? AND status='nova' "
                "ORDER BY id LIMIT ?", (user_id, limite)).fetchall()
            self._conn.executemany("UPDATE tarefas_navegador SET status='lendo' WHERE id=?",
                                   [(r["id"],) for r in rows])
        return [{"id": r["id"], "url": r["url"]} for r in rows]

    def concluir_tarefa_navegador(self, user_id: int, tarefa_id: int, resultado: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE tarefas_navegador SET status='feita', resultado=? WHERE id=? AND user_id=?",
                (resultado, tarefa_id, user_id),
            )
        return cur.rowcount == 1

    def tarefa_navegador(self, tarefa_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT status, resultado FROM tarefas_navegador WHERE id=?", (tarefa_id,)).fetchone()
        return dict(row) if row else None

    def cancelar_tarefa_navegador(self, tarefa_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE tarefas_navegador SET status='expirada' WHERE id=? AND status!='feita'",
                (tarefa_id,))

    # --- rotinas diárias ("fluxos de trabalho") ---
    def criar_rotina(self, user_id: int, hora: int, minuto: int, pedido: str, hoje: str,
                     ja_passou: bool) -> int:
        """Cria rotina diária. Se o horário de hoje já passou, ela começa amanhã."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO rotinas(user_id, hora, minuto, pedido, ultimo) VALUES (?,?,?,?,?)",
                (user_id, hora, minuto, pedido, hoje if ja_passou else ""),
            )
        return cur.lastrowid

    def rotinas(self, user_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, hora, minuto, pedido FROM rotinas WHERE user_id=? ORDER BY hora, minuto",
            (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def apagar_rotina(self, user_id: int, rotina_id: int) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM rotinas WHERE id=? AND user_id=?",
                                     (rotina_id, user_id))
        return cur.rowcount == 1

    def rotinas_vencidas(self, hoje: str, hora: int, minuto: int) -> list[dict]:
        """Rotinas cujo horário de hoje já chegou e que ainda não rodaram hoje. Marca como rodadas."""
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT id, user_id, pedido FROM rotinas WHERE ultimo!=? AND (hora<? OR (hora=? AND minuto<=?))",
                (hoje, hora, hora, minuto)).fetchall()
            self._conn.executemany("UPDATE rotinas SET ultimo=? WHERE id=?",
                                   [(hoje, r["id"]) for r in rows])
        return [dict(r) for r in rows]

    # --- histórico curto de conversa ---
    def adicionar_historico(self, user_id: int, papel: str, texto: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO historico(user_id, papel, texto, criado) VALUES (?,?,?,?)",
                (user_id, papel, texto, _agora()),
            )

    def historico(self, user_id: int, limite: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT papel, texto FROM historico WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limite),
        ).fetchall()
        return [{"role": r["papel"], "content": r["texto"]} for r in reversed(rows)]

    def limpar_historico(self, user_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM historico WHERE user_id=?", (user_id,))

    # --- deduplicação das respostas automáticas (comente QUERO) ---
    def marcar_resposta_auto(self, comment_id: str) -> bool:
        """Retorna False se esse comentário já foi respondido."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO respostas_auto(comment_id, criado) VALUES (?,?)",
                (comment_id, _agora()),
            )
        return cur.rowcount == 1
