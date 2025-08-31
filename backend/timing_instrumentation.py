import contextvars
import logging
import os
from time import perf_counter
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import event

# one shared mutable aggregator per request (works across threadpool via ContextVar copy)
_db_agg = contextvars.ContextVar("db_agg", default=None)


def attach_sqlalchemy_instrumentation(engine, slow_ms: int | None = None):
    slow_ms = slow_ms or int(os.getenv("DB_SLOW_MS", "100"))
    log = logging.getLogger("sqltiming")

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        stack = conn.info.setdefault("_q_start", [])
        stack.append(perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        stack = conn.info.get("_q_start")
        if not stack:
            return
        start = stack.pop()
        dt = (perf_counter() - start) * 1000.0
        agg = _db_agg.get()
        if isinstance(agg, dict):
            agg["ms"] += dt
            agg["q"] += 1
        if dt >= slow_ms:
            stmt = " ".join(str(statement).split())
            if len(stmt) > 800:
                stmt = stmt[:800] + " …"
            # keep params logging light
            p = "<many>" if isinstance(parameters, (list, tuple)) else parameters
            log.warning("SLOW SQL %.1f ms | params=%s | %s", dt, p, stmt)


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        agg = {"ms": 0.0, "q": 0}
        _db_agg.set(agg)
        t0 = perf_counter()
        resp = await call_next(request)
        total = (perf_counter() - t0) * 1000.0
        try:
            resp.headers["X-Total-Time-ms"] = f"{total:.1f}"
            resp.headers["X-DB-Time-ms"] = f"{agg['ms']:.1f}"
            resp.headers["X-DB-Queries"] = str(agg["q"])
        except Exception:
            pass
        logging.getLogger("apptime").info(
            "%s %s -> total=%.1f ms | db=%.1f ms in %d q",
            request.method, request.url.path, total, agg["ms"], agg["q"]
        )
        return resp
