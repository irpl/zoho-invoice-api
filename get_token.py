import webbrowser
import requests
from urllib.parse import urlencode
import os
from dotenv import load_dotenv

load_dotenv()

# Get these from your Zoho Developer Console
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"  # Must match what you set in the console

def generate_auth_url():
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": "ZohoInvoice.fullaccess.all",
        "redirect_uri": REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent"
    }
    
    auth_url = f"https://accounts.zoho.com/oauth/v2/auth?{urlencode(params)}"
    print("\nPlease visit this URL in your browser:")
    print(auth_url)
    print("\nAfter authorizing, you'll be redirected to a URL. Copy the 'code' parameter from that URL.")
    webbrowser.open(auth_url)

def get_refresh_token(authorization_code):
    url = "https://accounts.zoho.com/oauth/v2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": authorization_code
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        tokens = response.json()
        print("\nYour refresh token is:", tokens["refresh_token"])
        print("\nAdd this to your .env file as ZOHO_REFRESH_TOKEN")
    else:
        print("Error getting refresh token:", response.text)

if __name__ == "__main__":
    print("1. Generate authorization URL")
    print("2. Get refresh token using authorization code")
    choice = input("Enter your choice (1 or 2): ")
    
    if choice == "1":
        generate_auth_url()
    elif choice == "2":
        auth_code = input("Enter the authorization code: ")
        get_refresh_token(auth_code)
    else:
        print("Invalid choice") 