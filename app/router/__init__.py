from fastapi import APIRouter

from .endpoints import admin, auth, point, posts, quest, search, stamp

router = APIRouter()

router.include_router(auth.router)
router.include_router(point.router)
router.include_router(search.router)
router.include_router(admin.router)
router.include_router(quest.router)
router.include_router(posts.router)
router.include_router(stamp.router)
