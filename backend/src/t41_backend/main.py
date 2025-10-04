import asyncio

from typing import Set
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from contextlib import asynccontextmanager
from t41_backend.models import SDPModel
from t41_backend.radio import DummyRadio
from t41_backend.panadapter import RTCWaterfall

radio = DummyRadio()

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

@app.post("/webrtc", response_model=SDPModel)
async def webrtc(sdp: SDPModel):
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
    
    return SDPModel(sdp=pc.localDescription.sdp, type=pc.localDescription.type)
