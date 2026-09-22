# Pendências conhecidas — servidor Curio Quest

Registrado em 2026-09-18, ao fechar a rodada de mecânicas.

## [RESOLVIDO] Risco latente: BUY_SERVICE cobra as duas moedas

- **Resolvido em 22/09/2026:** Em `server/game/dalcs/merchant.py`, a função `buy_service` foi atualizada para respeitar `CURRENCY_ID` e a precificação individual do serviço (ouro ou plasma), sem somar indevidamente ambas as parcelas. Testado e validado.

## Bloqueio: tela de batalha trava no aparelho

Depois do `ENTER_BATTLE` o cliente fica no carregamento. 15 hipóteses eliminadas com evidência.
O próximo passo é instrumentar o `Pets.swf` com JPEXS — que **não está instalado nesta máquina**.

## Não implementado: PvP, clubes, eventos, chat, placar

Cinco famílias de DALC, ~85 ações, cinco livros vazios. Não é dívida técnica: nada do conteúdo
original sobreviveu, então é desenho de jogo do zero.
