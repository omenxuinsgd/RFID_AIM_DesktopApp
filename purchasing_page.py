import sys
import requests
import serial.tools.list_ports
import time
import base64
from io import BytesIO
from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QLineEdit, QMessageBox,
    QHeaderView, QStackedWidget, QGroupBox, QScrollArea,
    QProgressDialog, QFormLayout, QComboBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt6.QtGui import QIcon, QPixmap
from response import hex_readable, Response, WorkMode, InventoryWorkMode, InventoryMemoryBank
from transport import SerialTransport
from reader import Reader
import check_connection

class RFIDInventoryThread(QThread):
    tag_scanned = pyqtSignal(dict)
    reader_status = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.reader = None
        self.transport = None
        self._is_running = False  # Thread tidak berjalan sampai di-start
        self._should_scan = False
        self.current_port = None
        self.power_level = 30
        self.scanned_epcs = set()
        self.mutex = QMutex()
        self.connection_established = False

    def disconnect_reader(self):
        """Close connection to RFID reader"""
        try:
            print("DEBUG: Disconnecting RFID reader...")
            if self.reader:
                self.reader.close()
            self.reader = None
            self.transport = None
            self.reader_status.emit("Reader disconnected")
            print("DEBUG: RFID reader disconnected.")
            return True
        except Exception as e:
            print(f"DEBUG: Disconnection failed with error: {str(e)}")
            self.error_occurred.emit(f"Disconnection failed: {str(e)}")
            return False

    def connect_reader(self, port: str):
        """Initialize connection to RFID reader"""
        try:
            self.current_port = port
            self.transport = SerialTransport(port, 57600)
            self.reader = Reader(self.transport)
            
            # Configure reader settings
            response_power = self.reader.set_power(self.power_level)
            if response_power.status != 0x00:
                raise Exception("Failed to set power level")
            
            work_mode = self.reader.work_mode()
            work_mode.inventory_work_mode = InventoryWorkMode.ANSWER_MODE
            if self.reader.set_work_mode(work_mode).status != 0x00:
                raise Exception("Failed to set work mode")
                
            self.connection_established = True
            self.reader_status.emit(f"Connected to {port}")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Connection failed: {str(e)}")
            self.connection_established = False
            return False
        
    def _read_tid(self, epc: bytes) -> str:
        """Read TID from tag"""
        try:
            print(f"DEBUG: Reading TID for EPC: {hex_readable(epc)}...")
            response = self.reader.read_memory(
                epc=epc,
                memory_bank=InventoryMemoryBank.TID.value,
                start_address=2,
                length=4
            )
            if response.status == 0x00:
                tid_data = hex_readable(response.data)
                print(f"DEBUG: TID read successfully: {tid_data}")
                return tid_data
            else:
                print(f"DEBUG: Failed to read TID. Status: {hex(response.status)}")
                return ""
        except Exception as e:
            print(f"DEBUG: Error reading TID: {str(e)}")
            return ""

    def run(self):
        """Main thread loop for continuous operation"""
        print("RFID thread started and running...")
        self._is_running = True
        
        try:
            while self._is_running:
                if self._should_scan and self.connection_established:
                    try:
                        self._perform_inventory()
                        time.sleep(0.1)  # Small delay between scans
                    except Exception as e:
                        print(f"Scanning error: {e}")
                        self.error_occurred.emit(f"Scanning error: {str(e)}")
                        time.sleep(1)  # Wait before retrying
                else:
                    time.sleep(0.2)  # Longer delay when not scanning
                    
        except Exception as e:
            print(f"Thread error: {e}")
            self.error_occurred.emit(f"Thread error: {str(e)}")
        finally:
            print("RFID thread stopped")
            self._is_running = False
            self.reader_status.emit("Thread stopped")

    def _perform_inventory(self):
        """Perform tag inventory when scanning is active"""
        try:
            tags = list(self.reader.inventory_answer_mode())
            if not tags:
                return

            # Dictionary untuk menyimpan tag unik berdasarkan EPC
            unique_tags = {}
            for tag in tags:
                epc = hex_readable(tag)
                if epc not in unique_tags:
                    tid = self._read_tid(tag)
                    unique_tags[epc] = {
                        'epc': epc,
                        'tid': tid,
                        'uid': tid
                    }

            # Kirim hanya tag unik
            for tag_data in unique_tags.values():
                if not self._should_scan:  # Check if we should stop
                    break
                    
                with QMutexLocker(self.mutex):
                    if tag_data['epc'] not in self.scanned_epcs:
                        self.scanned_epcs.add(tag_data['epc'])
                        self.tag_scanned.emit(tag_data)
                    
        except Exception as e:
            print(f"Inventory error: {e}")
            raise

    def start_scanning(self):
        """Start the scanning process"""
        if not self.connection_established:
            self.error_occurred.emit("Reader not connected")
            return
            
        print("Starting RFID scanning...")
        with QMutexLocker(self.mutex):
            self._should_scan = True
            self.scanned_epcs.clear()
        self.reader_status.emit("Scanning started")

    def stop_scanning(self):
        """Stop the scanning process (thread tetap berjalan)"""
        print("Stopping RFID scanning (thread remains running)")
        with QMutexLocker(self.mutex):
            self._should_scan = False
        self.reader_status.emit("Scanning stopped")

    def stop_thread(self):
        """Stop the thread completely"""
        print("Stopping RFID thread completely...")
        self.stop_scanning()
        self._is_running = False
        if self.isRunning():
            self.wait(2000)  # Wait for thread to finish
        self.reader_status.emit("Thread stopped")

class PurchasingPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.token = None
        self.user_data = None
        self.rfid_thread = RFIDInventoryThread()
        self.scanned_assets = []
        self.init_ui()
        self._setup_rfid_connections()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Stacked widget untuk multi-page
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # Buat semua halaman
        self.scan_page = self._create_scan_page()
        self.login_page = self._create_login_page()
        self.checkout_page = self._create_checkout_page()
        
        # Tambahkan halaman ke stack
        self.stack.addWidget(self.scan_page)
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.checkout_page)
        
        # Tampilkan halaman pertama
        self.stack.setCurrentWidget(self.scan_page)
        
    def _create_scan_page(self):
        """Halaman untuk scan RFID tag produk"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Back to main menu button
        self.back_button = QPushButton("Back to Main Menu")
        self.back_button.setIcon(QIcon("icons/back.png"))
        self.back_button.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        layout.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Title
        title = QLabel("Scan Products for Checkout")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # RFID Connection Group
        connection_group = QGroupBox("RFID Connection")
        connection_layout = QVBoxLayout(connection_group)
        
        # COM Port Selection
        port_layout = QHBoxLayout()
        self.cb_com_ports = QComboBox()
        self._refresh_com_ports()
        port_layout.addWidget(QLabel("COM Port:"))
        port_layout.addWidget(self.cb_com_ports)
        
        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.clicked.connect(self._refresh_com_ports)
        port_layout.addWidget(refresh_btn)
        connection_layout.addLayout(port_layout)
        
        # Connect/Disconnect Button
        self.btn_connect = QPushButton("Connect to Reader")
        self.btn_connect.setIcon(QIcon("icons/connect.png"))
        self.btn_connect.clicked.connect(self.toggle_rfid_connection)
        connection_layout.addWidget(self.btn_connect)
        
        # Status label
        self.lbl_connection_status = QLabel("Status: Not connected")
        connection_layout.addWidget(self.lbl_connection_status)
        
        layout.addWidget(connection_group)
        
        # Scan Button
        self.btn_scan = QPushButton("Start Scanning")
        self.btn_scan.setIcon(QIcon("icons/rfid.png"))
        self.btn_scan.setEnabled(False)
        self.btn_scan.clicked.connect(self.toggle_scanning)
        layout.addWidget(self.btn_scan)
        
        # Table untuk menampilkan scanned products
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(4)
        self.products_table.setHorizontalHeaderLabels(["Name", "Price", "RFID EPC", "Action"])
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.products_table)
        
        # Checkout button
        self.btn_checkout = QPushButton("Proceed to Checkout")
        self.btn_checkout.setEnabled(False)
        self.btn_checkout.clicked.connect(self.proceed_to_checkout)
        layout.addWidget(self.btn_checkout)
        
        return page
    
    def _create_login_page(self):
        """Halaman login user untuk mendapatkan token"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Back button
        back_button = QPushButton("Back to Scanning")
        back_button.setIcon(QIcon("icons/back.png"))
        back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.scan_page))
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Title
        title = QLabel("User Login for Checkout")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Scroll area untuk form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        
        # Form input user
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Email")
        form_layout.addRow("Email:", self.txt_email)
        
        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Password")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self.txt_password)
        
        # Submit button
        btn_submit = QPushButton("Login & Checkout")
        btn_submit.clicked.connect(self.process_checkout)
        form_layout.addRow(btn_submit)
        
        scroll.setWidget(form_container)
        layout.addWidget(scroll)
        
        return page
    
    def _create_checkout_page(self):
        """Halaman untuk proses checkout dan pembayaran"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Back button
        back_button = QPushButton("Back to Login")
        back_button.setIcon(QIcon("icons/back.png"))
        back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Title
        title = QLabel("Checkout Summary")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # User info
        self.lbl_user_info = QLabel()
        content_layout.addWidget(self.lbl_user_info)
        
        # Items table
        self.checkout_table = QTableWidget()
        self.checkout_table.setColumnCount(3)
        self.checkout_table.setHorizontalHeaderLabels(["Item", "Quantity", "Price"])
        self.checkout_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.checkout_table)
        
        # Total amount
        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet("font-size: 16px; font-weight: bold;")
        content_layout.addWidget(self.lbl_total)
        
        # QR Code
        self.lbl_qr_code = QLabel()
        self.lbl_qr_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.lbl_qr_code)
        
        # Complete button
        btn_complete = QPushButton("Complete Checkout")
        btn_complete.clicked.connect(self.complete_checkout)
        content_layout.addWidget(btn_complete)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return page
    
    def _setup_rfid_connections(self):
        """Connect RFID thread signals to slots"""
        self.rfid_thread.tag_scanned.connect(self._handle_tag_scanned)
        self.rfid_thread.reader_status.connect(self._update_reader_status)
        self.rfid_thread.error_occurred.connect(self._handle_rfid_error)

    def _handle_tag_scanned(self, tag_data: dict):
        """Handle scanned RFID tag"""
        QApplication.processEvents()  # Ensure UI remains responsive
        
        # Check if EPC already exists in the table
        epc_exists = any(
            self.products_table.item(row, 2).text() == tag_data['epc']
            for row in range(self.products_table.rowCount())
        )
        
        if epc_exists:
            return
            
        # Get asset details from API using both EPC and UID (TID)
        self._fetch_asset_details(tag_data['epc'], tag_data['uid'])
        
    def _try_fallback_search(self, epc: str):
        """Fallback search using only EPC if initial search fails"""
        try:
            response = requests.get(
                'http://localhost:5000/api/assets',
                params={'epc': epc},
                timeout=5
            )
            
            if response.status_code == 200:
                assets = response.json()
                if isinstance(assets, list) and len(assets) > 0:
                    self._add_asset_to_table(assets[0])
                else:
                    print(f"No asset found even with EPC-only search: {epc}")
            else:
                print(f"Fallback search failed: {response.text}")
        except Exception as e:
            print(f"Error in fallback search: {str(e)}")
            
    def _fetch_asset_details(self, epc: str, uid: str):
        """Fetch asset details from API using both EPC and UID"""
        try:
            progress = QProgressDialog("Getting product info...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()
            
            print(f"Searching for asset with EPC: {epc} and UID: {uid}")  # Debug log
            
            # Search by UID (TID) first since it's more unique
            response = requests.get(
                'http://localhost:5000/api/assets',
                params={'uid': uid},
                timeout=5
            )

            if response.status_code == 200:
                assets = response.json()
                if isinstance(assets, list) and len(assets) > 0:
                    # Verify EPC matches
                    matched_asset = None
                    for asset in assets:
                        asset_epc = asset.get('rfidTag', {}).get('epc', '')
                        if asset_epc == epc:
                            matched_asset = asset
                            break
                    
                    if matched_asset:
                        self._add_asset_to_table(matched_asset)
                        progress.close()
                        return
                    
            # If not found by UID or EPC doesn't match, try by EPC
            print("Trying fallback search by EPC only")
            response = requests.get(
                'http://localhost:5000/api/assets',
                params={'epc': epc},
                timeout=5
            )
            
            progress.close()
            
            if response.status_code == 200:
                assets = response.json()
                if isinstance(assets, list) and len(assets) > 0:
                    self._add_asset_to_table(assets[0])
                else:
                    print(f"No asset found with EPC: {epc}")
                    QMessageBox.warning(self, "Warning", f"Produk dengan EPC {epc} tidak ditemukan di database")
            else:
                print(f"Failed to fetch asset: {response.text}")
                QMessageBox.warning(self, "Warning", "Gagal mengambil data produk dari server")
                
        except Exception as e:
            progress.close()
            print(f"Error fetching asset: {str(e)}")
            QMessageBox.warning(self, "Error", f"Terjadi kesalahan: {str(e)}")

    def _add_asset_to_table(self, asset_data: dict):
        """Add asset to the table with proper data validation"""
        try:
            rfid_tag = asset_data.get('rfidTag', {})
            epc = rfid_tag.get('epc', '')
            uid = rfid_tag.get('uid', '')
            
            if not epc:
                print("Asset has no EPC, skipping")
                return
                
            # Debug print to show what we're adding
            print(f"Adding asset to table - EPC: {epc}, UID: {uid}, Name: {asset_data.get('name')}")
            
            # Check if asset already exists in the table
            for existing_asset in self.scanned_assets:
                if existing_asset['rfidTag']['epc'] == epc:
                    print(f"Asset with EPC {epc} already in table")
                    return
            
            self.scanned_assets.append(asset_data)
            
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            
            # Add item data to table
            name = asset_data.get('name', 'Unknown Product')
            self.products_table.setItem(row, 0, QTableWidgetItem(name))
            
            # Format price properly
            price = asset_data.get('price', 0)
            if isinstance(price, (int, float)):
                price_text = f"Rp {price:,}"
            else:
                price_text = "N/A"
            self.products_table.setItem(row, 1, QTableWidgetItem(price_text))
            
            self.products_table.setItem(row, 2, QTableWidgetItem(epc))
            
            # Add remove button
            btn_remove = QPushButton("Remove")
            btn_remove.clicked.connect(lambda _, r=row, e=epc: self._remove_asset(r, e))
            self.products_table.setCellWidget(row, 3, btn_remove)
            
            # Enable checkout button if we have items
            self.btn_checkout.setEnabled(self.products_table.rowCount() > 0)
            
        except Exception as e:
            print(f"Error adding asset to table: {str(e)}")
            QMessageBox.warning(self, "Error", f"Gagal menambahkan produk ke tabel: {str(e)}")
                
    def _remove_asset(self, row: int, epc: str):
        """Remove asset from the scanning list"""
        self.products_table.removeRow(row)
        self.scanned_assets = [a for a in self.scanned_assets 
                             if a['rfidTag']['epc'] != epc]
        
        # Allow this EPC to be scanned again
        if self.rfid_thread:
            self.rfid_thread.mutex.lock()
            try:
                self.rfid_thread.scanned_epcs.discard(epc)
            finally:
                self.rfid_thread.mutex.unlock()
        
        self.btn_checkout.setEnabled(self.products_table.rowCount() > 0)

    def _update_reader_status(self, message: str):
        """Update RFID reader connection status"""
        self.lbl_connection_status.setText(f"Status: {message}")
        
        if "Connected" in message:
            self._update_connection_ui(True)
        elif "disconnected" in message.lower():
            self._update_connection_ui(False)

    def _update_connection_ui(self, connected: bool):
        """Update UI based on connection status"""
        if connected:
            self.btn_connect.setText("Disconnect Reader")
            self.btn_connect.setIcon(QIcon("icons/disconnect.png"))
            self.btn_scan.setEnabled(True)
        else:
            self.btn_connect.setText("Connect to Reader")
            self.btn_connect.setIcon(QIcon("icons/connect.png"))
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("Start Scanning")

    def _handle_rfid_error(self, error_msg: str):
        """Handle RFID reader errors"""
        print(f"RFID Error: {error_msg}")
        self._update_connection_ui(False)

    def _refresh_com_ports(self):
        """Refresh list of available COM ports"""
        check_connection.testConnect()
        self.cb_com_ports.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.cb_com_ports.addItem(f"{port.device} - {port.description}")
        
        if not ports:
            self.cb_com_ports.addItem("No COM ports found")

    def toggle_rfid_connection(self):
        """Toggle RFID reader connection"""
        if self.rfid_thread.connection_established:
            self._disconnect_reader()
        else:
            selected_port = self.cb_com_ports.currentText().split(' - ')[0]
            if selected_port and "No COM ports" not in selected_port:
                self._connect_reader(selected_port)
            else:
                QMessageBox.warning(self, "Warning", "Please select a valid COM port")

    def _connect_reader(self, port: str):
        """Connect to RFID reader"""
        try:
            check_connection.testConnect()
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Connecting...")
            QApplication.processEvents()
            
            if not self.rfid_thread.connect_reader(port):
                raise Exception("Failed to connect reader")
                
            if not self.rfid_thread.isRunning():
                self.rfid_thread.start()
                
            time.sleep(0.5)  # Tunggu koneksi stabil
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")
            self.rfid_thread.disconnect_reader()
        finally:
            self.btn_connect.setEnabled(True)

    def _disconnect_reader(self):
        """Disconnect from RFID reader"""
        try:
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Disconnecting...")
            QApplication.processEvents()
            
            if self.rfid_thread.isRunning:
                self.rfid_thread.stop_scanning()
                
            self.rfid_thread.quit()
            self.rfid_thread.wait(1000)
            
            if self.rfid_thread.isRunning():
                self.rfid_thread.terminate()
                
            self.rfid_thread.disconnect_reader()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to disconnect: {str(e)}")
        finally:
            self.btn_connect.setEnabled(True)

    def toggle_scanning(self):
        """Start or stop RFID scanning"""
        if not self.rfid_thread.connection_established:
            QMessageBox.warning(self, "Warning", "Please connect to reader first")
            return
            
        if self.rfid_thread._should_scan:
            self.rfid_thread.stop_scanning()
            self.btn_scan.setText("Start Scanning")
            self.btn_scan.setIcon(QIcon("icons/rfid.png"))
        else:
            self.rfid_thread.start_scanning()
            self.btn_scan.setText("Stop Scanning")
            self.btn_scan.setIcon(QIcon("icons/stop.png"))

    def proceed_to_checkout(self):
        """Pindah ke halaman login untuk checkout"""
        self.stack.setCurrentWidget(self.login_page)

    def process_checkout(self):
        """Proses login user dan checkout"""
        email = self.txt_email.text().strip()
        password = self.txt_password.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "Warning", "Email and password are required")
            return
            
        try:
            # Buat progress dialog
            progress = QProgressDialog("Processing checkout...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()
            
            # 1. Login untuk mendapatkan token
            login_response = requests.post(
                'http://localhost:5000/api/auth/login',
                json={'email': email, 'password': password},
                timeout=10
            )
            
            if login_response.status_code != 200:
                error_msg = login_response.json().get('message', 'Login failed')
                raise Exception(error_msg)
                
            login_data = login_response.json()
            self.token = login_data['token']
            self.user_data = {
                'username': login_data.get('username'),
                'role': login_data.get('role')
            }
            
            # 2. Proses checkout dengan token
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'rfidTags': [
                    {'uid': asset['rfidTag']['uid'], 'epc': asset['rfidTag']['epc']}
                    for asset in self.scanned_assets
                ]
            }
            
            checkout_response = requests.post(
                'http://localhost:5000/api/checkout/checkout',
                headers=headers,
                json=payload,
                timeout=10
            )
            
            progress.close()
            
            if checkout_response.status_code == 200:
                checkout_data = checkout_response.json()
                self._show_checkout_summary(checkout_data)
                self.stack.setCurrentWidget(self.checkout_page)
            else:
                error_msg = checkout_response.json().get('message', 'Checkout failed')
                raise Exception(error_msg)
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Checkout failed: {str(e)}")

    def _show_checkout_summary(self, checkout_data):
        """Tampilkan ringkasan checkout"""
        # Update user info
        self.lbl_user_info.setText(f"User: {checkout_data.get('username', '')}")
        
        # Update items table
        self.checkout_table.setRowCount(0)
        for item in checkout_data.get('items', []):
            row = self.checkout_table.rowCount()
            self.checkout_table.insertRow(row)
            self.checkout_table.setItem(row, 0, QTableWidgetItem(item.get('name', '')))
            self.checkout_table.setItem(row, 1, QTableWidgetItem("1"))  # Quantity
            self.checkout_table.setItem(row, 2, QTableWidgetItem(f"Rp {item.get('price', 0):,}"))
        
        # Update total
        self.lbl_total.setText(f"Total Amount: Rp {checkout_data.get('totalAmount', 0):,}")
        
        # Tampilkan QR code jika ada
        qr_code = checkout_data.get('paymentQRCode', '')
        if qr_code and qr_code.startswith('data:image/png;base64,'):
            try:
                # Decode base64 image
                base64_data = qr_code.split(',')[1]
                image_data = base64.b64decode(base64_data)
                
                # Convert ke QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                
                # Scale dan tampilkan
                self.lbl_qr_code.setPixmap(pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
            except Exception as e:
                print(f"Error displaying QR code: {str(e)}")

    def complete_checkout(self):
        """Selesaikan proses checkout"""
        QMessageBox.information(self, "Success", "Checkout completed successfully")
        
        # Reset semua state
        self.scanned_assets = []
        self.products_table.setRowCount(0)
        self.btn_checkout.setEnabled(False)
        self.txt_email.clear()
        self.txt_password.clear()
        
        # Kembali ke halaman scanning
        self.stack.setCurrentWidget(self.scan_page)

    def go_to_main_menu(self):
        """Kembali ke main menu"""
        # Implementasi disesuaikan dengan aplikasi utama
        pass

    def closeEvent(self, event):
        """Clean up when window is closed"""
        try:
            if self.rfid_thread.isRunning():
                self.rfid_thread.stop_thread()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            
        super().closeEvent(event)
