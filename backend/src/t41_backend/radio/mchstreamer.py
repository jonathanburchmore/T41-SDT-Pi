import asyncio
import aiofiles
import sounddevice as sd
import numpy as np

from .radio import Radio
from .events import RadioEvents

class MCHStreamer(Radio):
    def __init__(self, device=1, rx_i=0, rx_q=1, sample_rate=192000):
        super().__init__(sample_rate=sample_rate)
        self._device = device
        self._rx_i = rx_i
        self._rx_q = rx_q
        self._stream = None

    async def startup(self):
        await super().startup()

        self._loop = asyncio.get_running_loop()

        self._stream = sd.InputStream(
            device=self._device,
            channels=10,
            samplerate=self.iq.sample_rate,
            blocksize=self.iq.block_size,
            dtype='int32',
            callback=self._rx_iq
        )
        self._stream.start()

    async def shutdown(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        await super().shutdown()

    def _rx_iq(self, indata, frames, time, status):
        if status:
            print(f"MCHStreamer::_rx_iq: status: {status}", flush=True)

        iq_block = (indata[:, self._rx_i].astype(np.float32) + 1j * indata[:, self._rx_q].astype(np.float32))
        iq_block = iq_block.astype(np.complex64)

        self._loop.call_soon_threadsafe(self.iq.put_nowait, iq_block)
