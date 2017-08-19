import enum as _enum
import re as _re
import struct as _struct

import attr as _attr

from . import _messages_pb2
from . import _varint

@_enum.unique
class _UDPTypes(_enum.IntEnum):
    CELTAlpha = 0
    Ping      = 1
    Speex     = 2
    CELTBeta  = 3
    Opus      = 4

@_enum.unique
class _UDPTargets(_enum.IntEnum):
    NormalTalking  =  0
    ServerLoopback = 31

@_attr.s
class UDPTunnel:
    type = _attr.ib(default=_UDPTypes.Opus) # 0-7
    target = _attr.ib(default=_UDPTargets.ServerLoopback) # 0-31

    timestamp = _attr.ib(default=0)

    session_id = _attr.ib(default=0)
    sequence_number = _attr.ib(default=0)
    #voice_terminator = _attr.ib(default=True, validator)
    voice_frame = _attr.ib(default=b'')
    position = _attr.ib(default=_attr.Factory(lambda: [0., 0., 0.]))

    @timestamp.validator
    def _timestamp_validator(self, attribute, value):
        if not isinstance(value, int):
            raise ValueError('Timestamp must be int')
        if abs(value).bit_length() > 64:
            raise ValueError('Timestamp must be 64 bits or fewer')

    @position.validator
    def _position_validator(self, attribute, value):
        if len(value) != 3:
            raise ValueError('Position must be a 3-tuple of x, y, z')
        if not all(isinstance(v, (float, int)) for v in value):
            raise ValueError('Position elements must be int or float')

    def SerializeToString(self):
        header = _struct.pack('!B', ((self.type & 0b111) << 5) | (self.target & 0b11111))
        if self.type == _UDPTypes.Ping:
            payload = _varint.encode(self.timestamp)
        else:
            payload = bytearray()
            payload += _varint.encode(self.sequence_number)

            # TODO this is wrong
            payload += self.voice_frame

            payload += _struct.pack('!fff', *self.position)

        return header + bytes(payload)

    def ParseFromString(self, data):
        header = _struct.unpack('!B', bytes([data[0]]))[0]
        self.type = (0b11100000 & header) >> 5
        self.target = 0b00011111 & header
        self.payload = data[1:]

for constant_enum in (_UDPTypes, _UDPTargets):
    for k, v in constant_enum.__members__.items():
        setattr(UDPTunnel, k, v)

def _to_snake_case(name):
    s1 = _re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return _re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

_MESSAGE_CLASS_FROM_ID = {
    0: _messages_pb2.Version,
    1: UDPTunnel,
    2: _messages_pb2.Authenticate,
    3: _messages_pb2.Ping,
    4: _messages_pb2.Reject,
    5: _messages_pb2.ServerSync,
    6: _messages_pb2.ChannelRemove,
    7: _messages_pb2.ChannelState,
    8: _messages_pb2.UserRemove,
    9: _messages_pb2.UserState,
    10: _messages_pb2.BanList,
    11: _messages_pb2.TextMessage,
    12: _messages_pb2.PermissionDenied,
    13: _messages_pb2.ACL,
    14: _messages_pb2.QueryUsers,
    15: _messages_pb2.CryptSetup,
    16: _messages_pb2.ContextActionModify,
    17: _messages_pb2.ContextAction,
    18: _messages_pb2.UserList,
    19: _messages_pb2.VoiceTarget,
    20: _messages_pb2.PermissionQuery,
    21: _messages_pb2.CodecVersion,
    22: _messages_pb2.UserStats,
    23: _messages_pb2.RequestBlob,
    24: _messages_pb2.ServerConfig,
    25: _messages_pb2.SuggestConfig,
}

_MESSAGE_ID_FROM_CLASS = {v: k for k, v in _MESSAGE_CLASS_FROM_ID.items()}

_MESSAGE_NAME_FROM_CLASS = {v: _to_snake_case(v.__name__) for k, v in _MESSAGE_CLASS_FROM_ID.items()}

def get_class_by_id(message_id):
    return _MESSAGE_CLASS_FROM_ID[message_id]

def get_id_by_class(message_class):
    return _MESSAGE_ID_FROM_CLASS[message_class]

def get_name_by_class(message_class):
    return _MESSAGE_NAME_FROM_CLASS[message_class]

for message_class in _MESSAGE_ID_FROM_CLASS.keys():
    globals()[message_class.__name__] = message_class

def _serialize(message):
    message_id = get_id_by_class(message.__class__)
    message_data = message.SerializeToString()
    message_header = _struct.pack('!HI', message_id, len(message_data))
    return message_header + message_data

def _deserialize(message_id, message_data):
    message = get_class_by_id(message_id)()
    message.ParseFromString(message_data)
    return message

