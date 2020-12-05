import pytest
from mock import PropertyMock

from shared.reports.resources import ReportFile, _ignore_to_func
from shared.reports.types import ReportLine, ReportTotals


@pytest.mark.unit
def test_eof():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2)]
    assert r.eof == 3


@pytest.mark.unit
def test_len():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), None]
    assert len(r) == 2


@pytest.mark.unit
def test_repr():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), None]
    r.name = "name.py"
    assert repr(r) == "<ReportFile name=name.py lines=2>"


@pytest.mark.unit
@pytest.mark.parametrize(
    "line_modifier, lines",
    [(None, [(1, ReportLine(1)), (2, ReportLine(2))]), (lambda line: None, [])],
)
def test_lines(line_modifier, lines):
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), None]
    r._line_modifier = line_modifier
    assert list(r.lines) == lines


@pytest.mark.unit
def test_iter():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), None]
    r._line_modifier = lambda line: line if line.coverage == 1 else None
    lines = []
    for ln in r:
        lines.append(ln)
    assert lines == [ReportLine(1), None, None, None]


@pytest.mark.unit
def test_get_item():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), ReportLine(3), ReportLine(4)]
    r._totals = ReportTotals(0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert r[1] == ReportLine(1)
    assert r["totals"] == ReportTotals(0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0)


@pytest.mark.unit
@pytest.mark.parametrize(
    "get_val, error_message",
    [
        ([], "expecting type int got <class 'list'>"),
        (-1, "Line number must be greater then 0. Got -1"),
        (1, "Line #1 not found in report"),
    ],
)
def test_get_item_exception(get_val, error_message):
    r = ReportFile("filename")
    r._lines = []
    with pytest.raises(Exception) as e_info:
        r[get_val]
    assert str(e_info.value) == error_message


@pytest.mark.unit
@pytest.mark.parametrize(
    "ignore, get_val",
    [({"eof": "N", "lines": [1, 10]}, ReportLine(1)), ({}, ReportLine(0)),],
)
def test_set_item(ignore, get_val):
    r = ReportFile("filename")
    r._lines = [ReportLine(1)]
    r._line_modifier = None
    r._ignore = _ignore_to_func(ignore)
    assert r[1] == ReportLine(1)
    r[1] = ReportLine(0)
    assert r[1] == get_val


@pytest.mark.unit
@pytest.mark.parametrize(
    "index, set_val, error_message",
    [
        ("str", 1, "expecting type int got <class 'str'>"),
        (1, "str", "expecting type ReportLine got <class 'str'>"),
        (-1, ReportLine(), "Line number must be greater then 0. Got -1"),
    ],
)
def test_set_item_exception(index, set_val, error_message):
    r = ReportFile("filename")
    with pytest.raises(Exception) as e_info:
        r[index] = set_val
    assert str(e_info.value) == error_message


@pytest.mark.unit
def test_get_slice():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), ReportLine(3), ReportLine(4)]
    r._line_modifier = lambda line: None if line.coverage == 3 else line
    assert list(r[2:4]) == [
        (
            2,
            ReportLine(
                coverage=2, type=None, sessions=None, messages=None, complexity=None
            ),
        )
    ]


@pytest.mark.unit
def test_contains():
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), ReportLine(3), ReportLine(4)]
    assert (1 in r) is True
    assert (10 in r) is False


@pytest.mark.unit
def test_contains_exception():
    r = ReportFile("filename")
    with pytest.raises(Exception) as e_info:
        "str" in r
    assert str(e_info.value) == "expecting type int got <class 'str'>"


@pytest.mark.unit
@pytest.mark.parametrize(
    "totals, boolean", [(ReportTotals(), False), (ReportTotals(1, 1, 1, 1), True),]
)
def test_non_zero(totals, boolean):
    r = ReportFile("filename")
    r._totals = totals
    assert bool(r) is boolean


@pytest.mark.unit
@pytest.mark.parametrize(
    "line_modifier, line", [(None, ReportLine(1)), (lambda line: None, None),]
)
def test_get(line_modifier, line):
    r = ReportFile("filename")
    r._lines = [ReportLine(1), ReportLine(2), ReportLine(3), ReportLine(4)]
    r._line_modifier = line_modifier
    assert r.get(1) == line


