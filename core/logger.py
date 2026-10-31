import json
import os
import time


class JsonlLogger:
    def __init__(self, name):
        os.makedirs("logs", exist_ok=True)
        self.path = f"logs/{name}_{int(time.time())}.jsonl"

    def log(self, **data):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, default=str) + "\n")

