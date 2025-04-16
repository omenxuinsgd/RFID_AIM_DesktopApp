from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QComboBox,
    QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit,
    QGroupBox, QScrollArea, QStackedWidget, QApplication, 
    QCheckBox, QFrame, QProgressDialog
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QBrush, QColor
import serial.tools.list_ports
from typing import Iterator
from response import hex_readable, Response, WorkMode, InventoryWorkMode, InventoryMemoryBank
from transport import SerialTransport
from reader import Reader
import check_connection
import time

class RFIDReaderThread(QThread):
    tag_scanned = pyqtSignal(dict)  # {'uid': '...', 'epc': '...', 'tid': '...'}
    reader_status = pyqtSignal(str)  # Status messages
    error_occurred = pyqtSignal(str)  # Error messages

    def __init__(self):
        super().__init__()
        self.reader = None
        self.transport = None
        self.is_running = False
        self.current_port = None
        self.power_level = 30  # Default power level
        self.should_scan = False  # Flag untuk kontrol scanning

    def connect_reader(self, port: str):
        """Initialize connection to RFID reader""" 
        try:
            check_connection.testConnect()
            print(f"DEBUG: Connecting to RFID reader on port {port}...")
            self.current_port = port
            self.transport = SerialTransport(port, 57600)
            self.reader = Reader(self.transport)
            
            # Configure reader settings
            print("DEBUG: Setting power level...")
            response_power = self.reader.set_power(self.power_level)
            if response_power.status != 0x00:
                raise Exception(f"Failed to set power: {hex(response_power.status)}")
            
            print("DEBUG: Power level set successfully.")

            print("DEBUG: Setting work mode to ANSWER_MODE...")
            work_mode = self.reader.work_mode()
            work_mode.inventory_work_mode = InventoryWorkMode.ANSWER_MODE
            response_mode = self.reader.set_work_mode(work_mode)
            if response_mode.status != 0x00:
                raise Exception(f"Failed to set work mode: {hex(response_mode.status)}")
            print("DEBUG: Work mode set successfully.")
            self.reader_status.emit(f"Connected to {port} at 57600 baud")
            print(f"DEBUG: Successfully connected to {port}.")
            return True
            
        except Exception as e:
            print(f"DEBUG: Connection failed with error: {str(e)}")
            self.error_occurred.emit(f"Connection failed: {str(e)}")
            return False
    
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

    def start_scanning(self):
        """Start the scanning process"""
        self.should_scan = True
        self.is_running = True
        self.reader_status.emit("Ready to scan")

    def stop_scanning(self):
        """Stop the scanning process"""
        self.should_scan = False
        self.is_running = False
        self.reader_status.emit("Scan stopped")

    def run(self):
        """Main thread loop"""
        try:
            if not self.reader:
                raise Exception("Reader not connected")
            
            while True:
                if self.should_scan:
                    self._perform_scan()
                time.sleep(0.1)  # Reduce CPU usage
                
        except Exception as e:
            print(f"DEBUG: Thread error: {str(e)}")
            self.error_occurred.emit(f"Thread error: {str(e)}")
        finally:
            self.is_running = False
            self.reader_status.emit("Thread stopped")

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

    def _perform_scan(self):
        """Perform actual tag scanning"""
        try:
            self.reader_status.emit("Scanning for tags...")
            print("DEBUG: Scanning for tags...")
            
            # Inventory tags
            tags = list(self.reader.inventory_answer_mode())  # Convert generator to list
            if not tags:
                print("DEBUG: No tags detected.")
                return

            print(f"DEBUG: Detected {len(tags)} tag(s).")

            for tag in tags:
                epc = hex_readable(tag)
                print(f"DEBUG: EPC detected: {epc}")
                tid = self._read_tid(tag)
                print(f"DEBUG: TID read: {tid}")
                self.tag_scanned.emit({
                    'epc': epc,
                    'tid': tid,
                    'uid': tid  # Using TID as UID if needed
                })
                
        except Exception as e:
            self.disconnect_reader()
            print(f"DEBUG: Scan error: {str(e)}")
            self.error_occurred.emit(f"Scan error: {str(e)}")
            self.stop_scanning()

