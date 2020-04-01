import pytest
from json import loads
import dataclasses
import pprint

from covreports.reports.resources import (
    Report,
    ReportFile,
    ReportLine,
    LineSession,
    Session,
)
from covreports.reports.carryforward import (
    generate_carryforward_report,
    carriedforward_session_name,
)


@pytest.fixture
def sample_report():
    report = Report()
    first_file = ReportFile("file_1.go")
    first_file.append(
        1, ReportLine(coverage=1, sessions=[LineSession(0, 1), LineSession(1, 1)])
    )
    first_file.append(
        2, ReportLine(coverage=1, sessions=[LineSession(0, 0), LineSession(1, 1)])
    )
    first_file.append(
        3, ReportLine(coverage=1, sessions=[LineSession(0, 1), LineSession(1, 0)])
    )
    first_file.append(
        5, ReportLine(coverage=0, sessions=[LineSession(0, 0), LineSession(1, 0)])
    )
    first_file.append(
        6,
        ReportLine(coverage="1/2", sessions=[LineSession(0, "1/2"), LineSession(1, 0)]),
    )
    second_file = ReportFile("file_2.py")
    second_file.append(12, ReportLine(coverage=1, sessions=[[0, 1]]))
    second_file.append(51, ReportLine(coverage="1/2", type="b", sessions=[[0, 1]]))
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(id=0, flags=["simple"]))
    report.add_session(Session(id=1, flags=["complex"]))
    return report


