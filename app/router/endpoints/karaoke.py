from fastapi import APIRouter

from app.core import ServiceClient

router = APIRouter(prefix="/karaoke", tags=["karaoke"])
client = ServiceClient()
