from mangum import Mangum

from app.db.database import init_db
from app.main import app

# Entry point for AWS Lambda (container image). Mangum translates between
# the Lambda event format (API Gateway or a Function URL's request/response
# shape) and the ASGI calls FastAPI expects.
#
# lifespan="off" is required here: Mangum's default ("auto") re-runs the
# ASGI lifespan — our app's init_db() schema migrations AND close_pool() —
# on EVERY invocation, not just once at cold start, which both re-does
# every migration per request and tears down the connection pool right
# after building it. Instead we run init_db() once here, at module import
# time, which only happens on a cold start (Lambda reuses this module —
# and the pool it creates — across warm invocations of the same
# container). We never call close_pool(): Lambda just freezes or reclaims
# the execution environment, which is the normal way a container's
# lifetime ends here.
init_db()

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """Wraps Mangum's own handler to flush LangSmith's trace queue before
    returning. LangSmith's @traceable (see app/integrations/chat.py,
    app/integrations/syllabus_extraction.py) submits traces from a
    background thread by default — fine on a normal long-running server,
    but on Lambda the execution environment can freeze the instant this
    function returns, before that background thread ever gets to actually
    send the queued trace. A short, best-effort flush here closes that
    gap; wrapped in try/except and capped with a timeout so a LangSmith
    outage (or it simply not being configured at all) never breaks or
    measurably slows down a real response."""
    response = _mangum_handler(event, context)
    try:
        from langsmith.run_trees import get_cached_client

        get_cached_client().flush(timeout=5)
    except Exception:
        pass
    return response
