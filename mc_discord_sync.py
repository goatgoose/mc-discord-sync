import json
import discord
import asyncio

from mc_process import MCProcess

config = json.load(open("config.json"))


class MCSync(discord.Client):
    def __init__(self, *, intents, **options):
        super().__init__(intents=intents, **options)

        self.chat_channel_category_name = "Text Channels"
        self.chat_channel_name = "server-chat"

        self.mc_process = MCProcess(config["launch_command"], self.on_server_message)

    async def on_ready(self):
        print("Logged on as", self.user)

        for guild in self.guilds:
            chat_channel = discord.utils.get(guild.text_channels, name=self.chat_channel_name)
            if not chat_channel:
                print("creating server chat channel")
                text_category = discord.utils.get(guild.categories, name=self.chat_channel_category_name)
                assert text_category is not None
                await guild.create_text_channel("server-chat", category=text_category)

        await self.mc_process.poll()

    async def on_server_message(self, message):
        for guild in self.guilds:
            chat_channel = discord.utils.get(guild.text_channels, name=self.chat_channel_name)
            assert chat_channel is not None

            await chat_channel.send(message)

    async def on_message(self, message):
        if message.author == self.user:
            return
        if not message.content.startswith("!"):
            return

        command = message.content[1:]

        if command == 'ping':
            await message.channel.send('pong')


intents = discord.Intents.all()
client = MCSync(intents=intents)
client.run(config["discord_token"])
