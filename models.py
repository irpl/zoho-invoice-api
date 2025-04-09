from pydantic import BaseModel
from typing import List, Optional

class CustomerInfo(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    billing_address: Optional[dict] = None

class InvoiceItem(BaseModel):
    item_id: str
    quantity: int

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