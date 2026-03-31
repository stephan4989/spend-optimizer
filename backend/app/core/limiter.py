from slowapi import Limiter
from slowapi.util import get_remote_address

# Key on the client IP address.
# For requests behind a reverse proxy, set FORWARDED_ALLOW_IPS in the environment
# and uvicorn/nginx must forward the real IP via X-Forwarded-For.
# Default: 60 requests/minute per IP across all routes.
# The SlowAPIMiddleware in main.py enforces this globally — no per-endpoint
# decorators needed (they break FastAPI's Annotated dependency resolution).
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
