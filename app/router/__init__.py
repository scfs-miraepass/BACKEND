from fastapi import APIRouter
from .endpoints import auth
from .endpoints import point

router = APIRouter()

router.include_router(auth.router)
router.include_router(point.router)
