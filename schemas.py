from pydantic import BaseModel


class ItemBase(BaseModel):
    base64: str


class ItemCreate(ItemBase):
    developerId: int
    clientUserId: str

class ItemUpdate(ItemBase):
    pass
