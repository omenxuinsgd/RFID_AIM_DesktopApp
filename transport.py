from abc import ABC, abstractmethod
from socket import socket, AF_INET, SOCK_STREAM
from typing import TypeVar
import serial
 
T = TypeVar('T', bound='Parent')
 
 
class Transport(ABC):
    @abstractmethod
    def read_bytes(self, length: int) -> bytes:
        raise NotImplementedError
 
    @abstractmethod
    def write_bytes(self, buffer: bytes) -> None:
        raise NotImplementedError
 
    def read_frame(self) -> bytes | None:
        length_bytes = self.read_bytes(1)
        if not length_bytes:
            return
        frame_length = ord(chr(length_bytes[0]))
        data = length_bytes + self.read_bytes(frame_length)
        return bytearray(data)
 
    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
 
 
class TcpTransport(Transport):
    def __init__(self, ip_address: str, port: int, timeout: int = 1) -> None:
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.settimeout(timeout)
        self.socket.connect((ip_address, port))
 
    def read_bytes(self, length: int) -> bytes:
        return self.socket.recv(length)
 
    def write_bytes(self, buffer: bytes) -> None:
        self.socket.sendall(buffer)
 
    def close(self) -> None:
        self.socket.close()
 
 
class SerialTransport(Transport):
    def __init__(self, serial_port: str, baud_rate: int, timeout: int = 1) -> None:
        self.serial = serial.Serial(serial_port, baud_rate,
                                    timeout=timeout, write_timeout=timeout)
 
    def read_bytes(self, length: int) -> bytes:
        return self.serial.read(length)
 
    def write_bytes(self, buffer: bytes) -> None:
        self.serial.write(buffer)
 
    def close(self) -> None:
        self.serial.close()

# # Untuk koneksi Serial
# serial_transport = SerialTransport("COM8", 115200)
# if serial_transport:
#     print("terhubung")
# serial_transport.write_bytes(b"\x05hello")
# response = serial_transport.read_frame()
# serial_transport.close()