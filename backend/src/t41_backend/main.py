import asyncio
import json

from typing import Set, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from contextlib import asynccontextmanager
from t41_backend.models import SDP, EventPayload
from t41_backend.radio import MCHStreamer, RadioEvents
from t41_backend.panadapter import RTCWaterfall

radio = MCHStreamer(sample_rate=96000)

peers: Set[RTCPeerConnection] = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await radio.startup()
    yield
    await asyncio.gather(*(pc.close() for pc in list(peers)), return_exceptions=True)
    peers.clear()
    await radio.shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/webrtc", response_model=SDP)
async def webrtc(sdp: SDP):
    if sdp.type != "offer":
        raise HTTPException(status_code=400, detail="Expected offer")
    
    pc = RTCPeerConnection(RTCConfiguration())
    peers.add(pc)

    @pc.on("datachannel")
    def on_datachannel(channel):
        if channel.label == 'waterfall':
            waterfall = RTCWaterfall(radio, channel)

    offer = RTCSessionDescription(sdp=sdp.sdp, type=sdp.type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    return SDP(sdp=pc.localDescription.sdp, type=pc.localDescription.type)

@app.get("/events/human")
async def human_events():
    stream = RadioEvents.human.stream()

    async def event_stream():
        try:
            while True:
                try:
                    item = await asyncio.wait_for(stream.get(), 15)

                    lines = [f"event: {item['event']}"]
                    if item.get("kwargs"):
                        lines.append(f"data: {json.dumps(item['kwargs'])}")
                    yield "\n".join(lines) + "\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            RadioEvents.human.end_stream(stream)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/events/human/{event}")
async def emit_human_event(event: str, payload: Optional[EventPayload]=None):
    kwargs = payload.model_dump() if payload else {}
    await RadioEvents.human.emit(event, **kwargs)

@app.get("/events/command")
async def command_events():
    stream = RadioEvents.command.stream()

    async def event_stream():
        try:
            while True:
                try:
                    item = await asyncio.wait_for(stream.get(), 15)

                    lines = [f"event: {item['event']}"]
                    if item.get("kwargs"):
                        lines.append(f"data: {json.dumps(item['kwargs'])}")
                    yield "\n".join(lines) + "\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            RadioEvents.command.end_stream(stream)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/events/command/{event}")
async def post_command_event(event: str, payload: Optional[EventPayload]=None):
    kwargs = payload.model_dump() if payload else {}
    await RadioEvents.command.emit(event, **kwargs)

@app.get("/events/status")
async def command_events():
    stream = RadioEvents.status.stream()

    async def event_stream():
        try:
            while True:
                try:
                    item = await asyncio.wait_for(stream.get(), 15)

                    lines = [f"event: {item['event']}"]
                    if item.get("kwargs"):
                        lines.append(f"data: {json.dumps(item['kwargs'])}")
                    yield "\n".join(lines) + "\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            RadioEvents.status.end_stream(stream)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
