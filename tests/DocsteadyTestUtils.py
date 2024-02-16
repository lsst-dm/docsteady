import json

ROOT = "tests/data"
# ROOT = "data"


def write_test_data(data: dict, name: str) -> None:
    fn = f"{ROOT}/{name}.json"
    with open(fn, "w") as f:
        json.dump(data, f)


def read_test_data(name: str) -> dict:
    fn = f"{ROOT}/{name}.json"
    with open(fn) as f:
        return json.load(f)
