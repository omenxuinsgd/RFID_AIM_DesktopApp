from typing import Iterator
from transport import Transport
from command import *
from response import *
 
class Reader:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport
 
    def close(self) -> None:
        self.transport.close()
 
    def __send_request(self, command: Command) -> None:
        self.transport.write_bytes(command.serialize())
 
    def __get_response(self) -> bytes:
        return self.transport.read_frame()
 
    def inventory_answer_mode(self,
                              start_address_tid: int | None = None,
                              len_tid: int | None = None,
                              ) -> Iterator[bytes]:  # 8.2.1 Inventory (Answer Mode)
        if start_address_tid is not None and len_tid is not None:
            command: Command = Command(CMD_INVENTORY, data=[start_address_tid, len_tid])
        else:
            command: Command = Command(CMD_INVENTORY)
        self.__send_request(command)
 
        response: Response = Response(self.__get_response())
        data: bytes = response.data
 
        if not data:
            return iter(())
 
        tag_count: int = data[0]
 
        n: int = 0
        pointer: int = 1
        while n < tag_count:
            tag_len = int(data[pointer])
            tag_data_start = pointer + 1
            tag_main_start = tag_data_start
            tag_main_end = tag_main_start + tag_len
            next_tag_start = tag_main_end
            tag = data[tag_data_start:tag_main_start] \
                  + data[tag_main_start:tag_main_end] + data[tag_main_end:next_tag_start]
            yield tag
            pointer = next_tag_start
            n += 1
 
    def inventory_active_mode(self) -> Iterator[Response]:
        while True:
            try:
                raw_response: bytes | None = self.__get_response()
            except TimeoutError:
                continue
            if raw_response is None:
                continue
            response: Response = Response(raw_response)
            yield response
 
    def read_memory(self, epc: bytes, memory_bank: int, start_address: int, length: int,
                    access_password: bytes = bytes(4)) -> Response:  # 8.2.2 Read Data
        request_data = bytearray()
        request_data.extend(bytearray([int(len(epc) / 2)]))  # EPC Length in word
        request_data.extend(epc)
        request_data.extend(bytearray([memory_bank, start_address, length]))
        request_data.extend(access_password)
        command: Command = Command(CMD_READ_MEMORY, data=request_data)
        self.__send_request(command)
 
        return Response(self.__get_response())
 
    def write_memory(self, epc: bytes, memory_bank: int, start_address: int,
                     data_to_write: bytes,
                     access_password: bytes = bytes(4)) -> Response:  # 8.2.4 Write Data
        request_data: bytearray = bytearray()
        request_data.extend(bytearray([int(len(data_to_write) / 2)]))  # Data length in word
        request_data.extend(bytearray([int(len(epc) / 2)]))  # EPC Length in word
        request_data.extend(epc)
        request_data.extend(bytearray([memory_bank, start_address]))
        request_data.extend(data_to_write)
        request_data.extend(access_password)
        command: Command = Command(CMD_WRITE_MEMORY, data=request_data)
        self.__send_request(command)
 
        return Response(self.__get_response())
 
    def lock(self, epc: bytes, select: int, set_protect: int, access_password: bytes) -> Response:  # 8.2.6 Lock
        parameter: bytearray = bytearray([int(len(epc) / 2)]) + epc + \
                               bytearray([select, set_protect]) + access_password
 
        command: Command = Command(CMD_SET_LOCK, data=parameter)
        self.__send_request(command)
 
        return Response(self.__get_response())
 
    def set_power(self, power: int) -> Response:  # 8.4.6 Set Power
        assert 0 <= power <= 30
 
        command: Command = Command(CMD_SET_READER_POWER, data=bytearray([power]))
        self.__send_request(command)
 
        return Response(self.__get_response())
 
    def work_mode(self) -> WorkMode:  # 8.4.10 Get WorkMode
        command: Command = Command(CMD_GET_WORK_MODE)
        self.__send_request(command)
 
        return WorkMode(Response(self.__get_response()).data)
 
    def set_work_mode(self, work_mode: WorkMode) -> Response:  # 8.4.9 Set WorkMode
        command: Command = Command(CMD_SET_WORK_MODE, data=work_mode.to_bytes())
        self.__send_request(command)
 
        return Response(self.__get_response())