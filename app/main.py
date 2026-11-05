from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.api.notes import router as notes_router
from app.db import make_engine, make_session_factory
from app.services.notes import NoteNotFound


def create_app(session_factory: sessionmaker | None = None) -> FastAPI:
    app = FastAPI(title="hub-flow-test")
    app.state.session_factory = session_factory or make_session_factory(make_engine())

    @app.exception_handler(NoteNotFound)
    async def _note_not_found(_request: Request, _exc: NoteNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Note not found"}
        )

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        # Model-level validation; schemas should catch these first.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)}
        )

    app.include_router(notes_router)
    return app


app = create_app()
