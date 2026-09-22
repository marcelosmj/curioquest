"""ElectroServer 5 message table and BinaryTCP framing.

Frame (both directions): int32 length (= payload + 1), flags byte (bit 0 = zlib),
payload = int16 message type indicator + int32 message number + Thrift struct.
Messages numbered -1 bypass the client's ordering queue (ESEngine.checkMessageOrder).
"""
import struct
import zlib

# indicator -> (MessageType name, API class); from com.electrotank.electroserver5.api.EsUtility
MESSAGE_TYPES = {
    0: ("IdleTimeoutWarningEvent", "IdleTimeoutWarningEvent"),
    1: ("ServerKickUserEvent", "ServerKickUserEvent"),
    2: ("MarkGatewayClientLoggedInMessage", None),
    33: ("RegistryConnectionResponse", None),
    35: ("GatewayStartupExceptionsMessage", None),
    37: ("ValidateAdditionalLoginRequest", "ValidateAdditionalLoginRequest"),
    38: ("ValidateAdditionalLoginResponse", "ValidateAdditionalLoginResponse"),
    40: ("CreateOrJoinGameRequest", "QuickJoinGameRequest"),
    41: ("FindGamesResponse", "FindGamesResponse"),
    42: ("FindGamesRequest", "FindGamesRequest"),
    43: ("GetUserVariablesRequest", "GetUserVariablesRequest"),
    44: ("GetServerLocalTimeResponse", "GetServerLocalTimeResponse"),
    45: ("GetServerLocalTimeRequest", "GetServerLocalTimeRequest"),
    46: ("RemoveUDPConnectionResponse", "RemoveUDPConnectionResponse"),
    47: ("RemoveBuddiesResponse", "RemoveBuddiesResponse"),
    48: ("GetUserCountRequest", "GetUserCountRequest"),
    49: ("GetUserCountResponse", "GetUserCountResponse"),
    50: ("RegistryConnectToPreferredGatewayRequest", "RegistryConnectToPreferredGatewayRequest"),
    51: ("AggregatePluginRequest", "AggregatePluginRequest"),
    52: ("JoinGameRequest", "JoinGameRequest"),
    53: ("RegisterUDPConnectionRequest", "RegisterUDPConnectionRequest"),
    54: ("RegisterUDPConnectionResponse", "RegisterUDPConnectionResponse"),
    55: ("PingRequest", "PingRequest"),
    56: ("PingResponse", "PingResponse"),
    57: ("RemoveUDPConnectionRequest", "RemoveUDPConnectionRequest"),
    60: ("CrossDomainRequest", "CrossDomainPolicyRequest"),
    61: ("GetUserVariablesResponse", "GetUserVariablesResponse"),
    62: ("CrossDomainResponse", "CrossDomainPolicyResponse"),
    63: ("UdpBackchannelEvent", None),
    65: ("AddRoomOperatorRequest", "AddRoomOperatorRequest"),
    66: ("RemoveRoomOperatorRequest", "RemoveRoomOperatorRequest"),
    67: ("PluginRequest", "PluginRequest"),
    68: ("FindZoneAndRoomByNameRequest", "FindZoneAndRoomByNameRequest"),
    69: ("UpdateRoomDetailsEvent", "UpdateRoomDetailsEvent"),
    70: ("GetUsersInRoomResponse", "GetUsersInRoomResponse"),
    71: ("AggregatePluginMessageEvent", "AggregatePluginMessageEvent"),
    72: ("DeleteUserVariableRequest", "DeleteUserVariableRequest"),
    73: ("UpdateUserVariableRequest", "UpdateUserVariableRequest"),
    74: ("JoinRoomRequest", "JoinRoomRequest"),
    75: ("AddBuddiesRequest", "AddBuddiesRequest"),
    76: ("LoginRequest", "LoginRequest"),
    77: ("RemoveBuddiesRequest", "RemoveBuddiesRequest"),
    78: ("DeleteRoomVariableRequest", "DeleteRoomVariableRequest"),
    79: ("BuddyStatusUpdatedEvent", "BuddyStatusUpdateEvent"),
    80: ("PublicMessageRequest", "PublicMessageRequest"),
    81: ("CreateRoomRequest", "CreateRoomRequest"),
    82: ("JoinRoomEvent", "JoinRoomEvent"),
    83: ("EvictUserFromRoomRequest", "EvictUserFromRoomRequest"),
    84: ("UserEvictedFromRoomEvent", "UserEvictedFromRoomEvent"),
    85: ("UserUpdateEvent", "UserUpdateEvent"),
    86: ("ZoneUpdateEvent", "ZoneUpdateEvent"),
    87: ("LeaveRoomEvent", "LeaveRoomEvent"),
    88: ("LeaveZoneEvent", "LeaveZoneEvent"),
    89: ("UserVariableUpdateEvent", "UserVariableUpdateEvent"),
    90: ("JoinZoneEvent", "JoinZoneEvent"),
    92: ("AddBuddiesResponse", "AddBuddiesResponse"),
    94: ("GatewayKickUserRequest", "GatewayKickUserRequest"),
    95: ("CreateOrJoinGameResponse", "CreateOrJoinGameResponse"),
    97: ("PublicMessageEvent", "PublicMessageEvent"),
    98: ("GetZonesResponse", "GetZonesResponse"),
    99: ("ConnectionResponse", "ConnectionResponse"),
    100: ("GetRoomsInZoneResponse", "GetRoomsInZoneResponse"),
    101: ("GenericErrorResponse", "GenericErrorResponse"),
    102: ("PluginMessageEvent", "PluginMessageEvent"),
    103: ("FindZoneAndRoomByNameResponse", "FindZoneAndRoomByNameResponse"),
    104: ("UpdateRoomDetailsRequest", "UpdateRoomDetailsRequest"),
    105: ("SessionIdleEvent", "SessionIdleEvent"),
    107: ("GetUsersInRoomRequest", "GetUsersInRoomRequest"),
    108: ("LogOutRequest", "LogOutRequest"),
    109: ("LoginResponse", "LoginResponse"),
    110: ("CreateRoomVariableRequest", "CreateRoomVariableRequest"),
    111: ("UpdateRoomVariableRequest", "UpdateRoomVariableRequest"),
    112: ("PrivateMessageRequest", "PrivateMessageRequest"),
    113: ("RoomVariableUpdateEvent", "RoomVariableUpdateEvent"),
    114: ("PrivateMessageEvent", "PrivateMessageEvent"),
    115: ("GetZonesRequest", "GetZonesRequest"),
    116: ("GetRoomsInZoneRequest", "GetRoomsInZoneRequest"),
    117: ("Unknown", None),
    118: ("LeaveRoomRequest", "LeaveRoomRequest"),
    121: ("RegistryLoginResponse", None),
    122: ("DisconnectedEvent", None),
    144: ("RtmpPlayVideo", None),
    145: ("RtmpEventResponse", None),
    146: ("RtmpRecordVideo", None),
    147: ("RtmpPublishVideo", None),
    148: ("RtmpUnpublishVideo", None),
    149: ("RtmpAppendVideo", None),
    150: ("RtmpStreamingStart", None),
    151: ("RtmpStreamingStop", None),
    152: ("DHInitiate", "DHInitiateKeyExchangeRequest"),
    153: ("DHPublicNumbers", "DHPublicNumbersResponse"),
    154: ("DHSharedModulusRequest", "DHSharedModulusRequest"),
    155: ("DHSharedModulusResponse", "DHSharedModulusResponse"),
    156: ("EncryptionStateChange", "EncryptionStateChangeEvent"),
    157: ("ConnectionAttemptResponse", "ConnectionAttemptResponse"),
    158: ("ConnectionClosedEvent", "ConnectionClosedEvent"),
}

INDICATORS = {name: indicator for indicator, (name, _) in MESSAGE_TYPES.items()}

# The client treats every byte before the first 0 as a Flash policy file.
POLICY_TERMINATOR = b"\x00"

UNORDERED = -1


def thrift_struct(indicator):
    api_class = MESSAGE_TYPES.get(indicator, (None, None))[1]
    return "Thrift" + api_class if api_class else None


def build_frame(indicator, message_number, thrift_bytes, compress_threshold=None):
    payload = struct.pack(">hi", indicator, message_number) + thrift_bytes
    flags = 0
    if compress_threshold is not None and len(payload) >= compress_threshold:
        payload = zlib.compress(payload)
        flags |= 1
    return struct.pack(">ib", len(payload) + 1, flags) + payload


def parse_body(body):
    """Split a received frame body (after the length) into (indicator, number, thrift bytes)."""
    flags = body[0]
    payload = body[1:]
    if flags & 1:
        payload = zlib.decompress(payload)
    indicator, message_number = struct.unpack(">hi", payload[:6])
    return indicator, message_number, payload[6:]
