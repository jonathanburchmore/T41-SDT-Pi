import asyncio
import aiofiles
import soundcard as sc
import numpy as np

from .radio import Radio
from .events import RadioEvents

class MCHStreamer(Radio):
    def __init__(self, iq, audio_device="MCHStreamer Lite I2S TosLink Multichannel 10", rx_i=0, rx_q=0, sample_rate=192000):
        super().__init__(sample_rate=sample_rate)
        self._audio_device = audio_device
        self._rx_i = rx_i
        self._rx_q = rx_q

    async def startup(self):
        await super().startup()
        self._tasks["rx_iq"] = asyncio.create_task(self._rx_iq())

    async def _rx_iq(self):
        try:
            mic = sc.get_microphone(self._audio_device)
            input = mic.recorder(samplerate=self._iq.sample_rate, channels=10)

            while True:
                data = await asyncio.to_thread(input.record, numframes=self._iq.block_size)
                iq_block = (data[:, self._rx_i] + 1j * data[:, self._rx_q]).astype(np.complex64)

                await self.iq.put(iq_block)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"MCHStreamer::rx_iq: Exception: {e}")
