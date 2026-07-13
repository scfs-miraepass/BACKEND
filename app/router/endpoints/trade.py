from fastapi import APIRouter

from app.core.dependency import ServiceClient

router = APIRouter(
    prefix="/trade",
    tags=["trade"],
)
client = ServiceClient()
