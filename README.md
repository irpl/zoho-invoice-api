# Zoho Invoice API

A FastAPI backend that integrates with Zoho Invoice API to create invoices and manage customers.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your Zoho credentials:
```
ZOHO_CLIENT_ID=your_client_id
ZOHO_CLIENT_SECRET=your_client_secret
ZOHO_REFRESH_TOKEN=your_refresh_token
ZOHO_ORGANIZATION_ID=your_organization_id
```

## Running the API

Start the server:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Create Invoice
- **URL**: `/api/v1/create-invoice`
- **Method**: `POST`
- **Request Body**:
```json
{
    "customer_info": {
        "display_name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890",
        "billing_address": {
            "attention": "John Doe",
            "address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "country": "USA"
        }
    },
    "items": [
        {
            "item_id": "your_zoho_item_id",
            "quantity": 1,
            "rate": 100.00
        }
    ],
    "notes": "Optional notes about the invoice"
}
```

## Notes

- Make sure you have valid Zoho API credentials
- The API uses OAuth2 authentication with refresh tokens
- In production, update the CORS settings to allow only your frontend domain 