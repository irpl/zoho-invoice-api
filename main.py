from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from typing import List, Optional
from config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class CustomerInfo(BaseModel):
    display_name: str
    email: str
    phone: Optional[str] = None
    billing_address: Optional[dict] = None

class InvoiceItem(BaseModel):
    item_id: str
    quantity: int
    # rate: float

class CreateInvoiceRequest(BaseModel):
    customer_info: CustomerInfo
    items: List[InvoiceItem]
    notes: Optional[str] = None

class ZohoItem(BaseModel):
    item_id: str
    name: str
    description: Optional[str] = None
    rate: float
    unit: Optional[str] = None
    status: str

class ItemRate(BaseModel):
    item_id: str
    rate: float

class ItemRateResponse(BaseModel):
    items: List[ItemRate]

# Zoho API Helper Functions
def get_zoho_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    data = {
        "refresh_token": settings.ZOHO_REFRESH_TOKEN,
        "client_id": settings.ZOHO_CLIENT_ID,
        "client_secret": settings.ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to get Zoho access token")
    return response.json()["access_token"]

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
        for item in items_data
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
    item_rates = []
    
    for item in items_data:
        if item["item_id"] in item_list:
            item_rates.append(ItemRate(
                item_id=item["item_id"],
                rate=float(item["rate"])
            ))
    
    # Check if all requested items were found
    found_ids = {rate.item_id for rate in item_rates}
    missing_ids = set(item_list) - found_ids
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
        "contact_name": customer_info.display_name,
        "email": customer_info.email,
        "phone": customer_info.phone,
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
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    return response.json()["invoice"]

# API Endpoints
@app.get(f"{settings.API_V1_PREFIX}/items")
async def get_items():
    try:
        access_token = get_zoho_access_token()
        items = get_zoho_items(access_token)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(f"{settings.API_V1_PREFIX}/item-rates")
async def get_item_rates(item_ids: List[str]):
    try:
        access_token = get_zoho_access_token()
        item_rates = get_zoho_item_rates_by_ids(item_ids, access_token)
        return {"items": item_rates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(f"{settings.API_V1_PREFIX}/create-invoice")
async def create_invoice_endpoint(request: CreateInvoiceRequest):
    try:
        access_token = get_zoho_access_token()
        
        # Check if customer exists
        customer_id = find_customer_by_email(request.customer_info.email, access_token)
        
        # If customer doesn't exist, create them
        if not customer_id:
            customer_id = create_customer(request.customer_info, access_token)
        
        item_rates = get_zoho_item_rates_by_ids([item.item_id for item in request.items], access_token)

        # Create the invoice
        line_items = []
        for item, item_rate in zip(request.items, item_rates):
            line_items.append({
                "item_id": item.item_id,
                "quantity": item.quantity,
                "rate": item_rate.rate
            })
        
        invoice = create_invoice(customer_id, line_items, request.notes, access_token)
        
        return {"message": "Invoice created successfully", "invoice": invoice}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Zoho Invoice API is running"} 