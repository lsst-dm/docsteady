import unittest
from os.path import exists

from DocsteadyTestUtils import read_test_data

from docsteady.config import Config
from docsteady.formatters import alphanum_map_array_sort, alphanum_map_sort
from docsteady.tplan import render_report

# dumpPointers


# from DocsteadyTestUtils import getExecutionsData, getTprData


class TestTPR(unittest.TestCase):
    def test_gen(self) -> None:
        # plan = "LVV-P63"
        plan = "LVV-P90"
        path = "tpr_test.tex"
        ppath = "tp_plan.tex"

        Config.INCLUDE_ALL_EXECS = True

        Config.CACHED_POINTERS = read_test_data("POINTERS")

        # getExecutionsData([27531072, 27531013, 27531080])
        Config.CACHED_TEST_EXECUTIONS = read_test_data("TEST-EXECUTIONS")

        # getTprData(plan)

        plan_dict = read_test_data(f"TPR-{plan}")
        # the next updates the sorted result inside the map
        alphanum_map_array_sort(plan_dict["test_results_map"])
        metadata = {
            "today": "2021-08-31",
            "docsteady_version": "test",
            "project": "LVV",
        }
        metadata["namespace"] = Config.NAMESPACE
        metadata["component_long_name"] = "TESTY Component"
        for t in plan_dict["test_cases_map"].values():
            print(t["test_personnel"])
        itemscount = 0
        for cycle in plan_dict["test_cycles_map"].values():
            if "test_items" not in cycle:
                print(f"{cycle['key']} has no test_items")
            else:
                print(
                    f"{cycle['key']} has  {len(cycle['test_items'])} "
                    f"test_items"
                )
                itemscount += 1
                for test_item in cycle["test_items"]:
                    tckey = test_item["test_case_key"]
                    tcm = "test_cases_map"
                    print(
                        f'{test_item["key"]} - '
                        f'{plan_dict[tcm][tckey]["test_personnel"]}'
                    )

        self.assertTrue(
            itemscount > 0,
            "no test_items in plan_dict['test_cycles_map'] cycles",
        )
        self.assertTrue("LVV-R181" in plan_dict["test_results_map"])
        self.check_plan(plan_dict)
        render_report(metadata, "tpr", plan_dict, format="latex", path=path)
        self.assertTrue(exists(path))
        render_report(
            metadata, "tpnoresult", plan_dict, format="latex", path=ppath
        )
        self.assertTrue(exists(ppath))

    def check_plan(self, plan_dict: dict) -> None:
        """do some of the loops in jinga
        set up same variable
        """
        ok: bool = True
        testcycles_map = alphanum_map_sort(plan_dict["test_cycles_map"])
        testresults_map = alphanum_map_sort(plan_dict["test_results_map"])

        for cycle in testcycles_map.values():
            print(f"Check {cycle['key']}")
            if "test_items" in cycle:
                for test_item in cycle["test_items"]:
                    print(test_item["key"])
                    ok = ok and test_item["key"][0] == "L"
                    for run in testresults_map[cycle["key"]].values():
                        print(
                            f"Execution {run['key']} "
                            f"{run['testExecutionStatus']}"
                        )
                        for issue_key in run["issue_links"]:
                            print(f"{test_item['key']} - issue {issue_key}")
                        if "script_results" in run:
                            print(
                                f"{test_item['key']} - has  "
                                f"{len(run['script_results']) } "
                                f"script results "
                            )
                        else:
                            print(
                                f"{test_item['key']} - has  no script results "
                            )

                    for tresult in testresults_map[cycle["key"]].values():
                        print(
                            f" Details {cycle['key']}-{test_item['key']} "
                            f"{tresult['key']}-{tresult['id']}:"
                        )
                        for script_result in tresult["sorted"]:
                            print(
                                f"Step {script_result['label']}   "
                                f"Status: {script_result['status']}"
                            )
        self.assertTrue(ok, " there were problems with the plan")

    def getlabels(self, result_map: dict) -> list[str]:
        labels = []
        for k, r in result_map.items():
            for tk, tr in r.items():
                for sr in tr["script_results"]:
                    labels.append(sr["label"])
        return labels

    def test_sortarray(self) -> None:
        plan = "LVV-P90"
        plan_dict = read_test_data(f"TPR-{plan}")
        result_map = plan_dict["test_results_map"]
        before_label = self.getlabels(result_map)
        print(before_label)
        sorted_map = alphanum_map_array_sort(result_map)
        after_label = self.getlabels(sorted_map)
        print(after_label)
        # self.assertNotEquals(before_label, after_label)
