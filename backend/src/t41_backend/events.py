import asyncio

from pyee.asyncio import AsyncIOEventEmitter
from types import SimpleNamespace

class T41EventEmitter:
    def __init__(self):
        self._emitter = AsyncIOEventEmitter()
        self._streams = set()

    def stream(self):
        stream = asyncio.Queue()
        self._streams.add(stream)

        return stream

    def end_stream(self, stream):
        self._streams.remove(stream)

    def add_listener(self, event_name, f):
        return self._emitter.add_listener(event_name, f)
    
    async def emit(self, event, *args, **kwargs):
        self._emitter.emit(event, *args, **kwargs)

        for stream in self._streams:
            await stream.put({
                "event": event,
                "args": args,
                "kwargs": kwargs
            })

    def event_names(self):
        return self._emitter.event_names()

    def listeners(self, event):
        return self._emitter.listeners(event)

    def listens_to(self, event):
        return self._emitter.listens_to(event)

    def on(self, event, f=None):
        return self._emitter.on(event, f)

    def once(self, event, f=None):
        return self._emitter.once(event, f)

    def remove_all_listeners(self, event):
        return self._emitter.remove_all_listeners(event)

    def remove_listener(self, event, f):
        return self._emitter.remove_listener(event, f)

T41Events = SimpleNamespace(
    human=T41EventEmitter(),
    command=T41EventEmitter(),
    status=T41EventEmitter()
)