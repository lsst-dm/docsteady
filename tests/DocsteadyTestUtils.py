import json
from typing import List

import zephyr.scale.cloud.endpoints.paths

from docsteady.config import Config
from docsteady.tplan import build_tpr_model
from docsteady.utils import (
    get_all_executions,
    get_rest_session,
    get_teststeps,
    get_zephyr_api,
)
from docsteady.ve_baseline import do_ve_model, get_testcases_ve

ROOT = "tests/data"
# ROOT = "data"


def write_test_data(data: dict | list, name: str) -> None:
    """Wrtite a json file of the strucuter passed in"""
    fn = f"{ROOT}/{name}.json"
    with open(fn, "w") as f:
        json.dump(data, f)


def read_test_data(name: str) -> dict:
    fn = f"{ROOT}/{name}.json"
    with open(fn) as f:
        return json.load(f)


def getTplanData() -> None:
    # use zephy api
    tplan_key = "LVV-P90"
    # tplan_id='796396'
    # tplan = build_tpr_model(tplan_key)
    zapi = get_zephyr_api()
    resp = zapi.test_plans.get_test_plan(tplan_key)
    write_test_data(resp, "tplandata")


def getTestCycleData(id: str) -> None:
    zapi = get_zephyr_api()
    resp = zapi.test_cycles.get_test_cycle(id)
    write_test_data(resp, "TestCycle-" + id)


def getTestCaseData(id: str) -> None:
    zapi = get_zephyr_api()
    resp = zapi.test_cases.get_test_case(id)
    write_test_data(resp, "TestCase-" + id)


def getTestStepData(id: str) -> None:
    resp = get_teststeps(id)
    write_test_data(resp, "TestSteps-" + id)


def getTestResultData(id: str) -> None:
    "execution id form LVV-ENNNN"
    zapi = get_zephyr_api()
    resp = zapi.test_executions.get_test_execution(id)
    write_test_data(resp, "TestResult-" + id)


def getTestExecutionData(id: str) -> None:
    "test id form LVV-T2339"
    zapi = get_zephyr_api()
    resp = zapi.test_executions.get_test_executions(testCase=id)
    write_test_data(resp, "TestResult-" + id)


def getTestCases(id: str) -> list:
    return get_testcases_ve(id)


def getScriptStepsData(id: str) -> None:
    resp = get_teststeps(
        id, zephyr.scale.cloud.endpoints.paths.CloudPaths.EXECUTIONS_STEPS
    )
    write_test_data(resp, "ScriptSteps-" + id)


def getTprData(id: str) -> None:
    """construct the test plan and put in a file for testing."""
    tplan = build_tpr_model(id)
    write_test_data(tplan, "TPR-" + id)


def getVEdata(component: str = "DM", subcomponent: str = "") -> None:
    """construct the Verification Element  file for testing."""
    rs = get_rest_session()
    result = rs.get(
        Config.VE_COMPONENT_URL.format(cmpnt=component, maxR=5, startAt=0)
    ).json()
    ves = []
    for i in result["issues"]:
        det = rs.get(Config.ISSUE_URL.format(issue=i["key"]))
        ves.append(det.json())

    write_test_data(ves, f"VE-{component}-{subcomponent}")


def getVEdetail(key: str) -> None:
    """construct the Verification Element  file for testing."""
    rs = get_rest_session()
    ve_res = rs.get(Config.ISSUE_URL.format(issue=key))
    jve_res = ve_res.json()
    write_test_data(jve_res, f"VE-{key}")


def getExecutionsData(ids: List[str]) -> None:
    get_all_executions()
    keep = {}
    for id in ids:
        keep[id] = Config.CACHED_TEST_EXECUTIONS[id]
    write_test_data(keep, "TEST-EXECUTIONS")


def dumpPointers() -> None:
    write_test_data(Config.CACHED_POINTERS, "POINTERS")


def dumpTestcases() -> None:
    write_test_data(Config.CACHED_TESTCASES, "TESTCASES")


def getVEmodel() -> None:
    # May want to set DOFEW to true in ve_baseline .. to get small dataset
    mod = do_ve_model("DM", "")
    write_test_data(mod, "VEmodel")
