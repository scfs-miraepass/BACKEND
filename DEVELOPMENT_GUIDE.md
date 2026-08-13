# 미래패스 백엔드 개발 가이드 (Development Guide)

이 문서는 미래패스(Mirae Pass) 백엔드 프로젝트의 코드 스타일, 구조, 개발 컨벤션을 정의합니다. 새로운 개발자 또는 AI(예: Antigravity)가 코드베이스에 기여할 때 이 가이드를 반드시 숙지하고 준수해야 합니다.

## 1. 아키텍처 및 디자인 패턴 (Architecture & Design Patterns)

이 프로젝트는 **Layered Architecture (계층형 아키텍처)**를 지향합니다.

* **Controller Layer (`app/router/endpoints/`)**: API 요청을 받고 검증하며 응답을 반환하는 역할만 수행합니다. 비즈니스 로직이 방대해지는 경우 이곳에 모두 작성하지 않습니다.
* **Service Layer (`app/core/service/`)**: 복잡한 핵심 비즈니스 로직(예: 퀘스트 정산 로직, 복잡한 사용자 데이터 가공 등)을 추상화하여 담당합니다.
  * **Core Client & Service 구조**: 이 프로젝트는 `BaseCore`를 상속받아 싱글톤으로 동작하는 `ServiceClient`(`app/core/client.py`)와 각 모델 데이터를 래핑하는 `ServiceCore[T]`(`app/core/core.py`) 패턴을 사용합니다.
  * **ServiceCore 상속 방식**: 특정 도메인의 서비스 객체를 만들 때 `ServiceCore[모델타입]`을 상속받습니다. 이 객체는 내부에 실제 Pydantic/SQLModel 데이터를 `_payload`로 감싸며, 래핑된 데이터의 필드에 직접 접근할 수 있도록 오버라이딩(`__getattribute__`) 되어 있습니다.
  * **새로운 서비스 레이어 추가 방법**:
    1. `app/core/service/{도메인}.py` 파일을 만들고 `ServiceCore`를 상속받은 클래스를 작성합니다. (예: `class Payment(ServiceCore[Payments]):`)
    2. 생성한 클래스 안에 필요한 비즈니스 로직 메서드를 추가합니다.
    3. `app/core/service/__init__.py`에 해당 클래스를 명시적으로 Export (`__all__` 리스트에 추가) 합니다.
    4. `app/core/client.py`의 `ServiceClient`에 해당 데이터를 DB나 Redis(캐시)에서 가져와 서비스 객체 인스턴스(예: `Payment(payload=...)`)로 리턴해주는 메서드(예: `get_payment()`)를 구현합니다.
* **Data Access Layer / Model (`app/schemas/`)**: 데이터베이스와 1:1로 매칭되는 모델 및 통신 시 사용할 Pydantic 검증 모델들이 위치합니다. `SQLAlchemy` 및 `SQLModel` 기반으로 작성됩니다.

## 2. 엔드포인트(Endpoint) 작성 및 라우터 연동 방법

새로운 API 기능을 추가할 때 아래 프로세스를 따릅니다.

### 2.1 Router 파일 생성
`app/router/endpoints/` 디렉토리에 도메인 단위로 파일을 생성합니다. (예: `payment.py`)
```python
from fastapi import APIRouter
from app.schemas.response import ResponseModel

router = APIRouter(prefix="/payment", tags=["payment"])

@router.get("/")
async def get_payment_info():
    return ResponseModel[str](success=True, data="payment info")
```

### 2.2 메인 라우터에 등록
생성한 라우터를 `app/router/__init__.py`에 등록해야 애플리케이션에 실제 반영됩니다.
```python
from fastapi import APIRouter
from .endpoints import admin, auth, point, posts, quest, search, stamp, payment  # 모듈 추가

router = APIRouter()

# 기존 라우터들...
router.include_router(payment.router)  # 라우터 등록
```

## 3. 엔드포인트 응답 타입 규격 (Response Type)

모든 API 응답은 `app/schemas/response.py`에 정의된 규격을 사용해 프론트엔드와 통신합니다.

* **정상 응답 (`ResponseModel[T]`)**:
  ```python
  from app.schemas.response import ResponseModel

  @router.get("/info", response_model=ResponseModel[UserInfo])
  async def get_info():
      data = UserInfo(...)
      return ResponseModel[UserInfo](success=True, data=data)
  ```
* **에러 응답 (`ErrorResponse`)**:
  에러가 발생할 경우, 비즈니스 로직 및 라우터에서 `FastAPI`의 `HTTPException`을 발생시킵니다. 전역 `exception_handler`가 이를 캡처하여 자동으로 `ErrorResponse` 형태로 반환합니다.
  ```python
  from fastapi import HTTPException, status
  
  if not user:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="유저를 찾을 수 없습니다.")
  ```
* **응답 없이 성공 (204 No Content)**: 삭제나 단순 상태 변경 API의 경우 `response_class=Response`와 `status_code=204`를 활용할 수 있습니다.

## 4. 코드 스타일 및 린팅 (Code Style & Linting)

이 프로젝트는 **Ruff**를 린터와 포매터로 사용합니다.

* **줄 길이 (Line Length)**: 120자 제한
* **린팅 룰**: 기본 Ruff 룰 세트 적용 (예외 처리: E402, B904, RUF100)
* **강제 실행**:
  ```bash
  uv run ruff check --fix .
  uv run ruff format .
  ```

## 5. 핵심 개발 컨벤션 (Core Conventions)

### 5.1 비동기 프로그래밍 (Asynchronous Programming)
* 모든 I/O 작업(데이터베이스 쿼리, Redis 호출, 외부 API 요청 등)은 **비동기(`async/await`)로 작성**해야 합니다.

### 5.2 의존성 주입 (Dependency Injection)
* FastAPI의 `Depends`를 사용하여 데이터베이스 세션(`SessionDep`)이나 사용자 인증 정보(`LoginDep`)를 주입받습니다.

### 5.3 데이터베이스 통신 (SQLModel / SQLAlchemy)
* 모델 클래스는 `SQLModel` 또는 `SQLAlchemy`의 선언적 방식을 사용합니다.
* 쿼리는 비동기 SQLAlchemy의 2.0 스타일(`select`, `insert`, `update`)을 사용하여 작성합니다.

## 6. AI (Antigravity) 작동 지침 (AI Guidelines)

AI 에이전트가 코드를 수정하거나 기능을 추가할 때는 다음 규칙을 절대적으로 준수해야 합니다.
1. **신규 라우터 등록 잊지 않기**: 새 라우터 파일 생성 시 반드시 `app/router/__init__.py`에 등록합니다.
2. **응답 모델 래핑 강제**: 반환 값을 그냥 리턴하지 말고 반드시 `ResponseModel[Type](success=True, data=...)` 구조로 래핑하여 리턴합니다.
3. **타입 힌트 및 주석**: 모든 파라미터 및 반환값에 대해 Type Hinting을 강제하며, 복잡한 로직은 한국어 주석으로 설명합니다.