class TestCarryfowardFlag(object):
    def test_carriedforward_session_name(self):
        assert carriedforward_session_name(None) == "Carriedforward"
        assert carriedforward_session_name("") == "Carriedforward"
        assert carriedforward_session_name("Carriedforward") == "CF[1] - Carriedforward"
        assert carriedforward_session_name("Dude") == "CF[1] - Dude"
        assert carriedforward_session_name("CF[1] - Dude") == "CF[2] - Dude"
        assert carriedforward_session_name("CF[2] - Dude") == "CF[3] - Dude"
        assert carriedforward_session_name("CF[9] - Dude") == "CF[10] - Dude"
        assert carriedforward_session_name("CF[10] - Dude") == "CF[11] - Dude"
        assert carriedforward_session_name("CF CF Dude") == "CF[3] - Dude"
        assert carriedforward_session_name("CFCD") == "CF[1] - CFCD"
        assert (
            carriedforward_session_name("CF CF CF CF CF CF CF Dude") == "CF[8] - Dude"
        )

    def convert_report_to_better_readable(self, report):
        totals_dict, report_dict = report.to_database()
        report_dict = loads(report_dict)
        archive_dict = {}
        for filename in report.files:
            file_report = report.get(filename)
            lines = []
            for line_number, line in file_report.lines:
                (
                    coverage,
                    line_type,
                    sessions,
                    messages,
                    complexity,
                ) = dataclasses.astuple(line)
                sessions = [list(s) for s in sessions]
                lines.append(
                    (line_number, coverage, line_type, sessions, messages, complexity)
                )
            archive_dict[filename] = lines
        return {"totals": totals_dict, "report": report_dict, "archive": archive_dict}

    def test_generate_carryforward_report(self, sample_report):
        res = generate_carryforward_report(sample_report, flags=["simple"], paths=None)
        assert res.files == ["file_1.go", "file_2.py"]
        readable_report = self.convert_report_to_better_readable(res)
        expected_result = {
            "archive": {
                "file_1.go": [
                    (1, 1, None, [[0, 1, None, None, None]], None, None),
                    (2, 0, None, [[0, 0, None, None, None]], None, None),
                    (3, 1, None, [[0, 1, None, None, None]], None, None),
                    (5, 0, None, [[0, 0, None, None, None]], None, None),
                    (6, "1/2", None, [[0, "1/2", None, None, None]], None, None),
                ],
                "file_2.py": [
                    (12, 1, None, [[0, 1, None, None, None]], None, None),
                    (51, 1, "b", [[0, 1, None, None, None]], None, None),
                ],
            },
            "report": {
                "files": {
                    "file_1.go": [
                        0,
                        [0, 5, 2, 2, 1, "40.00000", 0, 0, 0, 0, 0, 0, 0],
                        [[0, 5, 2, 2, 1, "40.00000", 0, 0, 0, 0, 0, 0, 0]],
                        None,
                    ],
                    "file_2.py": [
                        1,
                        [0, 2, 2, 0, 0, "100", 1, 0, 0, 0, 0, 0, 0],
                        [[0, 2, 2, 0, 0, "100", 1, 0, 0, 0, 0, 0, 0]],
                        None,
                    ],
                },
                "sessions": {
                    "0": {
                        "a": None,
                        "c": None,
                        "d": readable_report["report"]["sessions"]["0"]["d"],
                        "e": None,
                        "f": ["simple"],
                        "N": "Carriedforward",
                        "j": None,
                        "n": None,
                        "p": None,
                        "st": "carriedforward",
                        "se": {},
                        "t": None,
                        "u": None,
                    }
                },
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 1,
                "c": "57.14286",
                "d": 0,
                "diff": None,
                "f": 2,
                "h": 4,
                "m": 2,
                "n": 7,
                "p": 1,
                "s": 1,
            },
        }
        assert readable_report["archive"] == expected_result["archive"]
        assert (
            readable_report["report"]["sessions"]
            == expected_result["report"]["sessions"]
        )
        assert readable_report["report"] == expected_result["report"]
        assert readable_report["totals"] == expected_result["totals"]
        assert readable_report == expected_result

    def test_generate_carryforward_report_with_paths(self, sample_report):
        res = generate_carryforward_report(
            sample_report, flags=["simple"], paths=["file_1.*"]
        )
        assert res.files == ["file_1.go"]
        readable_report = self.convert_report_to_better_readable(res)
        expected_result = {
            "archive": {
                "file_1.go": [
                    (1, 1, None, [[0, 1, None, None, None]], None, None),
                    (2, 0, None, [[0, 0, None, None, None]], None, None),
                    (3, 1, None, [[0, 1, None, None, None]], None, None),
                    (5, 0, None, [[0, 0, None, None, None]], None, None),
                    (6, "1/2", None, [[0, "1/2", None, None, None]], None, None),
                ],
            },
            "report": {
                "files": {
                    "file_1.go": [
                        0,
                        [0, 5, 2, 2, 1, "40.00000", 0, 0, 0, 0, 0, 0, 0],
                        [[0, 5, 2, 2, 1, "40.00000", 0, 0, 0, 0, 0, 0, 0]],
                        None,
                    ],
                },
                "sessions": {
                    "0": {
                        "a": None,
                        "c": None,
                        "d": readable_report["report"]["sessions"]["0"]["d"],
                        "e": None,
                        "f": ["simple"],
                        "N": "Carriedforward",
                        "j": None,
                        "n": None,
                        "p": None,
                        "st": "carriedforward",
                        "se": {},
                        "t": None,
                        "u": None,
                    }
                },
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 0,
                "c": "40.00000",
                "d": 0,
                "diff": None,
                "f": 1,
                "h": 2,
                "m": 2,
                "n": 5,
                "p": 1,
                "s": 1,
            },
        }
        assert readable_report["archive"] == expected_result["archive"]
        assert (
            readable_report["report"]["sessions"]
            == expected_result["report"]["sessions"]
        )
        assert readable_report["report"] == expected_result["report"]
        assert readable_report["totals"] == expected_result["totals"]
        assert readable_report == expected_result

    def test_generate_carryforward_report_with_path_none_matches(self, sample_report):
        res = generate_carryforward_report(
            sample_report, flags=["simple"], paths=["file_\\W.*"]
        )
        assert res.files == []
        readable_report = self.convert_report_to_better_readable(res)
        expected_result = {
            "archive": {},
            "report": {
                "files": {},
                "sessions": {
                    "0": {
                        "a": None,
                        "c": None,
                        "d": readable_report["report"]["sessions"]["0"]["d"],
                        "e": None,
                        "f": ["simple"],
                        "N": "Carriedforward",
                        "j": None,
                        "n": None,
                        "p": None,
                        "st": "carriedforward",
                        "se": {},
                        "t": None,
                        "u": None,
                    }
                },
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 0,
                "c": 0,
                "d": 0,
                "diff": None,
                "f": 0,
                "h": 0,
                "m": 0,
                "n": 0,
                "p": 0,
                "s": 1,
            },
        }
        assert readable_report["archive"] == expected_result["archive"]
        assert (
            readable_report["report"]["sessions"]
            == expected_result["report"]["sessions"]
        )
        assert readable_report["report"] == expected_result["report"]
        assert readable_report["totals"] == expected_result["totals"]
        assert readable_report == expected_result

    def test_generate_carryforward_report_with_path_two_patterns(self, sample_report):
        res = generate_carryforward_report(
            sample_report, flags=["simple"], paths=[".*\\.cpp", ".*_2\\..*"]
        )
        assert res.files == ["file_2.py"]
        readable_report = self.convert_report_to_better_readable(res)
        expected_result = {
            "archive": {
                "file_2.py": [
                    (12, 1, None, [[0, 1, None, None, None]], None, None),
                    (51, 1, "b", [[0, 1, None, None, None]], None, None),
                ],
            },
            "report": {
                "files": {
                    "file_2.py": [
                        0,
                        [0, 2, 2, 0, 0, "100", 1, 0, 0, 0, 0, 0, 0],
                        [[0, 2, 2, 0, 0, "100", 1, 0, 0, 0, 0, 0, 0]],
                        None,
                    ],
                },
                "sessions": {
                    "0": {
                        "a": None,
                        "c": None,
                        "d": readable_report["report"]["sessions"]["0"]["d"],
                        "e": None,
                        "f": ["simple"],
                        "N": "Carriedforward",
                        "j": None,
                        "n": None,
                        "p": None,
                        "st": "carriedforward",
                        "se": {},
                        "t": None,
                        "u": None,
                    }
                },
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 1,
                "c": "100",
                "d": 0,
                "diff": None,
                "f": 1,
                "h": 2,
                "m": 0,
                "n": 2,
                "p": 0,
                "s": 1,
            },
        }
        assert readable_report["archive"] == expected_result["archive"]
        assert (
            readable_report["report"]["sessions"]
            == expected_result["report"]["sessions"]
        )
        assert readable_report["report"]["files"] == expected_result["report"]["files"]
        assert readable_report["report"] == expected_result["report"]
        assert readable_report["totals"] == expected_result["totals"]
        assert readable_report == expected_result

    def test_generate_carryforward_report_one_file_not_covered(self, sample_report):
        res = generate_carryforward_report(sample_report, flags=["complex"], paths=None)
        assert res.files == ["file_1.go"]
        readable_report = self.convert_report_to_better_readable(res)

        pprint.pprint(readable_report)
        expected_result = {
            "archive": {
                "file_1.go": [
                    (1, 1, None, [[0, 1, None, None, None]], None, None),
                    (2, 1, None, [[0, 1, None, None, None]], None, None),
                    (3, 0, None, [[0, 0, None, None, None]], None, None),
                    (5, 0, None, [[0, 0, None, None, None]], None, None),
                    (6, 0, None, [[0, 0, None, None, None]], None, None),
                ],
            },
            "report": {
                "files": {
                    "file_1.go": [
                        0,
                        [0, 5, 2, 3, 0, "40.00000", 0, 0, 0, 0, 0, 0, 0],
                        [[0, 5, 2, 3, 0, "40.00000", 0, 0, 0, 0, 0, 0, 0]],
                        None,
                    ],
                },
                "sessions": {
                    "0": {
                        "a": None,
                        "c": None,
                        "d": readable_report["report"]["sessions"]["0"]["d"],
                        "e": None,
                        "f": ["complex"],
                        "N": "Carriedforward",
                        "j": None,
                        "n": None,
                        "p": None,
                        "st": "carriedforward",
                        "se": {},
                        "t": None,
                        "u": None,
                    }
                },
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 0,
                "c": "40.00000",
                "d": 0,
                "diff": None,
                "f": 1,
                "h": 2,
                "m": 3,
                "n": 5,
                "p": 0,
                "s": 1,
            },
        }
        assert readable_report["archive"] == expected_result["archive"]
        assert readable_report["report"] == expected_result["report"]
        assert readable_report["totals"] == expected_result["totals"]
        assert readable_report == expected_result

    def test_generate_carryforward_report_session_extras(self, sample_report):
        res = generate_carryforward_report(
            sample_report,
            flags=["complex"],
            paths=None,
            session_extras={"cfed_parent": "0f9ab1fe6c879bc49a9e559b23f49fd033daadb0"},
        )
        assert res.files == ["file_1.go"]
        readable_report = self.convert_report_to_better_readable(res)

        pprint.pprint(readable_report)
        expected_result = {
            "archive": {
                "file_1.go": [
                    (1, 1, None, [[0, 1, None, None, None]], None, None),
                    (2, 1, None, [[0, 1, None, None, None]], None, None),
                    (3, 0, None, [[0, 0, None, None, None]], None, None),
                    (5, 0, None, [[0, 0, None, None, None]], None, None),
                    (6, 0, None, [[0, 0, None, None, None]], None, None),
                ],
            },
            "report": {
                "files": {
                    "file_1.go": [
                        0,
                        [0, 5, 2, 3, 0, "40.00000", 0, 0, 0, 0, 0, 0, 0],
                        [[0, 5, 2, 3, 0, "40.00000", 0, 0, 0, 0, 0, 0, 0]],
                        None,
                    ],
                },
                "sessions": {
                    "0": {
                        "a": None,
                        "c": None,
                        "d": readable_report["report"]["sessions"]["0"]["d"],
                        "e": None,
                        "f": ["complex"],
                        "N": "Carriedforward",
                        "j": None,
                        "n": None,
                        "p": None,
                        "st": "carriedforward",
                        "se": {
                            "cfed_parent": "0f9ab1fe6c879bc49a9e559b23f49fd033daadb0"
                        },
                        "t": None,
                        "u": None,
                    }
                },
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 0,
                "c": "40.00000",
                "d": 0,
                "diff": None,
                "f": 1,
                "h": 2,
                "m": 3,
                "n": 5,
                "p": 0,
                "s": 1,
            },
        }
        assert readable_report["archive"] == expected_result["archive"]
        assert readable_report["report"] == expected_result["report"]
        assert readable_report["totals"] == expected_result["totals"]
        assert readable_report == expected_result