import gzip

import pytest

from quasileak.io import read_jsonl, write_jsonl


def test_round_trip(tmp_path):
    rows = [{"a": 1}, {"b": "é"}]
    write_jsonl(tmp_path / "x.jsonl", rows)
    assert read_jsonl(tmp_path / "x.jsonl") == rows


def test_reads_gzip(tmp_path):
    with gzip.open(tmp_path / "x.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write('{"a": 1}\n\n')
    assert read_jsonl(tmp_path / "x.jsonl.gz") == [{"a": 1}]


@pytest.mark.parametrize("line", ['{"a": NaN}', "[1, 2]", "{"])
def test_rejects_bad_lines(tmp_path, line):
    (tmp_path / "x.jsonl").write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="[Ll]ine 1"):
        read_jsonl(tmp_path / "x.jsonl")