class ManagementPage(QWidget):
    # Signal untuk menerima data RFID
    rfid_scanned = pyqtSignal(dict)  # Format: {'uid': '...', 'epc': '...'}
    reader_connected = pyqtSignal(bool)  # True if connected

    def __init__(self, db, rfid_reader):
        super().__init__()
        self.db = db
        self.rfid_reader = rfid_reader  # RFID reader instance
        self.current_asset_id = None
        self.is_reader_connected = False
        self.rfid_thread = RFIDReaderThread()
        
        # Main stacked widget for page navigation
        self.stack = QStackedWidget()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.stack)
        
        # Initialize all pages
        self.main_page = self._create_main_page()
        self.input_page = self._create_input_page()
        self.update_page = self._create_update_page()
        
        # Add pages to stack
        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.input_page)
        self.stack.addWidget(self.update_page)
        
        # Connect RFID signal
        self.rfid_scanned.connect(self._handle_rfid_scan)

        self.reader_connected.connect(self._handle_reader_connection)
        
        # Show main page first
        self.stack.setCurrentWidget(self.main_page)
             
        # Load initial data
        self.load_assets()

        self._setup_rfid_connections()

    def _handle_rfid_scan(self, tag_data: dict):
        """Handle scanned RFID tag data"""
        print(f"DEBUG: RFID tag scanned: {tag_data}")
        current_page = self.stack.currentWidget()
        
        if current_page == self.input_page:
            self.txt_uid.setText(tag_data.get('uid', ''))
            self.txt_epc.setText(tag_data.get('epc', ''))
        elif current_page == self.update_page:
            self.update_txt_uid.setText(tag_data.get('uid', ''))
            self.update_txt_epc.setText(tag_data.get('epc', ''))
        
        # Auto-stop scanning after successful read
        if self.rfid_thread.is_running:
            self.rfid_thread.stop_scanning()
            self.btn_scan.setText("Scan RFID Tag")

    def _setup_rfid_connections(self):
        """Connect RFID thread signals to slots"""
        self.rfid_thread.tag_scanned.connect(self._handle_rfid_scan)
        self.rfid_thread.reader_status.connect(self._update_reader_status)
        self.rfid_thread.error_occurred.connect(self._handle_rfid_error)
        self.reader_connected.connect(self._handle_reader_connection)

    def _update_reader_status(self, message: str):
        """Update connection status message"""
        print(f"DEBUG: Reader status updated: {message}")
        self.lbl_connection_status.setText(f"Status: {message}")
        
        # Enable scan button when connected
        if "Connected" in message:
            self._update_connection_ui(True)
        elif "disconnected" in message.lower():
            self._update_connection_ui(False)

    def _update_connection_ui(self, connected):
        """Update UI elements based on connection status"""
        if connected:
            self.btn_connect.setText("Disconnect Reader")
            self.btn_connect.setIcon(QIcon("icons/disconnect.png"))
            self.lbl_connection_status.setText("Status: Connected")
            self.btn_scan.setEnabled(True)
        else:
            self.btn_connect.setText("Connect to Reader")
            self.btn_connect.setIcon(QIcon("icons/connect.png"))
            self.lbl_connection_status.setText("Status: Not connected")
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("Scan RFID Tag")
            
            # Clear RFID fields
            self.txt_uid.clear()
            self.txt_epc.clear()

    def _handle_rfid_error(self, error_msg: str):
        """Handle RFID reader errors"""
        print(f"DEBUG: RFID error occurred: {error_msg}")
        QMessageBox.critical(self, "RFID Error", error_msg)
        self._update_connection_ui(False)
    
    def closeEvent(self, event):
        """Clean up when window is closed"""
        try:
            if self.rfid_thread.isRunning():
                self.rfid_thread.stop_scanning()
                self.rfid_thread.quit()
                self.rfid_thread.wait(1000)
                
                if self.rfid_thread.isRunning():
                    self.rfid_thread.terminate()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            
        super().closeEvent(event)

    def _handle_reader_connection(self, connected):
        """Update UI based on reader connection status"""
        if connected:
            self.btn_connect.setText("Disconnect Reader")
            self.btn_connect.setIcon(QIcon("icons/disconnect.png"))
            self.lbl_connection_status.setText("Status: Connected - Ready")
            self.btn_scan.setEnabled(True)
            self.btn_scan.setText("Scan RFID Tag")
            self.is_reader_connected = True
        else:
            self.btn_connect.setText("Connect to Reader")
            self.btn_connect.setIcon(QIcon("icons/connect.png"))
            self.lbl_connection_status.setText("Status: Not connected")
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("Scan RFID Tag")
            self.is_reader_connected = False
        
        # Clear RFID fields if disconnected
        if self.stack.currentWidget() == self.input_page:
            self.txt_uid.clear()
            self.txt_epc.clear()
        elif self.stack.currentWidget() == self.update_page:
            self.update_txt_uid.clear()
            self.update_txt_epc.clear()

    def _create_main_page(self):
        """Create the main management page with asset table"""
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
        lbl_title = QLabel("Asset Management")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("Add New Asset")
        self.btn_add.setIcon(QIcon("icons/add.png"))
        self.btn_add.clicked.connect(lambda: self.stack.setCurrentWidget(self.input_page))
        btn_layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Edit Asset")
        self.btn_edit.setIcon(QIcon("icons/edit.png"))
        self.btn_edit.clicked.connect(self.prepare_update_form)
        btn_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Delete Asset")
        self.btn_delete.setIcon(QIcon("icons/delete.png"))
        self.btn_delete.clicked.connect(self.delete_asset)
        btn_layout.addWidget(self.btn_delete)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setIcon(QIcon("icons/refresh.png"))
        self.btn_refresh.clicked.connect(self.load_assets)
        btn_layout.addWidget(self.btn_refresh)

        layout.addLayout(btn_layout)

        # Asset table
        self.table_assets = QTableWidget()
        self.table_assets.setColumnCount(11)
        self.table_assets.setHorizontalHeaderLabels([
        "ID", "Nama", "RFID UID", "Kategori", 
        "Status", "Jumlah", "Unit", "Harga", 
        "Tanggal Pembelian", "Lokasi", "Masa Garansi"
        ])
        # Atur lebar kolom
        self.table_assets.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        self.table_assets.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Nama
        self.table_assets.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # UID
        self.table_assets.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)  # Masa Garansi
        layout.addWidget(self.table_assets)

        # Enable custom sorting for price column
        self.table_assets.setSortingEnabled(True)
        self.table_assets.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table_assets.horizontalHeader().sectionClicked.connect(self._handle_header_click)

        # Style table
        self.table_assets.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 5px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 3px;
            }
        """)
        
        # Alternating row colors
        self.table_assets.setAlternatingRowColors(True)

        return page
    
    def _handle_header_click(self, logical_index):
        """Handle custom sorting for price column"""
        if logical_index == 7:  # Price column
            self.table_assets.sortItems(logical_index, self.table_assets.horizontalHeader().sortIndicatorOrder())

    def _create_input_page(self):
        """Create the new asset input form page"""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Back button
        self.btn_back = QPushButton("Back to Asset List")
        self.btn_back.setIcon(QIcon("icons/back.png"))
        self.btn_back.setStyleSheet("""
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
        
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.main_page))
        layout.addWidget(self.btn_back, alignment=Qt.AlignmentFlag.AlignLeft)

        # Title
        lbl_title = QLabel("Add New Asset")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scroll area for the form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        scroll.setWidget(form_container)

        # RFID Reader Connection Group
        grp_connection = QGroupBox("RFID Reader Connection")
        connection_layout = QVBoxLayout(grp_connection)
        
        # COM Port Selection
        layout_com = QHBoxLayout()
        self.cb_com_ports = QComboBox()
        self._refresh_com_ports()
        layout_com.addWidget(QLabel("COM Port:"))
        layout_com.addWidget(self.cb_com_ports)
        
        # Refresh COM Ports Button
        btn_refresh_com = QPushButton("Refresh Ports")
        btn_refresh_com.clicked.connect(self._refresh_com_ports)
        layout_com.addWidget(btn_refresh_com)
        connection_layout.addLayout(layout_com)

        # Connect/Disconnect Button
        self.btn_connect = QPushButton("Connect to Reader")
        self.btn_connect.setIcon(QIcon("icons/connect.png"))
        self.btn_connect.clicked.connect(self._toggle_reader_connection)
        connection_layout.addWidget(self.btn_connect)
        
        # Connection Status
        self.lbl_connection_status = QLabel("Status: Not connected")
        connection_layout.addWidget(self.lbl_connection_status)
        
        form_layout.addWidget(grp_connection)

        # RFID Information
        grp_rfid = QGroupBox("RFID Information")
        layout_rfid = QHBoxLayout(grp_rfid)

        # Scan Button
        self.btn_scan = QPushButton("Scan RFID Tag")
        self.btn_scan.setIcon(QIcon("icons/rfid.png"))
        self.btn_scan.clicked.connect(self._start_rfid_scan)
        self.btn_scan.setEnabled(False)  # Disabled by default
        layout_rfid.addWidget(self.btn_scan)
        
        # UID Field (Read-only)
        layout_uid = QHBoxLayout()
        self.txt_uid = QLineEdit()
        self.txt_uid.setPlaceholderText("Will be filled by RFID scan")
        self.txt_uid.setReadOnly(True)  # Tidak bisa diinput manual
        layout_uid.addWidget(QLabel("UID:"))
        layout_uid.addWidget(self.txt_uid)
        layout_rfid.addLayout(layout_uid)
        
        # EPC Field (Read-only)
        layout_epc = QHBoxLayout()
        self.txt_epc = QLineEdit()
        self.txt_epc.setPlaceholderText("Will be filled by RFID scan")
        self.txt_epc.setReadOnly(True)  # Tidak bisa diinput manual
        layout_epc.addWidget(QLabel("EPC:"))
        layout_epc.addWidget(self.txt_epc)
        layout_rfid.addLayout(layout_epc)
        
        form_layout.addWidget(grp_rfid)

        # Basic Information
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Asset Name")
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.txt_name)

        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Description")
        form_layout.addWidget(QLabel("Description:"))
        form_layout.addWidget(self.txt_desc)

        # Category and Status
        layout_info = QHBoxLayout()
        
        self.cb_category = QComboBox()
        self.cb_category.addItems([
            "electronics", "furniture", "tools", 
            "machinery", "consumables", "documents", "other"
        ])
        layout_info.addWidget(QLabel("Category:"))
        layout_info.addWidget(self.cb_category)
        
        self.cb_status = QComboBox()
        self.cb_status.addItems(['tersedia', 'dipinjam', 'rusak', 'terjual', 'hilang', 'maintenance/diperbaiki'])
        layout_info.addWidget(QLabel("Status:"))
        layout_info.addWidget(self.cb_status)
        
        form_layout.addLayout(layout_info)

        # Quantity and Unit
        layout_qty = QHBoxLayout()
        
        self.spn_qty = QSpinBox()
        self.spn_qty.setMinimum(1)
        self.spn_qty.setValue(1)
        layout_qty.addWidget(QLabel("Quantity:"))
        layout_qty.addWidget(self.spn_qty)
        
        self.cb_unit = QComboBox()
        self.cb_unit.addItems(["pcs", "pack"])
        self.cb_unit.currentTextChanged.connect(self._toggle_product_input)
        layout_qty.addWidget(QLabel("Unit:"))
        layout_qty.addWidget(self.cb_unit)
        
        form_layout.addLayout(layout_qty)

        # Products (visible only when unit is pack)
        self.grp_products = QGroupBox("Products in Pack")
        self.grp_products.setVisible(False)
        layout_products = QVBoxLayout(self.grp_products)
        
        self.txt_products = QTextEdit()
        self.txt_products.setPlaceholderText("Enter one product per line")
        layout_products.addWidget(self.txt_products)
        
        form_layout.addWidget(self.grp_products)

        # Price and Dates
        layout_details = QHBoxLayout()
        
        self.spn_price = QDoubleSpinBox()
        self.spn_price.setPrefix("Rp ")
        self.spn_price.setMaximum(999999999)
        layout_details.addWidget(QLabel("Price:"))
        layout_details.addWidget(self.spn_price)
        
        self.dt_purchase = QDateEdit()
        self.dt_purchase.setCalendarPopup(True)
        self.dt_purchase.setDate(QDate.currentDate())
        layout_details.addWidget(QLabel("Purchase Date:"))
        layout_details.addWidget(self.dt_purchase)
        
        form_layout.addLayout(layout_details)

        # Location
        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("Location")
        form_layout.addWidget(QLabel("Location:"))
        form_layout.addWidget(self.txt_location)

        # Masa Garansi Group Box (opsional)
        grp_garansi = QGroupBox("Masa Garansi (Opsional)")
        layout_garansi = QVBoxLayout(grp_garansi)

        # Checkbox untuk aktifkan masa garansi
        self.chk_garansi = QCheckBox("Aktifkan Masa Garansi")
        self.chk_garansi.stateChanged.connect(self._toggle_garansi_fields)
        layout_garansi.addWidget(self.chk_garansi)

        # Frame untuk fields garansi
        self.garansi_frame = QFrame()
        layout_garansi_frame = QHBoxLayout(self.garansi_frame)

        # Tanggal Mulai Garansi
        self.dt_garansi_mulai = QDateEdit()
        self.dt_garansi_mulai.setCalendarPopup(True)
        self.dt_garansi_mulai.setDate(QDate.currentDate())
        layout_garansi_frame.addWidget(QLabel("Mulai:"))
        layout_garansi_frame.addWidget(self.dt_garansi_mulai)

        # Tanggal Akhir Garansi
        self.dt_garansi_akhir = QDateEdit()
        self.dt_garansi_akhir.setCalendarPopup(True)
        self.dt_garansi_akhir.setDate(QDate.currentDate().addYears(1))  # Default 1 tahun
        layout_garansi_frame.addWidget(QLabel("Sampai:"))
        layout_garansi_frame.addWidget(self.dt_garansi_akhir)

        # Button untuk set 1 tahun
        btn_setahun = QPushButton("Set 1 Tahun")
        btn_setahun.clicked.connect(self._set_garansi_1tahun)
        layout_garansi_frame.addWidget(btn_setahun)

        layout_garansi.addWidget(self.garansi_frame)
        self.garansi_frame.setVisible(False)  # Awalnya disembunyikan
        form_layout.addWidget(grp_garansi)

        # Form buttons
        layout_buttons = QHBoxLayout()
        
        btn_submit = QPushButton("Submit")
        btn_submit.clicked.connect(self._submit_asset)
        layout_buttons.addWidget(btn_submit)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(lambda: self.stack.setCurrentWidget(self.main_page))
        layout_buttons.addWidget(btn_cancel)
        
        form_layout.addLayout(layout_buttons)
        form_layout.addStretch()

        layout.addWidget(scroll)
        return page
    
    def _refresh_com_ports(self):
        """Refresh list of available COM ports"""
        self.cb_com_ports.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.cb_com_ports.addItem(f"{port.device} - {port.description}")
        
        if not ports:
            self.cb_com_ports.addItem("No COM ports found")

    def _toggle_reader_connection(self):
        """Connect or disconnect from RFID reader"""
        if self.rfid_thread.isRunning():
            # Jika sudah terhubung, lakukan disconnect
            self._disconnect_reader()
        else:
            # Jika belum terhubung, lakukan connect
            selected_port = self.cb_com_ports.currentText().split(' - ')[0]
            if selected_port and "No COM ports" not in selected_port:
                self._connect_reader(selected_port)
            else:
                QMessageBox.warning(self, "Warning", "Please select a valid COM port")

    def _connect_reader(self, port: str):
        """Connect to RFID reader"""
        try:
            check_connection.testConnect()
            # Update UI untuk status connecting
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Connecting...")
            self.lbl_connection_status.setText("Status: Connecting...")
            QApplication.processEvents()  # Memastikan UI update
            
            # Setup dan mulai thread
            self.rfid_thread.current_port = port
            if not self.rfid_thread.connect_reader(port):
                raise Exception("Failed to initialize reader connection")
                
            # Mulai thread scanning
            self.rfid_thread.start()
            
            # Tunggu sebentar untuk memastikan koneksi stabil
            time.sleep(0.5)
            
            # Update status
            self.reader_connected.emit(True)
            
        except Exception as e:
            print(f"Connection error: {str(e)}")
            self.rfid_thread.disconnect_reader()
            self.reader_connected.emit(False)
            QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")
        finally:
            self.btn_connect.setEnabled(True)

    def _disconnect_reader(self):
        """Disconnect from RFID reader"""
        try:
            # Update UI
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Disconnecting...")
            QApplication.processEvents()
            
            # Stop scanning dan disconnect
            if self.rfid_thread.is_running:
                self.rfid_thread.stop_scanning()
                
            # Beri waktu untuk thread berhenti
            self.rfid_thread.quit()
            self.rfid_thread.wait(1000)  # Tunggu maksimal 1 detik
            
            # Pastikan reader benar-benar terputus
            if self.rfid_thread.isRunning():
                self.rfid_thread.terminate()
                
            # Update status
            self.reader_connected.emit(False)
            self.rfid_thread.disconnect_reader()
            
        except Exception as e:
            print(f"Disconnection error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to disconnect: {str(e)}")
        finally:
            self.btn_connect.setEnabled(True)
                  
    def _toggle_rfid_scan(self):
        """Start or stop RFID scanning"""
        if not self.is_reader_connected:
            QMessageBox.warning(self, "Warning", "Please connect to reader first")
            return
            
        if self.rfid_thread.is_running:
            self.rfid_thread.stop_scanning()
            self.btn_scan.setText("Scan RFID Tag")
        else:
            self.rfid_thread.start()
            self.btn_scan.setText("Stop Scanning")
            
    def _handle_reader_connection(self, connected):
        """Update UI based on reader connection status"""
        if connected:
            self.btn_connect.setText("Disconnect Reader")
            self.btn_connect.setIcon(QIcon("icons/disconnect.png"))
            self.lbl_connection_status.setText("Status: Connected")
            self.btn_scan.setEnabled(True)
            self.is_reader_connected = True
        else:
            self.btn_connect.setText("Connect to Reader")
            self.btn_connect.setIcon(QIcon("icons/connect.png"))
            self.lbl_connection_status.setText("Status: Not connected")
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("Scan RFID Tag")
            self.is_reader_connected = False
            
            # Clear RFID fields if disconnected
            if self.stack.currentWidget() == self.input_page:
                self.txt_uid.clear()
                self.txt_epc.clear()
            elif self.stack.currentWidget() == self.update_page:
                self.update_txt_uid.clear()
                self.update_txt_epc.clear()

    def _start_rfid_scan(self):
        """Start or stop RFID scanning based on current state"""
        if not self.is_reader_connected:
            QMessageBox.warning(self, "Warning", "Please connect to RFID reader first")
            return
            
        if self.rfid_thread.is_running and self.rfid_thread.should_scan:
            # Stop scanning
            self.rfid_thread.stop_scanning()
            self.btn_scan.setText("Scan RFID Tag")
            self.btn_scan.setIcon(QIcon("icons/rfid.png"))
        else:
            # Start scanning
            self.btn_scan.setText("Stop Scanning")
            self.btn_scan.setIcon(QIcon("icons/stop.png"))
            self.rfid_thread.start_scanning()

    def _create_update_page(self):
        """Create the asset update form page"""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Back button
        btn_back = QPushButton("Back to Asset List")
        btn_back.setIcon(QIcon("icons/back.png"))
        btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.main_page))
        layout.addWidget(btn_back, alignment=Qt.AlignmentFlag.AlignLeft)

        # Title
        lbl_title = QLabel("Edit Asset")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scroll area for the form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        scroll.setWidget(form_container)

        # Asset ID display
        self.lbl_asset_id = QLabel()
        form_layout.addWidget(QLabel("Asset ID:"))
        form_layout.addWidget(self.lbl_asset_id)

        # Add all the same fields as input form but with update_ prefix
        # RFID Information
        grp_rfid = QGroupBox("RFID Information")
        layout_rfid = QHBoxLayout(grp_rfid)

        # Scan Button
        btn_scan = QPushButton("Re-scan RFID Tag")
        btn_scan.setIcon(QIcon("icons/rfid.png"))
        btn_scan.clicked.connect(self._start_rfid_scan)
        layout_rfid.addWidget(btn_scan)
        
        # UID Field (Read-only)
        layout_uid = QHBoxLayout()
        self.update_txt_uid = QLineEdit()
        self.update_txt_uid.setReadOnly(True)
        layout_uid.addWidget(QLabel("UID:"))
        layout_uid.addWidget(self.update_txt_uid)
        layout_rfid.addLayout(layout_uid)
        
        # EPC Field (Read-only)
        layout_epc = QHBoxLayout()
        self.update_txt_epc = QLineEdit()
        self.update_txt_epc.setReadOnly(True)
        layout_epc.addWidget(QLabel("EPC:"))
        layout_epc.addWidget(self.update_txt_epc)
        layout_rfid.addLayout(layout_epc)
        
        form_layout.addWidget(grp_rfid)

        # Basic Information
        self.update_txt_name = QLineEdit()
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.update_txt_name)

        self.update_txt_desc = QTextEdit()
        form_layout.addWidget(QLabel("Description:"))
        form_layout.addWidget(self.update_txt_desc)

        # Category and Status
        layout_info = QHBoxLayout()
        
        self.update_cb_category = QComboBox()
        self.update_cb_category.addItems([
            "electronics", "furniture", "tools", 
            "machinery", "consumables", "documents", "other"
        ])
        layout_info.addWidget(QLabel("Category:"))
        layout_info.addWidget(self.update_cb_category)
        
        self.update_cb_status = QComboBox()
        self.update_cb_status.addItems([
            "available", "borrowed", "maintenance", "disposed", "lost"
        ])
        layout_info.addWidget(QLabel("Status:"))
        layout_info.addWidget(self.update_cb_status)
        
        form_layout.addLayout(layout_info)

        # Quantity and Unit
        layout_qty = QHBoxLayout()
        
        self.update_spn_qty = QSpinBox()
        self.update_spn_qty.setMinimum(1)
        layout_qty.addWidget(QLabel("Quantity:"))
        layout_qty.addWidget(self.update_spn_qty)
        
        self.update_cb_unit = QComboBox()
        self.update_cb_unit.addItems(["pcs", "pack"])
        self.update_cb_unit.currentTextChanged.connect(self._toggle_update_product_input)
        layout_qty.addWidget(QLabel("Unit:"))
        layout_qty.addWidget(self.update_cb_unit)
        
        form_layout.addLayout(layout_qty)

        # Products (visible only when unit is pack)
        self.update_grp_products = QGroupBox("Products in Pack")
        self.update_grp_products.setVisible(False)
        layout_products = QVBoxLayout(self.update_grp_products)
        
        self.update_txt_products = QTextEdit()
        layout_products.addWidget(self.update_txt_products)
        
        form_layout.addWidget(self.update_grp_products)

        # Price and Dates
        layout_details = QHBoxLayout()
        
        self.update_spn_price = QDoubleSpinBox()
        self.update_spn_price.setPrefix("Rp ")
        self.update_spn_price.setMaximum(999999999)
        layout_details.addWidget(QLabel("Price:"))
        layout_details.addWidget(self.update_spn_price)
        
        self.update_dt_purchase = QDateEdit()
        self.update_dt_purchase.setCalendarPopup(True)
        layout_details.addWidget(QLabel("Purchase Date:"))
        layout_details.addWidget(self.update_dt_purchase)
        
        form_layout.addLayout(layout_details)

        # Location
        self.update_txt_location = QLineEdit()
        form_layout.addWidget(QLabel("Location:"))
        form_layout.addWidget(self.update_txt_location)

        # Masa Garansi Group Box (opsional)
        update_grp_garansi = QGroupBox("Masa Garansi (Opsional)")
        update_layout_garansi = QVBoxLayout(update_grp_garansi)

        # Checkbox untuk aktifkan masa garansi
        self.update_chk_garansi = QCheckBox("Aktifkan Masa Garansi")
        self.update_chk_garansi.stateChanged.connect(self._toggle_update_garansi_fields)
        update_layout_garansi.addWidget(self.update_chk_garansi)

        # Frame untuk fields garansi
        self.update_garansi_frame = QFrame()
        update_layout_garansi_frame = QHBoxLayout(self.update_garansi_frame)

        # Tanggal Mulai Garansi
        self.update_dt_garansi_mulai = QDateEdit()
        self.update_dt_garansi_mulai.setCalendarPopup(True)
        self.update_dt_garansi_mulai.setDate(QDate.currentDate())
        update_layout_garansi_frame.addWidget(QLabel("Mulai:"))
        update_layout_garansi_frame.addWidget(self.update_dt_garansi_mulai)

        # Tanggal Akhir Garansi
        self.update_dt_garansi_akhir = QDateEdit()
        self.update_dt_garansi_akhir.setCalendarPopup(True)
        self.update_dt_garansi_akhir.setDate(QDate.currentDate().addYears(1))
        update_layout_garansi_frame.addWidget(QLabel("Sampai:"))
        update_layout_garansi_frame.addWidget(self.update_dt_garansi_akhir)

        # Button untuk set 1 tahun
        update_btn_setahun = QPushButton("Set 1 Tahun")
        update_btn_setahun.clicked.connect(self._update_set_garansi_1tahun)
        update_layout_garansi_frame.addWidget(update_btn_setahun)

        update_layout_garansi.addWidget(self.update_garansi_frame)
        self.update_garansi_frame.setVisible(False)
        form_layout.addWidget(update_grp_garansi)

        # Form buttons
        layout_buttons = QHBoxLayout()
        
        btn_update = QPushButton("Update")
        btn_update.clicked.connect(self._update_asset)
        layout_buttons.addWidget(btn_update)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(lambda: self.stack.setCurrentWidget(self.main_page))
        layout_buttons.addWidget(btn_cancel)
        
        form_layout.addLayout(layout_buttons)
        form_layout.addStretch()

        layout.addWidget(scroll)
        return page
    
    def _toggle_update_garansi_fields(self, state):
        """Toggle visibility of warranty period fields in update form"""
        self.update_garansi_frame.setVisible(state == Qt.CheckState.Checked.value)

    def _update_set_garansi_1tahun(self):
        """Set warranty period to 1 year from start date in update form"""
        start_date = self.update_dt_garansi_mulai.date()
        end_date = start_date.addYears(1)
        self.update_dt_garansi_akhir.setDate(end_date)
    
    def _toggle_garansi_fields(self, state):
        """Toggle visibility of warranty period fields"""
        self.garansi_frame.setVisible(state == Qt.CheckState.Checked.value)

    def _set_garansi_1tahun(self):
        """Set warranty period to 1 year from start date"""
        start_date = self.dt_garansi_mulai.date()
        end_date = start_date.addYears(1)
        self.dt_garansi_akhir.setDate(end_date)
    
    def _toggle_product_input(self, unit):
        """Toggle products input visibility based on unit selection"""
        self.grp_products.setVisible(unit == "pack")

    def _toggle_update_product_input(self, unit):
        """Toggle products input visibility in update form"""
        self.update_grp_products.setVisible(unit == "pack")

    def go_to_main_menu(self):
        """Callback for returning to main menu (set from main application)"""
        pass

    def load_assets(self):
        """Load assets from API and display in table"""
        try:
            # Clear table
            self.table_assets.setRowCount(0)
            
            # Show loading state
            self.table_assets.setSortingEnabled(False)
            loading_row = self.table_assets.rowCount()
            self.table_assets.insertRow(loading_row)
            loading_item = QTableWidgetItem("Memuat data...")
            loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_assets.setItem(loading_row, 0, loading_item)
            self.table_assets.setSpan(loading_row, 0, 1, self.table_assets.columnCount())
            QApplication.processEvents()

            # Fetch data from API
            assets = self._get_assets_from_api()
            
            # Remove loading row
            self.table_assets.removeRow(loading_row)
            
            if not assets:
                self.table_assets.setRowCount(0)
                return

            # Populate table
            for asset in assets:
                row = self.table_assets.rowCount()
                self.table_assets.insertRow(row)
                
                # Handle masaGaransi if exists
                masa_garansi = asset.get('masaGaransi', {})
                garansi_text = ""
                if masa_garansi:
                    garansi_text = f"{masa_garansi.get('from', '')} s/d {masa_garansi.get('to', '')}"

                self.table_assets.setItem(row, 0, QTableWidgetItem(str(asset.get('_id', ''))))
                self.table_assets.setItem(row, 1, QTableWidgetItem(asset.get('name', '')))
                self.table_assets.setItem(row, 2, QTableWidgetItem(asset.get('rfidTag', {}).get('uid', '')))
                self.table_assets.setItem(row, 3, QTableWidgetItem(asset.get('kategori', '')))
                self.table_assets.setItem(row, 4, QTableWidgetItem(asset.get('status', '')))
                self.table_assets.setItem(row, 5, QTableWidgetItem(str(asset.get('jumlah', 1))))
                self.table_assets.setItem(row, 6, QTableWidgetItem(asset.get('unit', 'pcs')))
                
                # Format price with currency
                price = asset.get('price', 0)
                price_item = QTableWidgetItem(f"Rp {price:,.0f}")
                price_item.setData(Qt.ItemDataRole.UserRole, price)  # Store raw value for sorting
                self.table_assets.setItem(row, 7, price_item)
                
                self.table_assets.setItem(row, 8, QTableWidgetItem(asset.get('tanggalPembelian', '')))
                self.table_assets.setItem(row, 9, QTableWidgetItem(asset.get('location', '')))
                self.table_assets.setItem(row, 10, QTableWidgetItem(garansi_text))

            # Enable sorting
            self.table_assets.setSortingEnabled(True)
            
        except Exception as e:
            self.table_assets.setRowCount(0)
            
            # Add error row
            error_row = self.table_assets.rowCount()
            self.table_assets.insertRow(error_row)
            error_item = QTableWidgetItem(f"Error: {str(e)}")
            error_item.setForeground(QBrush(QColor(255, 0, 0)))  # Red text
            error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_assets.setItem(error_row, 0, error_item)
            self.table_assets.setSpan(error_row, 0, 1, self.table_assets.columnCount())
            
            # Add retry button
            retry_row = self.table_assets.rowCount()
            self.table_assets.insertRow(retry_row)
            retry_item = QTableWidgetItem()
            self.table_assets.setItem(retry_row, 0, retry_item)
            
            retry_button = QPushButton("Coba Lagi")
            retry_button.clicked.connect(self.load_assets)
            retry_button.setStyleSheet("padding: 3px;")
            self.table_assets.setCellWidget(retry_row, 0, retry_button)
            self.table_assets.setSpan(retry_row, 0, 1, self.table_assets.columnCount())
            
    def _get_assets_from_api(self):
        """Helper method to get assets from API"""
        try:
            import requests
            from requests.exceptions import RequestException
            
            print("[DEBUG] Mengirim request GET ke http://localhost:5000/api/assets")
            response = requests.get('http://localhost:5000/api/assets', timeout=10)
            print(f"[DEBUG] Response status code: {response.status_code}")
            
            # Debugging: Print raw response content
            print(f"[DEBUG] Raw response content: {response.text[:200]}...")  # Print first 200 chars
            
            try:
                json_data = response.json()
                print("[DEBUG] Response JSON parsed successfully")
                print(f"[DEBUG] JSON keys: {json_data.keys() if isinstance(json_data, dict) else 'response is not a dict'}")
                
                # Handle different response formats
                if isinstance(json_data, list):
                    print("[DEBUG] Response is a list, returning directly")
                    return json_data
                elif isinstance(json_data, dict):
                    print("[DEBUG] Response is a dictionary, checking for 'data' key")
                    if 'data' in json_data:
                        print(f"[DEBUG] Found 'data' key with {len(json_data['data'])} items")
                        return json_data['data']
                    else:
                        print("[DEBUG] No 'data' key found, returning full response as list")
                        return [json_data]
                else:
                    raise Exception("Format response tidak dikenali")
                    
            except ValueError as e:
                print(f"[DEBUG] Gagal parse JSON: {str(e)}")
                if response.text:
                    raise Exception(f"Gagal parse response: {response.text[:100]}...")
                else:
                    raise Exception("Response kosong dari server")
                    
        except RequestException as e:
            print(f"[DEBUG] RequestException: {str(e)}")
            raise Exception(f"Koneksi gagal: {str(e)}")
        except Exception as e:
            print(f"[DEBUG] Unexpected error: {str(e)}")
            raise Exception(f"Error: {str(e)}")
        
    def prepare_update_form(self):
        """Prepare the update form with selected asset data using QProgressDialog"""
        selected = self.table_assets.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Silakan pilih aset yang akan diedit")
            return

        # Buat progress dialog
        progress = QProgressDialog("Sedang mengambil data aset...", None, 0, 0, self)
        progress.setWindowTitle("Memuat Data")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)  # Nonaktifkan tombol cancel
        progress.show()
        QApplication.processEvents()

        try:
            row = selected[0].row()
            rfid_uid = self.table_assets.item(row, 2).text()
            self.current_rfid_uid = rfid_uid

            asset = self._get_asset_by_rfid(rfid_uid)
            progress.close()

            if not asset:
                QMessageBox.warning(self, "Warning", f"Aset dengan UID {rfid_uid} tidak ditemukan")
                return
                
            self._fill_update_form(asset)
            self.stack.setCurrentWidget(self.update_page)
            
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Gagal mempersiapkan form edit: {str(e)}")
        finally:
            if progress.isVisible():
                progress.close()

    def _get_asset_by_rfid(self, rfid_uid):
        """Helper method to get asset by RFID UID from API"""
        try:
            import requests
            from requests.exceptions import RequestException
            
            print(f"[DEBUG] Mengambil data aset dengan UID: {rfid_uid}")
            response = requests.get(
                'http://localhost:5000/api/assets',
                params={'uid': rfid_uid},
                timeout=5
            )
            print(f"[DEBUG] Status code: {response.status_code}")
            print(f"[DEBUG] Response content: {response.text[:200]}...")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[DEBUG] Data diterima: {data}")
                
                # Handle different response formats
                if isinstance(data, list):
                    if len(data) > 0:
                        return data[0]  # Ambil item pertama jika response berupa list
                    return None
                elif isinstance(data, dict):
                    if 'data' in data:
                        if isinstance(data['data'], list) and len(data['data']) > 0:
                            return data['data'][0]
                        elif isinstance(data['data'], dict):
                            return data['data']
                    return data  # Return langsung jika format tidak sesuai
                return None
                
            elif response.status_code == 404:
                print("[DEBUG] Aset tidak ditemukan")
                return None
            else:
                error_msg = f"HTTP Error {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except ValueError:
                    pass
                raise Exception(error_msg)
                
        except RequestException as e:
            raise Exception(f"Koneksi gagal: {str(e)}")
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
        
    def _fill_update_form(self, asset):
        """Fill update form with asset data"""
        # Pastikan asset memiliki rfidTag
        rfid_tag = asset.get('rfidTag', {})
        
        self.lbl_asset_id.setText(asset.get('_id', ''))
        self.update_txt_uid.setText(rfid_tag.get('uid', ''))
        self.update_txt_epc.setText(rfid_tag.get('epc', ''))
        self.update_txt_name.setText(asset.get('name', ''))
        self.update_txt_desc.setPlainText(asset.get('description', ''))
        
        # Set category
        category = asset.get('kategori', '')
        index = self.update_cb_category.findText(category)
        if index >= 0:
            self.update_cb_category.setCurrentIndex(index)
        
        # Set status
        status = asset.get('status', '')
        index = self.update_cb_status.findText(status)
        if index >= 0:
            self.update_cb_status.setCurrentIndex(index)
        
        # Set quantity and unit
        self.update_spn_qty.setValue(asset.get('jumlah', 1))
        
        unit = asset.get('unit', 'pcs')
        index = self.update_cb_unit.findText(unit)
        if index >= 0:
            self.update_cb_unit.setCurrentIndex(index)
            self._toggle_update_product_input(unit)
        
        # Set products if unit is pack
        if unit == 'pack' and 'products' in asset:
            self.update_txt_products.setPlainText('\n'.join(asset['products']))
        
        # Set price and purchase date
        self.update_spn_price.setValue(asset.get('price', 0))
        purchase_date = asset.get('tanggalPembelian', QDate.currentDate().toString("yyyy-MM-dd"))
        self.update_dt_purchase.setDate(QDate.fromString(purchase_date, "yyyy-MM-dd"))
        
        # Set location
        self.update_txt_location.setText(asset.get('location', ''))
        
        # Handle masa garansi
        masa_garansi = asset.get('masaGaransi', {})
        if masa_garansi and 'from' in masa_garansi and 'to' in masa_garansi:
            self.update_chk_garansi.setChecked(True)
            self.update_dt_garansi_mulai.setDate(QDate.fromString(masa_garansi['from'], "yyyy-MM-dd"))
            self.update_dt_garansi_akhir.setDate(QDate.fromString(masa_garansi['to'], "yyyy-MM-dd"))
        else:
            self.update_chk_garansi.setChecked(False)
            self.update_dt_garansi_mulai.setDate(QDate.currentDate())
            self.update_dt_garansi_akhir.setDate(QDate.currentDate().addYears(1))
            
    def _get_asset_from_api(self, asset_id):
        """Helper method to get single asset from API"""
        try:
            import requests
            from requests.exceptions import RequestException
            
            print(f"[DEBUG] Mengambil data aset dengan ID: {asset_id}")
            response = requests.get(f'http://localhost:5000/api/assets/{asset_id}', timeout=5)
            print(f"[DEBUG] Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[DEBUG] Data diterima: {data}")
                return data.get('data') if isinstance(data, dict) else data
            elif response.status_code == 404:
                print("[DEBUG] Aset tidak ditemukan")
                return None
            else:
                error_msg = f"HTTP Error {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                except ValueError:
                    pass
                raise Exception(error_msg)
                
        except RequestException as e:
            raise Exception(f"Koneksi gagal: {str(e)}")
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
            
    def _submit_asset(self):
        """Handle new asset submission to API"""
        try:
            # Validate inputs
            if not self.txt_name.text().strip():
                QMessageBox.warning(self, "Warning", "Nama aset harus diisi")
                return
                
            if not self.txt_uid.text().strip() or not self.txt_epc.text().strip():
                QMessageBox.warning(self, "Warning", "UID dan EPC RFID harus diisi")
                return
                
            if self.cb_unit.currentText() == "pack" and not self.txt_products.toPlainText().strip():
                QMessageBox.warning(self, "Warning", "Silakan masukkan produk untuk unit pack")
                return
            
            # Prepare asset data according to API specification
            asset_data = {
                "rfidTag": {
                    "uid": self.txt_uid.text().strip(),
                    "epc": self.txt_epc.text().strip()
                },
                "name": self.txt_name.text().strip(),
                "description": self.txt_desc.toPlainText().strip(),
                "location": self.txt_location.text().strip(),
                "kategori": self.cb_category.currentText(),
                "status": self.cb_status.currentText(),
                "jumlah": self.spn_qty.value(),
                "unit": self.cb_unit.currentText(),
                "price": self.spn_price.value(),
                "tanggalPembelian": self.dt_purchase.date().toString("yyyy-MM-dd"),
                "masaGaransi": {
                    "from": self.dt_purchase.date().toString("yyyy-MM-dd"),
                    "to": self.dt_purchase.date().addYears(1).toString("yyyy-MM-dd")  # 1 tahun garansi
                }
            }

            # Tambahkan masa garansi jika diaktifkan
            if self.chk_garansi.isChecked():
                asset_data["masaGaransi"] = {
                    "from": self.dt_garansi_mulai.date().toString("yyyy-MM-dd"),
                    "to": self.dt_garansi_akhir.date().toString("yyyy-MM-dd")
                }
            
            # Add products if unit is pack
            if self.cb_unit.currentText() == "pack":
                products = [p.strip() for p in self.txt_products.toPlainText().split('\n') if p.strip()]
                asset_data["products"] = products
            
            # Send POST request to API
            response = self._send_asset_to_api(asset_data)
            
            if response.get('success'):
                QMessageBox.information(self, "Success", "Aset berhasil ditambahkan")
                self.load_assets()
                self.stack.setCurrentWidget(self.main_page)
                self._clear_input_form()
            else:
                error_msg = response.get('message', 'Gagal menambahkan aset')
                QMessageBox.warning(self, "Warning", error_msg)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menambahkan aset: {str(e)}")

    def _send_asset_to_api(self, asset_data):
        """Helper method to send asset data to API"""
        try:
            import requests
            from requests.exceptions import RequestException
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.post(
                'http://localhost:5000/api/assets',
                json=asset_data,
                headers=headers
            )
            
            # Check response status
            if response.status_code == 201:
                return {
                    'success': True,
                    'message': 'Asset created successfully'
                }
            else:
                try:
                    error_data = response.json()
                    return {
                        'success': False,
                        'message': error_data.get('message', 'Failed to create asset')
                    }
                except ValueError:
                    return {
                        'success': False,
                        'message': f"HTTP Error {response.status_code}"
                    }
                    
        except RequestException as e:
            return {
                'success': False,
                'message': f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"Unexpected error: {str(e)}"
            }
    
    def _update_asset(self):
        """Handle asset update via API"""
        try:
            # Validate that we have a selected RFID UID
            if not hasattr(self, 'current_rfid_uid') or not self.current_rfid_uid:
                print("DEBUG: No RFID UID selected for update")
                QMessageBox.warning(self, "Warning", "Silakan pilih aset yang akan diupdate")
                return
                
            # Validate inputs
            if not self.update_txt_name.text().strip():
                QMessageBox.warning(self, "Warning", "Nama aset harus diisi")
                return
                
            if not self.update_txt_uid.text().strip() or not self.update_txt_epc.text().strip():
                QMessageBox.warning(self, "Warning", "UID dan EPC RFID harus diisi")
                return
                
            if self.update_cb_unit.currentText() == "pack" and not self.update_txt_products.toPlainText().strip():
                QMessageBox.warning(self, "Warning", "Silakan masukkan produk untuk unit pack")
                return
            
            # Show loading dialog
            progress = QProgressDialog("Mengupdate data aset...", None, 0, 0, self)
            progress.setWindowTitle("Please Wait")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()

            # Prepare update data
            update_data = {
                "rfidTag": {
                    "uid": self.update_txt_uid.text().strip(),
                    "epc": self.update_txt_epc.text().strip()
                },
                "name": self.update_txt_name.text().strip(),
                "description": self.update_txt_desc.toPlainText().strip(),
                "kategori": self.update_cb_category.currentText(),
                "status": self.update_cb_status.currentText(),
                "jumlah": self.update_spn_qty.value(),
                "unit": self.update_cb_unit.currentText(),
                "price": self.update_spn_price.value(),
                "location": self.update_txt_location.text().strip(),
                "tanggalPembelian": self.update_dt_purchase.date().toString("yyyy-MM-dd")
            }
            
            if self.update_cb_unit.currentText() == "pack":
                products = [p.strip() for p in self.update_txt_products.toPlainText().split('\n') if p.strip()]
                update_data["products"] = products
            
            if self.update_chk_garansi.isChecked():
                update_data["masaGaransi"] = {
                    "from": self.update_dt_garansi_mulai.date().toString("yyyy-MM-dd"),
                    "to": self.update_dt_garansi_akhir.date().toString("yyyy-MM-dd")
                }
            else:
                update_data["masaGaransi"] = None
            
            # Send PUT request to API
            response = self._send_update_to_api(self.current_rfid_uid, update_data)
            progress.close()

            # Check response based on status code first
            if response is None:
                QMessageBox.warning(self, "Warning", "Tidak ada response dari server")
            elif response.get('status_code', 0) == 200:
                QMessageBox.information(self, "Success", "Aset berhasil diupdate")
                self.load_assets()
                self.stack.setCurrentWidget(self.main_page)
            else:
                error_msg = response.get('message', 'Gagal mengupdate aset')
                QMessageBox.warning(self, "Warning", error_msg)
                
        except Exception as e:
            if 'progress' in locals() and progress.isVisible():
                progress.close()
            QMessageBox.critical(self, "Error", f"Gagal mengupdate aset: {str(e)}")
            
    def _send_update_to_api(self, rfid_uid, update_data):
        """Helper method to send update to API"""
        try:
            import requests
            from requests.exceptions import RequestException
            
            print(f"[DEBUG] Mengirim update untuk UID: {rfid_uid}")
            print(f"[DEBUG] Data yang dikirim: {update_data}")
            
            response = requests.put(
                f'http://localhost:5000/api/assets/{rfid_uid}',
                json=update_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            print(f"[DEBUG] Status code: {response.status_code}")
            print(f"[DEBUG] Response: {response.text[:200]}...")
            
            # Always return the status code and parsed JSON if available
            result = {
                'status_code': response.status_code
            }
            
            try:
                json_data = response.json()
                result.update(json_data)
                result['success'] = response.status_code == 200
            except ValueError:
                result['message'] = response.text[:100]
                result['success'] = response.status_code == 200
                
            return result
                    
        except RequestException as e:
            print(f"[DEBUG] Request error: {str(e)}")
            return {
                'success': False,
                'message': f"Koneksi gagal: {str(e)}"
            }
        except Exception as e:
            print(f"[DEBUG] Unexpected error: {str(e)}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
      
    def delete_asset(self):
        """Handle asset deletion via API"""
        selected = self.table_assets.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Silakan pilih aset yang akan dihapus")
            return
            
        try:
            row = selected[0].row()
            rfid_uid = self.table_assets.item(row, 2).text()  # Ambil UID dari kolom ke-2
            asset_name = self.table_assets.item(row, 1).text()
            
            # Konfirmasi penghapusan
            reply = QMessageBox.question(
                self, 
                "Konfirmasi Penghapusan", 
                f"Apakah Anda yakin ingin menghapus '{asset_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Show loading dialog
                progress = QProgressDialog("Menghapus aset...", None, 0, 0, self)
                progress.setWindowTitle("Please Wait")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setCancelButton(None)
                progress.show()
                QApplication.processEvents()

                # Kirim permintaan DELETE ke API
                success, message = self._delete_asset_via_api(rfid_uid)
                progress.close()

                if success:
                    QMessageBox.information(self, "Success", "Aset berhasil dihapus")
                    self.load_assets()
                else:
                    QMessageBox.warning(self, "Warning", message)
                    
        except Exception as e:
            if 'progress' in locals() and progress.isVisible():
                progress.close()
            QMessageBox.critical(self, "Error", f"Gagal menghapus aset: {str(e)}")

    def _delete_asset_via_api(self, rfid_uid):
        """Helper method to delete asset via API"""
        try:
            import requests
            from requests.exceptions import RequestException
            
            print(f"[DEBUG] Mengirim permintaan DELETE untuk UID: {rfid_uid}")
            response = requests.delete(
                f'http://localhost:5000/api/assets/{rfid_uid}',
                timeout=10
            )
            
            print(f"[DEBUG] Status code: {response.status_code}")
            print(f"[DEBUG] Response: {response.text[:200]}...")
            
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    return True, json_data.get('message', 'Aset berhasil dihapus')
                except ValueError:
                    return True, "Aset berhasil dihapus"
            elif response.status_code == 404:
                return False, "Aset tidak ditemukan"
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get('message', f"Gagal menghapus (HTTP {response.status_code})")
                except ValueError:
                    return False, f"Gagal menghapus (HTTP {response.status_code})"
                    
        except RequestException as e:
            print(f"[DEBUG] Request error: {str(e)}")
            return False, f"Koneksi gagal: {str(e)}"
        except Exception as e:
            print(f"[DEBUG] Unexpected error: {str(e)}")
            return False, f"Error: {str(e)}"
        
    def _clear_input_form(self):
        """Clear all input fields in the add form"""
        self.txt_name.clear()
        self.txt_uid.clear()
        self.txt_epc.clear()
        self.txt_desc.clear()
        self.spn_qty.setValue(1)
        self.spn_price.setValue(0)
        self.txt_location.clear()
        self.txt_products.clear()
        self.dt_purchase.setDate(QDate.currentDate())
        self.cb_category.setCurrentIndex(0)
        self.cb_status.setCurrentIndex(0)
        self.cb_unit.setCurrentIndex(0)
        self.grp_products.setVisible(False)
        # Reset garansi fields
        self.chk_garansi.setChecked(False)
        self.dt_garansi_mulai.setDate(QDate.currentDate())
        self.dt_garansi_akhir.setDate(QDate.currentDate().addYears(1))
        self.garansi_frame.setVisible(False)

