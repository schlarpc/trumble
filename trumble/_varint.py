import struct as _struct

def decode(data):
    if data[0] & 0b10000000 == 0b00000000:
        # 0xxxxxxx - 7-bit positive number
        return _struct.unpack('!B', bytes([data[0] & 0b01111111]))[0], data[1:]
    elif data[0] & 0b11000000 == 0b10000000:
        # 10xxxxxx + 1 byte - 14-bit positive number
        return _struct.unpack('!H', bytes([data[0] & 0b00111111, data[1]]))[0], data[2:]
    elif data[0] & 0b11100000 == 0b11000000:
        # 110xxxxx + 2 bytes - 21-bit positive number
        return _struct.unpack('!I', bytes([0, data[0] & 0b00011111, data[1], data[2]]))[0], data[3:]
    elif data[0] & 0b11110000 == 0b11100000:
        # 1110xxxx + 3 bytes - 28-bit positive number
        return _struct.unpack('!I', bytes([data[0] & 0b00001111, data[1], data[2], data[3]]))[0], data[4:]
    elif data[0] & 0b11111100 == 0b11110000:
        # 111100__ + int (32-bit) - 32-bit positive number
        return _struct.unpack('!L', data[1:5])[0], data[5:]
    elif data[0] & 0b11111100 == 0b11110100:
        # 111101__ + long (64-bit) - 64-bit number
        return _struct.unpack('!Q', data[1:9])[0], data[9:]
    elif data[0] & 0b11111100 == 0b11111000:
        # 111110__ + varint - Negative recursive varint
        varint, remainder = decode(data[1:])
        return -varint, remainder
    elif data[0] & 0b11111100 == 0b11111100:
        # 111111xx - Byte-inverted negative two bit number (~xx)
        return ~_struct.unpack('!B', bytes([data[0] & 0b00000011]))[0], data[1:]

def encode(num):
    if num >= 0:
        if num.bit_length() <= 7:
            return _struct.pack('!B', num) 
        elif num.bit_length() <= 14:
            return _struct.pack('!H', num | (0b10000000 << 8))
        elif num.bit_length() <= 21:
            return _struct.pack('!I', num | (0b11000000 << 16)).lstrip(b'\x00')
        elif num.bit_length() <= 28:
            return _struct.pack('!I', num | (0b11100000 << 24))
        elif num.bit_length() <= 32:
            return bytes([0b11110000]) + _struct.pack('!L', num)
        elif num.bit_length() <= 64:
            return bytes([0b11110100]) + _struct.pack('!Q', num)
    elif num < -4:
        return bytes([0b11111000]) + encode(-num)
    else:
        return _struct.pack('!B', ~num | 0b11111100)
        
