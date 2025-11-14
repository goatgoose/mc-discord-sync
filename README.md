# mc-discord-sync

mc-discord-sync is a Discord bot that spawns a vanilla Minecraft server, and provides features enables interaction between Discord and Minecraft.

Features include:
- **Chat sync:** Creates a `#chat-sync` Discord channel, which synchronizes Discord and Minecraft chat messages.
- **Server console:** Creates a `#server-console` Discord channel, which contains real-time Minecraft server logs. Messages sent to `#server-console` are sent to the Minecraft server, allowing the server to be managed from Discord.
- **Server commands:** Creates a `#server-commands` Discord channel, which allow non-admin Discord users to interact with the server (see [Discord Commands](#discord-commands)).
- **Auto shutdown:** mc-discord-sync will monitor Minecraft player activity, and call a shutdown script after a configurable amount of time has passed.
- **Emotes:** Uses the Minecraft `trigger` feature to provide in-game auto-completed `/<emote>` commands.
- **God:** Invokes a configurable Bedrock flow when "God" (configurable) is mentioned, allowing players to talk to an AI model.

## Usage

Configure mc-discord-sync by creating a `config.json` file in the project directory:
```
{
  "discord_token": "<Discord bot token>",
  "launch_command": "./path/to/start_mc_server.sh",
  "shutdown_command": "./path/to/shutdown_machine.sh",
  "category": "mc-server", <-- The Discord category that channels will be created under.
  "aws_access_key_id": "<>", <-- AWS stuff is currently only used for the God feature
  "aws_secret_access_key": "<>",
  "flow_id": "<>",
  "flow_alias_id": "<>",
  "aws_region": "<>",
  "manhunt_mode": false, <-- Experimental manhunt mode.
  "inactive_shutdown_seconds": 300, <-- How long to wait before calling the shutdown script.
  "god_alias": "Bing Bong" <-- Optional alias for God.
}
```

Run mc-discord-sync as follows:
```
pip3 install -r requirements.txt
python3 mc_discord_sync.py
```

Using mc-discord-sync as intended currently requires manually setting up the infrastructure. See [goatcraft](#goatcraft) for a high-level overview.

### Discord Commands

Discord commands are entered in the automatically created `#server-commands` channel. The supported commands are as follows:
- `!stop`: Stops the Minecraft server, which then invokes the shutdown script.
- `!whitelist [add/remove] [player]`: Adds/removes a player from the Minecraft whitelist.

## Goatcraft

This package is part of the Goatcraft suite of software used to run the Goatcraft Minecraft server hosted with hourly compute. The primary aim of the Goatcraft software is to reduce server costs by providing convenient features for players to start/stop the server when it's not in use.

[mc-watcher](https://github.com/goatgoose/mc-watcher) is configured to run 24/7 on an extremely cheap instance. mc-watcher watches for `!start` commands in the `#server-commands` channel, and launches the more expensive instance running mc-discord-sync when received. mc-discord-sync is configured to run on startup, and starts the server when it's launched. It then waits until everyone has logged out for `inactive_shutdown_seconds`, and calls the shutdown script to shutdown the instance.

[mc-server-receptionist](https://github.com/goatgoose/mc-server-receptionist) is an alternative to launching the Minecraft server with mc-watcher via `!start`. Instead, the receptionist runs on another cheap instance, and proxies Minecraft join requests, launches the mc-discord-instance if it's off, and transfers the player after it launches.
