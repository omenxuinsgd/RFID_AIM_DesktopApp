from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize

class MenuCard(QWidget):
    def __init__(self, title, description, icon_path, click_handler):
        super().__init__()
        self.title = title
        self.description = description
        self.icon_path = icon_path
        self.click_handler = click_handler
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the card UI"""
        self.setFixedSize(220, 260)
        self.setObjectName(f"menuCard{self.title}")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Icon
        icon_label = QLabel()
        icon_pixmap = QPixmap(self.icon_path).scaled(
            80, 80, Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setObjectName("menuCardTitle")
        
        # Description
        desc_label = QLabel(self.description)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("menuCardDesc")
        
        # Button
        button = QPushButton("Open")
        button.setObjectName("menuCardButton")
        button.clicked.connect(self.click_handler)
        
        # Add widgets to layout
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addWidget(button)
        
        # Set cursor to pointer
        self.setCursor(Qt.CursorShape.PointingHandCursor)

class AssetForm(QWidget):
    """Base form for asset operations"""
    def __init__(self):
        super().__init__()
        # Common form elements can be defined here
        pass