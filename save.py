from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QComboBox,
    QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit,
    QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon

class ManagementPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_assets()

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # Back button
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
        self.layout.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Title
        title = QLabel("Asset Management")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.layout.addWidget(title)

        # Create action buttons
        self.create_action_buttons()

        # Create asset table
        self.create_asset_table()

        # Create forms (initially hidden)
        self.create_input_form()
        self.create_update_form()
        
        self.layout.addStretch()

    def create_action_buttons(self):
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add New Asset")
        self.add_btn.setIcon(QIcon("icons/add.png"))
        self.add_btn.clicked.connect(self.show_input_form)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit Asset")
        self.edit_btn.setIcon(QIcon("icons/edit.png"))
        self.edit_btn.clicked.connect(self.show_update_form)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete Asset")
        self.delete_btn.setIcon(QIcon("icons/delete.png"))
        self.delete_btn.clicked.connect(self.delete_asset)
        btn_layout.addWidget(self.delete_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(QIcon("icons/refresh.png"))
        self.refresh_btn.clicked.connect(self.load_assets)
        btn_layout.addWidget(self.refresh_btn)

        self.layout.addLayout(btn_layout)

    def create_asset_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "RFID UID", "Category", 
            "Status", "Qty", "Unit", "Price", 
            "Purchase Date", "Location"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.layout.addWidget(self.table)

    def create_input_form(self):
        self.input_form = QGroupBox("Add New Asset")
        self.input_form.setVisible(False)
        
        form_layout = QVBoxLayout()

        # RFID Fields
        rfid_group = QGroupBox("RFID Information")
        rfid_layout = QHBoxLayout()
        
        self.uid_input = QLineEdit()
        self.uid_input.setPlaceholderText("UID")
        rfid_layout.addWidget(QLabel("UID:"))
        rfid_layout.addWidget(self.uid_input)
        
        self.epc_input = QLineEdit()
        self.epc_input.setPlaceholderText("EPC")
        rfid_layout.addWidget(QLabel("EPC:"))
        rfid_layout.addWidget(self.epc_input)
        
        rfid_group.setLayout(rfid_layout)
        form_layout.addWidget(rfid_group)

        # Basic Info
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Asset Name")
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_input)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Description")
        form_layout.addWidget(QLabel("Description:"))
        form_layout.addWidget(self.desc_input)

        # Category and Status
        info_layout = QHBoxLayout()
        
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "electronics", "furniture", "tools", 
            "machinery", "consumables", "documents", "other"
        ])
        info_layout.addWidget(QLabel("Category:"))
        info_layout.addWidget(self.category_combo)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems([
            "available", "borrowed", "maintenance", "disposed", "lost"
        ])
        info_layout.addWidget(QLabel("Status:"))
        info_layout.addWidget(self.status_combo)
        
        form_layout.addLayout(info_layout)

        # Quantity and Unit
        qty_layout = QHBoxLayout()
        
        self.qty_input = QSpinBox()
        self.qty_input.setMinimum(1)
        self.qty_input.setValue(1)
        qty_layout.addWidget(QLabel("Quantity:"))
        qty_layout.addWidget(self.qty_input)
        
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["pcs", "pack"])
        self.unit_combo.currentTextChanged.connect(self.toggle_product_input)
        qty_layout.addWidget(QLabel("Unit:"))
        qty_layout.addWidget(self.unit_combo)
        
        form_layout.addLayout(qty_layout)

        # Products (visible only when unit is pack)
        self.products_group = QGroupBox("Products in Pack")
        self.products_group.setVisible(False)
        products_layout = QVBoxLayout()
        
        self.products_input = QTextEdit()
        self.products_input.setPlaceholderText("Enter one product per line")
        products_layout.addWidget(self.products_input)
        
        self.products_group.setLayout(products_layout)
        form_layout.addWidget(self.products_group)

        # Price and Dates
        detail_layout = QHBoxLayout()
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setPrefix("Rp ")
        self.price_input.setMaximum(999999999)
        detail_layout.addWidget(QLabel("Price:"))
        detail_layout.addWidget(self.price_input)
        
        self.purchase_date = QDateEdit()
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setDate(QDate.currentDate())
        detail_layout.addWidget(QLabel("Purchase Date:"))
        detail_layout.addWidget(self.purchase_date)
        
        form_layout.addLayout(detail_layout)

        # Location
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Location")
        form_layout.addWidget(QLabel("Location:"))
        form_layout.addWidget(self.location_input)

        # Form buttons
        btn_layout = QHBoxLayout()
        
        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.submit_asset)
        btn_layout.addWidget(submit_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.hide_input_form)
        btn_layout.addWidget(cancel_btn)
        
        form_layout.addLayout(btn_layout)

        self.input_form.setLayout(form_layout)
        self.layout.addWidget(self.input_form)

    def create_update_form(self):
        self.update_form = QGroupBox("Edit Asset")
        self.update_form.setVisible(False)
        
        # Similar to input form but with ID field
        form_layout = QVBoxLayout()

        self.update_id = QLabel()
        form_layout.addWidget(QLabel("Asset ID:"))
        form_layout.addWidget(self.update_id)

        # Add all the same fields as input form
        # ... (copy fields from input form but prefix with 'update_')
        
        # Form buttons
        btn_layout = QHBoxLayout()
        
        update_btn = QPushButton("Update")
        update_btn.clicked.connect(self.update_asset_data)
        btn_layout.addWidget(update_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.hide_update_form)
        btn_layout.addWidget(cancel_btn)
        
        form_layout.addLayout(btn_layout)

        self.update_form.setLayout(form_layout)
        self.layout.addWidget(self.update_form)

    def toggle_product_input(self, unit):
        self.products_group.setVisible(unit == "pack")

    def show_input_form(self):
        self.input_form.setVisible(True)
        self.update_form.setVisible(False)
        self.clear_input_form()

    def hide_input_form(self):
        self.input_form.setVisible(False)

    def show_update_form(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an asset to edit")
            return

        self.update_form.setVisible(True)
        self.input_form.setVisible(False)
        
        # Get selected asset data
        row = selected[0].row()
        asset_id = self.table.item(row, 0).text()
        
        # Here you would load the asset data from DB
        # and populate the update form fields
        # Example:
        # asset = self.db.get_asset_by_id(asset_id)
        # self.update_id.setText(asset_id)
        # self.update_name_input.setText(asset['name'])
        # etc...

    def hide_update_form(self):
        self.update_form.setVisible(False)

    def clear_input_form(self):
        self.name_input.clear()
        self.uid_input.clear()
        self.epc_input.clear()
        self.desc_input.clear()
        self.qty_input.setValue(1)
        self.price_input.setValue(0)
        self.location_input.clear()
        self.products_input.clear()
        self.purchase_date.setDate(QDate.currentDate())
        self.category_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.unit_combo.setCurrentIndex(0)

    def load_assets(self):
        # Clear table
        self.table.setRowCount(0)
        
        # Here you would fetch assets from database
        # Example:
        # assets = self.db.get_all_assets()
        # for asset in assets:
        #     row = self.table.rowCount()
        #     self.table.insertRow(row)
        #     self.table.setItem(row, 0, QTableWidgetItem(asset['_id']))
        #     self.table.setItem(row, 1, QTableWidgetItem(asset['name']))
        #     etc...
        
        # Dummy data for example
        assets = [
            {
                "_id": "1", 
                "name": "Laptop Dell",
                "rfidTag": {"uid": "UID123", "epc": "EPC456"},
                "category": "electronics",
                "status": "available",
                "quantity": 1,
                "unit": "pcs",
                "price": 15000000,
                "purchaseDate": "2023-05-15",
                "location": "IT Room"
            },
            {
                "_id": "2", 
                "name": "Office Chair",
                "rfidTag": {"uid": "UID789", "epc": "EPC012"},
                "category": "furniture",
                "status": "available",
                "quantity": 5,
                "unit": "pcs",
                "price": 1200000,
                "purchaseDate": "2023-06-20",
                "location": "Meeting Room"
            }
        ]
        
        for asset in assets:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(asset['_id']))
            self.table.setItem(row, 1, QTableWidgetItem(asset['name']))
            self.table.setItem(row, 2, QTableWidgetItem(asset['rfidTag']['uid']))
            self.table.setItem(row, 3, QTableWidgetItem(asset['category']))
            self.table.setItem(row, 4, QTableWidgetItem(asset['status']))
            self.table.setItem(row, 5, QTableWidgetItem(str(asset['quantity'])))
            self.table.setItem(row, 6, QTableWidgetItem(asset['unit']))
            self.table.setItem(row, 7, QTableWidgetItem(f"Rp {asset['price']:,}"))
            self.table.setItem(row, 8, QTableWidgetItem(asset['purchaseDate']))
            self.table.setItem(row, 9, QTableWidgetItem(asset['location']))

    def submit_asset(self):
        # Validate inputs
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Warning", "Asset name is required")
            return
            
        if not self.uid_input.text().strip() or not self.epc_input.text().strip():
            QMessageBox.warning(self, "Warning", "RFID UID and EPC are required")
            return
            
        if self.unit_combo.currentText() == "pack" and not self.products_input.toPlainText().strip():
            QMessageBox.warning(self, "Warning", "Please enter products for pack unit")
            return
        
        # Prepare asset data
        asset_data = {
            "name": self.name_input.text(),
            "description": self.desc_input.toPlainText(),
            "rfidTag": {
                "uid": self.uid_input.text(),
                "epc": self.epc_input.text()
            },
            "category": self.category_combo.currentText(),
            "status": self.status_combo.currentText(),
            "quantity": self.qty_input.value(),
            "unit": self.unit_combo.currentText(),
            "price": self.price_input.value(),
            "purchaseDate": self.purchase_date.date().toString("yyyy-MM-dd"),
            "location": self.location_input.text()
        }
        
        if self.unit_combo.currentText() == "pack":
            products = self.products_input.toPlainText().split('\n')
            asset_data["products"] = [p.strip() for p in products if p.strip()]
        
        # Here you would save to database
        # Example:
        # result = self.db.add_asset(asset_data)
        # if result:
        #     QMessageBox.information(self, "Success", "Asset added successfully")
        #     self.load_assets()
        #     self.hide_input_form()
        
        # For now just show the data
        print("Asset data to be saved:", asset_data)
        QMessageBox.information(self, "Success", "Asset added successfully (demo)")
        self.load_assets()
        self.hide_input_form()

    def update_asset_data(self):
        # Similar to submit_asset but for updating
        pass

    def delete_asset(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an asset to delete")
            return
            
        row = selected[0].row()
        asset_id = self.table.item(row, 0).text()
        asset_name = self.table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete '{asset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Here you would delete from database
            # Example:
            # result = self.db.delete_asset(asset_id)
            # if result:
            #     QMessageBox.information(self, "Success", "Asset deleted successfully")
            #     self.load_assets()
            
            # For now just show message
            print(f"Asset {asset_id} would be deleted")
            QMessageBox.information(self, "Success", "Asset deleted successfully (demo)")
            self.load_assets()