@pytest.mark.unit
@pytest.mark.parametrize(
    "get_val, error_message",
    [
        ("str", "expecting type int got <class 'str'>"),
        (-1, "Line number must be greater then 0. Got -1"),
    ],
)
def test_report_file_get_exception(get_val, error_message):
    r = ReportFile("filename")
    with pytest.raises(Exception) as e_info:
        r.get(get_val)
    assert str(e_info.value) == error_message


@pytest.mark.unit
@pytest.mark.parametrize(
    "ignore, boolean, lines",
    [({"eof": "N", "lines": [1, 10]}, False, []), ({}, True, [(1, ReportLine(1))]),],
)
def test_append(ignore, boolean, lines):
    r = ReportFile("filename")
    r._ignore = _ignore_to_func(ignore)
    r._line_modifier = None
    r._lines = []
    assert r.append(1, ReportLine(1)) is boolean
    assert list(r.lines) == lines


@pytest.mark.unit
@pytest.mark.parametrize(
    "key, val, error_message",
    [
        ("str", ReportLine(), "expecting type int got <class 'str'>"),
        (1, "str", "expecting type ReportLine got <class 'str'>"),
        (-1, ReportLine(), "Line number must be greater then 0. Got -1"),
    ],
)
def test_report_file_append_exception(key, val, error_message):
    r = ReportFile("filename")
    with pytest.raises(Exception) as e_info:
        r.append(key, val)
    assert str(e_info.value) == error_message


@pytest.mark.unit
@pytest.mark.parametrize(
    "name, totals, list_before, merge_val, merge_return, list_after",
    [
        ("file.py", None, [], None, None, []),
        (
            "file.rb",
            None,
            [],
            ReportFile(name="file.rb", lines=[ReportLine(2)]),
            True,
            [(1, ReportLine(2))],
        ),
    ],
)
def test_merge(name, totals, list_before, merge_val, merge_return, list_after):
    r = ReportFile("filename")
    r.name = name
    r._lines = []
    r._totals = totals
    assert list(r.lines) == list_before
    assert r.merge(merge_val) == merge_return
    assert list(r.lines) == list_after


@pytest.mark.unit
@pytest.mark.parametrize(
    "_process_totals_return_val, _totals, is_process_called, totals",
    [
        (ReportTotals(1), None, True, ReportTotals(1)),
        (ReportTotals(2), ReportTotals(1), False, ReportTotals(1)),
    ],
)
def test_totals(_process_totals_return_val, _totals, is_process_called, totals, mocker):
    mocker.patch.object(
        ReportFile, "_process_totals", return_value=_process_totals_return_val
    )
    r = ReportFile("filename")
    r._totals = _totals
    assert r.totals == totals
    assert ReportFile._process_totals.called is is_process_called


@pytest.mark.unit
@pytest.mark.parametrize(
    "lines, diff, new_file, boolean",
    [
        ([], {"segments": []}, ReportFile("new.py"), False),
        (
            [],
            {
                "segments": [
                    {"header": [1, 1, 1, 1], "lines": ["- afefe", "+ fefe", "="]}
                ]
            },
            ReportFile("new.py"),
            False,
        ),
        (
            [ReportLine(1), ReportLine(2)],
            {
                "segments": [
                    {"header": [1, 1, 1, 1], "lines": ["- afefe", "+ fefe", "="]}
                ]
            },
            ReportFile("new.py"),
            True,
        ),
        (
            [],
            {
                "segments": [
                    {"header": [1, 1, 1, 1], "lines": ["- afefe", "+ fefe", "="]}
                ]
            },
            ReportFile("new.py", lines=[ReportLine(1), ReportLine(2)]),
            True,
        ),
    ],
)
def test_does_diff_adjust_tracked_lines(lines, diff, new_file, boolean):
    r = ReportFile("filename")
    r._lines = lines
    assert r.does_diff_adjust_tracked_lines(diff, new_file) is boolean


@pytest.mark.unit
def test_shift_lines_by_diff():
    r = ReportFile("filename")
    r._lines = [ReportLine(), ReportLine()]
    assert len(list(r.lines)) == 2
    r.shift_lines_by_diff(
        {
            "segments": [
                {
                    # [-, -, POS_to_start, new_lines_added]
                    "header": [1, 1, 1, 1],
                    "lines": ["- afefe", "+ fefe", "="],
                }
            ]
        }
    )
    assert len(list(r.lines)) == 1


@pytest.mark.unit
def test_del_item():
    r = ReportFile("name.h")
    with pytest.raises(TypeError):
        del r["line"]
    with pytest.raises(ValueError):
        del r[-1]
