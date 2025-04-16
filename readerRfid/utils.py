def calculate_checksum(data: bytes) -> bytearray:
    value = 0xFFFF
    for d in data:
        value ^= d
        for _ in range(8):
            value = (value >> 1) ^ 0x8408 if value & 0x0001 else (value >> 1)
    crc_msb = value >> 0x08
    crc_lsb = value & 0xFF
    return bytearray([crc_lsb, crc_msb])
 
 
def hex_readable(data: bytes | int, bytes_separator: str = " ") -> str:
    if isinstance(data, int):
        return "{:02X}".format(data)
    return bytes_separator.join("{:02X}".format(x) for x in data)

# # usage checksum
# data = b"\x01\x02\x03"
# checksum = calculate_checksum(data)  # Returns bytearray of two bytes
# print(data)
# print(checksum)

# # usage hec_readable
# print(hex_readable(255))          # Output: "FF"
# print(hex_readable(b"\x01\x02"))  # Output: "01 02"
# print(hex_readable(b"\x01\x02", ":"))  # Output: "01:02"