import json
import time
import asyncio
import discord
import csv
import pathlib
import random
from io import BytesIO

from mc_process import MCProcess
from mc_event import Done, PlayerMessage, PlayerJoin, PlayerLeave, Shutdown, List, \
    Trigger, WhitelistAdd, WhitelistRemove, GodQuestion, RawData
from bedrock import God

mc_discord_dir = pathlib.Path(__file__).parent.resolve()
config = json.load(open(f"{mc_discord_dir}/config.json"))


class ServerMessage:
    def __init__(self, username, message):
        self.username = username
        self.message = message


class Emote:
    def __init__(self, command, local_general, local_target, global_general, global_target):
        self.command = command
        self.local_general = local_general
        self.local_target = local_target
        self.global_general = global_general
        self.global_target = global_target

    def local_general_message(self):
        return self.local_general

    def local_target_message(self, target):
        return self.local_target.replace("(Target)", target)

    def global_general_message(self, player):
        return self.global_general.replace("(Player)", player)

    def global_target_message(self, player, target):
        return self.global_target.replace("(Player)", player).replace("(Target)", target)


class MCSync(discord.Client):
    INACTIVE_SHUTDOWN_SECONDS = 20 * 60
    PRE_INIT_SERVER_HEARTBEAT_SECONDS = 120
    SERVER_HEARTBEAT_SECONDS = 30

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

        self.active_players = []
        self.mc_process_task = None
        self.server_data_task = None
        self.shutdown_task = None
        self.init_objectives_task = None
        self.heartbeat_task = None
        self.last_server_data_receive_time = None
        self.list_task = None

        self.server_done = False
        self.startup_data = []

        self.objectives = {"roll", "compass"}
        self.emotes = {}
        with open(f"{mc_discord_dir}/emotes.csv") as emote_file:
            reader = csv.reader(emote_file)
            for row in reader:
                command = row[0]
                local_general = row[1]
                local_target = row[2]
                global_general = row[3]
                global_target = row[4]
                self.emotes[command] = Emote(command, local_general, local_target, global_general, global_target)
                self.objectives.add(command)

        self.mc_process = MCProcess(config["launch_command"])
        self.mc_process.listen_for_event(RawData, self.on_raw_data)
        self.mc_process.listen_for_event(Done, self.on_done)
        self.mc_process.listen_for_event(PlayerMessage, self.on_player_message)
        self.mc_process.listen_for_event(PlayerJoin, self.on_player_join)
        self.mc_process.listen_for_event(PlayerLeave, self.on_player_leave)
        self.mc_process.listen_for_event(List, self.on_list)
        self.mc_process.listen_for_event(Shutdown, self.on_shutdown)
        self.mc_process.listen_for_event(Trigger, self.on_trigger)
        self.mc_process.listen_for_event(WhitelistAdd, self.on_whitelist_add)
        self.mc_process.listen_for_event(WhitelistRemove, self.on_whitelist_remove)
        self.mc_process.listen_for_event(GodQuestion, self.on_god_question)

        self.god = None
        if God.available():
            print("God is available")
            self.god = God()

        self.manhunt_mode = False
        if "manhunt_mode" in config:
            self.manhunt_mode = config["manhunt_mode"]
        if self.manhunt_mode:
            print("Manhunt mode enabled")

    async def send_discord_message(self, channel_name, message):
        for guild in self.guilds:
            category = discord.utils.get(guild.categories, name=self.category_name)
            assert category is not None
            channel = discord.utils.get(category.text_channels, name=channel_name)
            assert channel is not None
            await channel.send(message)

    async def send_discord_text_file(self, channel_name, message, file_name):
        for guild in self.guilds:
            category = discord.utils.get(guild.categories, name=self.category_name)
            assert category is not None
            channel = discord.utils.get(category.text_channels, name=channel_name)
            assert channel is not None
            await channel.send(file=discord.File(BytesIO(message.encode("utf-8")), file_name))

    async def on_ready(self):
        print("Logged on as", self.user)

        await self.create_channels()

        self.mc_process_task = asyncio.create_task(self.mc_process.poll())
        self.server_data_task = asyncio.create_task(self.push_server_data())
        self.heartbeat_task = asyncio.create_task(self.probe_server_heartbeat())

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
            await asyncio.sleep(1)

            chunk = self.mc_process.get_all()
            if chunk is None:
                continue

            if len(chunk) > 1950:
                await self.send_discord_text_file(self.console_channel_name, chunk, "server-data.txt")
            else:
                await self.send_discord_message(
                    self.console_channel_name,
                    "```" +
                    chunk +
                    "```"
                )

    async def on_raw_data(self, raw_data):
        self.last_server_data_receive_time = time.time()

    async def on_done(self, done):
        print(f"done: {done.init_time}")
        self.server_done = True
        self.list_task = asyncio.create_task(self.list_players())
        self.shutdown_task = asyncio.create_task(self.inactive_shutdown_timer(self.INACTIVE_SHUTDOWN_SECONDS))
        self.init_objectives_task = asyncio.create_task(self.init_objectives())

    async def on_player_message(self, player_message):
        print(f"player message: {player_message.message}")
        await self.send_discord_message(
            self.chat_channel_name,
            "***@" + player_message.username + "***: " + player_message.message
        )

    async def on_player_join(self, player_join):
        print(f"player joined: {player_join.username}")
        await self.mc_process.write("list")
        for objective in self.objectives:
            await self.mc_process.write(f"scoreboard players enable {player_join.username} {objective}")

    async def on_player_leave(self, player_leave):
        print(f"player left: {player_leave.username}")
        await self.mc_process.write("list")

    async def on_list(self, list_):
        print(f"list: {list_.players}")
        self.active_players = list_.players
        if len(self.active_players) == 0 and self.shutdown_task is None:
            self.shutdown_task = asyncio.create_task(self.inactive_shutdown_timer(self.INACTIVE_SHUTDOWN_SECONDS))
        elif len(self.active_players) > 0 and self.shutdown_task is not None:
            self.shutdown_task.cancel()
            self.shutdown_task = None

    async def on_shutdown(self, shutdown):
        print("shutdown")
        await self.shutdown()

    async def on_trigger(self, trigger):
        print(f"{trigger.username} triggered {trigger.objective} with {trigger.value}")
        await self.mc_process.write(f"scoreboard players enable {trigger.username} {trigger.objective}")

        message = None
        public = True
        if trigger.objective in self.emotes:
            emote = self.emotes[trigger.objective]
            message = emote.global_general_message(trigger.username)
            if trigger.value is not None:
                player_index = trigger.value - 1
                if 0 <= player_index < len(self.active_players):
                    message = emote.global_target_message(trigger.username, self.active_players[player_index])
        elif trigger.objective == "roll":
            roll = random.randint(1, 100)
            message = f"{trigger.username} rolls {roll} (1-100)"
        elif trigger.objective == "compass":
            public = False
            if not self.manhunt_mode:
                message = "Manhunt mode is disabled."
            else:
                message = "Behold: a compass."
                await self.mc_process.write(f"give {trigger.username} minecraft:compass")
        assert message is not None

        selector = "@a" if public else trigger.username
        await self.mc_process.write(f"tellraw {selector} {json.dumps([{'text': message}])}")
        if public:
            await self.send_discord_message(self.chat_channel_name, message)

    async def on_whitelist_add(self, whitelist_add):
        if whitelist_add.username:
            message = f"Added {whitelist_add.username} to the whitelist."
        else:
            message = "Player is already whitelisted."
        print(message)
        await self.send_discord_message(self.commands_channel_name, message)

    async def on_whitelist_remove(self, whitelist_remove):
        if whitelist_remove.username:
            message = f"Remove {whitelist_remove.username} from the whitelist."
        else:
            message = "Player is not whitelisted."
        print(message)
        await self.send_discord_message(self.commands_channel_name, message)

    async def on_god_question(self, god_question):
        print(f"god message: {god_question.question}")
        if not self.god:
            print("God not found")
            return

        reply = await asyncio.to_thread(self.god.ask, god_question.question)

        reply = reply.replace("\"", "")
        reply = reply.strip()

        formatted_message = json.dumps([
            "",
            {
                "text": "<God> ",
                "bold": True,
                "italic": True,
                "color": "dark_green",
            },
            {
                "text": reply
            }
        ])
        await self.mc_process.write("tellraw @a " + formatted_message)

        await self.send_discord_message(
            self.chat_channel_name,
            f"***@God***: {reply}"
        )

    async def list_players(self):
        while True:
            await self.mc_process.write("list")
            await asyncio.sleep(self.SERVER_HEARTBEAT_SECONDS)

    async def probe_server_heartbeat(self):
        self.last_server_data_receive_time = time.time()
        while True:
            if self.server_done:
                heartbeat_seconds = self.SERVER_HEARTBEAT_SECONDS
            else:
                heartbeat_seconds = self.PRE_INIT_SERVER_HEARTBEAT_SECONDS
            await asyncio.sleep(heartbeat_seconds)

            if time.time() - self.last_server_data_receive_time > heartbeat_seconds * 1.5:
                await self.send_discord_message(
                    self.commands_channel_name,
                    f"Shutting down {self.category_name} due to losing connection with the server. Use `!start` to "
                    f"reboot the instance after shutdown."
                )
                await self.shutdown()
                return

    async def init_objectives(self):
        for objective in self.objectives:
            await self.mc_process.write(f"scoreboard objectives add {objective} trigger")

    async def inactive_shutdown_timer(self, seconds):
        print(f"starting shutdown timer: {seconds}")
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            print("canceling shutdown timer")
            return

        print("shutdown timer elapsed")

        await self.send_discord_message(
            self.commands_channel_name,
            f"Shutting down {self.category_name} due to inactivity."
        )

        await self.start_shutdown()

    async def start_shutdown(self):
        await self.mc_process.write("stop")

    async def shutdown(self):
        if not self.shutdown_command:
            return

        await asyncio.sleep(5)

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
            command_split = [
                arg.strip() for arg in
                message.content[1:].split()
            ]
            command = command_split[0]
            args = command_split[1:]

            if command == "stop":
                await message.channel.send(
                    f"Stopping {self.category_name}.\n"
                    f"> Note: manually stopping the server is no longer necessary. The server will now automatically "
                    f"shutdown after {self.INACTIVE_SHUTDOWN_SECONDS / 60} minutes of inactivity."
                )
                await self.start_shutdown()
            if command == "kill":
                await message.channel.send(
                    f"Forcefully stopping {self.category_name}.\n"
                )
                await self.shutdown()
            if command == "whitelist":
                invalid_usage_message = f"Usage:\n" \
                                        f"`!whitelist <add/remove> <player>`"
                if len(args) != 2:
                    await message.channel.send(invalid_usage_message)
                    return

                add_remove = args[0]
                player = args[1]
                if add_remove == "add":
                    await message.channel.send(
                        f"Whitelisting {player}..."
                    )
                    await self.mc_process.write(f"whitelist add {player}")
                elif add_remove == "remove":
                    await message.channel.send(
                        f"Removing {player} from whitelist..."
                    )
                    await self.mc_process.write(f"whitelist remove {player}")
                else:
                    await message.channel.send(invalid_usage_message)
                    return


intents = discord.Intents.all()
client = MCSync(intents=intents)
client.run(config["discord_token"])
