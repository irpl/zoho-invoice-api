from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import requests
from typing import List, Optional
from config import settings
from models import CustomerInfo, CreateInvoiceRequest, ZohoItem, ItemRate
from database import get_db, init_db, get_refresh_token, update_access_token, ZohoToken, set_initial_refresh_token, SessionLocal
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)

# Initialize database and set initial refresh token if needed
init_db()
try:
    with SessionLocal() as db:
        get_refresh_token(db)
except Exception:
    if not settings.ZOHO_REFRESH_TOKEN:
        raise Exception("ZOHO_REFRESH_TOKEN environment variable is required for initial setup")
    with SessionLocal() as db:
        set_initial_refresh_token(db, settings.ZOHO_REFRESH_TOKEN)

# Enable CORS
origins = settings.ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Zoho API Helper Functions
def get_zoho_access_token(db: Session):
    # Check if we have a valid access token
    token = db.query(ZohoToken).first()
    if token and token.access_token and token.access_token_expiry:
        if token.access_token_expiry.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            return token.access_token

    # If no valid token, refresh it
    url = "https://accounts.zoho.com/oauth/v2/token"
    refresh_token = get_refresh_token(db)
    data = {
        "refresh_token": refresh_token,
        "client_id": settings.ZOHO_CLIENT_ID,
        "client_secret": settings.ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to get Zoho access token")
    
    response_data = response.json()
    expiry = datetime.now(timezone.utc) + timedelta(seconds=response_data["expires_in"])
    update_access_token(db, response_data["access_token"], expiry)
    
    return response_data["access_token"]

# @app.post(f"{settings.API_V1_PREFIX}/update-token")
# async def update_token(new_token: str, db: Session = Depends(get_db)):
#     """Update the Zoho refresh token in the database"""
#     token = db.query(ZohoToken).first()
#     if not token:
#         token = ZohoToken(refresh_token=new_token)
#         db.add(token)
#     else:
#         token.refresh_token = new_token
#     db.commit()
#     return {"message": "Token updated successfully"}

def get_zoho_items(access_token: str):
    url = "https://invoice.zoho.com/api/v3/items"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch items from Zoho")
    
    items_data = response.json().get("items", [])
    return [
        ZohoItem(
            item_id=item["item_id"],
            name=item["name"],
            description=item.get("description"),
            rate=float(item["rate"]),
            unit=item.get("unit"),
            status=item["status"]
        )
        for item in filter(lambda x: x["status"] == "active", items_data)
    ]

def get_zoho_item_rates_by_ids(item_list: List[str], access_token: str) -> List[ItemRate]:
    url = "https://invoice.zoho.com/api/v3/items"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch items from Zoho")
    
    items_data = response.json().get("items", [])
    
    # Create a dictionary for O(1) lookups
    item_dict = {item["item_id"]: item for item in items_data}
    
    # Fetch rates for requested items
    item_rates = []
    missing_ids = []
    
    for item_id in item_list:
        if item_id in item_dict:
            item_rates.append(ItemRate(
                item_id=item_id,
                rate=float(item_dict[item_id]["rate"])
            ))
        else:
            missing_ids.append(item_id)
    
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Items not found: {', '.join(missing_ids)}"
        )
    
    return item_rates

def find_customer_by_email(email: str, access_token: str):
    url = f"https://invoice.zoho.com/api/v3/contacts"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID
    }
    params = {"email": email}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("contacts"):
            return data["contacts"][0]["contact_id"]
    return None

def create_customer(customer_info: CustomerInfo, access_token: str):
    url = f"https://invoice.zoho.com/api/v3/contacts"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID,
        "Content-Type": "application/json"
    }
    data = {
        "contact_name": customer_info.first_name + " " + customer_info.last_name,
        "contact_persons": [
            {
                "first_name": customer_info.first_name,
                "last_name": customer_info.last_name,
                "email": customer_info.email,
                "phone": customer_info.phone,
                "is_primary_contact": True
            }
        ],
        "billing_address": customer_info.billing_address
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 201:
        raise HTTPException(status_code=500, detail="Failed to create customer")
    return response.json()["contact"]["contact_id"]

def create_invoice(customer_id: str, items: List[dict], notes: Optional[str], access_token: str):
    url = f"https://invoice.zoho.com/api/v3/invoices"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID,
        "Content-Type": "application/json"
    }
    data = {
        "customer_id": customer_id,
        "line_items": items,
        "notes": notes
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 201:
        logger.error(f"Failed to create invoice: {response.json()}")
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    return response.json()["invoice"]

# API Endpoints
@app.get(f"{settings.API_V1_PREFIX}/items")
async def get_items(db: Session = Depends(get_db)):
    try:
        access_token = get_zoho_access_token(db)
        items = get_zoho_items(access_token)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @app.post(f"{settings.API_V1_PREFIX}/item-rates")
# async def get_item_rates(item_ids: List[str], db: Session = Depends(get_db)):
#     try:
#         access_token = get_zoho_access_token(db)
#         item_rates = get_zoho_item_rates_by_ids(item_ids, access_token)
#         return {"items": item_rates}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@app.post(f"{settings.API_V1_PREFIX}/create-invoice")
async def create_invoice_endpoint(request: CreateInvoiceRequest, db: Session = Depends(get_db)):
    try:
        access_token = get_zoho_access_token(db)
        
        # Check if customer exists
        customer_id = find_customer_by_email(request.customer_info.email, access_token)
        
        # If customer doesn't exist, create them
        if not customer_id:
            customer_id = create_customer(request.customer_info, access_token)
        
        item_rates = get_zoho_item_rates_by_ids([item.item_id for item in request.items], access_token)
        
        line_items = [{"item_id": item.item_id, "quantity": item.quantity, "rate": item_rate.rate} for item in request.items for item_rate in item_rates if item.item_id == item_rate.item_id]
        
        invoice = create_invoice(customer_id, line_items, request.notes, access_token)
        
        return {"message": "Invoice created successfully", "invoice": invoice}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Zoho Invoice API is running"} 