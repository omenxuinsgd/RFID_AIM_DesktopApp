import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QStackedWidget)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize
from database import Database
from widgets import MenuCard
from tracking_page import TrackingPage
from borrowing_page import BorrowingPage
from returning_page import ReturningPage
from purchasing_page import PurchasingPage
from management_page import ManagementPage
from rfid_reader import RFIDReader

class AssetManagementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asset Management System")
        self.setGeometry(100, 100, 1000, 700)
        
        # Initialize database
        self.db = Database()
        
        # Setup UI
        self.init_ui()
        
        # Apply styles
        self.apply_styles()

    def init_ui(self):
        # Create main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        
        # Create header
        self.create_header()
        
        # Create stacked widget for pages
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        # Initialize all pages
        self.init_pages()
        
        # Show main menu first
        self.show_main_menu()
    
    def create_header(self):
        """Create the application header"""
        self.header_layout = QHBoxLayout()
        title_label = QLabel("Asset Management System")
        title_label.setObjectName("headerTitle")
        self.header_layout.addWidget(title_label)
        self.header_layout.addStretch()
        self.main_layout.addLayout(self.header_layout)
    
    def init_pages(self):
        """Initialize all content pages"""
        # Main Menu Page
        self.main_menu_page = QWidget()
        self.main_menu_layout = QVBoxLayout(self.main_menu_page)
        self.create_menu_cards()
        self.stacked_widget.addWidget(self.main_menu_page)
        
        # Tracking page
        self.tracking_page = TrackingPage(self.db)
        self.stacked_widget.addWidget(self.tracking_page)
        
        # Borrowing page
        self.borrowing_page = BorrowingPage(self.db)
        self.stacked_widget.addWidget(self.borrowing_page)
        
        # Returning page
        self.returning_page = ReturningPage(self.db)
        self.stacked_widget.addWidget(self.returning_page)
        
        # Purchasing page
        self.purchasing_page = PurchasingPage(self.db)
        self.stacked_widget.addWidget(self.purchasing_page)

        # Initialize RFID reader
        self.rfid_reader = RFIDReader()
        
        # Management page
        self.management_page = ManagementPage(self.db, self.rfid_reader)
        self.stacked_widget.addWidget(self.management_page)
        
    def create_menu_cards(self):
        """Create menu cards in 2 rows (3 top, 2 bottom centered)"""
        # Clear existing layout
        while self.main_menu_layout.count():
            child = self.main_menu_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Create card rows
        top_row = QHBoxLayout()
        bottom_row = QHBoxLayout()
        
        # Set spacing and alignment
        top_row.setSpacing(30)
        bottom_row.setSpacing(30)
        bottom_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create cards for top row (3 cards)
        tracking_card = MenuCard(
            "Tracking", 
            "Lacak Asset", 
            "icons/tracking.png",
            lambda: self.stacked_widget.setCurrentWidget(self.tracking_page)
        )
        borrowing_card = MenuCard(
            "Borrowing", 
            "Peminjaman Asset", 
            "icons/borrowing.png",
            lambda: self.stacked_widget.setCurrentWidget(self.borrowing_page)
        )
        returning_card = MenuCard(
            "Returning", 
            "Pengembalian Asset", 
            "icons/returning.png",
            lambda: self.stacked_widget.setCurrentWidget(self.returning_page)
        )
        
        # Create cards for bottom row (2 cards)
        purchasing_card = MenuCard(
            "Purchasing", 
            "Pembelian Asset", 
            "icons/purchasing.png",
            lambda: self.stacked_widget.setCurrentWidget(self.purchasing_page)
        )
        management_card = MenuCard(
            "Management", 
            "Manajemen Asset", 
            "icons/management.png",
            lambda: self.stacked_widget.setCurrentWidget(self.management_page)
        )
        
        # Add cards to rows
        top_row.addWidget(tracking_card)
        top_row.addWidget(borrowing_card)
        top_row.addWidget(returning_card)
        
        bottom_row.addWidget(purchasing_card)
        bottom_row.addWidget(management_card)
        
        # Add rows to main layout
        self.main_menu_layout.addLayout(top_row)
        self.main_menu_layout.addLayout(bottom_row)
        self.main_menu_layout.addStretch()
    
    def show_main_menu(self):
        """Show main menu and setup back button on all pages"""
        self.stacked_widget.setCurrentWidget(self.main_menu_page)
        
        # Setup back button for all pages
        for page in [self.tracking_page, self.borrowing_page, self.returning_page, 
                    self.purchasing_page, self.management_page]:
            if hasattr(page, 'back_button'):
                page.back_button.clicked.connect(self.show_main_menu)
    
    def apply_styles(self):
        """Apply styles to the application"""
        try:
            with open('styles.qss', 'r') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            # Default styles if stylesheet not found
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                }
                QLabel#headerTitle {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    padding: 15px;
                }
            """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AssetManagementApp()
    window.show()
    sys.exit(app.exec())