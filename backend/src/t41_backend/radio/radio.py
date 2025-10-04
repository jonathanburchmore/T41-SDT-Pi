import asyncio
import aiofiles
import numpy as np

from abc import ABC, abstractmethod

class IQBuffer:
    def __init__(self, sample_rate=192000, block_size=2048):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.queues = []

    def add_consumer(self, maxsize=16):
        queue = asyncio.Queue(maxsize=maxsize)
        self.queues.append(queue)
        return queue

    async def put(self, block):
        for queue in self.queues:
            if queue.full():
                # Discard oldest block
                _ = queue.get_nowait()
                
            await queue.put(block)

class Radio(ABC):
    def __init__(self, sample_rate=192000):
        self.iq = IQBuffer(sample_rate=sample_rate)

    async def startup(self):
        self.rx_iq_task = asyncio.create_task( self._rx_iq_job() )

    async def shutdown(self):
        self.rx_iq_task.cancel()

        try:
            await self.rx_iq_task
        except Exception:
            pass

    @abstractmethod
    async def _rx_iq_job(self):
        pass

class DummyRadio(Radio):
    def __init__(self):
        super().__init__(sample_rate=192000)
        self._gqrx_file = "gqrx_20250930_023302_128975000_192000_fc.raw"

    async def _rx_iq_job(self):
        try:
            # Calculate delay to simulate "real" sample capture rate
            block_time = self.iq.block_size / self.iq.sample_rate

            # Replay the same file over and over, endlessly    
            while True:
                async with aiofiles.open( self._gqrx_file, "rb" ) as input:
                    while True:
                        raw = await input.read( self.iq.block_size * 2 * 4 )
                        if len( raw ) < self.iq.block_size * 2 * 4:
                            break

                        # Unpack interleaved I/Q samples and convert to complex64
                        raw = np.frombuffer( raw, dtype='<f4' )
                        iq_block = np.empty( self.iq.block_size, dtype='complex64' )
                        iq_block[ : ] = raw[ 0::2 ] + 1j * raw[ 1::2 ]

                        # Queue block
                        await self.iq.put( iq_block )

                        await asyncio.sleep( block_time )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print( e )
