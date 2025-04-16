import requests
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QMessageBox
import json

class AuthService:
    def __init__(self, api_base="http://localhost:5000"):
        self.api_base = api_base
        self.token = None
        self.token_expiry = None
        self.current_user = None
        self.refresh_token = None

    def login(self, email, password):
        """Handle login process with proper error handling"""
        try:
            response = requests.post(
                f"{self.api_base}/api/auth/login",
                json={
                    "email": email,
                    "password": password
                },
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            response.raise_for_status()  # Will raise HTTPError for 4XX/5XX status
            data = response.json()

            if not data.get('token'):
                raise ValueError("Invalid response: No token received")

            self.token = data['token']
            self.current_user = {
                'userId': data.get('userId'),
                'email': email,
                'role': data.get('role', 'user')
            }
            
            # Calculate expiry (assuming JWT with 'exp' claim)
            self.token_expiry = datetime.now() + timedelta(hours=1)  # Default 1 hour
            return True

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', error_msg)
                except json.JSONDecodeError:
                    error_msg = e.response.text or error_msg
            QMessageBox.critical(None, "Login Failed", error_msg)
            return False

        except Exception as e:
            QMessageBox.critical(None, "Login Error", f"An error occurred: {str(e)}")
            return False

    def is_token_valid(self):
        """Check if token exists and not expired"""
        return self.token and (not self.token_expiry or datetime.now() < self.token_expiry)

    def get_auth_headers(self):
        """Return headers with authorization token"""
        if not self.is_token_valid():
            return None
            
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def logout(self):
        """Clear authentication data"""
        self.token = None
        self.token_expiry = None
        self.current_user = None