from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QLineEdit, QMessageBox,
    QHeaderView, QStackedWidget, QGroupBox, QScrollArea,
    QProgressDialog, QFormLayout, QComboBox, QDateEdit, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QMutex, QMutexLocker, QDate
from PyQt6.QtGui import QIcon, QPixmap
from response import hex_readable, Response, WorkMode, InventoryWorkMode, InventoryMemoryBank
from transport import SerialTransport
from reader import Reader
import check_connection
import requests
import serial.tools.list_ports
import time
import base64
from io import BytesIO
from PIL import Image
from purchasing_page import RFIDInventoryThread

class BorrowingPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.token = None
        self.user_data = None
        self.scanned_assets = []
        self.rfid_thread = RFIDInventoryThread()
        self.init_ui()
        self._setup_rfid_connections()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Stacked widget for multi-page
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # Create all pages
        self.scan_page = self._create_scan_page()
        self.login_page = self._create_login_page()
        self.confirm_page = self._create_confirm_page()
        
        # Add pages to stack
        self.stack.addWidget(self.scan_page)
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.confirm_page)
        
        # Show first page
        self.stack.setCurrentWidget(self.scan_page)
        
    def _create_scan_page(self):
        """Page for scanning RFID tags of products to borrow"""
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
        title = QLabel("Scan Products to Borrow")
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
        
        # Table for scanned products
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(4)
        self.products_table.setHorizontalHeaderLabels(["Name", "Status", "RFID EPC", "Action"])
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.products_table)
        
        # Proceed button
        self.btn_proceed = QPushButton("Proceed to Login")
        self.btn_proceed.setEnabled(False)
        self.btn_proceed.clicked.connect(self.proceed_to_login)
        layout.addWidget(self.btn_proceed)
        
        return page
    
    def _create_login_page(self):
        """User login page to get token"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Back button
        back_button = QPushButton("Back to Scanning")
        back_button.setIcon(QIcon("icons/back.png"))
        back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.scan_page))
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Title
        title = QLabel("User Login for Borrowing")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        
        # User input form
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Email")
        form_layout.addRow("Email:", self.txt_email)
        
        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Password")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self.txt_password)
        
        # Submit button
        btn_submit = QPushButton("Login & Continue")
        btn_submit.clicked.connect(self.process_borrowing)
        form_layout.addRow(btn_submit)
        
        scroll.setWidget(form_container)
        layout.addWidget(scroll)
        
        return page
    
    def _create_confirm_page(self):
        """Confirmation page for borrowing"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Back button
        back_button = QPushButton("Back to Login")
        back_button.setIcon(QIcon("icons/back.png"))
        back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.login_page))
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Title
        title = QLabel("Confirm Borrowing")
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
        self.borrow_table = QTableWidget()
        self.borrow_table.setColumnCount(3)
        self.borrow_table.setHorizontalHeaderLabels(["Item", "Status", "RFID EPC"])
        self.borrow_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.borrow_table)
        
        # Return date input
        return_date_layout = QHBoxLayout()
        return_date_layout.addWidget(QLabel("Return Date:"))
        
        self.date_return = QDateEdit()
        self.date_return.setMinimumDate(QDate.currentDate())
        self.date_return.setCalendarPopup(True)
        return_date_layout.addWidget(self.date_return)
        
        content_layout.addLayout(return_date_layout)
        
        # Borrow button
        btn_borrow = QPushButton("Confirm Borrowing")
        btn_borrow.clicked.connect(self.confirm_borrowing)
        content_layout.addWidget(btn_borrow)
        
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
        QApplication.processEvents()
        
        # Check if EPC already exists in table
        epc_exists = any(
            self.products_table.item(row, 2).text() == tag_data['epc']
            for row in range(self.products_table.rowCount())
        )
        
        if epc_exists:
            return
            
        # Get asset details from API
        self._fetch_asset_details(tag_data['epc'], tag_data['uid'])

    def _fetch_asset_details(self, epc: str, uid: str):
        """Fetch asset details from API and check availability"""
        try:
            progress = QProgressDialog("Checking product availability...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()
            
            # First try to get by UID as it's more unique
            response = requests.get(
                f'http://localhost:5000/api/assets',
                params={'uid': uid},
                timeout=5
            )
            
            if response.status_code == 200:
                assets = response.json()
                if isinstance(assets, list) and len(assets) > 0:
                    # Find exact match with EPC
                    matched_asset = None
                    for asset in assets:
                        asset_epc = asset.get('rfidTag', {}).get('epc', '')
                        if asset_epc == epc:
                            matched_asset = asset
                            break
                    
                    if matched_asset:
                        # Check availability
                        if matched_asset.get('status', '').lower() != 'available':
                            QMessageBox.warning(self, "Not Available", 
                                f"Product {matched_asset.get('name')} is not available for borrowing")
                            progress.close()
                            return
                            
                        self._add_asset_to_table(matched_asset)
                        progress.close()
                        return
            
            # Fallback to search by EPC only
            response = requests.get(
                f'http://localhost:5000/api/assets',
                params={'epc': epc},
                timeout=5
            )
            
            progress.close()
            
            if response.status_code == 200:
                assets = response.json()
                if isinstance(assets, list) and len(assets) > 0:
                    asset = assets[0]
                    # Check availability
                    if asset.get('status', '').lower() != 'available':
                        QMessageBox.warning(self, "Not Available", 
                            f"Product {asset.get('name')} is not available for borrowing")
                        return
                        
                    self._add_asset_to_table(asset)
                else:
                    QMessageBox.warning(self, "Not Found", f"No product found with EPC: {epc}")
            else:
                QMessageBox.warning(self, "Error", f"Failed to fetch product: {response.text}")
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to check product: {str(e)}")

    def _add_asset_to_table(self, asset_data: dict):
        """Add available asset to the table"""
        try:
            rfid_tag = asset_data.get('rfidTag', {})
            epc = rfid_tag.get('epc', '')
            
            if not epc or any(a['rfidTag']['epc'] == epc for a in self.scanned_assets):
                return
                
            self.scanned_assets.append(asset_data)
            
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            
            self.products_table.setItem(row, 0, QTableWidgetItem(asset_data.get('name', 'N/A')))
            self.products_table.setItem(row, 1, QTableWidgetItem(asset_data.get('status', 'N/A')))
            self.products_table.setItem(row, 2, QTableWidgetItem(epc))
            
            # Add remove button
            btn_remove = QPushButton("Remove")
            btn_remove.clicked.connect(lambda _, r=row, e=epc: self._remove_asset(r, e))
            self.products_table.setCellWidget(row, 3, btn_remove)
            
            # Enable proceed button if we have items
            self.btn_proceed.setEnabled(self.products_table.rowCount() > 0)
            
        except Exception as e:
            print(f"Error adding asset to table: {str(e)}")

    def _remove_asset(self, row: int, epc: str):
        """Remove asset from borrowing list"""
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
        
        self.btn_proceed.setEnabled(self.products_table.rowCount() > 0)

    def proceed_to_login(self):
        """Move to login page for borrowing"""
        self.stack.setCurrentWidget(self.login_page)

    def process_borrowing(self):
        """Process user login and prepare borrowing"""
        email = self.txt_email.text().strip()
        password = self.txt_password.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "Warning", "Email and password are required")
            return
            
        try:
            progress = QProgressDialog("Processing login...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()
            
            # 1. Login to get token
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
            
            progress.close()
            
            # 2. Show confirmation page
            self._prepare_confirmation_page()
            self.stack.setCurrentWidget(self.confirm_page)
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Login failed: {str(e)}")

    def _prepare_confirmation_page(self):
        """Prepare confirmation page with scanned items"""
        # Set user info
        self.lbl_user_info.setText(f"User: {self.user_data.get('username', '')}")
        
        # Populate items table
        self.borrow_table.setRowCount(0)
        for asset in self.scanned_assets:
            row = self.borrow_table.rowCount()
            self.borrow_table.insertRow(row)
            
            rfid_tag = asset.get('rfidTag', {})
            
            self.borrow_table.setItem(row, 0, QTableWidgetItem(asset.get('name', 'N/A')))
            self.borrow_table.setItem(row, 1, QTableWidgetItem(asset.get('status', 'N/A')))
            self.borrow_table.setItem(row, 2, QTableWidgetItem(rfid_tag.get('epc', 'N/A')))

    def confirm_borrowing(self):
        """Finalize the borrowing process"""
        if not self.token or not self.scanned_assets:
            QMessageBox.warning(self, "Warning", "Invalid borrowing data")
            return
            
        try:
            progress = QProgressDialog("Processing borrowing...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()
            
            # Prepare payload
            payload = {
                "rfidTags": [
                    {
                        "uid": asset['rfidTag'].get('uid'),
                        "epc": asset['rfidTag'].get('epc')
                    }
                    for asset in self.scanned_assets
                ],
                "returnDate": self.date_return.date().toString(Qt.DateFormat.ISODate)
            }
            
            # Send borrowing request
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                'http://localhost:5000/api/borrowing/borrow',
                headers=headers,
                json=payload,
                timeout=10
            )
            
            progress.close()
            
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Borrowing processed successfully")
                self._reset_borrowing_flow()
            else:
                error_msg = response.json().get('message', 'Borrowing failed')
                raise Exception(error_msg)
                
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Borrowing failed: {str(e)}")

    def _reset_borrowing_flow(self):
        """Reset the borrowing process"""
        self.scanned_assets = []
        self.products_table.setRowCount(0)
        self.borrow_table.setRowCount(0)
        self.txt_email.clear()
        self.txt_password.clear()
        self.token = None
        self.user_data = None
        self.stack.setCurrentWidget(self.scan_page)

    # RFID-related methods (similar to PurchasingPage)
    def _refresh_com_ports(self):
        check_connection.testConnect()
        self.cb_com_ports.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.cb_com_ports.addItem(f"{port.device} - {port.description}")
        
        if not ports:
            self.cb_com_ports.addItem("No COM ports found")

    def toggle_rfid_connection(self):
        if self.rfid_thread.connection_established:
            self._disconnect_reader()
        else:
            selected_port = self.cb_com_ports.currentText().split(' - ')[0]
            if selected_port and "No COM ports" not in selected_port:
                self._connect_reader(selected_port)
            else:
                QMessageBox.warning(self, "Warning", "Please select a valid COM port")

    def _connect_reader(self, port: str):
        try:
            check_connection.testConnect()
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Connecting...")
            QApplication.processEvents()
            
            if not self.rfid_thread.connect_reader(port):
                raise Exception("Failed to connect reader")
                
            if not self.rfid_thread.isRunning():
                self.rfid_thread.start()
                
            time.sleep(0.5)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")
            self.rfid_thread.disconnect_reader()
        finally:
            self.btn_connect.setEnabled(True)

    def _disconnect_reader(self):
        try:
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("Disconnecting...")
            QApplication.processEvents()
            
            if self.rfid_thread.isRunning():
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

    def _update_reader_status(self, message: str):
        self.lbl_connection_status.setText(f"Status: {message}")
        
        if "Connected" in message:
            self._update_connection_ui(True)
        elif "disconnected" in message.lower():
            self._update_connection_ui(False)

    def _update_connection_ui(self, connected: bool):
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
        print(f"RFID Error: {error_msg}")
        self._update_connection_ui(False)

    def go_to_main_menu(self):
        """Return to main menu"""
        if self.rfid_thread.isRunning():
            self.rfid_thread.stop_thread()
        # Implement navigation to main menu as needed