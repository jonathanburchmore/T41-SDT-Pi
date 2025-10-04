import asyncio
import numpy as np
import pyfftw
import math

from aiortc import RTCDataChannel
from t41_backend.radio import Radio

class RTCWaterfall:
    def __init__(self, radio: Radio, channel: RTCDataChannel, fft_size=8000):
        self._radio = radio
        self._fft_size = fft_size
        self._channel = channel
        self._task = None

        if channel.readyState == "open":
            self._task = asyncio.create_task(self.waterfall())
        else:
            @channel.on("open")
            async def on_open():
                self._task = asyncio.create_task(self.waterfall())

        @channel.on("close")
        async def on_close():
            if self._task:
                self._task.cancel()
                await self._task                           
         
    async def waterfall(self):
        try:        
            fft_in = pyfftw.empty_aligned(self._fft_size, dtype='complex64')
            fft_out = pyfftw.empty_aligned(self._fft_size, dtype='complex64') 

            fft = pyfftw.FFTW(fft_in, fft_out)

            buffer = np.empty((1 + math.ceil(self._fft_size / self._radio.iq.block_size)) * self._radio.iq.block_size, dtype='complex64')
            buffer_len = 0

            iq_stream = self._radio.iq.add_consumer()

            while self._channel.readyState == "open":
                # If the WebRTC channel backlog gets high, drop any old buffered samples and
                # wait until it recovers.
                while self._channel.bufferedAmount > self._fft_size * 2:
                    buffer_len = 0
                    await asyncio.sleep(0.001)

                iq_block = await iq_stream.get()
                buffer[buffer_len:buffer_len + self._radio.iq.block_size] = iq_block
                buffer_len += self._radio.iq.block_size

                while buffer_len >= self._fft_size:
                    fft_in[:] = buffer[:self._fft_size]
                    fft()
                    buffer_len -= self._fft_size
                    buffer[:buffer_len] = buffer[self._fft_size:self._fft_size + buffer_len]

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

                    self._channel.send(shifted.tobytes())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"RTCWaterfall::waterfall: Exception: {e}")
