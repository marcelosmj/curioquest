"""Ponte entre o app Android e o servidor do Curio Quest.

O servidor original descobre tudo a partir de __file__ (livros, conteudo web,
saves).  No Android isso nao funciona: o Chaquopy extrai os .py mas nao os
arquivos de dados, e nada fica gravavel dentro do pacote.  Por isso aqui todos
os caminhos chegam prontos, vindos do Kotlin.

Tambem escuta so em 127.0.0.1: o jogo roda no mesmo aparelho, entao nao ha
motivo para expor as portas na rede.
"""
import asyncio
import logging
import os
import threading
from pathlib import Path

_thread = None
log = logging.getLogger("android")


def iniciar(apk_path, saves_dir, content_dir, bind="127.0.0.1", http_port=8080, es_port=9899):
    global _thread
    if _thread and _thread.is_alive():
        return "ja estava no ar"

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)-6s %(message)s", datefmt="%H:%M:%S")

    content = Path(content_dir)
    apk, saves = Path(apk_path), Path(saves_dir)
    saves.mkdir(parents=True, exist_ok=True)

    # keys.py le es_constants.json ao ser importado, e no Android ele nao esta ao lado
    # do codigo: precisa apontar para os dados extraidos ANTES de qualquer import.
    os.environ["CURIOQUEST_ES5_DIR"] = str(content)

    from server.web import ContentStore, start_web_server
    from server.game.game import Game
    from server.es5.session import Es5Server

    store = ContentStore(content / "web", str(apk), content / "asset_aliases.json")
    start_web_server(bind, http_port, store, es_port)
    game = Game(books_dir=content / "books", saves_dir=saves, packet_log=False)
    es = Es5Server(game, content / "thrift_spec.json", bind, es_port)

    def rodar():
        laco = asyncio.new_event_loop()
        asyncio.set_event_loop(laco)
        try:
            laco.run_until_complete(_servir(es))
        except Exception:
            log.exception("servidor caiu")

    _thread = threading.Thread(target=rodar, daemon=True, name="curioquest-server")
    _thread.start()
    log.info("servidor no ar em %s (http %d, es5 %d)", bind, http_port, es_port)
    return "no ar"


async def _servir(es):
    await es.start()
    await asyncio.Event().wait()
