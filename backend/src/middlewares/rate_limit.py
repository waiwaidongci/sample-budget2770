import os
from redis import Redis
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

LIMIT=int(os.environ.get('RATE_LIMIT_PER_MINUTE','240'))
redis=Redis.from_url(os.environ['REDIS_URL']) if os.environ.get('REDIS_URL') else None

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        if redis is None or request.url.path=='/health': return await call_next(request)
        try:
            key='http:'+str(request.client.host)+':'+str(int(__import__('time').time())//60)
            n=redis.incr(key)
            if n==1: redis.expire(key,65)
            if n>LIMIT: return JSONResponse({'detail':f'每分钟最多{LIMIT}次，请稍后重试'},status_code=429)
        except Exception:
            pass
        return await call_next(request)
