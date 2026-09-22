# Pendências conhecidas — servidor Curio Quest

Registrado em 2026-09-18, ao fechar a rodada de mecânicas.

## Risco latente: BUY_SERVICE cobra as duas moedas

`MerchantDALC.doBuyService` envia `CURRENCY_ID`, igual ao `doPurchaseItem`, mas o handler
em `server/game/dalcs/merchant.py` chama `_charge(service.cost_gold, service.cost_credits)`
somando as duas parcelas.

**Hoje não tem efeito:** dos 10 serviços autorados, nove custam só plasma e um só ouro, então
uma das parcelas é sempre zero e a soma dá no mesmo. **Passa a ter efeito** no instante em que
alguém autorar um serviço com preço em ouro *e* plasma — ele ficará impossível de comprar, do
mesmo modo que os curios raros ficaram antes da correção de 18/09.

Correção: aplicar em `buy_service` a mesma lógica já usada em `purchase_item` (honrar
`CURRENCY_ID`, com fallback para a moeda em que o item está realmente precificado).

## Bloqueio: tela de batalha trava no aparelho

Depois do `ENTER_BATTLE` o cliente fica no carregamento. 15 hipóteses eliminadas com evidência.
O próximo passo é instrumentar o `Pets.swf` com JPEXS — que **não está instalado nesta máquina**.

## Não implementado: PvP, clubes, eventos, chat, placar

Cinco famílias de DALC, ~85 ações, cinco livros vazios. Não é dívida técnica: nada do conteúdo
original sobreviveu, então é desenho de jogo do zero.
