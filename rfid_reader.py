import serial
from PyQt6.QtCore import QObject, pyqtSignal

class RFIDReader(QObject):
    tag_scanned = pyqtSignal(dict)  # {'uid': '...', 'epc': '...'}
    
    def __init__(self):
        super().__init__()
        self.serial_conn = None
        self.is_connected = False

    def connect(self, port):
        """Connect to RFID reader on specified COM port"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=1
            )
            self.is_connected = True
            return True
            
        except Exception as e:
            self.is_connected = False
            raise Exception(f"Connection failed: {str(e)}")

    def disconnect(self):
        """Disconnect from RFID reader"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.is_connected = False
            return True
        except Exception as e:
            raise Exception(f"Disconnection failed: {str(e)}")

    def start_scan(self, callback):
        """Start RFID scanning process"""
        try:
            if not self.is_connected:
                raise Exception("Reader not connected")
                
            # Send scan command (protocol specific)
            self.serial_conn.write(b'SCAN\r\n')  # Example command
            
            # Read response (adjust based on your reader's protocol)
            response = self.serial_conn.read_until(b'\r\n').decode().strip()
            
            if not response:
                raise Exception("No response from reader")
                
            # Parse response (example format: "UID:12345678,EPC:ABCD1234")
            parts = response.split(',')
            tag_data = {}
            
            for part in parts:
                key, value = part.split(':')
                tag_data[key.lower()] = value
                
            # Emit the scanned data
            callback.emit(tag_data)
            
        except Exception as e:
            callback.emit({'error': str(e)})