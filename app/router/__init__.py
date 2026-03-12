from fastapi import APIRouter
from .endpoints import auth
from .endpoints import point
from .endpoints import search

router = APIRouter()

router.include_router(auth.router)
router.include_router(point.router)
router.include_router(search.router)
