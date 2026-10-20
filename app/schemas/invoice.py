from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    reservation_id: int
    customer_id: int
    payment_id: int
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    created_at: datetime