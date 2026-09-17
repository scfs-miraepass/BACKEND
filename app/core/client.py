from app.schemas import Posts, Quests

from .core import BaseCore
from .service import History, Karaoke, Post, Quest, User


class ServiceClient(BaseCore):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    @staticmethod
    async def get_user(
        _id: int,
        /,
        *,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
    ) -> User | None:
        """
        ID를 이용해 사용자를 가져옵니다.

        Args:
            _id: 사용자 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 유저를 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            User | None
        """
        return await User.get_by_id(user_id=_id, cache=cache, save_cache=save_cache, lock=lock)

    async def get_post(
        self,
        /,
        _id: int,
        *,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
    ) -> Post | None:
        """
        ID를 이용해 게시글을 가져옵니다.

        Args:
            _id: 게시글 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            Post | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=Post,
            model_cls=Posts,
            prefix="post",
            ttl=60 * 60 * 24,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )

    async def get_quest(
        self,
        /,
        _id: int,
        *,
        cache: bool = False,
        save_cache: bool = True,
        lock: bool = False,
    ) -> Quest | None:
        """
        ID를 이용해 퀘스트를 가져옵니다.

        Args:
            _id: 퀘스트 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            Quest | None
        """
        return await self._get_item(
            _id=_id,
            wrapper_cls=Quest,
            model_cls=Quests,
            prefix="quest",
            ttl=60 * 5,
            cache=cache,
            save_cache=save_cache,
            lock=lock,
        )

    @staticmethod
    async def get_history(
        _id: int, /, *, cache: bool = False, save_cache: bool = True, lock: bool = False
    ) -> History | None:
        """
        ID를 이용해 포인트 기록을 가져옵니다.

        Args:
            _id: 포인트 기록 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            History | None
        """
        return await History.get_by_id(history_id=_id, cache=cache, save_cache=save_cache, lock=lock)

    @staticmethod
    async def get_karaoke(
        _id: int, /, *, cache: bool = False, save_cache: bool = True, lock: bool = False
    ) -> Karaoke | None:
        """
        ID를 이용해 노래방 예약을 가져옵니다.

        Args:
            _id: 노래방 예약 ID
            cache: 캐시 사용 여부 (lock이 True 일경우 무시됨)
            save_cache: 가져온 후 캐시를 저장 여부
            lock: 조회후 Row-level Lock를 설정 여부

        Returns:
            Karaoke | None
        """
        return await Karaoke.get_by_id(karaoke_id=_id, cache=cache, save_cache=save_cache, lock=lock)
