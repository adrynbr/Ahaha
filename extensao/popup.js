const $ = (id) => document.getElementById(id);
let itens = [];

function mostrar() {
  $("lista").innerHTML = "";
  for (const it of itens) {
    const li = document.createElement("li");
    li.textContent = `#${it.numero} ${it.rede} ${it.usuario ? "@" + it.usuario : ""} — ${it.fala.slice(0, 50)}`;
    $("lista").appendChild(li);
  }
  $("abrir").disabled = itens.length === 0;
  $("abrir").textContent = itens.length ? `Abrir abas (${itens.length} encontradas)` : "Abrir abas";
}

$("ler").onclick = () => {
  itens = LeadHunterParser.analisar($("texto").value);
  if (!itens.length) {
    $("lista").innerHTML = "<li>Nenhuma oportunidade encontrada. Cole a resposta inteira do bot.</li>";
  }
  chrome.storage.local.set({ texto: $("texto").value });
  mostrar();
};

$("abrir").onclick = async () => {
  const max = Math.max(1, Math.min(10, Number($("max").value) || 5));
  const lote = itens.slice(0, max);
  await chrome.runtime.sendMessage({ tipo: "abrir", itens: lote });
  itens = itens.slice(max);
  mostrar();
};

$("limpar").onclick = () => {
  $("texto").value = "";
  itens = [];
  chrome.storage.local.remove("texto");
  mostrar();
};

chrome.storage.local.get("texto").then(({ texto }) => {
  if (texto) { $("texto").value = texto; itens = LeadHunterParser.analisar(texto); mostrar(); }
});


// --- Conexão com o bot ---
async function atualizarEstado() {
  const { url, codigo, ultimoContato, erro, leitura = true, leituras = 0 } =
    await chrome.storage.local.get(["url", "codigo", "ultimoContato", "erro", "leitura", "leituras"]);
  $("leitura").checked = leitura;
  $("leituras").textContent = leituras ? `Páginas lidas para o bot: ${leituras}` : "";
  $("url").value = url || "";
  $("codigo").value = codigo || "";
  if (!url || !codigo) { $("estado").textContent = "⚪ desconectada"; $("conexao").open = true; return; }
  $("estado").textContent = erro ? "🔴 erro" : "🟢 conectada";
  $("msgConexao").textContent = erro ? erro :
    (ultimoContato ? "Último contato: " + new Date(ultimoContato).toLocaleTimeString() : "Aguardando primeiro contato…");
}

$("leitura").onchange = () => chrome.storage.local.set({ leitura: $("leitura").checked });

$("salvar").onclick = async () => {
  await chrome.storage.local.set({ url: $("url").value.trim(), codigo: $("codigo").value.trim(), erro: "" });
  $("msgConexao").textContent = "Testando…";
  const r = await chrome.runtime.sendMessage({ tipo: "testar" });
  if (r.ok) {
    await chrome.storage.local.set({ ultimoContato: Date.now() });
    $("msgConexao").textContent = `✅ Conectada! ${r.pendentes} oportunidade(s) esperando.`;
    $("estado").textContent = "🟢 conectada";
  } else {
    $("msgConexao").textContent = "❌ " + r.erro;
    $("estado").textContent = "🔴 erro";
  }
};

$("buscar").onclick = async () => {
  const max = Math.max(1, Math.min(10, Number($("max").value) || 5));
  $("buscar").disabled = true;
  const r = await chrome.runtime.sendMessage({ tipo: "buscar_do_bot", limite: max });
  $("buscar").disabled = false;
  $("lista").innerHTML = "";
  const li = document.createElement("li");
  li.textContent = r.ok ? (r.n ? `Abri ${r.n} aba(s).` : "Nada novo no bot. Toque em CAÇAR CLIENTES no Telegram.")
                        : "❌ " + r.erro;
  $("lista").appendChild(li);
};

atualizarEstado();
