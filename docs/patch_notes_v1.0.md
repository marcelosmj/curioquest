# Curio Quest Revival — Relatório de Restauração & Patch Notes v1.0

**Data:** 22 de setembro de 2026  
**Status do Projeto:** Fase Final de Desbloqueio da Campanha (Tier 0)  
**Ambiente Alvo:** Android (Xiaomi Redmi Note 11S - Adobe AIR 3.4.3 ARMv7)  

---

## 1. Patch Notes: Tudo o que Foi Restaurado e Construído

### 🌐 Rede e Infraestrutura (100% Autoral)
- **Servidor ElectroServer 5 Binário em Python (`asyncio`):**
  - Reversão completa do protocolo proprietário ES5 sobre TCP.
  - Implementação de 96 tipos de mensagem e 93 structs Apache Thrift (`TBinaryProtocol`).
  - Suporte ao formato de serialização `EsObject` (chaves compactas + identificadores de tipos).
  - Tratamento de handshake de política Flash/AIR (`crossdomain.xml` terminado em `\0`).
  - Resolução de envelopes DALC com sinalizador `roomLevelPlugin = False` para compatibilidade com o `ServerPlugin` do cliente.
- **CDN HTTP Local Integrado (Porta 8080):**
  - Roteamento dinâmico de `Server.xml` (apontando o cliente para o IP/porta do ElectroServer).
  - Extração em tempo de execução de assets a partir do APK original (`Curio Quest_1.15.00.apk`), eliminando dependência de servidores mortos da 5th Planet Games.
  - Sistema de aliases (`asset_aliases.json`) para mapeamento de imagens e SWFs.
- **Conectividade Persistente via ADB:**
  - Daemon em background monitorando túneis reversos `tcp:8080` e `tcp:9899`, impedindo encerramento de portas pelo Windows Job Objects.

### 🎮 Sistemas de Jogo (DALCs & Engine)
- **Personagem e Save Game (`player.py` / `CharacterDALC`):**
  - Criação de avatar, seleção de gênero, persistência atômica em JSON (`server/saves/`).
  - Sistema de recarga periódica de energia e fichas (`refill`), cálculo de atributos de combate com bônus de consumíveis.
  - Curva de XP de jogador e de Curios até o teto de nível.
- **Campanha e Zonas (`game.py` / `ZoneBook` / `Zone1.xml` / `Zone2.xml`):**
  - 25 livros XML reconstruídos e validados contra os assets do APK.
  - Renderização do mapa de nós no aparelho físico, nós bloqueados/desbloqueados, requisitos de energia e diálogos de história (`DialogBook`).
  - Suporte a nós repetíveis com batalhas de saúde progressiva (`getCurrentBattleRef`).
- **Motor de Combate por Turnos (`battle.py`):**
  - Simulação completa do combate 1v1 Curio contra Curio.
  - Sistema de habilidades, cálculo de custos de mana/vida, buffs ativos (`ActiveBuff`) e cooldowns.
  - IA de oponentes selvagens calibrada com base nos dados preservados da wiki.
  - Distribuição de recompensas de combate: Ouro, Experiência de Curio, XP de Jogador e DNA.
- **Loja e Serviços (`merchant.py` / `MerchantDALC`):**
  - Compra de Curios e sacolas de prêmios (`GrabBag`).
  - Catálogo de 10 serviços utilitários.
  - **Correção Crítica (22/09):** Corrigido bug de dupla cobrança em `buy_service` (agora respeita estritamente `CURRENCY_ID` individual).
- **Minigames e Retenção (`player.py` / `Dalcs`):**
  - **Roda de Prêmios (`PrizeWheel`):** Giros gratuitos temporizados e giros extras com cálculo de raridade.
  - **Mesa de Plinko:** Física e trajetória de pinos simulada pelo servidor com prêmios de DNA e ouro.
  - **Recompensa Diária (`DailyReward`):** Registro de streak diário com resets às 00h.
  - **Trabalhos Diários (`job.py`):** 3 missões diárias com verificação de requisitos.
  - **Conquistas (`AchievementDALC`):** 33 conquistas empurradas pelo servidor com recompensas em plasma/créditos.
- **Gerenciamento de Curios (`PetDALC`):**
  - Alocação de pontos de habilidade, subida de Rank com custos escalonados, fusão e troca de Curios.

---

## 2. O Desbloqueio da Batalha (Tier 0)

- **O Problema de 2 Semanas:** A transição para o combate travava na tela `LOADING...` a 29 FPS no Android sem mensagens de erro no `logcat`.
- **Diagnóstico:** Adobe AIR silencia exceções em builds de release. Em `MenuScreen.as:1360`, `DialogManager.hideLoading(true)` só roda após `BattleScreen.fromEsObject`. Se houver erro de objeto nulo no `ServerPlugin.getRoom`, a execução é abortada.
- **Solução Implementada:** Envio síncrono da sala via `ThriftRoomListEntry` no `JoinZoneEvent` antes de despachar `ENTER_BATTLE`, garantindo que a sala exista no `zoneManager` do cliente no momento exato do consumo.

---

## 3. Matriz de Progresso e Conclusão

| Componente | Estado | % Concluído | Observações |
| :--- | :---: | :---: | :--- |
| **Infraestrutura de Rede (ES5 + CDN)** | ✅ Funcional | 98% | Estável, túnel persistente, pacotes validados |
| **Sistemas Base de Jogo (Save, XP, Loja)** | ✅ Funcional | 92% | Economia, minigames e persistência ativos |
| **Mapa de Campanha (Zonas 1 e 2)** | ✅ Funcional | 88% | Mapas, nós, diálogos e bandeiras renderizando |
| **Combate Single Player (T0)** | 🟡 Em Desbloqueio | 85% | Motor pronto no backend; transição visual sendo ativada |
| **Sistemas Secundários (Forja/Encantos)** | 🟠 Parcial | 35% | Livros mapeados, falta desenho fino de regras |
| **Arena PvP / Clubes / Eventos (T4)** | ⚪ Não Iniciado | 10% | Requer desenho novo; planejado para v2 |
| **Total Global para v1.0 (Campanha SP)** | 🚀 **82%** | **Meta: Campanha Completa e Jogável** |

---

## 4. Estimativa de Entrega da v1.0

- **Meta da v1.0:** Jogo 100% jogável nas Zonas 1 e 2 no celular físico (criação de conta, progressão no mapa, entrar e vencer batalhas, coletar loot e salvar progresso).
- **Previsão de Entrega da v1.0:** **Hoje (22/09/2026)**.
  - **Fase I (Imediata):** Desbloqueio da tela visual de combate no celular físico.
  - **Fase II (Final do dia):** Validação do ciclo completo de batalha (Entrar -> Lutar -> Vencer/Perder -> Telas de Vitória -> Atualizar Mapa com Estrelas).
