import json
import discord
import asyncio

from mc_process import MCProcess

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

        self.mc_process = MCProcess(config["launch_command"], on_message_cb=self.on_server_line)

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

    @staticmethod
    def parse_chat_message(line):
        if "[Server thread/INFO]" not in line:
            return None
        if (username_start := line.find(": <")) == -1:
            return None
        if (username_end := line.find(">", username_start + 1)) == -1:
            return None
        if not (username := line[username_start + 3:username_end]):
            return None
        if not (message := line[username_end + 1:]):
            return None
        if not (message := message.strip()):
            return None

        return ServerMessage(username, message)

    async def on_server_line(self, line):
        message = self.parse_chat_message(line)
        if not message:
            return

        for guild in self.guilds:
            category = discord.utils.get(guild.categories, name=self.category_name)
            assert category is not None
            chat_channel = discord.utils.get(category.text_channels, name=self.chat_channel_name)
            assert chat_channel is not None

            await chat_channel.send(
                "***@" + message.username + "***: " +
                message.message
            )

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

        if not message.content.startswith("!"):
            return

        command = message.content[1:]
        if command == 'ping':
            await message.channel.send('pong')


intents = discord.Intents.all()
client = MCSync(intents=intents)
client.run(config["discord_token"])
