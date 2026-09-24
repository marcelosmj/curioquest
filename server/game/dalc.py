"""Base for the server side of the client's DALCs (data access layer components).

Every ServerPlugin request carries DALC_ID and ACTION_TYPE; replies must echo both,
because plugins.ServerPlugin.onPluginMessage routes them to <Name>DALC.parse(), which
switches on ACTION_TYPE.
"""
import logging

from ..es5.esobject import EsObject
from .keys import K, NAMES

log = logging.getLogger("dalc")

SERVER_PLUGIN = "ServerPlugin"

# Nenhum pedido pode ficar sem resposta.  Varios paineis chamam DialogManager.showLoading() antes
# de enviar e so fecham o dialogo quando a resposta chega (MenuProfilePanel e o caso exemplar):
# sem resposta o cliente gira para sempre e, 60s depois, o timeout derruba a sessao inteira.
# Responder com erro fecha o LOADING e mantem o jogador dentro do jogo.  ErrorCode.getErrorMessage
# devolve "" para um codigo que nao conhece, entao o popup sai sem texto - feio, mas vivo.
NOT_IMPLEMENTED = 200


def action(action_id):
    """Mark a Dalc method as the handler of one ACTION_TYPE."""
    def mark(method):
        method.action_id = action_id
        return method
    return mark


class Dalc:
    dalc_id = None
    name = "?"

    def __init__(self, game):
        self.game = game
        self._actions = {}
        for attr in dir(type(self)):
            method = getattr(self, attr)
            action_id = getattr(method, "action_id", None)
            if action_id is not None:
                self._actions[action_id] = method

    async def handle(self, session, action_id, request):
        method = self._actions.get(action_id)
        if method is None:
            log.warning("[%d] %s: acao %s nao implementada: %s",
                        session.id, self.name, action_id, request.to_debug(NAMES))
            self.send(session, action_id, EsObject().set_integer(K.ACTION_ERROR, NOT_IMPLEMENTED))
            return
        try:
            response = await method(session, request)
        except Exception:
            log.exception("[%d] %s: erro na acao %s: %s", session.id, self.name, action_id, request.to_debug(NAMES))
            self.send(session, action_id, EsObject().set_integer(K.ACTION_ERROR, NOT_IMPLEMENTED))
            return
        if response is not None:
            self.send(session, action_id, response)

    def send(self, session, action_id, eso):
        eso.set_integer(K.DALC_ID, self.dalc_id)
        eso.set_integer(K.ACTION_TYPE, action_id)
        if self.game.packet_log:
            log.info("[%d] -> %s acao %s: %s", session.id, self.name, action_id, eso.to_debug(NAMES))
        session.send_plugin_message(SERVER_PLUGIN, eso)
