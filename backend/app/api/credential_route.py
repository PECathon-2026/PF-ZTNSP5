"""Prevent credential-bearing validation inputs from being echoed to clients."""

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute


class CredentialSafeRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                          for error in exc.errors()]
                raise HTTPException(status_code=422, detail=errors) from None

        return handler
