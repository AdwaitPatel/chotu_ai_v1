from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
class DomainError(Exception):
    status_code=400; code="DOMAIN_ERROR"
    def __init__(self,message:str): self.message=message
class NotFoundError(DomainError): status_code=404; code="NOT_FOUND"
class OutOfStockError(DomainError): status_code=409; code="OUT_OF_STOCK"
async def domain_error_handler(_:Request,exc:DomainError): return JSONResponse(status_code=exc.status_code,content={"success":False,"error":{"code":exc.code,"message":exc.message}})
async def integrity_error_handler(_:Request,__:IntegrityError): return JSONResponse(status_code=409,content={"success":False,"error":{"code":"CONFLICT","message":"A record with these unique fields already exists."}})
