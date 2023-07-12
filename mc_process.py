import asyncio


class MCProcess:
    def __init__(self, command, on_message_cb=None):
        self.command = command
        self.on_message_cb = on_message_cb

        self.process = None
        self.line_buffer = []

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

    async def _read_stream(self, steam):
        while True:
            line = await steam.readline()
            if not line:
                break
            line = line.decode().strip()
            self.line_buffer.append(line)

            if self.on_message_cb:
                await self.on_message_cb(line)

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
