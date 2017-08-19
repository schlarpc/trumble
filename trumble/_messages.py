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
    """ Basically trying to emulate the protobuf mouthfeel, but for UDP packets """

    type = _attr.ib(default=_UDPTypes.Opus) # 0-7
    target = _attr.ib(default=_UDPTargets.NormalTalking) # 0-31

    # only for ping (type 1)
    timestamp = _attr.ib(default=0)

    # only for audio (types 0, 2, 3, 4)
    session_id = _attr.ib(default=0) # only for incoming
    sequence_number = _attr.ib(default=0)
    end_transmission = _attr.ib(default=False)
    voice_frames = _attr.ib(default=_attr.Factory(list))
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

    def _serialize_ping(self):
        return _varint.encode(self.timestamp)

    def _serialize_audio(self):
        payload = bytearray()
        payload += _varint.encode(self.sequence_number)
        if self.type == _UDPTypes.Opus:
            payload += self._serialize_opus()
        else:
            payload += self._serialize_celt()
        payload += _struct.pack('!fff', *self.position)
        return bytes(payload)

    def _serialize_opus(self):
        if len(self.voice_frames) != 1:
            raise ValueError('Opus always contains only one frame in the packet')
        if not all(isinstance(frame, bytes) for frame in self.voice_frames):
            raise ValueError('Voice frames must be bytes')
        voice_frame = self.voice_frames[0]
        if len(voice_frame) > 8191:
            raise ValueError('The maximum voice frame size is 8191')
        # "The 14th bit is the terminator bit, which signals whether
        # the packet is the last one in the voice transmission."
        # (negated to force the varint to be 14 bits)
        voice_header = _varint.encode(0x2000 | len(voice_frame))
        if not self.end_transmission:
            voice_header = bytes([voice_header[0] & 0b11011111, voice_header[1]])
        return voice_header + voice_frame

    def _serialize_celt(self):
        # TODO test this
        payload = bytearray()
        for idx, voice_frame in enumerate(self.voice_frames):
            voice_header = len(voice_frame)
            # "The most significant bit (0x80) acts as the continuation bit
            # and is set for all but the last frame in the payload."
            if idx != (len(self.voice_frames) - 1):
                voice_header = voice_header & 0b10000000
            payload += voice_header + voice_frame
            # "Note the length may be zero, which is used to signal the end of a voice
            # transmission. In this case the audio data is a single zero-byte which can be
            # interpreted normally as length of 0 with no continuation bit set."
            if self.end_transmission:
                payload += b'\x00'
        return bytes(payload)

    def SerializeToString(self):
        header = _struct.pack('!B', ((self.type & 0b111) << 5) | (self.target & 0b11111))
        if self.type == _UDPTypes.Ping:
            payload = self._serialize_ping()
        elif self.type in (_UDPTypes.CELTBeta, _UDPTypes.CELTAlpha, _UDPTypes.Speex, _UDPTypes.Opus):
            payload = self._serialize_audio()
        else:
            raise NotImplementedError('Unimplemented type')
        return header + payload

    def _deserialize_ping(self, data):
        self.timestamp = _varint.decode(data)

    def _deserialize_audio(self, data):
        self.session_id, remainder = _varint.decode(data)
        self.sequence_number, remainder = _varint.decode(remainder)
        if self.type == _UDPTypes.Opus:
            remainder = self._deserialize_opus(remainder)
        else:
            remainder = self._deserialize_celt(remainder)
        # "The payload must be self-delimiting to determine whether the position info
        # exists at the end of the packet."
        if len(remainder) == 3:
            self.position = _struct.unpack('!fff', remainder)
        elif len(remainder) != 0:
            pass
            # TODO not true?
            # raise ValueError('Position is supposed to be a float[3] if present, got %s', remainder)

    def _deserialize_opus(self, data):
        header, frame = _varint.decode(data)
        # "The 14th bit is the terminator bit, which signals whether
        # the packet is the last one in the voice transmission."
        self.end_transmission = bool(0x2000 & header)
        frame_length = 0x1fff & header
        self.voice_frames = [frame[:frame_length]]
        remainder = frame[frame_length+1:]
        return remainder

    def _deserialize_celt(self, data):
        frames = []
        for header, data in data[0], data[1:]:
            # "The remaining 7 bits of the header contain the actual length of the Data frame."
            length = 0x7f & header
            # "Note the length may be zero, which is used to signal the end of a voice transmission."
            if length == 0:
                self.end_transmission = True
                break
            frame, data = data[:length], data[length+1:]
            frames.append(frame)
            # "The most significant bit (0x80) acts as the continuation bit and is set
            # for all but the last frame in the payload."
            if header & 0x80:
                break
        self.voice_frames = frames
        return data

    def ParseFromString(self, data):
        header = _struct.unpack('!B', bytes([data[0]]))[0]
        self.type = (0b11100000 & header) >> 5
        self.target = 0b00011111 & header
        if self.type == _UDPTypes.Ping:
            self._deserialize_ping(data[1:])
        elif self.type in (_UDPTypes.CELTBeta, _UDPTypes.CELTAlpha, _UDPTypes.Speex, _UDPTypes.Opus):
            self._deserialize_audio(data[1:])
        else:
            raise NotImplementedError('Unimplemented type')

# attach the enums to UDPTunnel, since this is similar to how protobufs work
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

