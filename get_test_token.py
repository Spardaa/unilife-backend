"""
Generate a JWT Access Token for testing api
Usage: python3 get_test_token.py [user_id]
"""
import sys
import os

# Filter paths
sys.path.append(os.getcwd())

from app.services.token_service import token_service
from app.config import settings

def main():
    if len(sys.path) < 2:
        user_id = "test_user_001"
    else:
        user_id = sys.argv[1] if len(sys.argv) > 1 else "test_user_001"
    
    # Increase token duration for testing
    original_expire = token_service.access_token_expire_minutes
    token_service.access_token_expire_minutes = 60 * 24 * 30  # 30 days
    
    print(f"Generating test token for user: {user_id}")
    token = token_service.create_access_token(user_id)
    
    print("\n" + "="*50)
    print("YOUR ACCESS TOKEN:")
    print("="*50 + "\n")
    print(token)
    print("\n" + "="*50)
    print(f"Expires in: 30 days")
    print("="*50 + "\n")
    
    # Restore (not really needed for script)
    token_service.access_token_expire_minutes = original_expire

if __name__ == "__main__":
    main()
