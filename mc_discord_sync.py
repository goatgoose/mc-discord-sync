import json
import discord
import asyncio

from mc_process import MCProcess
from mc_event import PlayerMessage, PlayerJoin, PlayerLeave

config = json.load(open("config.json"))


class ServerMessage:
    def __init__(self, username, message):
        self.username = username
        self.message = message


class MCSync(discord.Client):
    def __init__(self, *, intents, **options):
        super().__init__(intents=intents, **options)

        self.console_channel_name = "server-console"
        self.chat_channel_name = "chat-sync"
        self.channel_names = [
            self.console_channel_name,
            self.chat_channel_name,
        ]

        self.category_name = config.get("category")
        if self.category_name is None:
            self.category_name = "mc-server"

        self.mc_process = MCProcess(config["launch_command"])
        self.mc_process.listen_for_event(PlayerMessage, self.on_player_message)
        self.mc_process.listen_for_event(PlayerJoin, self.on_player_join)
        self.mc_process.listen_for_event(PlayerLeave, self.on_player_leave)

    async def on_ready(self):
        print("Logged on as", self.user)

        await self.create_channels()

        mc_process_task = asyncio.create_task(self.mc_process.poll())
        server_data_push_task = asyncio.create_task(self.server_data_task())

        await asyncio.gather(
            mc_process_task,
            server_data_push_task
        )

    async def create_channels(self):
        for guild in self.guilds:
            category = discord.utils.get(guild.categories, name=self.category_name)
            if not category:
                print(f"Creating {self.category_name} category")
                await guild.create_category(self.category_name)

            category = discord.utils.get(guild.categories, name=self.category_name)
            assert category is not None

            for channel_name in self.channel_names:
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if not channel:
                    print(f"Creating {channel_name} channel")
                    await category.create_text_channel(channel_name)

    async def server_data_task(self):
        while True:
            while (chunk := self.mc_process.get_chunk(1950)) is not None:
                for guild in self.guilds:
                    category = discord.utils.get(guild.categories, name=self.category_name)
                    assert category is not None
                    server_channel = discord.utils.get(category.text_channels, name=self.console_channel_name)
                    assert server_channel is not None

                    await server_channel.send(
                        "```" +
                        chunk +
                        "```"
                    )

            await asyncio.sleep(1)

    async def on_player_message(self, player_message):
        for guild in self.guilds:
            category = discord.utils.get(guild.categories, name=self.category_name)
            assert category is not None
            chat_channel = discord.utils.get(category.text_channels, name=self.chat_channel_name)
            assert chat_channel is not None

            await chat_channel.send(
                "***@" + player_message.username + "***: " +
                player_message.message
            )

    async def on_player_join(self, player_join):
        print(f"{player_join.username} joined the game!")

    async def on_player_leave(self, player_leave):
        print(f"{player_leave.username} left the game.")

    async def send_server_chat_message(self, message):
        formatted_message = json.dumps([
            "",
            {
                "text": f"@{message.username}: ",
                "bold": True,
                "italic": True,
                "color": "aqua",
                "hoverEvent": {
                    "action": "show_text",
                    "contents": "Synced from discord!"
                }
            },
            {
                "text": message.message
            }
        ])
        await self.mc_process.write("tellraw @a " + formatted_message)

    async def on_message(self, message):
        if message.author == self.user:
            return

        channel = message.channel
        if not channel.category:
            return

        if channel.category.name != self.category_name:
            return

        if message.channel.name == self.console_channel_name:
            await self.mc_process.write(message.content)
            return

        if message.channel.name == self.chat_channel_name:
            await self.send_server_chat_message(
                ServerMessage(message.author, message.content)
            )
            return


intents = discord.Intents.all()
client = MCSync(intents=intents)
client.run(config["discord_token"])
