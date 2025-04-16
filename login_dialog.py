from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

class LoginDialog(QDialog):
    login_success = pyqtSignal()

    def __init__(self, auth_service, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.setWindowTitle("Login Required")
        self.setWindowIcon(QIcon("icons/login.png"))
        self.setFixedSize(350, 250)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header
        header = QLabel("Asset Management System")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Form
        form = QFormLayout()
        form.setContentsMargins(20, 20, 20, 20)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        form.addRow("Email:", self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self.password_input)
        
        layout.addLayout(form)
        
        # Login Button
        login_btn = QPushButton("Login")
        login_btn.setIcon(QIcon("icons/login.png"))
        login_btn.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-weight: bold;
            }
        """)
        login_btn.clicked.connect(self.attempt_login)
        layout.addWidget(login_btn)
        
        # Footer
        footer = QLabel("© 2023 Asset Management System")
        footer.setStyleSheet("font-size: 10px; color: #666;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    def attempt_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        
        # Validasi input
        if not email:
            QMessageBox.warning(self, "Invalid Input", "Email cannot be empty")
            return
        if "@" not in email or "." not in email:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address")
            return
        if not password:
            QMessageBox.warning(self, "Invalid Input", "Password cannot be empty")
            return
            
        # Coba login
        if self.auth_service.login(email, password):
            self.login_success.emit()
            self.accept()
        else:
            self.password_input.clear()