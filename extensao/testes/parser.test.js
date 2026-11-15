const assert = require("node:assert");
const { analisar } = require("../parser.js");

const exemplo = `🔎 **10 oportunidades verificadas: 7 no Instagram e 3 no Facebook.** Os sinais são de intenção.

#1 · Instagram Reels — @sonia_soarees · 92/100 · Intenção direta  
🔗 https://www.instagram.com/p/DflB-VRguIO/c/17879664798573081  
💬 “Que maravilha eu quero” (14/11/2026)  
✍️ Sugestão de resposta: Oi, Sonia! Vi que você se interessou pelo aspirador portátil. R$ 119,90 com frete grátis: https://pratikasa.vercel.app/migazero

#2 · Facebook — @monica.kohut.2025 · 98/100 · Pediu o link  
🔗 https://www.facebook.com/reel/2031045924249145/?comment_id=1596197501819232  
💬 “Manda o link do mz” (10/11/2026)  
✍️ Sugestão de resposta: Oi, Monica! O MigaZero é um aspirador portátil sem fio: https://pratikasa.vercel.app/migazero

#3 · Facebook — Talia Biasini · 98/100 · Pediu o link  
🔗 https://www.facebook.com/reel/2031045924249145/?comment_id=1774755707154460  
💬 “Manda o link do aspirador” (10/11/2026)  
✍️ Sugestão de resposta: Oi, Talia! Segue o link do MigaZero: https://pratikasa.vercel.app/migazero

📌 **Resumo de mercado**
- A demanda mais forte está em pedidos explícitos de link.

📎 **Relatório de execução:** Google e coletores públicos.`;

const itens = analisar(exemplo);
assert.strictEqual(itens.length, 3);
assert.deepStrictEqual(
  { n: itens[0].numero, u: itens[0].usuario, r: itens[0].rede, p: itens[0].perfil },
  { n: 1, u: "sonia_soarees", r: "instagram", p: "https://www.instagram.com/sonia_soarees/" });
assert.strictEqual(itens[0].link, "https://www.instagram.com/p/DflB-VRguIO/c/17879664798573081");
assert.ok(itens[0].sugestao.startsWith("Oi, Sonia!"));
assert.ok(itens[0].sugestao.endsWith("https://pratikasa.vercel.app/migazero"));
assert.strictEqual(itens[1].perfil, "https://www.facebook.com/monica.kohut.2025");
assert.strictEqual(itens[2].usuario, "");          // sem @: sem botão de perfil
assert.strictEqual(itens[2].perfil, "");
assert.ok(!itens[2].sugestao.includes("Resumo"), "não pode levar o resumo junto");
assert.strictEqual(itens[0].fala, "“Que maravilha eu quero” (14/11/2026)");
assert.deepStrictEqual(analisar("texto qualquer sem oportunidades"), []);
console.log("parser ok:", itens.length, "itens");

const { deServidor } = require("../parser.js");
const d = deServidor({ id: 7, link: "https://www.instagram.com/p/X/c/1", trecho: "Quero link",
  data: "11/11/2026", sinal: "Pediu o link", sugestao: "Oi!", usuario: "@laiany_alves" });
assert.strictEqual(d.perfil, "https://www.instagram.com/laiany_alves/");
assert.strictEqual(d.fala, "“Quero link” (11/11/2026)");
assert.strictEqual(d.numero, 7);
console.log("deServidor ok");
