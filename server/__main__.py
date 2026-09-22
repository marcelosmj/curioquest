"""Curio Quest offline server.  Run from the project folder:  python -m server"""
import argparse
import asyncio
import logging
from pathlib import Path

from .es5.session import Es5Server
from .game.game import Game
from .web import ContentStore, start_web_server

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(prog="python -m server", description="Servidor offline do Curio Quest")
    parser.add_argument("--bind", default="0.0.0.0", help="endereco de escuta (padrao: todas as interfaces)")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--es-port", type=int, default=9899)
    parser.add_argument("--apk", default=str(HERE.parent / "Curio Quest_1.15.00.apk"),
                        help="APK original, de onde saem os assets do jogo")
    parser.add_argument("--packet-log", action="store_true", help="mostra cada requisicao/resposta decodificada")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(name)-6s %(message)s", datefmt="%H:%M:%S")
    store = ContentStore(HERE / "content" / "web", args.apk, HERE / "content" / "asset_aliases.json")
    start_web_server(args.bind, args.http_port, store, args.es_port)
    game = Game(books_dir=HERE / "content" / "books", saves_dir=HERE / "saves", packet_log=args.packet_log)
    es_server = Es5Server(game, HERE / "es5" / "thrift_spec.json", args.bind, args.es_port)
    try:
        asyncio.run(_serve(es_server))
    except KeyboardInterrupt:
        pass


async def _serve(es_server):
    await es_server.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    main()
