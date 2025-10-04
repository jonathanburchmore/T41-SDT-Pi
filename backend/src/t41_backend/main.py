import asyncio
import aiofiles
import json
import numpy as np
import pyfftw
import math

from typing import Set
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from contextlib import asynccontextmanager
from t41_backend.models import SDPModel
from t41_backend.radio import DummyRadio

radio = DummyRadio()

peers: Set[ RTCPeerConnection ] = set()

async def waterfall_task(channel):
    try:        
        fft_size = 8000

        fft_in = pyfftw.empty_aligned(fft_size, dtype='complex64')
        fft_out = pyfftw.empty_aligned(fft_size, dtype='complex64') 

        fft = pyfftw.FFTW(fft_in, fft_out)

        buffer = np.empty((1 + math.ceil(fft_size / radio.iq.block_size)) * radio.iq.block_size, dtype='complex64')
        buffer_len = 0

        iq_stream = radio.iq.add_consumer()

        while channel.readyState == "open":
            # If the WebRTC channel backlog gets high, drop any old buffered samples and
            # wait until it recovers.
            while channel.bufferedAmount > fft_size * 2:
                buffer_len = 0
                await asyncio.sleep(0.001)

            iq_block = await iq_stream.get()
            buffer[buffer_len:buffer_len + radio.iq.block_size] = iq_block
            buffer_len += radio.iq.block_size

            while buffer_len >= fft_size:
                fft_in[:] = buffer[:fft_size]
                fft()
                buffer_len -= fft_size
                buffer[:buffer_len] = buffer[fft_size:fft_size + buffer_len]

                # Compute magnitude in dB
                db = 20 * np.log10(np.abs(fft_out) + 1e-6)

                # Expected dynamic range: -70 dB to 0 dB
                min_db, max_db = -15.0, 50.0

                # Normalize into 0–255 (full 8-bit unsigned range)
                db_norm = (db - min_db) / (max_db - min_db) * 255.0

                # Clip and cast
                spectrum = np.clip(db_norm, 0, 255).astype(np.uint8)

                # Shift zero frequency to center (optional for plotting)
                half = len(spectrum) // 2
                shifted = np.empty_like(spectrum)
                shifted[:half] = spectrum[half:]
                shifted[half:] = spectrum[:half]

                channel.send(shifted.tobytes())

        print(f"Exiting waterfall thread: {channel.state}")
    except asyncio.CancelledError:
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    await radio.startup()
    yield
    await asyncio.gather(*( pc.close() for pc in list(peers)), return_exceptions=True)
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
async def waterfall(sdp: SDPModel):
    if sdp.type != "offer":
        raise HTTPException(status_code=400, detail="Expected offer")
    
    pc = RTCPeerConnection(RTCConfiguration())
    peers.add(pc)

    @pc.on("datachannel")
    def on_datachannel(channel):
        task = None
        task_fn = None

        if channel.label == "waterfall":
            task_fn = waterfall_task

        if task_fn != None:
            if channel.readyState == "open":
                task = asyncio.create_task(task_fn(channel))
            else:
                @channel.on("open")
                def on_open():
                    nonlocal task
                    task = asyncio.create_task(task_fn(channel))

            @channel.on("close")
            def on_close():
                if task and not task.done():
                    task.cancel()

    offer = RTCSessionDescription(sdp=sdp.sdp, type=sdp.type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    return SDPModel(sdp=pc.localDescription.sdp, type=pc.localDescription.type)
