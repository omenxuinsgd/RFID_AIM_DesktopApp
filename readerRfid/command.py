from utils import calculate_checksum
 
CMD_INVENTORY: int = 0x01
CMD_READ_MEMORY: int = 0x02
CMD_WRITE_MEMORY: int = 0x03
CMD_WRITE_EPC : int = 0x04
CMD_SET_LOCK: int = 0x06
CMD_SET_READER_POWER: int = 0x2F
CMD_GET_WORK_MODE: int = 0x36
CMD_SET_WORK_MODE: int = 0x35
 
 
class Command:
    def __init__(self, command: int, reader_address: int = 0xFF,
                 data: bytes | int | None = None):
        self.command = command
        self.reader_address = reader_address
        self.data = data
        if isinstance(data, int):
            self.data = bytearray([data])
        if data is None:
            self.data = bytearray()
        self.frame_length = 4 + len(self.data)
        self.base_data = bytearray([self.frame_length, self.reader_address, self.command])
        self.base_data.extend(self.data)
 
    def serialize(self) -> bytes:
        serialize = self.base_data
        checksum = calculate_checksum(serialize)
        serialize.extend(checksum)
        return serialize