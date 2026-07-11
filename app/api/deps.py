from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def get_device_id(x_device_id: Annotated[str | None, Header()] = None) -> str:
    """Every card/collection request is scoped to this device — there's no
    login, so this header is the only thing separating one phone's data
    from another's."""
    if not x_device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="X-Device-Id header is required"
        )
    return x_device_id


DeviceIdDep = Annotated[str, Depends(get_device_id)]
