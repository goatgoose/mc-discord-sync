import pathlib
import json
import boto3


mc_discord_dir = pathlib.Path(__file__).parent.resolve()
config = json.load(open(f"{mc_discord_dir}/config.json"))


class God:
    MODEL_ID = "meta.llama2-70b-chat-v1"
    MAX_GEN_LEN = 256

    def __init__(self):
        self.bedrock = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=config["aws_access_key_id"],
            aws_secret_access_key=config["aws_secret_access_key"],
            region_name=config["aws_region"],
        )

        with open(f"{mc_discord_dir}/god_prompt.txt") as god_prompt:
            self.inst = god_prompt.read().strip()

    @staticmethod
    def available():
        return "aws_access_key_id" in config

    def ask(self, question):
        prompt = f"{self.inst}\n\n{question}"
        body = json.dumps({
            "prompt": prompt,
            "max_gen_len": self.MAX_GEN_LEN,
        })
        print(body)

        response = self.bedrock.invoke_model(
            body=body,
            modelId=self.MODEL_ID,
            accept="application/json",
            contentType="application/json",
        )

        response_body = json.loads(response.get("body").read())
        generation = response_body.get("generation")
        return generation


if __name__ == '__main__':
    god = God()
    print(god.ask("God, why did beans1797 build such a big house?"))
