"""
캐시 무효화 이벤트

데이터가 변경되었을 때 함께 지워야 하는 캐시를 도메인 이벤트 단위로 모아둔 모듈입니다.
캐시를 지울 때는 Key를 직접 삭제하지 않고 이 모듈의 함수를 호출해, 무효화 범위가 호출하는 곳마다 달라지지 않도록 합니다.
"""

from collections.abc import Iterable
from datetime import date

from .redis import RedisCore
from .redis_keys import Keys

RANKING_TYPES = ("student", "teacher")


async def _clear_ranking(user_type: str | None, *, count: bool = False):
    """user_type이 None이면 모든 랭킹을 지웁니다. 랭킹 대상이 아닌 타입(service)은 무시합니다."""
    types = RANKING_TYPES if user_type is None else (str(user_type),)
    for t in types:
        if t not in RANKING_TYPES:
            continue
        await RedisCore.delete_pattern(Keys.Ranking.PAGE.pattern(type=t))
        if count:
            await RedisCore.delete(Keys.Ranking.COUNT(type=t))


# ---------- 유저 / 포인트 ----------


async def on_user_cache_changed(user_id: int):
    """유저 데이터 중 목록/랭킹에 영향이 없는 값(비밀번호 등)이 변경된 경우"""
    await RedisCore.delete(Keys.User.ITEM(user_id=user_id))


async def on_points_changed(user_ids: Iterable[int], user_type: str | None = None):
    """
    포인트 또는 포인트 기록이 변경된 경우

    Args:
        user_ids: 포인트가 변경된 유저 ID 목록
        user_type: 유저 타입. 모르거나 여러 타입이 섞인 경우 None (모든 랭킹을 지움)
    """
    for user_id in user_ids:
        await RedisCore.delete(Keys.User.ITEM(user_id=user_id), Keys.PointHistory.COUNT(user_id=user_id))
        await RedisCore.delete_pattern(Keys.PointHistory.PAGE.pattern(user_id=user_id))
    await _clear_ranking(user_type)


async def on_point_changed(user_id: int, user_type: str | None = None):
    await on_points_changed([user_id], user_type)


async def on_point_history_deleted(history_id: int, user_id: int, user_type: str | None = None):
    await RedisCore.delete(Keys.PointHistory.ITEM(history_id=history_id))
    await on_point_changed(user_id, user_type)


async def on_user_profile_changed(user_id: int, user_type: str):
    """이름, 권한 등 검색/랭킹 결과에 영향을 주는 유저 정보가 변경된 경우"""
    await RedisCore.delete(Keys.User.ITEM(user_id=user_id))
    await _clear_ranking(user_type, count=True)
    await RedisCore.delete_pattern(Keys.Search.USERS)


async def on_user_created(user_type: str):
    await _clear_ranking(user_type, count=True)
    await RedisCore.delete_pattern(Keys.Search.USERS)


async def on_user_deleted(user_id: int, user_type: str):
    await on_point_changed(user_id, user_type)
    await on_user_created(user_type)


# ---------- 게시글 / 퀘스트 ----------


async def on_post_changed(post_id: int | None = None, *, count: bool = False):
    """
    Args:
        post_id: 변경된 게시글 ID (생성의 경우 None)
        count: 게시글 개수가 변경된 경우(생성/삭제) True
    """
    if post_id is not None:
        await RedisCore.delete(Keys.Post.ITEM(post_id=post_id))
    if count:
        await RedisCore.delete(Keys.Post.COUNT())
    await RedisCore.delete_pattern(Keys.Post.PAGE)


async def on_quest_changed(quest_id: int | None = None):
    if quest_id is not None:
        await RedisCore.delete(Keys.Quest.ITEM(quest_id=quest_id))
    await RedisCore.delete(Keys.Quest.COUNT())
    await RedisCore.delete_pattern(Keys.Quest.PAGE)


# ---------- 노래방 ----------


async def on_karaoke_list_changed(_date: date):
    await RedisCore.delete(Keys.Karaoke.LIST(date=_date))


async def on_karaoke_changed(karaoke_id: int, _date: date):
    """경매 상태 등 경매 데이터가 변경된 경우"""
    await RedisCore.delete(Keys.Karaoke.ITEM(karaoke_id=karaoke_id), Keys.Karaoke.LIST(date=_date))


async def on_karaoke_bid(karaoke_id: int, _date: date):
    """새로운 입찰로 최고가와 입찰 기록이 변경된 경우 (최고가 Key는 호출부에서 새로 저장)"""
    await RedisCore.delete(
        Keys.Karaoke.ITEM(karaoke_id=karaoke_id),
        Keys.Karaoke.BIDS(karaoke_id=karaoke_id),
        Keys.Karaoke.LIST(date=_date),
    )


async def on_karaoke_deleted(karaoke_id: int, _date: date):
    await RedisCore.delete(
        Keys.Karaoke.ITEM(karaoke_id=karaoke_id),
        Keys.Karaoke.HIGHEST(karaoke_id=karaoke_id),
        Keys.Karaoke.BIDS(karaoke_id=karaoke_id),
        Keys.Karaoke.LIST(date=_date),
    )
    await RedisCore.delete_pattern(Keys.Karaoke.USER_PARTY.pattern(karaoke_id=karaoke_id))


async def on_party_changed(party_id: int):
    """파티 데이터(해산 여부 등)가 변경된 경우"""
    await RedisCore.delete(Keys.Karaoke.PARTY(party_id=party_id))


async def on_party_members_changed(party_id: int, auction_id: int, user_ids: Iterable[int]):
    """
    파티 멤버 구성(초대, 수락, 거절, 강퇴, 해산)이 변경된 경우

    Args:
        party_id: 파티 ID
        auction_id: 파티가 속한 경매 ID
        user_ids: 소속 정보가 변경된 유저 ID 목록
    """
    keys = [Keys.Karaoke.PARTY_MEMBERS(party_id=party_id)]
    for user_id in user_ids:
        keys.append(Keys.Karaoke.PARTY_MEMBER(party_id=party_id, user_id=user_id))
        keys.append(Keys.Karaoke.USER_PARTY(karaoke_id=auction_id, user_id=user_id))
    await RedisCore.delete(*keys)
