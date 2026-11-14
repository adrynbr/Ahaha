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
async function verificar() {
  if (!(await config())) return;
  try {
    const r = await api("/api/extensao/pendente");
    await chrome.storage.local.set({ ultimoContato: Date.now(), erro: "" });
    if (r.abrir && r.itens.length) {
      await abrir(r.itens.map(LeadHunterParser.deServidor));
      await api("/api/extensao/confirmar", { method: "POST", body: JSON.stringify({ ids: r.itens.map((i) => i.id) }) });
    }
  } catch (e) {
    await chrome.storage.local.set({ erro: String(e.message || e) });
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
