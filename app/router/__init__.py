from fastapi import APIRouter
from .endpoints import auth
from .endpoints import point
from .endpoints import search
from .endpoints import admin
from .endpoints import posts

router = APIRouter()

router.include_router(auth.router)
router.include_router(point.router)
router.include_router(search.router)
router.include_router(admin.router)
router.include_router(posts.router)
