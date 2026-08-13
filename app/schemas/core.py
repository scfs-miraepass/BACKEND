from datetime import datetime
from zoneinfo import ZoneInfo


class ClassProperty:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        return self.method(owner)


class SchemaCore:
    instance = None

    timezone = ZoneInfo("UTC")

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    @classmethod
    def sync_timezone(cls, _: datetime):
        if _.tzinfo is None:
            # Mysql 기준, DB서버 시간대로 자동 생성시 TZ이 없음 -> TZ 데이터추가
            return _.replace(tzinfo=cls.timezone)
        elif _.utcoffset() != cls.timezone.utcoffset(_.replace(tzinfo=None)):
            # TimeZone이 있지만, 서버와 다른경우
            return _.astimezone(tz=cls.timezone)
        return _
