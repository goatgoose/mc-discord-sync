import asyncio
from typing import Callable, Type

from mc_event import Event, Done, PlayerMessage, PlayerJoin, \
    PlayerLeave, Shutdown, List, Trigger, WhitelistAdd, WhitelistRemove, GodQuestion


class MCProcess:
    def __init__(self, command):
        self.command = command

        self.process = None
        self.line_buffer = []
        self.events = [
            Done,
            PlayerMessage,
            PlayerJoin,
            PlayerLeave,
            Shutdown,
            List,
            Trigger,
            WhitelistAdd,
            WhitelistRemove,
            GodQuestion
        ]
        self.event_callbacks: dict[Type[Event], [Callable]] = {
            event_type: [] for event_type in self.events
        }
        self.tasks = set()

    def spawn_task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def listen_for_event(self, event_type: Type[Event], callback: Callable):
        self.event_callbacks[event_type].append(callback)

    def get_chunk(self, char_limit):
        if len(self.line_buffer) == 0:
            return None

        chunk = ""
        while len(self.line_buffer) > 0:
            line = self.line_buffer[0]
            if len(line) + 1 > char_limit:
                # line is too big to send any chunk, so skip it
                self.line_buffer.pop(0)
                continue

            if len(chunk) + len(line) + 1 > char_limit:
                break

            chunk += line + "\n"
            self.line_buffer.pop(0)

        assert len(chunk) > 0
        return chunk

    async def _read_stream(self, stream):
        while True:
            try:
                line = await stream.readline()
            except EOFError:
                return
            if not line:
                return

            line = line.decode().strip()
            self.line_buffer.append(line)

            for event in self.events:
                parsed = event.parse(line)
                if parsed:
                    for callback in self.event_callbacks[event]:
                        self.spawn_task(callback(parsed))

    async def poll(self):
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE
        )

        await asyncio.gather(
            self._read_stream(self.process.stdout),
            self._read_stream(self.process.stderr),
        )

        await self.process.wait()

    async def write(self, message):
        assert self.process is not None
        message = message + "\n"
        message = message.encode()
        self.process.stdin.write(message)
