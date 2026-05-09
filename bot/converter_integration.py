# coding=utf-8
"""备份转换集成模块 - 负责备份完成后调用转换服务并导入后端"""
import os
import httpx
from typing import Any, Dict

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
CONVERTER_URL = os.getenv("CONVERTER_URL", "http://127.0.0.1:8002")


async def to_tdata_from_converter(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    调用独立转换服务，将 Telethon session 转换为 tdata 格式
    """
    timeout = httpx.Timeout(12.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"{CONVERTER_URL}/to-tdata", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return {"error": "timeout", "detail": "Converter service timed out"}
        except httpx.HTTPStatusError as exc:
            return {"error": "http_error", "status": exc.response.status_code, "detail": exc.response.text}
        except Exception as exc:
            return {"error": "unexpected_error", "detail": str(exc)}


async def post_import(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    调用后端 API 将转换后的 tdata 导入系统
    """
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"{API_URL}/api/backup/import", json=config)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return {"error": "timeout", "detail": "后端 API 超时"}
        except httpx.HTTPStatusError as exc:
            return {
                "error": "http_error",
                "status": exc.response.status_code,
                "detail": exc.response.text
            }
        except Exception as exc:
            return {"error": "unexpected_error", "detail": str(exc)}


async def on_backup_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    备份完成后的完整流程：
    1. 调用转换服务将 session 转换为 tdata
    2. 调用后端 API 导入 tdata
    """
    backup_data = payload.get("backup", {})
    options = payload.get("options", {})

    tdata_resp = await to_tdata_from_converter({
        "backup": backup_data,
        "options": options
    })

    if "error" in tdata_resp:
        return {"status": "failed", "error": tdata_resp["error"], "stage": "conversion"}

    import_result = await post_import({
        "tdata": tdata_resp.get("tdata"),
        "phone": tdata_resp.get("phone"),
        "options": options
    })

    if "error" in import_result:
        return {"status": "failed", "error": import_result["error"], "stage": "import"}

    return {
        "status": "success",
        "tdata": tdata_resp.get("tdata"),
        "import_id": import_result.get("import_id")
    }