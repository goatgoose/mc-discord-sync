import pathlib
import json

_config_dir = pathlib.Path(__file__).parent.resolve()
_config_path = f"{_config_dir}/config.json"

class _Config:
    def __init__(self, config_path):
        self._config = json.load(open(config_path))

        self.launch_command = self._config["launch_command"]
        self.discord_token = self._config["discord_token"]

        self.god_alias = "God"
        if "god_alias" in self._config:
            self.god_alias = self._config["god_alias"]

        self.manhunt_mode = False
        if "manhunt_mode" in self._config:
            self.manhunt_mode = self._config["manhunt_mode"]

        self.inactive_shutdown_seconds = 10 * 60
        if "inactive_shutdown_seconds" in self._config:
            self.inactive_shutdown_seconds = self._config["inactive_shutdown_seconds"]

        self.category = "mc-server"
        if "category" in self._config:
            self.category = self._config["category"]

        self.shutdown_command = None
        if "shutdown_command" in self._config:
            self.shutdown_command = self._config["shutdown_command"]

        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.aws_region = None
        if "aws_access_key_id" in self._config:
            self.aws_access_key_id = self._config["aws_access_key_id"]
        if "aws_secret_access_key" in self._config:
            self.aws_secret_access_key = self._config["aws_secret_access_key"]
        if "aws_region" in self._config:
            self.aws_region = self._config["aws_region"]

        self.flow_id = None
        self.flow_alias_id = None
        if "flow_id" in self._config:
            self.flow_id = self._config["flow_id"]
        if "flow_alias_id" in self._config:
            self.flow_alias_id = self._config["flow_alias_id"]

Config = _Config(_config_path)
