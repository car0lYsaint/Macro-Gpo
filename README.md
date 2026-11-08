# GPO Halloween Macro (Rare Fruit Chest)

Farm de portas do evento de Halloween do GPO + compra automática do Rare Fruit Chest.
O app **enxerga a tela**: detecta o aviso "Knock", lê o contador "N/500 Candies" e acha
o card do baú na loja. Tudo em código aberto, feito do zero.

## Instalação (Windows)
1. Instale o Python 3.10+ (marque "Add to PATH").
2. Na pasta do projeto: `pip install -r requirements.txt`
3. Rode: `python app.py`

## Primeiro uso (aba Setup)
1. **Capturar templates** (jogo na MESMA resolução/UI de sempre; botão "Capturar" dá 5 s
   para você deixar o jogo mostrando a coisa, depois arraste um retângulo sobre ela):
   - `knock`: já vem um exemplo para 1920x1080; recapture se o ✗ aparecer ou não detectar.
   - `shop_title`: título "Halloween Shop" com a loja aberta.
   - `rare_chest`: o card do Rare Fruit Chest (nome + preço).
   - `confirm` e `shop_close`: só se a compra pedir confirmação / se quiser fechar a loja pelo botão.
2. **Gravar rotas** (F4 liga/desliga a gravação, com o jogo em foco, câmera de cima):
   - `farm`: comece num ponto fixo, dê uma volta pelas casas e termine no MESMO ponto.
     Pare em frente a cada porta por um instante; o macro aperta E sozinho quando vê o "Knock".
   - `to_shop` / `from_shop`: opcionais (do fim da volta até a bruxa e de volta).
3. **Test buying**: fique perto da bruxa e clique; ele abre a loja e compra 1 baú.
4. Comece o farm com a cesta **desequipada**, no ponto inicial da rota. **F3** liga/desliga.

## Como funciona
Repete a volta gravada; a cada porta detectada, para, aperta E e confere os doces. No fim da
volta, se os doces >= "Comprar quando doces ≥", vai à bruxa e compra até o máx. de baús.

## Limitações conhecidas
- A rota é gravada (dead-reckoning): com lag ou mudança de câmera ela pode desviar. Se isso
  acontecer, reposicione no ponto inicial e reinicie.
- O fluxo exato de compra (clique no card, confirmação, fechar a loja) depende da interface
  real; use o Test buying e capture `confirm`/`shop_close` se necessário.
- Macros podem violar as regras do jogo/Roblox: use por sua conta e risco (de preferência em conta secundária).
