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

handler = Mangum(app, lifespan="off")
