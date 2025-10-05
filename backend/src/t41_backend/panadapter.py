import asyncio
import numpy as np
import pyfftw
import math

from aiortc import RTCDataChannel
from collections import deque
from t41_backend.radio import Radio

class RTCWaterfall:
    def __init__(self, radio: Radio, channel: RTCDataChannel, fft_size=8000):
        self._radio = radio
        self._fft_size = fft_size
        self._channel = channel
        self._task = None
        self._agc = False

        # Fixed scaling
        self._fixed_min_db = -19
        self._fixed_max_db = 50

        # AGC
        self._agc_history_len = 50          # number of frames to remember
        self._agc_margin_db = 2.0           # extra headroom
        self._agc_alpha = 0.1               # smoothing factor (0 < alpha <= 1)

        self._agc_max_history = deque(maxlen=self._agc_history_len)
        self._agc_min_history = deque(maxlen=self._agc_history_len)

        self._agc_smoothed_max = None
        self._agc_smoothed_min = None

        if channel.readyState == "open":
            self._task = asyncio.create_task(self.waterfall())
        else:
            @channel.on("open")
            async def on_open():
                self._task = asyncio.create_task(self.waterfall())

        @channel.on("close")
        async def on_close():
            print("RTCWaterfall: datachannel on_close")
            if self._task:
                self._task.cancel()
                await self._task                           
         
    async def waterfall(self):
        try:        
            fft_in = pyfftw.empty_aligned(self._fft_size, dtype='complex64')
            fft_out = pyfftw.empty_aligned(self._fft_size, dtype='complex64') 

            fft = pyfftw.FFTW(fft_in, fft_out)
            window = np.hanning(self._fft_size)

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
                    samples = buffer[:self._fft_size]

                    # Remove DC offset
                    samples = samples - np.mean(samples)

                    # Apply window
                    samples = samples * window

                    # Perform FFT
                    fft_in[:] = samples
                    fft()

                    # Rotate used samples out of buffer
                    buffer_len -= self._fft_size
                    buffer[:buffer_len] = buffer[self._fft_size:self._fft_size + buffer_len]

                    # Compute magnitude in dB
                    db = 20 * np.log10(np.abs(fft_out) + 1e-6)

                    # Scale
                    spectrum = self.scale(db)

                    # Shift zero frequency to center
                    spectrum = np.fft.fftshift(spectrum)

                    self._channel.send(spectrum.tobytes())

            print(f"RTCWaterfall::waterfall: exiting with channel readyState {self._channel.readyState}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"RTCWaterfall::waterfall: Exception: {e}")

    def scale(self, db):
        if self._agc:
            return self.scale_agc(db)
        else:
            return self.scale_fixed(db)

    def scale_fixed(self, db):
        # Normalize into 0–255 (full 8-bit unsigned range)
        db_norm = (db - self._fixed_min_db) / (self._fixed_max_db - self._fixed_min_db) * 255.0

        # Clip and cast
        return np.clip(db_norm, 0, 255).astype(np.uint8)

    def scale_agc(self, db):
        # Update history
        sample = db[self._fft_size // 4:self._fft_size - (self._fft_size // 4)]

        self._agc_max_history.append(sample.max())
        self._agc_min_history.append(sample.min())

        # Compute recent max/min from history
        recent_max = max(self._agc_max_history)
        recent_min = min(self._agc_min_history)

        # Initialize smoothing if first frame
        if self._agc_smoothed_max is None:
            self._agc_smoothed_max = recent_max
            self._agc_smoothed_min = recent_min
        else:
            # Exponential smoothing
            self._agc_smoothed_max = self._agc_alpha * recent_max + (1 - self._agc_alpha) * self._agc_smoothed_max
            self._agc_smoothed_min = self._agc_alpha * recent_min + (1 - self._agc_alpha) * self._agc_smoothed_min

        # Apply margin
        min_db = self._agc_smoothed_min - self._agc_margin_db
        max_db = self._agc_smoothed_max + self._agc_margin_db

        # Normalize to 0–255
        db_norm = (db - min_db) / (max_db - min_db) * 255.0
        return np.clip(db_norm, 0, 255).astype(np.uint8)
