import asyncio
import aiofiles
import numpy as np

from .radio import Radio
from .events import RadioEvents

class DummyRadio(Radio):
    def __init__(self):
        super().__init__(sample_rate=192000)
        self._gqrx_file = "gqrx_20250930_023302_128975000_192000_fc.raw"

    async def startup(self):
        await super().startup()
        self._tasks["rx_iq"] = asyncio.create_task(self._rx_iq())
        self._tasks["status"] = asyncio.create_task(self._status())

    async def _rx_iq(self):
        try:
            # Calculate delay to simulate "real" sample capture rate
            block_time = self.iq.block_size / self.iq.sample_rate

            # Replay the same file over and over, endlessly    
            while True:
                async with aiofiles.open(self._gqrx_file, "rb") as input:
                    while True:
                        raw = await input.read(self.iq.block_size * 2 * 4)
                        if len( raw ) < self.iq.block_size * 2 * 4:
                            break

                        # Unpack interleaved I/Q samples and convert to complex64
                        raw = np.frombuffer(raw, dtype='<f4')
                        iq_block = np.empty(self.iq.block_size, dtype='complex64')
                        iq_block[:] = raw[0::2] + 1j * raw[1::2]

                        # Queue block
                        await self.iq.put(iq_block)

                        await asyncio.sleep(block_time)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"DummyRadio::rx_iq: Exception: {e}")

    async def _status(self):
        try:
            while True:
                await RadioEvents.status.emit("iq", sample_rate=self.iq.sample_rate, block_size=self.iq.block_size)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"DummyRadio::status: Exception: {e}")
