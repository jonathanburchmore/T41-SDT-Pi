import asyncio

from typing import Optional
from abc import ABC, abstractmethod
from pyee.asyncio import AsyncIOEventEmitter
from .events import RadioEvents

class BaseMenu(ABC):
    def __init__(self, parent: Optional["BaseMenu"]=None):
        self.human = AsyncIOEventEmitter()
        self.parent = parent

        pass

    async def push(self, child: "BaseMenu"):
        if self.parent:
            await self.parent.push(child)

    async def pop(self):
        if self.parent:
            await self.parent.pop()

    async def show(self):
        pass

    async def hide(self):
        self.human.remove_all_listeners()

    async def emit(self, event, *args, **kwargs):
        self.human.emit(event, *args, **kwargs)


class MainMenu(BaseMenu):
    def __init__(self):
        super().__init__()

        self._menu_stack = [self]
        self._tasks = {}

    async def startup(self):
        self._tasks["rx_iq"] = asyncio.create_task(self._event_pump())
        await self.show()

    async def shutdown(self):
        for task in self._tasks.values():
            task.cancel()
            await task

        for submenu in reversed(self._menu_stack):
            await submenu.hide()

    async def _event_pump(self):
        stream = RadioEvents.human.stream()

        try:
            while True:
                item = await stream.get()
                await self._menu_stack[-1].emit(item["event"], *item["args"], **item["kwargs"])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"MainMenu::_event_pump: Exception: {e}")
        finally:
            RadioEvents.human.end_stream(stream)

    async def push(self, child: BaseMenu):
        self._menu_stack.append(child)
        await child.show()

    async def pop(self):
        if len(self._menu_stack) > 1:
            menu = self._menu_stack.pop()
            await menu.hide()

    async def show(self):
        self.human.add_listener("button1", self.button_select)
        self.human.add_listener("button2", self.button_menu_up)
        self.human.add_listener("button3", self.button_band_up)
        self.human.add_listener("button4", self.button_zoom)
        self.human.add_listener("button5", self.button_menu_down)
        self.human.add_listener("button6", self.button_band_down)

    async def button_select(self):
        await RadioEvents.status.emit("select")

    async def button_menu_up(self):
        await RadioEvents.status.emit("menu_up")

    async def button_menu_down(self):
        await RadioEvents.status.emit("menu_down")

    async def button_band_up(self):
        await RadioEvents.status.emit("band_up")

    async def button_band_down(self):
        await RadioEvents.status.emit("band_down")

    async def button_zoom(self):
        await RadioEvents.status.emit("zoom")
