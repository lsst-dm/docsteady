import json

ROOT = "tests/data"


def write(data: dict, name: str) -> None:
    fn = f"{ROOT}/{name}.json"
    with open(fn, "w") as f:
        json.dump(data, f)


def read(name: str) -> None:
    fn = f"{ROOT}/{name}.json"
    with open(fn) as f:
        return json.load(f)
