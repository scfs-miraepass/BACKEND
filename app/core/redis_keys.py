"""
Redis Key 레지스트리

프로젝트에서 사용하는 모든 Redis Key(및 Pub/Sub 채널)는 이 파일의 `Keys`에 정의합니다.
Key 문자열을 코드에 직접 작성하지 않고, 아래와 같이 정의된 Key를 호출해 사용합니다.

    key = Keys.User.ITEM(user_id=user.id)       # -> BoundKey("user:item:1101"), TTL 포함
    await client.redis.set(key, value)          # TTL은 Key에 정의된 값이 기본으로 사용됨
    await client.redis.delete_pattern(Keys.Ranking.PAGE.pattern(type="student"))

명명 규칙: `{도메인}:{종류}:{파라미터...}`
- 첫 두 구간은 고정 문자열, 이후 구간은 `{파라미터}` 하나씩으로 작성합니다.
- 단, `session:{session_id}`는 기존 로그인 세션 유지를 위해 예외로 기존 형태를 유지합니다.

전체 목록은 `python tools/cli.py redis-keys` 로 확인할 수 있습니다.
"""

import re
from dataclasses import dataclass, field
from string import Formatter

from .config import settings

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR

_GLOB_SPECIAL = re.compile(r"([*?\[\]\\])")


class BoundKey(str):
    """
    파라미터가 모두 채워진 실제 Redis Key.

    `str`을 상속하므로 pipeline, publish, pubsub 등 Redis 원본 API에도 그대로 전달할 수 있습니다.
    """

    ttl: int | None

    def __new__(cls, value: str, ttl: int | None = None):
        obj = super().__new__(cls, value)
        obj.ttl = ttl
        return obj

    @classmethod
    def unchecked(cls, value: str) -> BoundKey:
        """
        레지스트리를 거치지 않은 임의의 Key를 만듭니다.
        **CLI 등 디버깅 도구에서만 사용합니다.**
        """
        return cls(value)


class KeyPattern(str):
    """`delete_pattern`에 전달하는 glob 패턴"""

    @classmethod
    def unchecked(cls, value: str) -> KeyPattern:
        """
        레지스트리를 거치지 않은 임의의 패턴을 만듭니다.
        **CLI 등 디버깅 도구에서만 사용합니다.**
        """
        return cls(value)


@dataclass(frozen=True, slots=True)
class RedisKey:
    template: str
    ttl: int | None
    """기본 TTL(초). None인 경우 저장 시 TTL을 직접 지정해야 합니다."""
    description: str
    fields: tuple[str, ...] = field(init=False)

    def __post_init__(self):
        names = tuple(name for _, name, _, _ in Formatter().parse(self.template) if name)
        object.__setattr__(self, "fields", names)

    def _check_params(self, params: dict, *, require_all: bool):
        unknown = set(params) - set(self.fields)
        if unknown:
            raise TypeError(f"'{self.template}'에 없는 파라미터입니다: {sorted(unknown)}")
        missing = set(self.fields) - set(params)
        if require_all and missing:
            raise TypeError(f"'{self.template}'에 필요한 파라미터가 없습니다: {sorted(missing)}")

    def __call__(self, **params) -> BoundKey:
        self._check_params(params, require_all=True)
        return BoundKey(self.template.format(**params), self.ttl)

    def pattern(self, **params) -> KeyPattern:
        """
        일부 파라미터만 채운 삭제용 패턴을 만듭니다. 채우지 않은 파라미터는 `*`로 대체됩니다.

        예) `Keys.Ranking.PAGE.pattern(type="student")` -> `ranking:page:student:*:*:*:*`
        """
        self._check_params(params, require_all=False)
        values = {
            name: _GLOB_SPECIAL.sub(r"\\\1", str(params[name])) if name in params else "*" for name in self.fields
        }
        return KeyPattern(self.template.format(**values))


