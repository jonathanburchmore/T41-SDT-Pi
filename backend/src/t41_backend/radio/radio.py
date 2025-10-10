import asyncio

from abc import ABC, abstractmethod
from .menu import MainMenu

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

    def put_nowait(self, block):
        for queue in self.queues:
            if queue.full():
                # Discard oldest block
                _ = queue.get_nowait()
                
            queue.put_nowait(block)


class Radio(ABC):
    def __init__(self, sample_rate=192000):
        self.iq = IQBuffer(sample_rate=sample_rate)
        self._tasks = {}
        self._menu = MainMenu()

    async def startup(self):
        await self._menu.startup()

    async def shutdown(self):
        await self._menu.shutdown()

        for task in self._tasks.values():
            task.cancel()
            await task
