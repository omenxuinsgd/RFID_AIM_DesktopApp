from dataclasses import dataclass
from enum import Enum
from utils import calculate_checksum, hex_readable
 
 
class Response:
    def __init__(self, response_bytes: bytes):
        if len(response_bytes) < 6:
            raise ValueError("Response data is too short to be valid.")
 
        self.response_bytes = response_bytes
        self.length = response_bytes[0]
 
        if len(response_bytes) < self.length:
            raise ValueError("Response length mismatch.")
 
        self.reader_address = response_bytes[1]
        self.command = response_bytes[2]
        self.status = response_bytes[3]  # Check 5. LIST OF COMMAND EXECUTION RESULT STATUS
        self.data = response_bytes[4: self.length - 1]
        self.checksum = response_bytes[self.length - 1: self.length + 1]
 
        # Verify checksum
        data = bytearray(self.response_bytes[0:4])
        data.extend(self.data)
        crc_msb, crc_lsb = calculate_checksum(data)
        assert self.checksum[0] == crc_msb and self.checksum[1] == crc_lsb
 
    def __str__(self) -> str:
        lines = [
            ">>> START RESPONSE ================================",
            f"RESPONSE       >> {hex_readable(self.response_bytes)}",
            f"READER ADDRESS >> {hex_readable(self.reader_address)}",
            f"COMMAND        >> {hex_readable(self.command)}",
            f"STATUS         >> {hex_readable(self.status)}",
        ]
 
        if self.data:
            lines.append(f"DATA           >> {hex_readable(self.data)}")
 
        lines.append(f"CHECKSUM       >> {hex_readable(self.checksum)}")
        lines.append(">>> END RESPONSE   ================================")
 
        return "\n".join(lines)
 
 
 
class InventoryWorkMode(Enum):
    ANSWER_MODE: int = 0
    ACTIVE_MODE: int = 1
    TRIGGER_MODE_LOW: int = 2
    TRIGGER_MODE_HIGH: int = 3
 
 
class OutputInterface(Enum):
    WIEGAND: int = 0
    RS232_485: int = 1
    SYRIS485: int = 2
 
 
class Protocol(Enum):
    PROTOCOL_18000_6C: int = 0
    PROTOCOL_18000_6B: int = 1
 
 
class AddressType(Enum):
    WORD: int = 0
    BYTE: int = 1
 
 
class WiegandOutputAddressing(Enum):
    WORD: int = 0
    BYTE: int = 1
 
 
class WiegandFormat(Enum):
    WIEGAND_26BITS: int = 0
    WIEGAND_34BITS: int = 1
 
 
class WiegandBitOrder(Enum):
    HIGH_BIT_FIRST: int = 0
    LOW_BIT_FIRST: int = 1
 
 
class WiegandMode:
    def __init__(self, value: int):
        self.value: int = value
 
        self._wiegand_format: WiegandFormat = WiegandFormat(value & 0b1)
        self._bit_order: WiegandBitOrder = WiegandBitOrder((value & 0b10) >> 1)
 
    def __str__(self) -> str:
        return (f"Wiegand Mode: {self.wiegand_format.name.replace('_', ' ')}, "
                f"Bit Order: {self.bit_order.name.replace('_', ' ')}")
 
    @property
    def wiegand_format(self) -> WiegandFormat:
        return self._wiegand_format
 
    @wiegand_format.setter
    def wiegand_format(self, fmt: WiegandFormat):
        self._wiegand_format = fmt
        self.update_value()
 
    @property
    def bit_order(self) -> WiegandBitOrder:
        return self._bit_order
 
    @bit_order.setter
    def bit_order(self, order: WiegandBitOrder):
        self._bit_order = order
        self.update_value()
 
    def update_value(self):
        self.value = (self._wiegand_format.value & 0b1) | ((self._bit_order.value & 0b1) << 1)
 
 
class WorkModeState:
    def __init__(self, value: int):
        self.value: int = value
 
        self.protocol: Protocol = Protocol(value & 0b1)
        self.output_interface: OutputInterface = OutputInterface((value & 0b10) >> 1)
        self.beep: bool = not bool(value & 0b100)
        self.address_type: AddressType = AddressType(value & 0b1000)
        self.rs485_enable: bool = bool(value & 0b10000)
 
    def __str__(self) -> str:
        return (f"Protocol: {self.protocol.name.replace('_', '-')} "
                f"| Output Mode: {self.output_interface.name.replace('_', '/')} "
                f"| Address Type: {self.address_type} | RS485: {'Enabled' if self.rs485_enable else 'Disabled'} "
                f"| Beep/Buzzer: {'Enabled' if self.beep else 'Disabled'}")
 
    def to_int(self) -> int:
        value = 0
        value |= self.protocol.value  # Bit 0
        value |= (self.output_interface.value << 1)  # Bit 1
        value |= (0 if self.beep else 0b100)  # Bit 2
        value |= (self.address_type.value << 3)  # Bit 3
        value |= (self.rs485_enable << 4)  # Bit 4
        return value
 
 
class InventoryMemoryBank(Enum):
    PASSWORD: int = 0
    EPC: int = 1
    TID: int = 2
    USER: int = 3
    INVENTORY_MULTIPLE: int = 4
    INVENTORY_SINGLE: int = 5
    EAS_ALARM: int = 6
 
 
class WorkMode:
    def __init__(self, response_bytes: bytes):
        self.wiegand_mode = WiegandMode(response_bytes[0])
        self.wiegand_interval = response_bytes[1]
        self.wiegand_pulse_width = response_bytes[2]
        self.wiegand_pulse_interval = response_bytes[3]
        self.inventory_work_mode = InventoryWorkMode(response_bytes[4])
        self.work_mode_state = WorkModeState(response_bytes[5])
        self.memory_bank = InventoryMemoryBank(response_bytes[6])
        self.first_address = response_bytes[7]
        self.word_number = response_bytes[8]
        self.single_tag_time = response_bytes[9]
        self.accuracy = response_bytes[10]
        self.offset_time = response_bytes[11]
 
    def __str__(self) -> str:
        return "\n".join([
            f"Wiegand Mode: {self.wiegand_mode}",
            f"Wiegand Interval: {self.wiegand_interval}",
            f"Wiegand Pulse Width: {self.wiegand_pulse_width}",
            f"Wiegand Pulse Interval: {self.wiegand_pulse_interval}",
            f"Inventory Work Mode: {self.inventory_work_mode.name.replace('_', ' ')}",
            f"Work Mode State: {self.work_mode_state}",
            f"Memory Bank: {self.memory_bank.name.replace('_', ' ')}",
            f"First Address: {self.first_address}",
            f"Word Number: {self.word_number}",
            f"Single Tag Time: {self.single_tag_time}",
            f"Accuracy: {self.accuracy}",
            f"Offset Time: {self.offset_time}"
        ])
 
    def to_bytes(self) -> bytes:
        return bytes([
            self.inventory_work_mode.value,
            self.work_mode_state.to_int(),
            self.memory_bank.value,
            self.first_address,
            self.word_number,
            self.single_tag_time,
        ])