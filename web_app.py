#!/usr/bin/env python3
"""
MediX Web frontend server.

Run:
    python web_app.py
"""
import argparse
import asyncio
import json
import os
import socket
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from aiohttp import web
from loguru import logger

os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GLOG_minloglevel", "2")

PROJECT_ROOT = Path(__file__).parent
WEB_ROOT = PROJECT_ROOT / "web"
FRONTEND_DIST_ROOT = PROJECT_ROOT / "frontend" / "dist"
AUTH_LOG_PATH = PROJECT_ROOT / "memory" / "auth_verifications.jsonl"
AUTH_SESSION_PATH = PROJECT_ROOT / "memory" / "auth_sessions.json"
RECENT_CONVERSATIONS_PATH = PROJECT_ROOT / "memory" / "recent_conversations.json"
RECENT_CONVERSATIONS_KEY = "medix:recent_conversations"
sys.path.insert(0, str(PROJECT_ROOT))

from swarm import SwarmCoordinator
from config import REDIS_CONFIG


def setup_logger(verbose: bool = False) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="DEBUG" if verbose else "INFO",
    )


async def get_coordinator(app: web.Application) -> SwarmCoordinator:
    coordinator = app.get("coordinator")
    if coordinator is None:
        coordinator = SwarmCoordinator(enable_swarm=True)
        app["coordinator"] = coordinator
    return coordinator


async def warmup_embedding_model(app: web.Application) -> None:
    """Load the retrieval model before the first user request.

    Loading is performed in a worker thread so the aiohttp event loop remains
    responsive. A failed warmup is non-fatal; the knowledge base can retry on
    first use.
    """
    if os.getenv("MEDIX_WARMUP_EMBEDDING", "1").lower() in {"0", "false", "no"}:
        return
    try:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        logger.info(f"Warming up embedding model: {model_name}")
        started = asyncio.get_running_loop().time()
        model = await asyncio.to_thread(SentenceTransformer, model_name, device="cpu")
        await asyncio.to_thread(model.encode, ["warmup"])
        elapsed = asyncio.get_running_loop().time() - started
        app["embedding_warmup"] = {"ok": True, "model": model_name, "seconds": round(elapsed, 2)}
        logger.info(f"Embedding model warmup complete ({elapsed:.2f}s)")
    except Exception as exc:
        app["embedding_warmup"] = {"ok": False, "error": repr(exc)}
        logger.warning(f"Embedding model warmup failed; continuing without preload: {exc!r}")


async def index(_: web.Request) -> web.FileResponse:
    frontend_index = FRONTEND_DIST_ROOT / "index.html"
    if frontend_index.exists():
        return web.FileResponse(frontend_index)
    return web.FileResponse(WEB_ROOT / "index.html")


async def icon(_: web.Request) -> web.FileResponse:
    return web.FileResponse(PROJECT_ROOT / "icon.png")


async def brand_title(_: web.Request) -> web.FileResponse:
    return web.FileResponse(PROJECT_ROOT / "brand-title.png")


async def health(request: web.Request) -> web.Response:
    return web.json_response({
        "ok": True,
        "service": "medix-web",
        "coordinator_ready": request.app.get("coordinator") is not None,
        "embedding_warmup": request.app.get("embedding_warmup"),
    })


def _auth_store(app: web.Application) -> Dict[str, str]:
    if "auth_sessions" not in app:
        app["auth_sessions"] = _load_auth_sessions()
    return app["auth_sessions"]


def _load_auth_sessions() -> Dict[str, str]:
    try:
        if AUTH_SESSION_PATH.exists():
            with AUTH_SESSION_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        logger.warning(f"Failed to load auth sessions: {e}")
    return {}


def _save_auth_sessions(sessions: Dict[str, str]) -> None:
    AUTH_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = AUTH_SESSION_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(sessions, file, ensure_ascii=False, indent=2)
    tmp_path.replace(AUTH_SESSION_PATH)


