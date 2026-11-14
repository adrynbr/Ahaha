// Abre cada oportunidade numa aba e lembra qual mensagem pertence a qual aba.
chrome.runtime.onMessage.addListener((msg, sender, responder) => {
  if (msg.tipo === "abrir") {
    (async () => {
      for (const item of msg.itens) {
        const aba = await chrome.tabs.create({ url: item.link, active: false });
        await chrome.storage.session.set({ ["aba_" + aba.id]: item });
      }
      responder({ ok: true });
    })();
    return true;
  }
  if (msg.tipo === "meu_item" && sender.tab) {
    chrome.storage.session.get("aba_" + sender.tab.id).then((r) => responder(r["aba_" + sender.tab.id] || null));
    return true;
  }
});

chrome.tabs.onRemoved.addListener((id) => chrome.storage.session.remove("aba_" + id));
