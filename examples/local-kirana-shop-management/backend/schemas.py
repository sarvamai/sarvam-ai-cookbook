from pydantic import BaseModel
from datetime import datetime

class TransactionCreate(BaseModel):
    customer_name: str
    amount: float
    item_description: str
    transaction_type: str

class TransactionResponse(TransactionCreate):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True
