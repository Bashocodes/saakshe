"""saakshe.witness.voice — the Gemini Live voice bridge for the witness.

The founder can ask saakshe out loud: "anyone waiting on me?", "what did today
cost?", "what's reversible?". The voice agent rides the SAME tools-over-telemetry
contract as the text witness — it holds no static knowledge and refuses beyond the
stream. That parity is deliberate: voice can never say something the screen can't.

Gemini Live (BidiGenerateContent over a WebSocket) is live-only by nature — it
needs Vertex/Gemini credentials and a real audio stream, so it cannot be honestly
stubbed. This module therefore ships TWO paths over one WebSocket endpoint:

  * DEMO (creds-free, what the video shows): a text protocol over the socket that
    routes every message through the identical witness tools (witness.agent.respond),
    so the refusal beat and the telemetry answers work end-to-end without creds.
  * LIVE: opens a Gemini Live session with the five telemetry tools as function
    declarations and bridges audio frames both ways. Wired here; activates the
    moment ADC + a Gemini model resolve.

Protocol (both paths), JSON text frames:
    client → {"type":"text","text":"anyone waiting on me?","run_id":"fw_..."}
    server → {"type":"reply","text":"...","refused":false,"tool":"anyone_waiting", ...}
    server → {"type":"hello","mode":"demo|live","tools":[...]}            (on connect)
"""

from __future__ import annotations

import json
from typing import Any

from common import config
from common.stream import STREAM
from . import agent as witness
from . import telemetry as tel

# Advertise the tools by the SAME names the live Gemini-Live function
# declarations use in _run_live (tool_fns below), so the hello handshake can
# never drift from the real callable tools. (KNOWN_BUCKETS keys are the
# human-facing bucket labels, not the tool function names.)
_TOOL_NAMES = ["anyone_waiting", "cost_today", "whats_reversible", "what_learned", "whos_acting_now"]


async def handle_ws(websocket: Any) -> None:
    """FastAPI WebSocket handler. Accepts, greets, then serves the witness."""
    await websocket.accept()
    live = config.is_live()
    await websocket.send_text(json.dumps({
        "type": "hello",
        "mode": "live" if live else "demo",
        "tools": _TOOL_NAMES,
        "note": ("Gemini Live audio bridge active" if live
                 else "demo: text-over-WS through the same telemetry tools (voice activates with creds)"),
    }))

    if live:
        try:
            await _run_live(websocket)
            return
        except Exception as exc:  # noqa: BLE001 — degrade to text rather than drop the socket
            await websocket.send_text(json.dumps({"type": "notice", "text": f"live voice unavailable ({exc}); text mode"}))

    await _run_text(websocket)


async def _run_text(websocket: Any) -> None:
    """Demo path: text over the socket through the witness tools (incl. the refusal)."""
    from starlette.websockets import WebSocketDisconnect

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"type": "text", "text": raw}
            if msg.get("type") not in (None, "text"):
                continue
            run_id = msg.get("run_id")
            reply = await witness.respond(msg.get("text", ""), run_id, STREAM)
            await websocket.send_text(json.dumps({"type": "reply", **reply}))
    except WebSocketDisconnect:
        return


async def _run_live(websocket: Any) -> None:
    """Live path: bridge the WebSocket to a Gemini Live session whose only tools
    are the witness's telemetry readers. Audio in → Gemini → audio out; tool calls
    resolved against the live stream. (Activates with Vertex/Gemini creds.)"""
    from google import genai
    from google.genai import types
    from starlette.websockets import WebSocketDisconnect

    client = genai.Client(
        vertexai=True,
        project=config.GOOGLE_CLOUD_PROJECT or None,
        location=config.GEMINI_LOCATION,
    )

    # The five telemetry tools, declared so Gemini can call them mid-conversation.
    tool_fns = {
        "anyone_waiting": lambda: tel.anyone_waiting(None, STREAM),
        "cost_today": lambda: tel.cost_today(None, STREAM),
        "whats_reversible": lambda: tel.whats_reversible(None, STREAM),
        "what_learned": lambda: tel.what_learned(None, STREAM),
        "whos_acting_now": lambda: tel.whos_acting_now(None, STREAM),
    }
    declarations = [
        types.FunctionDeclaration(name=n, description=tel.KNOWN_BUCKETS.get(n, n),
                                  parameters=types.Schema(type=types.Type.OBJECT, properties={}))
        for n in tool_fns
    ]
    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=witness.WITNESS_SYSTEM)]),
        tools=[types.Tool(function_declarations=declarations)],
    )

    model = config.MODEL_LIVE  # GA native-audio Live model (config-overridable)
    async with client.aio.live.connect(model=model, config=live_config) as session:
        async def pump_client_to_gemini() -> None:
            try:
                while True:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                    if msg.get("type") == "audio":
                        await session.send_realtime_input(
                            audio=types.Blob(data=bytes.fromhex(msg["data"]), mime_type="audio/pcm")
                        )
                    elif msg.get("type") == "text":
                        await session.send_client_content(
                            turns=types.Content(role="user", parts=[types.Part(text=msg.get("text", ""))])
                        )
            except WebSocketDisconnect:
                return

        import asyncio
        pump = asyncio.create_task(pump_client_to_gemini())
        try:
            async for response in session.receive():
                # Resolve any tool calls against the live telemetry, then reply.
                if response.tool_call:
                    answers = []
                    for fc in response.tool_call.function_calls:
                        result = tool_fns.get(fc.name, lambda: {"error": "unknown tool"})()
                        answers.append(types.FunctionResponse(id=fc.id, name=fc.name, response=result))
                    await session.send_tool_response(function_responses=answers)
                data = getattr(response, "data", None)
                if data:
                    await websocket.send_text(json.dumps({"type": "audio", "data": data.hex()}))
                text = getattr(response, "text", None)
                if text:
                    await websocket.send_text(json.dumps({"type": "reply", "text": text, "live": True}))
        finally:
            pump.cancel()
