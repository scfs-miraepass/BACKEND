class ServiceError(Exception):
    pass


class NotFound(ServiceError):
    """
    데이터, 객체 등을 찾지 못할 경우 발생합니다.
    """

    pass


class Forbidden(ServiceError):
    """
    권한이 없을경우 발생합니다.
    """

    pass


class LimitExceeded(ServiceError):
    """
    제한을 초과했을 때 발생합니다.
    """

    pass


class ExpiredError(ServiceError):
    """
    만료되었을 때 발생합니다.
    """

    pass
