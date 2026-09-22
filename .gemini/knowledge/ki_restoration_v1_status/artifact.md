# Knowledge Item: Status da Restauração e Roadmap da v1.0

## Contexto
O projeto Curio Quest Revival tem o objetivo de ressuscitar o jogo mobile Curio Quest (Adobe AIR 3.4.3 sobre Android) utilizando um servidor offline local em Python 3 (`asyncio`) que emula o ElectroServer 5 e um CDN HTTP estático.

## Principais Marcos Atingidos
1. **Infraestrutura de Rede e Protocolo:** 96 tipos de mensagens ES5, 93 structs Thrift binárias, decodificação/codificação de EsObjects. CDN local na porta 8080 com extração direta de assets do APK oficial.
2. **Sistemas de Jogo Funcionais:** Criação de personagem, saves locais atômicos, gerenciamento de Curios, alocação de skills, subida de rank, Plinko simulado no servidor, roda de prêmios, tarefas diárias e 33 conquistas.
3. **Causa Raiz do Travamento de Batalha (RESOLVIDO):** O travamento no `LOADING...` em `MenuScreen.onEnterGame` era provocado por uma exceção `TypeError #1009 (NullPointerException)` no ActionScript 3 em `BattlePlayer.as:397` (`this._battleScreen.petContainer.addChild`). O erro acontecia porque o servidor enviava `BATTLE_CURRENT_PET_INDEX = 0` no payload `ENTER_BATTLE`, fazendo `BattlePlayer.fromEsObject` chamar `setCurrentPet` antes do `BattleScreen` ser instanciado (`this._battleScreen` era nulo). A solução foi enviar `BATTLE_CURRENT_PET_INDEX = -1` no `ENTER_BATTLE` e despachar a entrada dos Curios na arena via mensagens legítimas `SELECT_PET` do `BattlePlugin`.
4. **Combate Validado de Ponta a Ponta (100% Êxito):** Validado com `tools/test_battle_flow.py` cobrindo room join, entrada de batalha, turnos de habilidade do jogador, resposta da IA, cálculo de dano elemental, vitória, premiação (ouro/xp/itens) e gravação de save atômico no disco.
5. **Meta da v1.0 Atingida:** Campanha jogável com combate ativo e persistência total.
