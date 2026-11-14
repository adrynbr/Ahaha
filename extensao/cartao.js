// Mostra um cartão flutuante com a mensagem pronta na aba aberta pela extensão.
// Não envia nada: só copia ou cola o texto na caixa, e você aperta enviar.
(async () => {
  let item;
  try { item = await chrome.runtime.sendMessage({ tipo: "meu_item" }); } catch (e) { return; }
  if (!item || document.getElementById("leadhunter-cartao")) return;

  const caixa = document.createElement("div");
  caixa.id = "leadhunter-cartao";
  caixa.attachShadow({ mode: "open" }).innerHTML = `
    <style>
      .c { position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; width: 340px;
           background: #111; color: #eee; border-radius: 12px; padding: 12px; font: 13px system-ui, sans-serif;
           box-shadow: 0 8px 30px rgba(0,0,0,.4); }
      .t { font-weight: 700; margin-bottom: 4px; }
      .f { color: #aaa; font-style: italic; margin-bottom: 8px; }
      textarea { width: 100%; box-sizing: border-box; height: 110px; background: #1d1d1d; color: #eee;
                 border: 1px solid #333; border-radius: 8px; padding: 6px; font: 12px system-ui; }
      .b { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
      button { flex: 1; padding: 8px; border: 0; border-radius: 8px; background: #2f6df6; color: #fff;
               font-weight: 600; cursor: pointer; font-size: 12px; }
      button.s { background: #2a2a2a; }
      .ok { color: #6ee7a8; font-size: 12px; margin-top: 6px; min-height: 14px; }
    </style>
    <div class="c">
      <div class="t">#${item.numero} · ${item.usuario ? "@" + item.usuario : item.rede}</div>
      <div class="f"></div>
      <textarea></textarea>
      <div class="b">
        <button id="copiar">Copiar</button>
        <button id="colar">Colar na caixa</button>
        ${item.perfil ? '<button id="perfil" class="s">Abrir perfil (DM)</button>' : ""}
        <button id="fechar" class="s">✕</button>
      </div>
      <div class="ok"></div>
    </div>`;
  const r = caixa.shadowRoot;
  r.querySelector(".f").textContent = item.fala ? `“${item.fala.replace(/^[“"]|[”"]$/g, "")}”` : "";
  r.querySelector("textarea").value = item.sugestao;
  const aviso = (t) => { r.querySelector(".ok").textContent = t; };
  const texto = () => r.querySelector("textarea").value;

  r.getElementById("copiar").onclick = async () => {
    await navigator.clipboard.writeText(texto());
    aviso("Copiado! Cole na resposta ou na DM e envie.");
  };

  r.getElementById("colar").onclick = async () => {
    // Procura a caixa de comentário/resposta visível da página.
    const alvos = [...document.querySelectorAll(
      'textarea, [contenteditable="true"][role="textbox"], div[contenteditable="true"]'
    )].filter((el) => el.offsetParent !== null && !caixa.contains(el));
    const alvo = alvos[0];
    if (!alvo) {
      await navigator.clipboard.writeText(texto());
      aviso("Não achei a caixa. Clique em 'Responder' no comentário e cole (já copiei).");
      return;
    }
    alvo.focus();
    const ok = document.execCommand("insertText", false, texto());
    if (!ok) {
      await navigator.clipboard.writeText(texto());
      aviso("Copiei o texto: clique na caixa e cole.");
    } else {
      aviso("Texto colocado na caixa. Revise e envie você mesmo.");
    }
  };

  const perfil = r.getElementById("perfil");
  if (perfil) perfil.onclick = async () => {
    await navigator.clipboard.writeText(texto());
    window.open(item.perfil, "_blank");
    aviso("Texto copiado. No perfil, toque em 'Enviar mensagem' e cole.");
  };

  r.getElementById("fechar").onclick = () => caixa.remove();
  document.documentElement.appendChild(caixa);
})();