class Keys:
    class Auth:
        SESSION = RedisKey("session:{session_id}", settings.service.session.expire_seconds, "로그인 세션 → user_id")

    class User:
        ITEM = RedisKey("user:item:{user_id}", settings.service.session.expire_seconds, "유저 데이터")

    class PointLimit:
        GRANT = RedisKey(
            "point_limit:grant:{user_id}:{week}",
            None,
            "교사가 이번 주(월요일 시작일 week)에 사용한 지급/보상 한도. 주가 끝나면 만료",
        )
        STUDENT = RedisKey(
            "point_limit:student:{user_id}:{date}",
            None,
            "학생이 date 날에 받은 포인트. 하루가 끝나면 만료",
        )

    class PointHistory:
        ITEM = RedisKey("point_history:item:{history_id}", 5 * MINUTE, "포인트 기록 단건")
        COUNT = RedisKey("point_history:count:{user_id}", DAY, "유저의 포인트 기록 총 개수")
        PAGE = RedisKey("point_history:page:{user_id}:{limit}:{offset}", DAY, "유저의 포인트 기록 페이지")

    class Ranking:
        COUNT = RedisKey("ranking:count:{type}", 5 * MINUTE, "랭킹 대상 인원 수")
        PAGE = RedisKey(
            "ranking:page:{type}:{period}:{week}:{limit}:{offset}",
            5 * MINUTE,
            "랭킹 페이지 (week: 주간 시작일 또는 all)",
        )

    class Search:
        USERS = RedisKey("search:users:{query}:{types}", 5 * MINUTE, "유저 검색 결과 (유저 ID 목록)")

    class Post:
        ITEM = RedisKey("post:item:{post_id}", DAY, "게시글 단건")
        COUNT = RedisKey("post:count", DAY, "게시글 총 개수")
        PAGE = RedisKey("post:page:{page}:{size}", DAY, "게시글 목록 페이지")

    class Quest:
        ITEM = RedisKey("quest:item:{quest_id}", 5 * MINUTE, "퀘스트 단건")
        COUNT = RedisKey("quest:count", 5 * MINUTE, "퀘스트 총 개수")
        PAGE = RedisKey("quest:page:{limit}:{offset}", 5 * MINUTE, "퀘스트 목록 페이지")

    class Karaoke:
        ITEM = RedisKey("karaoke:item:{karaoke_id}", 5 * MINUTE, "노래방 경매 단건")
        LIST = RedisKey("karaoke:list:{date}", 5 * MINUTE, "date(YYYY-MM-DD) 날의 노래방 경매 목록")
        HIGHEST = RedisKey("karaoke:highest:{karaoke_id}", None, "경매 최고 입찰. TTL은 경매 종료 시각 기준")
        BIDS = RedisKey("karaoke:bids:{karaoke_id}", 5 * MINUTE, "경매 입찰 기록")
        USER_PARTY = RedisKey(
            "karaoke:user_party:{karaoke_id}:{user_id}", 5 * MINUTE, "경매에서 유저가 소속된(리더 포함) 파티 ID"
        )
        PARTY = RedisKey("karaoke:party:{party_id}", DAY, "노래방 파티 단건")
        PARTY_MEMBERS = RedisKey("karaoke:party_members:{party_id}", DAY, "파티 멤버 목록 (초대 수락 완료)")
        PARTY_MEMBER = RedisKey("karaoke:party_member:{party_id}:{user_id}", HOUR, "파티 멤버 단건 (초대 대기 포함)")
        CHANNEL = RedisKey("karaoke:channel:{karaoke_id}", None, "경매 이벤트 Pub/Sub 채널")

    @classmethod
    def all(cls) -> dict[str, RedisKey]:
        """`{도메인}.{이름}` 형태의 이름으로 모든 Key를 반환합니다."""
        result: dict[str, RedisKey] = {}
        for group_name, group in vars(cls).items():
            if not isinstance(group, type):
                continue
            for key_name, key in vars(group).items():
                if isinstance(key, RedisKey):
                    result[f"{group_name}.{key_name}"] = key
        return result


def _validate_registry():
    """
    Key 정의 오류(형식 위반, 다른 Key와 겹칠 수 있는 템플릿)를 서버 시작 시점에 확인합니다.
    두 템플릿이 같은 실제 Key를 만들 수 있으면 캐시가 섞이거나 패턴 삭제 범위가 겹치므로 허용하지 않습니다.
    """
    segments: dict[str, list[str | None]] = {}
    for name, key in Keys.all().items():
        parsed: list[str | None] = []
        for segment in key.template.split(":"):
            if segment.startswith("{") and segment.endswith("}") and segment[1:-1] in key.fields:
                parsed.append(None)  # 파라미터 구간
            elif "{" in segment or "}" in segment or not segment:
                raise ValueError(f"{name}: 구간에는 고정 문자열 또는 파라미터 하나만 올 수 있습니다. ({key.template})")
            else:
                parsed.append(segment)
        if parsed[0] is None:
            raise ValueError(f"{name}: 첫 구간은 도메인 이름이어야 합니다. ({key.template})")
        if len(set(key.fields)) != len(key.fields):
            raise ValueError(f"{name}: 파라미터 이름이 중복됩니다. ({key.template})")
        segments[name] = parsed

    names = list(segments)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            sa, sb = segments[a], segments[b]
            if len(sa) == len(sb) and all(x is None or y is None or x == y for x, y in zip(sa, sb, strict=True)):
                raise ValueError(f"{a}와 {b}의 Key가 겹칠 수 있습니다. ({Keys.all()[a].template})")


_validate_registry()
