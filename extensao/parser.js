// Lê a resposta do CAÇAR CLIENTES (copiada do Telegram) e separa as oportunidades.
// Usado pelo popup e pelos testes (node).
(function (raiz) {
  function limpar(t) {
    return t.replace(/\*\*/g, "").replace(/__/g, "").trim();
  }

  function analisar(texto) {
    const t = texto.replace(/\r/g, "");
    // Cada oportunidade começa com "#N ·" no início da linha.
    const partes = t.split(/\n(?=\s*\**#\d+\s*·)/);
    const itens = [];
    for (const parte of partes) {
      const cab = parte.match(/^\s*\**#(\d+)\s*·([^\n]*)/);
      if (!cab) continue;
      const link = (parte.match(/🔗\s*(https?:\/\/\S+)/) || [])[1];
      if (!link) continue;
      const fala = (parte.match(/💬\s*([^\n]+)/) || [])[1] || "";
      let sugestao = "";
      const s = parte.match(/✍️\s*(?:\**\s*Sugest[aã]o de resposta:?\s*\**)?\s*([\s\S]*)/i);
      if (s) {
        // Para no resumo de mercado / relatório, se vierem colados no último item.
        sugestao = s[1].split(/\n\s*(?:📌|📎|📩)/)[0];
      }
      const usuario = (cab[2].match(/@([A-Za-z0-9._]+)/) || [])[1] || "";
      let rede = "outro";
      if (/instagram\.com/.test(link)) rede = "instagram";
      else if (/facebook\.com|fb\.com/.test(link)) rede = "facebook";
      else if (/tiktok\.com/.test(link)) rede = "tiktok";
      else if (/(^|\.)x\.com|twitter\.com/.test(link)) rede = "x";
      let perfil = "";
      if (usuario && rede === "instagram") perfil = "https://www.instagram.com/" + usuario + "/";
      else if (usuario && rede === "facebook") perfil = "https://www.facebook.com/" + usuario;
      else if (usuario && rede === "tiktok") perfil = "https://www.tiktok.com/@" + usuario;
      itens.push({
        numero: Number(cab[1]),
        titulo: limpar(cab[2]).replace(/^[\s·]+/, ""),
        link: link.replace(/[)\].,]+$/, ""),
        fala: limpar(fala),
        sugestao: limpar(sugestao),
        usuario,
        rede,
        perfil,
      });
    }
    return itens;
  }

  // Converte uma oportunidade vinda do servidor do bot para o formato do cartão.
  function deServidor(o) {
    const link = o.link || "";
    const usuario = (o.usuario || "").replace(/^@/, "");
    let rede = "outro";
    if (/instagram\.com/.test(link)) rede = "instagram";
    else if (/facebook\.com|fb\.com/.test(link)) rede = "facebook";
    else if (/tiktok\.com/.test(link)) rede = "tiktok";
    else if (/(^|\.)x\.com|twitter\.com/.test(link)) rede = "x";
    let perfil = "";
    if (usuario && rede === "instagram") perfil = "https://www.instagram.com/" + usuario + "/";
    else if (usuario && rede === "facebook") perfil = "https://www.facebook.com/" + usuario;
    else if (usuario && rede === "tiktok") perfil = "https://www.tiktok.com/@" + usuario;
    const data = o.data && o.data !== "não verificada" ? " (" + o.data + ")" : "";
    return {
      id: o.id, numero: o.id, titulo: o.sinal || "", link,
      fala: o.trecho ? "“" + o.trecho + "”" + data : "",
      sugestao: o.sugestao || "", usuario, rede, perfil,
    };
  }

  raiz.LeadHunterParser = { analisar, deServidor };
  if (typeof module !== "undefined") module.exports = { analisar, deServidor };
})(typeof self !== "undefined" ? self : globalThis);
