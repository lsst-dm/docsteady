import unittest
from os.path import exists

from DocsteadyTestUtils import read_test_data

from docsteady.config import Config
from docsteady.formatters import alphanum_map_array_sort
from docsteady.tplan import render_report


class TestTPR(unittest.TestCase):
    def test_gen(self) -> None:
        path = "tpr_test.tex"

        # data =

        # write_test_data(data, "tpr")

        plan_dict = read_test_data("tpr")
        # the next updates the sorted result inside the map
        alphanum_map_array_sort(plan_dict["test_results_map"])
        metadata = {
            "today": "2021-08-31",
            "docsteady_version": "test",
            "project": "LVV",
        }
        metadata["namespace"] = Config.NAMESPACE
        metadata["component_long_name"] = "TESTY Component"
        render_report(metadata, "tpr", plan_dict, format="latex", path=path)
        self.assertTrue(exists(path))

    def getlabels(self, result_map: dict) -> list[str]:
        labels = []
        for k, r in result_map.items():
            for tk, tr in r.items():
                for ttr in tr:
                    for sr in ttr["script_results"]:
                        labels.append(sr["label"])
        return labels

    def test_sortarray(self) -> None:
        plan_dict = read_test_data("tpr")
        result_map = plan_dict["test_results_map"]
        before_label = self.getlabels(result_map)
        print(before_label)
        sorted_map = alphanum_map_array_sort(result_map)
        after_label = self.getlabels(sorted_map)
        print(after_label)
        # self.assertNotEquals(before_label, after_label)
