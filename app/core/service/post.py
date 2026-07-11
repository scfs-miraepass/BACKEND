from typing import TYPE_CHECKING
from sqlmodel import delete, col

from app.schemas import Posts

from ..core import ServiceCore


if TYPE_CHECKING:
    _Type = Posts
else:
    _Type = object


class Post(ServiceCore[Posts], _Type):
    async def delete(self):
        """
        게시글을 삭제합니다.
        """
        async with self.session as session:
            exc = delete(Posts).where(col(Posts.id) == self.id)
            await session.execute(exc)

        await self.redis.delete(f"post:{self.id}")
        await self.redis.delete("posts_count")
        await self.redis.delete_pattern("posts:list:*")

        self.logs.service_post.info(
            f"게시글 삭제 - {self.id}({self.title[:10] + '...' if len(self.title) > 10 else self.title})"
        )
