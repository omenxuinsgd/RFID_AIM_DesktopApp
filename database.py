from pymongo import MongoClient
from datetime import datetime

class Database:
    def __init__(self):
        # Connect to MongoDB (adjust connection string as needed)
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["asset_management"]
        
        # Collections
        self.assets = self.db["assets"]
        self.users = self.db["users"]
        self.transactions = self.db["transactions"]
    
    # Asset operations
    def add_asset(self, asset_data):
        """Add a new asset to the database"""
        asset_data["created_at"] = datetime.now()
        asset_data["updated_at"] = datetime.now()
        return self.assets.insert_one(asset_data)
    
    def get_asset_by_rfid(self, rfid_tag):
        """Get asset by RFID tag"""
        return self.assets.find_one({"rfid_tag": rfid_tag})
    
    def update_asset(self, asset_id, update_data):
        """Update asset information"""
        update_data["updated_at"] = datetime.now()
        return self.assets.update_one(
            {"_id": asset_id},
            {"$set": update_data}
        )
    
    # User operations
    def add_user(self, user_data):
        """Add a new user to the database"""
        return self.users.insert_one(user_data)
    
    def get_user(self, user_id):
        """Get user by ID"""
        return self.users.find_one({"_id": user_id})
    
    # Transaction operations
    def create_transaction(self, transaction_data):
        """Create a new transaction (borrow/return/purchase)"""
        transaction_data["timestamp"] = datetime.now()
        return self.transactions.insert_one(transaction_data)
    
    def get_asset_transactions(self, asset_id):
        """Get all transactions for an asset"""
        return list(self.transactions.find({"asset_id": asset_id}))