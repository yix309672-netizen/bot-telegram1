# coding=utf-8
import os
import httpx
from typing import Any, Dict

CONVERTER_URL = os.getenv("CONVERTER_URL", "http://localhost:8002/to-tdata")


async def to_tdata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """调用独立转换服务，将 session 转换为 tdata 格式"""
    timeout = httpx.Timeout(12.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(CONVERTER_URL, json=payload)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {"error": "invalid_response", "detail": "Converter service did not return JSON"}
        except httpx.TimeoutException:
            return {"error": "timeout", "detail": "Converter service timed out"}
        except httpx.HTTPStatusError as exc:
            return {"error": "http_error", "status": exc.response.status_code, "detail": exc.response.text}
        except Exception as exc:
            return {"error": "unexpected_error", "detail": str(exc)}