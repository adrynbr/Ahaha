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
