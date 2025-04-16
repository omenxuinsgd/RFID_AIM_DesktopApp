from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, 
    QLineEdit, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import requests

class TrackingPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.base_url = "http://localhost:5000/api/assets"
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # Tombol kembali
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

        # Judul halaman
        title = QLabel("Asset Tracking")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Input pencarian
        search_layout = QHBoxLayout()
        self.criteria_combo = QComboBox()
        self.criteria_combo.addItems(["category", "name", "location", "status"])
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search value...")
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_tracking_data)

        search_layout.addWidget(QLabel("Search by:"))
        search_layout.addWidget(self.criteria_combo)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        self.layout.addLayout(search_layout)

        # Tabel untuk menampilkan hasil
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)  # Sesuaikan dengan jumlah kolom yang ingin ditampilkan
        self.result_table.setHorizontalHeaderLabels([
            "Name", "Category", "Location", "Status", "Quantity", "Last Update"
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Style tabel
        self.result_table.setStyleSheet("""
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
        """)
        
        self.layout.addWidget(self.result_table)

    def search_tracking_data(self):
        criterion = self.criteria_combo.currentText()
        value = self.search_input.text().strip()

        if not value:
            self.result_table.setRowCount(0)
            self.result_table.setRowCount(1)
            self.result_table.setItem(0, 0, QTableWidgetItem("Please enter a value to search."))
            self.result_table.setSpan(0, 0, 1, self.result_table.columnCount())
            return

        url = f"{self.base_url}/track/tags?{criterion}={value}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                self.display_results(data)
            else:
                self.show_error_message(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            self.show_error_message(f"Request failed: {str(e)}")

    def display_results(self, data):
        """Display search results in table format"""
        if not data:
            self.show_error_message("No matching assets found.")
            return

        self.result_table.setRowCount(0)  # Clear previous results

        # Filter out RFID tag details and prepare data for display
        display_data = []
        for item in data:
            display_item = {
                'name': item.get('name', ''),
                'category': item.get('kategori', ''),
                'location': item.get('location', ''),
                'status': item.get('status', ''),
                'quantity': str(item.get('jumlah', '')),
                'last_update': item.get('tanggalPendataan', '')
            }
            display_data.append(display_item)

        # Populate table
        self.result_table.setRowCount(len(display_data))
        for row, asset in enumerate(display_data):
            self.result_table.setItem(row, 0, QTableWidgetItem(asset['name']))
            self.result_table.setItem(row, 1, QTableWidgetItem(asset['category']))
            self.result_table.setItem(row, 2, QTableWidgetItem(asset['location']))
            self.result_table.setItem(row, 3, QTableWidgetItem(asset['status']))
            self.result_table.setItem(row, 4, QTableWidgetItem(asset['quantity']))
            self.result_table.setItem(row, 5, QTableWidgetItem(asset['last_update']))

    def show_error_message(self, message):
        """Show error message in the table"""
        self.result_table.setRowCount(0)
        self.result_table.setRowCount(1)
        error_item = QTableWidgetItem(message)
        error_item.setForeground(Qt.GlobalColor.red)
        self.result_table.setItem(0, 0, error_item)
        self.result_table.setSpan(0, 0, 1, self.result_table.columnCount())