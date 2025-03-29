import os.path
import pathlib
import json
import boto3
import logging


mc_discord_dir = pathlib.Path(__file__).parent.resolve()
config = json.load(open(f"{mc_discord_dir}/config.json"))


class God:
    MAX_GEN_LEN = 256

    def __init__(self):
        self.bedrock = boto3.client(
            "bedrock-agent-runtime",
            aws_access_key_id=config["aws_access_key_id"],
            aws_secret_access_key=config["aws_secret_access_key"],
            region_name=config["aws_region"],
        )
        self.flow_id = config["flow_id"]
        self.flow_alias_id = config["flow_alias_id"]

    @staticmethod
    def available():
        if "aws_access_key_id" not in config:
            return False
        if "flow_id" not in config:
            return False
        if "flow_alias_id" not in config:
            return False
        return True

    def ask(self, requester, question, message_history):
        prompt = f"{requester} asks: {question}\n\n"
        prompt += "The following messages were exchanged on the server prior to this question:\n"
        for message in message_history:
            prompt += f"> {message.username}: {message.message}\n"

        response = self.bedrock.invoke_flow(
            flowAliasIdentifier=self.flow_alias_id,
            flowIdentifier=self.flow_id,
            inputs=[
                {
                    "content": { "document": prompt },
                    "nodeName": "FlowInputNode",
                    "nodeOutputName": "document",
                }
            ]
        )

        for event in response["responseStream"]:
            if "flowOutputEvent" in event:
                content = event["flowOutputEvent"]["content"]["document"]
                return content

        assert False, "No flowOutputEvent in responseStream"


if __name__ == '__main__':
    from collections import deque
    from mc_event import PlayerMessage

    test_history = deque(maxlen=30)
    test_history.append(PlayerMessage("player1", "Hello, world!"))
    test_history.append(PlayerMessage("player2", "Hello, player1!"))
    test_history.append(PlayerMessage("player1", "Hello, player2!"))

    god = God()
    print(god.ask("player1", "God, which player said hello first?", test_history))
    print(god.ask("player1", "God, how do I triple ores in mekanism?", test_history))
