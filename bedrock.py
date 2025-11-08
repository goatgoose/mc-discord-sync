import boto3

from config import Config


class God:
    MAX_GEN_LEN = 256

    def __init__(self):
        self.bedrock = boto3.client(
            "bedrock-agent-runtime",
            aws_access_key_id=Config.aws_access_key_id,
            aws_secret_access_key=Config.aws_secret_access_key,
            region_name=Config.aws_region,
        )
        self.flow_id = Config.flow_id
        self.flow_alias_id = Config.flow_alias_id

    @staticmethod
    def available():
        if Config.aws_access_key_id is None:
            return False
        if Config.flow_id is None:
            return False
        if Config.flow_alias_id is None:
            return False
        return True

    def ask(self, requester, statement, context_log):
        prompt = f"{requester} says: {statement}\n\n"
        prompt += "The following events occurred on the server prior to this statement:\n"
        for message in context_log:
            prompt += f"> {message}\n"

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
