importScripts("parser.js");

// Abre cada oportunidade numa aba e lembra qual mensagem pertence a qual aba.
async function abrir(itens) {
  for (const item of itens) {
    const aba = await chrome.tabs.create({ url: item.link, active: false });
    await chrome.storage.session.set({ ["aba_" + aba.id]: item });
  }
}

async function config() {
  const { url, codigo } = await chrome.storage.local.get(["url", "codigo"]);
  return url && codigo ? { url: url.replace(/\/+$/, ""), codigo } : null;
}

async function api(caminho, opcoes = {}) {
  const c = await config();
  if (!c) throw new Error("Extensão não conectada.");
  const r = await fetch(c.url + caminho, {
    ...opcoes,
    headers: { Authorization: "Bearer " + c.codigo, "Content-Type": "application/json" },
  });
  if (!r.ok) throw new Error(r.status === 401 ? "Código inválido: gere outro com /conectar." : "Erro " + r.status);
  return r.json();
}

// Verifica se o bot pediu para abrir (botão ABRIR NA EXTENSÃO no Telegram).
async function verificarAbertura() {
  const r = await api("/api/extensao/pendente");
  await chrome.storage.local.set({ ultimoContato: Date.now(), erro: "" });
  if (r.abrir && r.itens.length) {
    await abrir(r.itens.map(LeadHunterParser.deServidor));
    await api("/api/extensao/confirmar", { method: "POST", body: JSON.stringify({ ids: r.itens.map((i) => i.id) }) });
  }
}

// --- Leitura de páginas pedida pelo agente (como a "Superagent") ---------------------------
// O bot pede uma URL; a extensão abre numa aba em segundo plano, rola os comentários,
// copia o TEXTO da página e fecha a aba. Só lê: não clica em curtir, não comenta, não envia.

const ESPERA_CARREGAR = 25000;

function esperarCarregar(abaId) {
  return new Promise((ok) => {
    const fim = setTimeout(() => { chrome.tabs.onUpdated.removeListener(ouvir); ok(); }, ESPERA_CARREGAR);
    function ouvir(id, info) {
      if (id === abaId && info.status === "complete") {
        clearTimeout(fim);
        chrome.tabs.onUpdated.removeListener(ouvir);
        ok();
      }
    }
    chrome.tabs.onUpdated.addListener(ouvir);
  });
}

// Roda DENTRO da página: rola a página e as áreas de comentários e devolve o texto visível.
async function lerPaginaNaAba() {
  const pausa = (ms) => new Promise((r) => setTimeout(r, ms));
  await pausa(2500);
  for (let i = 0; i < 5; i++) {
    window.scrollBy(0, 1200);
    for (const el of document.querySelectorAll("div, section, ul")) {
      const st = getComputedStyle(el);
      if (el.scrollHeight > el.clientHeight + 80 && /(auto|scroll)/.test(st.overflowY)) el.scrollTop += 1500;
    }
    await pausa(1300);
  }
  const texto = (document.body ? document.body.innerText : "").replace(/\n{3,}/g, "\n\n");
  return "URL: " + location.href + "\nTítulo: " + document.title + "\n\n" + texto.slice(0, 30000);
}

async function lerTarefa(t) {
  let aba;
  try {
    aba = await chrome.tabs.create({ url: t.url, active: false });
    await esperarCarregar(aba.id);
    const [res] = await chrome.scripting.executeScript({ target: { tabId: aba.id }, func: lerPaginaNaAba });
    await api("/api/extensao/tarefa/" + t.id, { method: "POST", body: JSON.stringify({ texto: (res && res.result) || "" }) });
    const { leituras = 0 } = await chrome.storage.local.get("leituras");
    await chrome.storage.local.set({ leituras: leituras + 1 });
  } catch (e) {
    await api("/api/extensao/tarefa/" + t.id, { method: "POST", body: JSON.stringify({ erro: String(e.message || e) }) }).catch(() => {});
  } finally {
    if (aba) chrome.tabs.remove(aba.id).catch(() => {});
  }
}

async function verificarLeituras() {
  const { leitura = true } = await chrome.storage.local.get("leitura");
  const r = await api("/api/extensao/tarefas?leitura=" + (leitura ? 1 : 0));
  for (const t of r.tarefas || []) await lerTarefa(t);
  return (r.tarefas || []).length;
}

// O alarme dispara a cada 30 s; dentro dele consultamos o bot a cada 4 s por ~25 s,
// para o agente não esperar muito pelas leituras.
let rodando = false;
async function verificar() {
  if (rodando || !(await config())) return;
  rodando = true;
  try {
    const fim = Date.now() + 25000;
    await verificarAbertura();
    while (Date.now() < fim) {
      const n = await verificarLeituras();
      if (!n) await new Promise((r) => setTimeout(r, 4000));
    }
  } catch (e) {
    await chrome.storage.local.set({ erro: String(e.message || e) });
  } finally {
    rodando = false;
  }
}

chrome.runtime.onInstalled.addListener(() => chrome.alarms.create("verificar", { periodInMinutes: 0.5 }));
chrome.runtime.onStartup.addListener(() => chrome.alarms.create("verificar", { periodInMinutes: 0.5 }));
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "verificar") verificar(); });

chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  if (msg.tipo === "abrir") {
    abrir(msg.itens).then(() => responder({ ok: true }));
    return true;
  }
  if (msg.tipo === "buscar_do_bot") {
    (async () => {
      try {
        const r = await api("/api/extensao/oportunidades?limite=" + (msg.limite || 5));
        const itens = r.itens.map(LeadHunterParser.deServidor);
        await abrir(itens);
        if (r.itens.length) {
          await api("/api/extensao/confirmar", { method: "POST", body: JSON.stringify({ ids: r.itens.map((i) => i.id) }) });
        }
        responder({ ok: true, n: itens.length });
      } catch (e) {
        responder({ ok: false, erro: String(e.message || e) });
      }
    })();
    return true;
  }
  if (msg.tipo === "testar") {
    api("/api/extensao/status").then((r) => responder({ ok: true, ...r }))
      .catch((e) => responder({ ok: false, erro: String(e.message || e) }));
    return true;
  }
  if (msg.tipo === "meu_item" && sender.tab) {
    chrome.storage.session.get("aba_" + sender.tab.id).then((r) => responder(r["aba_" + sender.tab.id] || null));
    return true;
  }
});

chrome.tabs.onRemoved.addListener((id) => chrome.storage.session.remove("aba_" + id));