def _client_ip(request: web.Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.remote or "unknown"


def _client_hostname(ip_address: str) -> str:
    if not ip_address or ip_address == "unknown":
        return "unknown"
    try:
        return socket.getfqdn(ip_address)
    except Exception:
        return "unknown"


def _is_verified(app: web.Application, session_id: str, auth_token: str) -> bool:
    if not session_id or not auth_token:
        return False
    return _auth_store(app).get(session_id) == auth_token


def _verification_record(request: web.Request, session_id: str) -> Dict[str, Any]:
    ip_address = _client_ip(request)
    return {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "ip": ip_address,
        "client_hostname": _client_hostname(ip_address),
        "server_hostname": socket.gethostname(),
        "host_header": request.host,
        "user_agent": request.headers.get("User-Agent", ""),
    }


def _append_auth_log(record: Dict[str, Any]) -> None:
    AUTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTH_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


async def auth_verify(request: web.Request) -> web.Response:
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        session_id = f"web-{uuid.uuid4().hex[:12]}"

    answer = str(payload.get("answer") or "").strip()
    if answer != "瑞":
        return web.json_response({
            "verified": False,
            "error": "verification_failed",
            "message": "验证失败",
        }, status=403)

    auth_token = uuid.uuid4().hex
    sessions = _auth_store(request.app)
    sessions[session_id] = auth_token
    _save_auth_sessions(sessions)
    record = _verification_record(request, session_id)
    _append_auth_log(record)
    logger.info(f"Web access verified (session={session_id}, ip={record['ip']})")

    return web.json_response({
        "verified": True,
        "session_id": session_id,
        "auth_token": auth_token,
    })


async def auth_status(request: web.Request) -> web.Response:
    session_id = request.query.get("session_id", "")
    auth_token = request.query.get("auth_token", "")
    return web.json_response({
        "verified": _is_verified(request.app, session_id, auth_token),
    })


async def chat(request: web.Request) -> web.Response:
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    question = str(payload.get("question", "")).strip()
    if not question:
        return web.json_response({"error": "question_required"}, status=400)

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        session_id = f"web-{uuid.uuid4().hex[:12]}"

    auth_token = str(payload.get("auth_token") or "").strip()
    if not _is_verified(request.app, session_id, auth_token):
        return web.json_response({
            "error": "not_verified",
            "answer": "请先完成验证确认。",
            "session_id": session_id,
        }, status=401)

    context = payload.get("context")
    if context is not None and not isinstance(context, dict):
        return web.json_response({"error": "context_must_be_object"}, status=400)

    coordinator = await get_coordinator(request.app)

    try:
        result = await asyncio.wait_for(
            coordinator.process(question, context=context, session_id=session_id),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Web chat timeout (session={session_id})")
        return web.json_response({
            "error": "timeout",
            "answer": "系统处理超时。请简化问题后重试；如症状严重或紧急，请立即就医。",
            "session_id": session_id,
            "suggestions": [],
            "disclaimer": "以上信息仅供参考，不能替代专业医生的诊断和治疗。",
        }, status=504)
    except Exception as e:
        logger.exception(f"Web chat failed: {e!r}")
        return web.json_response({
            "error": repr(e),
            "answer": "抱歉，处理您的问题时出现错误。",
            "session_id": session_id,
            "suggestions": [],
            "disclaimer": "以上信息仅供参考，不能替代专业医生的诊断和治疗。",
        }, status=500)

    result.setdefault("session_id", session_id)
    result.setdefault("suggestions", [])
    result.setdefault("disclaimer", "以上信息仅供参考，不能替代专业医生的诊断和治疗。")
    if not str(result.get("answer") or "").strip():
        logger.error(f"Coordinator returned empty answer (keys={list(result.keys())}, session={session_id})")
        result["error"] = "empty_answer"
        result["answer"] = "系统没有返回有效回答。请简化问题后重试；如症状严重或紧急，请立即就医。"
        return web.json_response(result, status=502)
    return web.json_response(result)


def _task_store(app: web.Application) -> Dict[str, Dict[str, Any]]:
    if "chat_tasks" not in app:
        app["chat_tasks"] = {}
    return app["chat_tasks"]


def _redis_client(app: web.Application):
    if "redis_client" in app:
        return app["redis_client"]
    try:
        import redis
        client = redis.Redis(
            host=REDIS_CONFIG.get("host", "localhost"),
            port=REDIS_CONFIG.get("port", 6379),
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password"),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        client.ping()
        app["redis_client"] = client
        logger.info("Recent conversations storage: Redis")
        return client
    except Exception as e:
        logger.info(f"Recent conversations storage: local file fallback ({e})")
        app["redis_client"] = None
        return None


def _load_recent_conversations_file() -> list:
    try:
        if RECENT_CONVERSATIONS_PATH.exists():
            with RECENT_CONVERSATIONS_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning(f"Failed to load recent conversations: {e}")
    return []


def _save_recent_conversations_file(items: list) -> None:
    RECENT_CONVERSATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = RECENT_CONVERSATIONS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)
    tmp_path.replace(RECENT_CONVERSATIONS_PATH)


def _conversation_title(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:18] + ("..." if len(compact) > 18 else "")


def _save_recent_conversation(app: web.Application, item: Dict[str, Any], limit: int = 20) -> None:
    client = _redis_client(app)
    if client:
        client.lpush(RECENT_CONVERSATIONS_KEY, json.dumps(item, ensure_ascii=False))
        client.ltrim(RECENT_CONVERSATIONS_KEY, 0, limit - 1)
        return

    items = _load_recent_conversations_file()
    items = [existing for existing in items if existing.get("id") != item.get("id")]
    items.insert(0, item)
    _save_recent_conversations_file(items[:limit])


def _get_recent_conversations(app: web.Application, limit: int = 10) -> list:
    client = _redis_client(app)
    if client:
        raw_items = client.lrange(RECENT_CONVERSATIONS_KEY, 0, limit - 1)
        items = []
        for raw in raw_items:
            try:
                items.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return items
    return _load_recent_conversations_file()[:limit]


async def chat_start(request: web.Request) -> web.Response:
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    question = str(payload.get("question", "")).strip()
    if not question:
        return web.json_response({"error": "question_required"}, status=400)

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        session_id = f"web-{uuid.uuid4().hex[:12]}"

    auth_token = str(payload.get("auth_token") or "").strip()
    if not _is_verified(request.app, session_id, auth_token):
        return web.json_response({
            "error": "not_verified",
            "message": "请先完成验证确认。",
            "session_id": session_id,
        }, status=401)

    context = payload.get("context")
    if context is not None and not isinstance(context, dict):
        return web.json_response({"error": "context_must_be_object"}, status=400)

    task_id = uuid.uuid4().hex
    store = _task_store(request.app)
    store[task_id] = {
        "task_id": task_id,
        "status": "running",
        "session_id": session_id,
        "question": question,
        "created_at": datetime.now().isoformat(),
        "progress": {
            "stage": "dispatch",
            "label": "任务已提交，等待后端接收",
            "percent": 3,
            "agents": [{"name": "Web API", "state": "排队"}],
            "mode": "协作",
        },
        "result": None,
        "error": None,
    }

    asyncio.create_task(
        run_chat_task(request.app, task_id, question, session_id, context)
    )
    return web.json_response({
        "task_id": task_id,
        "session_id": session_id,
        "status": "running",
    })


async def run_chat_task(
    app: web.Application,
    task_id: str,
    question: str,
    session_id: str,
    context: Any,
) -> None:
    store = _task_store(app)

    async def progress_callback(progress: Dict[str, Any]) -> None:
        task = store.get(task_id)
        if not task:
            return
        task["progress"] = {
            **task.get("progress", {}),
            **progress,
            "updated_at": datetime.now().isoformat(),
        }

    try:
        coordinator = await get_coordinator(app)
        result = await asyncio.wait_for(
            coordinator.process(
                question,
                context=context,
                session_id=session_id,
                progress_callback=progress_callback,
            ),
            timeout=180.0,
        )
        result.setdefault("session_id", session_id)
        result.setdefault("suggestions", [])
        result.setdefault("disclaimer", "以上信息仅供参考，不能替代专业医生的诊断和治疗。")
        if not str(result.get("answer") or "").strip():
            result["error"] = "empty_answer"
            result["answer"] = "系统没有返回有效回答。请简化问题后重试；如症状严重或紧急，请立即就医。"
            store[task_id]["status"] = "failed"
            store[task_id]["error"] = "empty_answer"
        else:
            store[task_id]["status"] = "completed"
            _save_recent_conversation(app, {
                "id": task_id,
                "session_id": session_id,
                "question": question,
                "title": _conversation_title(question),
                "created_at": datetime.now().isoformat(),
                "mode": "swarm" if result.get("swarm_enabled") else "single_agent",
                "agent_id": result.get("agent_id"),
                "agents_involved": result.get("agents_involved", []),
            })
        store[task_id]["result"] = result
        store[task_id]["progress"] = {
            "stage": "reply",
            "label": "回答已生成",
            "percent": 100,
            "agents": [{"name": "Response Writer", "state": "完成"}],
            "mode": "协作" if result.get("swarm_enabled") else "单 Agent",
            "updated_at": datetime.now().isoformat(),
        }
    except asyncio.TimeoutError:
        logger.warning(f"Web chat task timeout (task={task_id}, session={session_id})")
        store[task_id]["status"] = "failed"
        store[task_id]["error"] = "timeout"
        store[task_id]["progress"] = {
            "stage": "reply",
            "label": "系统处理超时",
            "percent": 100,
            "agents": [{"name": "Web API", "state": "超时"}],
            "mode": "协作",
            "updated_at": datetime.now().isoformat(),
        }
        store[task_id]["result"] = {
            "error": "timeout",
            "answer": "系统处理超时。请简化问题后重试；如症状严重或紧急，请立即就医。",
            "session_id": session_id,
            "suggestions": [],
            "disclaimer": "以上信息仅供参考，不能替代专业医生的诊断和治疗。",
        }
    except Exception as e:
        logger.exception(f"Web chat task failed: {e!r}")
        store[task_id]["status"] = "failed"
        store[task_id]["error"] = repr(e)
        store[task_id]["progress"] = {
            "stage": "reply",
            "label": "后端处理失败",
            "percent": 100,
            "agents": [{"name": "Web API", "state": "失败"}],
            "mode": "协作",
            "updated_at": datetime.now().isoformat(),
        }
        store[task_id]["result"] = {
            "error": repr(e),
            "answer": "抱歉，处理您的问题时出现错误。",
            "session_id": session_id,
            "suggestions": [],
            "disclaimer": "以上信息仅供参考，不能替代专业医生的诊断和治疗。",
        }


async def chat_status(request: web.Request) -> web.Response:
    task_id = request.match_info["task_id"]
    task = _task_store(request.app).get(task_id)
    if not task:
        return web.json_response({"error": "task_not_found"}, status=404)
    return web.json_response(task)


async def recent_conversations(request: web.Request) -> web.Response:
    limit = request.query.get("limit", "10")
    try:
        limit_int = max(1, min(50, int(limit)))
    except ValueError:
        limit_int = 10
    return web.json_response({
        "items": _get_recent_conversations(request.app, limit=limit_int)
    })


def create_app() -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)
    app.on_startup.append(warmup_embedding_model)
    app.router.add_get("/", index)
    app.router.add_get("/icon.png", icon)
    app.router.add_get("/brand-title.png", brand_title)
    app.router.add_get("/api/health", health)
    app.router.add_post("/api/auth/verify", auth_verify)
    app.router.add_get("/api/auth/status", auth_status)
    app.router.add_post("/api/chat", chat)
    app.router.add_post("/api/chat/start", chat_start)
    app.router.add_get("/api/chat/status/{task_id}", chat_status)
    app.router.add_get("/api/conversations/recent", recent_conversations)
    if FRONTEND_DIST_ROOT.exists():
        app.router.add_static("/assets", FRONTEND_DIST_ROOT / "assets", show_index=False)
    app.router.add_static("/static", WEB_ROOT, show_index=False)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MediX web frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=7860, type=int)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logger(args.verbose)
    logger.info(f"Starting MediX web frontend at http://{args.host}:{args.port}")
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
