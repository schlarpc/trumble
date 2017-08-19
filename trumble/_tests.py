"""
Unit tests are not implemented yet, so we're just saving this for later.
"""

def test_varint():
    test_cases = [
        ([0b01000000], 2 ** 6),
        ([0b10110000, 0b10000001], 2 ** 0 + 2 ** 7 + 2 ** 12 + 2 ** 13),
        ([0b11010000, 0b00010000, 0b00000001], 2 ** 0 + 2 ** 12 + 2 ** 20),
        ([0b11101000, 0b10000000, 0b00000001, 0b00000000], 2 ** 27 + 2 ** 8 + 2 ** 23),
        ([0b11110011, 0b10000000, 0b00000000, 0b10000000, 0b00000001], 2 ** 0 + 2 ** 15 + 2 ** 31),
        ([0b11110110, 0b10000000, 0, 0, 0, 0b10000000, 0b00000000, 0b10000000, 0b00000001], 2 ** 0 + 2 ** 15 + 2 ** 31 + 2 ** 63),
        ([0b11111101], -2),
    ]
    for varint_bytes, expected_value in test_cases:
        for negatize in (False, True):
            if negatize:
                varint_bytes = [0b11111010] + varint_bytes
                expected_value *= -1
            result, remainder = varint.decode(bytes(varint_bytes) + b'garbage')
            assert result == expected_value
            assert remainder == b'garbage'

            encoded_bytes = varint.encode(expected_value)
            result, garbage = varint.decode(encoded_bytes)
            assert result == expected_value
            assert not garbage
