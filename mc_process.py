import asyncio


class MCProcess:
    def __init__(self, command, on_message_cb):
        self.command = command
        self.on_message_cb = on_message_cb

    async def _read_stream(self, steam):
        while True:
            line = await steam.readline()
            if not line:
                break
            await self.on_message_cb(line.decode())

    async def poll(self):
        process = await asyncio.create_subprocess_exec(
            self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await asyncio.gather(
            self._read_stream(process.stdout),
            self._read_stream(process.stderr),
        )

        await process.wait()
