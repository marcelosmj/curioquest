# Knowledge Item: Status da Restauração e Roadmap da v1.0

## Contexto
O projeto Curio Quest Revival tem o objetivo de ressuscitar o jogo mobile Curio Quest (Adobe AIR 3.4.3 sobre Android) utilizando um servidor offline local em Python 3 (`asyncio`) que emula o ElectroServer 5 e um CDN HTTP estático.

## Principais Marcos Atingidos
1. **Infraestrutura de Rede e Protocolo:** 96 tipos de mensagens ES5, 93 structs Thrift binárias, decodificação/codificação de EsObjects. CDN local na porta 8080 com extração direta de assets do APK oficial.
2. **Sistemas de Jogo Funcionais:** Criação de personagem, saves locais atômicos, gerenciamento de Curios, alocação de skills, subida de rank, Plinko simulado no servidor, roda de prêmios, tarefas diárias e 33 conquistas.
3. **Causa Raiz do Travamento de Batalha (T0):** Adobe AIR em Android oculta exceções não tratadas. O travamento no `LOADING...` ocorria em `MenuScreen.onEnterGame` porque `ServerPlugin.getRoom` recebia zona/sala nulas quando `JoinZoneEvent` era enviado sem a lista de salas populada de forma síncrona.
4. **Meta da v1.0:** Campanha single-player (Zonas 1 e 2) jogável do início ao fim com persistência de save e combate funcional.
