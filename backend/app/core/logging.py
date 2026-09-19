"""Small JSON logger and request-observability middleware."""
import json, logging, time, uuid
from starlette.middleware.base import BaseHTTPMiddleware
class JsonFormatter(logging.Formatter):
    def format(self, record:logging.LogRecord)->str:
        payload={"level":record.levelname,"logger":record.name,"message":record.getMessage()}
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for field in ("request_id","merchant_id","endpoint","duration_ms","status_code"):
            if hasattr(record,field): payload[field]=getattr(record,field)
        return json.dumps(payload,default=str)
def configure_logging()->None:
    handler=logging.StreamHandler(); handler.setFormatter(JsonFormatter()); root=logging.getLogger()
    if not root.handlers: root.addHandler(handler)
    root.setLevel(logging.INFO)
class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        request_id=request.headers.get("X-Request-ID",str(uuid.uuid4())); started=time.perf_counter()
        response=await call_next(request); response.headers["X-Request-ID"]=request_id
        logging.getLogger("growthos.request").info("request_complete",extra={"request_id":request_id,"endpoint":request.url.path,"duration_ms":round((time.perf_counter()-started)*1000,2),"status_code":response.status_code})
        return response
