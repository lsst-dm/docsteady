# LSST Data Management System
# Copyright 2018 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
import re
from typing import Any


def as_anchor(text: str) -> str:
    """Convert text to an anchor tag.
    :type text: `str` Text to convert to an anchor
    :return: `str` Anchor tag
    """
    text = re.sub("[^0-9a-zA-Z -]+", "", text)
    text = text.replace(" ", "-")
    text = text.lower()
    return text


def alphanum_key(key: str) -> list[str | int]:
    """Turn a string into a list of string and number chunks.
    :type key: str
    """
    return [int(c) if c.isdigit() else c for c in re.split("([0-9]+)", key)]


def alphanum_map_sort(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return a new map according to the alphanum sorting of it"""
    return {
        i: mapping[i]
        for i in sorted(mapping, key=lambda item: alphanum_key(item))
    }


def alphanum_map_array_sort(mapping: dict[str, Any]) -> dict[str, Any]:
    """Updated the sorted result arrays in the map map map (map) list"""
    for k, r in mapping.items():
        for tk, tr in mapping.items():
            for ttk, ttrr in tr.items():
                if "script_results" in ttrr:
                    ttrr["sorted"] = sorted(
                        ttrr["script_results"], key=lambda d: d["index"]
                    )
                    continue
                for ttr in ttrr:
                    ttr["sorted"] = sorted(
                        ttr["script_results"], key=lambda d: d["index"]
                    )
    return mapping
