from enum import Enum, auto
from abc import ABC, abstractmethod
import re


class Event(ABC):
    @staticmethod
    @abstractmethod
    def parse(line: str):
        pass


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
        match = re.match(r"^[^<>]*: ([a-zA-Z0-9_]{2,16}) joined the game", line)
        if match:
            return PlayerJoin(match.group(1))
        return None


class PlayerLeave(Event):
    def __init__(self, username):
        self.username = username

    @staticmethod
    def parse(line: str):
        match = re.match(r"^[^<>]*: ([a-zA-Z0-9_]{2,16}) left the game", line)
        if match:
            return PlayerLeave(match.group(1))
        return None
