from enum import Enum, auto
from abc import ABC, abstractmethod
import re
import logging


class Event(ABC):
    @staticmethod
    @abstractmethod
    def parse(line: str):
        pass


class RawData(Event):
    def __init__(self, data):
        self.data = data

    @staticmethod
    def parse(line: str):
        return RawData(line)


class Done(Event):
    def __init__(self, init_time):
        self.init_time = init_time

    @staticmethod
    def parse(line: str):
        # [15:20:41] [Server thread/INFO]: Done (3.854s)! For help, type "help"
        match = re.match(r'^[^<>]*: Done \(([0-9.sm]+)\)! For help, type "help"', line)
        if match:
            return Done(match.group(1))


class PlayerMessage(Event):
    def __init__(self, username, message):
        self.username = username
        self.message = message

    @staticmethod
    def parse(line):
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

        return PlayerMessage(username, message)


class PlayerJoin(Event):
    def __init__(self, username):
        self.username = username

    @staticmethod
    def parse(line: str):
        match = re.match(r"^[^<>*]*: ([a-zA-Z0-9_]{2,16}) joined the game", line)
        if match:
            return PlayerJoin(match.group(1))
        return None


class PlayerLeave(Event):
    def __init__(self, username):
        self.username = username

    @staticmethod
    def parse(line: str):
        match = re.match(r"^[^<>*]*: ([a-zA-Z0-9_]{2,16}) left the game", line)
        if match:
            return PlayerLeave(match.group(1))
        return None


class Shutdown(Event):
    def __init__(self):
        pass

    @staticmethod
    def parse(line: str):
        match = re.match(r"^[^<>*]*: All dimensions are saved|^[^<>*]* Stopping server", line)
        if match:
            return Shutdown()
        return None


class List(Event):
    def __init__(self, players):
        self.players = players

    @staticmethod
    def parse(line: str):
        match = re.match(r"^[^<>]*: There are [0-9]+ of a max of [0-9]+ players online:(.*)", line)
        if match:
            players_list = match.group(1)
            if not players_list:
                return List([])

            return List(List._parse_players_list(players_list))

    @staticmethod
    def from_v12(line: str):
        # [01:31:07] [Server thread/INFO] [minecraft/DedicatedServer]: goatgoose1142
        match = re.match(r"^[^<>]*:(.*)", line)
        assert match is not None
        players_list = match.group(1)
        logging.info(f"v12 player list: {players_list}")
        if not players_list:
            return List([])

        return List(List._parse_players_list(players_list))

    @staticmethod
    def _parse_players_list(players_list: str):
        players = players_list.split(",")
        return [player.strip() for player in players]


class V12ListIndicator(Event):
    @staticmethod
    def parse(line: str):
        # [01:31:07] [Server thread/INFO] [minecraft/DedicatedServer]: There are 1/20 players online:
        match = re.match(r"^[^<>]*: There are [0-9]+/[0-9]+ players online:", line)
        if match:
            logging.info(f"v12 indicator: {line}")
            return V12ListIndicator()


class Trigger(Event):
    def __init__(self, username, objective, add_, set_):
        self.username = username
        self.objective = objective
        self.add = int(add_) if add_ else None
        self.set = int(set_) if set_ else None
        self.value = self.add if self.add else self.set

    @staticmethod
    def parse(line: str):
        # [15:58:36] [Server thread/INFO]: [goatgoose1142: Triggered [test]]
        # [14:33:17] [Server thread/INFO]: [goatgoose1142: Triggered [test] (added 11 to value)]
        # [14:32:56] [Server thread/INFO]: [goatgoose1142: Triggered [test] (set value to 1)]
        match = re.match(
            r"^[^<>]*: \["
            r"([a-zA-Z0-9_]{2,16}): "
            r"Triggered \[([a-zA-Z0-9_]+)\] ?"
            r"\(?(?:added ([0-9]+) to value|set value to ([0-9]+))?\)?"
            r"\]",
            line
        )
        if match:
            username = match.group(1)
            objective = match.group(2)
            add_ = match.group(3)
            set_ = match.group(4)
            return Trigger(username, objective, add_, set_)


class WhitelistAdd(Event):
    def __init__(self, username):
        self.username = username

    @staticmethod
    def parse(line: str):
        player_added_match = re.match(
            r"^[^<>]*: Added ([a-zA-Z0-9_]{2,16}) to the whitelist",
            line
        )
        if player_added_match:
            username = player_added_match.group(1)
            return WhitelistAdd(username)

        already_whitelisted_match = re.match(
            r"^[^<>]*: Player is already whitelisted",
            line
        )
        if already_whitelisted_match:
            return WhitelistAdd(None)


class WhitelistRemove(Event):
    def __init__(self, username):
        self.username = username

    @staticmethod
    def parse(line: str):
        player_removed_match = re.match(
            r"^[^<>]*: Removed ([a-zA-Z0-9_]{2,16}) from the whitelist",
            line
        )
        if player_removed_match:
            username = player_removed_match.group(1)
            return WhitelistRemove(username)

        player_not_whitelisted_match = re.match(
            r"^[^<>]*: Player is not whitelisted",
            line
        )
        if player_not_whitelisted_match:
            return WhitelistRemove(None)


class GodQuestion(Event):
    def __init__(self, username, question):
        self.username = username
        self.question = question

    @staticmethod
    def parse(line: str):
        player_message = PlayerMessage.parse(line)
        if player_message is None:
            return None

        if not player_message.message.lower().startswith("god"):
            return None
        if not player_message.message.lower().endswith("?"):
            return None

        return GodQuestion(player_message.username, player_message.message)
