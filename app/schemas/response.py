from typing import TypeVar

from pydantic import BaseModel, Field

Data = TypeVar("Data")


class ResponsePayload(BaseModel):
    success: bool


class ResponseModel[Data](ResponsePayload):
    data: Data = Field(description="응답 데이터")


class ErrorResponse(ResponsePayload):
    message: str = Field(description="에러 메시지")
