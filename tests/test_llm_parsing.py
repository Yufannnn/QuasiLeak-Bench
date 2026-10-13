import pytest

from quasileak.confidence import sanitize_ranked
from quasileak.llm.matching import truth_in_top
from quasileak.llm.parsing import parse_object, probability, probe_rows, request_object


@pytest.mark.parametrize("raw", ["", '{"x": 1, "x": 2}', '{"x": NaN}', '{"x":', 'text {"x": 1}', "[]"])
def test_bad_json(raw):
    with pytest.raises(ValueError):
        parse_object(raw)


def test_json_fence():
    assert parse_object('```json\n{"x": 1}\n```') == {"x": 1}


@pytest.mark.parametrize("value", [None, True, "0.8", -0.1, 1.1, float("inf"), float("nan")])
def test_invalid_confidence(value):
    with pytest.raises(ValueError):
        probability(value)


def test_missing_probe():
    with pytest.raises(ValueError, match="cover"):
        probe_rows({}, ["1"])


def test_closed_set_rank():
    assert truth_in_top(["Female", "Male"], "Male", attribute="gender") == 2
    assert truth_in_top(["very high income", "high income"], "high income", attribute="income") == 2
    assert sanitize_ranked("gender", ["invalid", "Male", "Female"]) == ["", "male", "female"]


def test_retry_keeps_prompt():
    class Client:
        users = []

        def generate(self, **kwargs):
            self.users.append(kwargs["user"])
            return '{"1": 2}' if len(self.users) == 2 else "{"

    client = Client()
    assert request_object(client, system="rules", user="question") == {"1": 2}
    assert client.users[1].startswith("question")
