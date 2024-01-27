import json
import time
import asyncio
import discord

from mc_process import MCProcess
from mc_event import PlayerMessage, PlayerJoin, PlayerLeave, Shutdown

config = json.load(open("config.json"))


class ServerMessage:
    def __init__(self, username, message):
        self.username = username
        self.message = message


class MCSync(discord.Client):
    INACTIVE_SHUTDOWN_SECONDS = 10 * 60

    def __init__(self, *, intents, **options):
        super().__init__(intents=intents, **options)

        self.console_channel_name = "server-console"
        self.chat_channel_name = "chat-sync"
        self.commands_channel_name = "server-commands"
        self.channel_names = [
            self.console_channel_name,
            self.chat_channel_name,
            self.commands_channel_name,
        ]

        self.category_name = config.get("category")
        if self.category_name is None:
            self.category_name = "mc-server"
        self.shutdown_command = config.get("shutdown_command")

        self.active_players = set()
        self.mc_process_task = None
        self.server_data_task = None
        self.shutdown_task = None

        self.mc_process = MCProcess(config["launch_command"])
        self.mc_process.listen_for_event(PlayerMessage, self.on_player_message)
        self.mc_process.listen_for_event(PlayerJoin, self.on_player_join)
        self.mc_process.listen_for_event(PlayerLeave, self.on_player_leave)
        self.mc_process.listen_for_event(Shutdown, self.on_shutdown)

    async def on_ready(self):
        print("Logged on as", self.user)

        await self.create_channels()

        self.mc_process_task = asyncio.create_task(self.mc_process.poll())
        self.server_data_task = asyncio.create_task(self.push_server_data())
        self.shutdown_task = asyncio.create_task(self.inactive_shutdown_timer(self.INACTIVE_SHUTDOWN_SECONDS))

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

    async def push_server_data(self):
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

    async def start_shutdown(self):
        await self.mc_process.write("stop")

    async def inactive_shutdown_timer(self, seconds):
        print(f"starting shutdown timer: {seconds}")
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            print("canceling shutdown timer")
            return

        print("shutdown timer elapsed")

        for guild in self.guilds:
            category = discord.utils.get(guild.categories, name=self.category_name)
            assert category is not None
            commands_channel = discord.utils.get(category.text_channels, name=self.commands_channel_name)
            assert commands_channel is not None
            await commands_channel.send(f"Shutting down {self.category_name} due to inactivity.")

        await self.start_shutdown()

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
        self.active_players.add(player_join.username)
        if self.shutdown_task:
            self.shutdown_task.cancel()
            self.shutdown_task = None

    async def on_player_leave(self, player_leave):
        self.active_players.remove(player_leave.username)
        if len(self.active_players) == 0:
            self.shutdown_task = asyncio.create_task(self.inactive_shutdown_timer(self.INACTIVE_SHUTDOWN_SECONDS))

    async def on_shutdown(self, shutdown):
        print("shutdown")
        if not self.shutdown_command:
            return

        shutdown_process = await asyncio.create_subprocess_exec(
            self.shutdown_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await shutdown_process.communicate()
        if stdout:
            print(stdout)
        if stderr:
            print(stderr)

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

        if message.channel.name == self.commands_channel_name:
            if not message.content.startswith("!"):
                return
            command = message.content[1:]

            if command == "stop":
                await message.channel.send(
                    f"Stopping {self.category_name}.\n"
                    f"> Note: manually stopping the server is no longer necessary. The server will now automatically "
                    f"shutdown after {self.INACTIVE_SHUTDOWN_SECONDS / 60} minutes of inactivity."
                )
                await self.start_shutdown()


intents = discord.Intents.all()
client = MCSync(intents=intents)
client.run(config["discord_token"])
