import json
import discord
import asyncio

from mc_process import MCProcess

config = json.load(open("config.json"))


class MCSync(discord.Client):
    def __init__(self, *, intents, **options):
        super().__init__(intents=intents, **options)

        self.console_channel_name = "server-console"

        self.mc_process = MCProcess(config["launch_command"])

    async def on_ready(self):
        print("Logged on as", self.user)

        for guild in self.guilds:
            server_channel = discord.utils.get(guild.text_channels, name=self.console_channel_name)
            if not server_channel:
                print("creating server console channel")
                await guild.create_text_channel(self.console_channel_name)

        mc_process_task = asyncio.create_task(self.mc_process.poll())
        server_data_push_task = asyncio.create_task(self.server_data_task())

        await asyncio.gather(
            mc_process_task,
            server_data_push_task
        )

    async def server_data_task(self):
        while True:
            while (chunk := self.mc_process.get_chunk(1950)) is not None:
                for guild in self.guilds:
                    server_channel = discord.utils.get(guild.text_channels, name=self.console_channel_name)
                    assert server_channel is not None

                    await server_channel.send(
                        "```" +
                        chunk +
                        "```"
                    )

            await asyncio.sleep(1)

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.channel.name == self.console_channel_name:
            await self.mc_process.write(message.content)

        if not message.content.startswith("!"):
            return

        command = message.content[1:]
        if command == 'ping':
            await message.channel.send('pong')


intents = discord.Intents.all()
client = MCSync(intents=intents)
client.run(config["discord_token"])
