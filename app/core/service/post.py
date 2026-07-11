from typing import TYPE_CHECKING
from sqlmodel import delete, col, select

from app.schemas import Posts, PostContent

from ..core import ServiceCore


if TYPE_CHECKING:
    _Type = Posts
else:
    _Type = object


class Post(ServiceCore[Posts], _Type):
    async def get_content(self) -> dict:
        """
        게시글의 내용 데이터를 가져옵니다.

        Returns:
            Dict (Tiptap Editor JSON DATA)
        """
        content: PostContent
        if self.content is None:
            async with self.session as session:
                query = select(PostContent).where(PostContent.post_id == self.id)
                result = await session.execute(query)
                content = result.scalar_one()
        else:
            content = self.content

        return content.data

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
            f"게시글 삭제 - ID {self.id}({self.title[:10] + '...' if len(self.title) > 10 else self.title})"
        )

    async def edit(self, *, title: str | None = None, content: dict | None = None):
        """
        게시글을 수정합니다.

        Args:
            title: 게시글의 제목
            content: 게시글의 본문 데이터
        """
        async with self.session as session:
            post = await session.merge(self._payload)
            if title is not None:
                post.title = title

            if content is not None:
                if post.content:
                    post.content.data = content
                else:
                    post.content = PostContent(data=content)

        await self.redis.delete(f"post:{self.id}")
        await self.redis.delete_pattern("posts:list:*")
        self._payload = post

        self.logs.service_post.info(f"게시글 수정 - ID {self.id}")
