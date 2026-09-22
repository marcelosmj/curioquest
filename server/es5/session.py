"""ElectroServer 5 BinaryTCP server: connection handshake and message dispatch.

Game rules live in the `game` object handed to Es5Server; this module only knows the
ElectroServer protocol (connection, login, plugin requests, pings).
"""
import asyncio
import itertools
import logging
import struct
import time

from . import esobject, protocol
from .thrift_binary import ThriftCodec

log = logging.getLogger("es5")


def flatten(eso):
    return {"encodedEntries": esobject.encode(eso)}


def unflatten(flattened):
    if not flattened or "encodedEntries" not in flattened:
        return esobject.EsObject()
    return esobject.decode(flattened["encodedEntries"])


class Es5Server:
    def __init__(self, game, spec_path, host="0.0.0.0", port=9899, compress_threshold=None):
        self.game = game
        self.thrift = ThriftCodec(spec_path)
        self.host = host
        self.port = port
        self.compress_threshold = compress_threshold
        self.sessions = set()
        self._server = None

    async def start(self):
        self._server = await asyncio.start_server(self._on_client, self.host, self.port)
        log.info("ElectroServer 5 (BinaryTCP) ouvindo em %s:%d", self.host, self.port)

    async def _on_client(self, reader, writer):
        session = Es5Session(self, reader, writer)
        self.sessions.add(session)
        try:
            await session.run()
        finally:
            self.sessions.discard(session)
            await self.game.on_disconnect(session)


class Es5Session:
    _ids = itertools.count(1)

    def __init__(self, server, reader, writer):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.id = next(self._ids)
        self.peer = writer.get_extra_info("peername")
        self.user_name = None
        self.data = {}
        self._closed = False

    @property
    def thrift(self):
        return self.server.thrift

    async def run(self):
        log.info("[%d] cliente conectou de %s", self.id, self.peer)
        try:
            self.writer.write(protocol.POLICY_TERMINATOR)
            self.send("ConnectionResponse", successful=True, hashId=self.id,
                      protocolConfiguration={"messageCompressionThreshold": -1}, serverVersion="5.3.3")
            await self.writer.drain()
            while not self._closed:
                (length,) = struct.unpack(">i", await self.reader.readexactly(4))
                body = await self.reader.readexactly(length)
                indicator, _number, data = protocol.parse_body(body)
                await self._dispatch(indicator, data)
                await self.writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        except Exception:
            log.exception("[%d] erro na sessao", self.id)
        finally:
            self.close()
            log.info("[%d] cliente desconectou", self.id)

    def close(self):
        if not self._closed:
            self._closed = True
            self.writer.close()

    def send(self, message_name, **fields):
        indicator = protocol.INDICATORS[message_name]
        struct_name = protocol.thrift_struct(indicator)
        data = self.thrift.encode(struct_name, fields) if struct_name else bytes([0])
        self.writer.write(protocol.build_frame(indicator, protocol.UNORDERED, data, self.server.compress_threshold))
        log.debug("[%d] -> %s", self.id, message_name)

    def join_room(self, zone_id, zone_name, room_id, room_name):
        """Put the client in a room: BattleScreen looks the room up by zone and room id."""
        log.info("[%d] entrando na sala %d da zona %d (%s)", self.id, room_id, zone_id, room_name)
        room_entry = {
            "roomId": room_id,
            "zoneId": zone_id,
            "roomName": room_name,
            "userCount": 1,
            "roomDescription": "",
            "capacity": 2,
            "hasPassword": False,
        }
        self.send("JoinZoneEvent", zoneId=zone_id, zoneName=zone_name, rooms=[room_entry])
        self.send("JoinRoomEvent", zoneId=zone_id, roomId=room_id, roomName=room_name,
                  roomDescription="", hasPassword=False, hidden=False, capacity=2,
                  users=[{"userName": self.user_name, "userVariables": [], "sendingVideo": False,
                          "videoStreamName": "", "roomOperator": False}],
                  roomVariables=[])

    def send_plugin_message(self, plugin_name, eso, zone_id=-1, room_id=-1):
        room_level = room_id >= 0
        self.send("PluginMessageEvent", pluginName=plugin_name, sentToRoom=room_level,
                  destinationZoneId=zone_id, destinationRoomId=room_id, roomLevelPlugin=room_level,
                  originZoneId=zone_id, originRoomId=room_id, parameters=flatten(eso))

    async def _dispatch(self, indicator, data):
        name = protocol.MESSAGE_TYPES.get(indicator, (f"?{indicator}", None))[0]
        struct_name = protocol.thrift_struct(indicator)
        message = self.thrift.decode(struct_name, data) if struct_name in self.thrift.structs else {}
        handler = getattr(self, "on_" + name, None)
        if handler is None:
            log.warning("[%d] <- %s (sem tratamento): %s", self.id, name, message)
            return
        log.debug("[%d] <- %s", self.id, name)
        await handler(message)

    async def on_LoginRequest(self, message):
        ok, eso, user_name = await self.server.game.on_login(self, message)
        self.user_name = user_name
        fields = {"successful": ok, "userName": user_name, "userVariables": {}, "buddyListEntries": {}}
        if eso is not None:
            fields["esObject"] = flatten(eso)
        self.send("LoginResponse", **fields)

    async def on_PluginRequest(self, message):
        await self.server.game.on_plugin_request(
            self, message.get("pluginName"), message.get("zoneId", -1), message.get("roomId", -1),
            unflatten(message.get("parameters")))

    async def on_AggregatePluginRequest(self, message):
        for request in message.get("pluginRequestArray", []):
            await self.server.game.on_plugin_request(
                self, request.get("pluginName"), request.get("zoneId", -1), request.get("roomId", -1),
                unflatten(request.get("parameters")))

    async def on_PingRequest(self, message):
        allowed = self.thrift.fields("ThriftPingResponse")
        self.send("PingResponse", **{k: v for k, v in message.items() if k in allowed})

    async def on_GetServerLocalTimeRequest(self, message):
        self.send("GetServerLocalTimeResponse", serverLocalTimeInMilliseconds=int(time.time() * 1000))

    async def on_LogOutRequest(self, message):
        self.close()
