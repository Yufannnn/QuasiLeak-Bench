"""Value matching for closed-set and open-set attributes."""

from quasileak.confidence import values_match
from quasileak.llm.matching import truth_in_top
from quasileak.llm.recovery import recovered_pure


def test_closed_set_values():
    assert values_match("gender", "M", "male")
    assert values_match("income", "High", "high income")
    assert not values_match("relationship", "married", "engaged")


def test_open_set_ranking():
    assert truth_in_top(["Accountant", "Hotel accountant"], "Hotel accountant", attribute="occupation") == 1
    assert truth_in_top(["Masters in Finance"], "PhD in Chemistry", attribute="education") == 99
    assert truth_in_top(["early 40s"], "41", attribute="age") == 1

