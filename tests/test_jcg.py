"""Tests of the extraction of the Japan Coast Guard's volcano pages (tools/parse_jcg.py) and of
its import (tools/import_jcg.py). The pages are small fixtures in the shape of the real ones; no
network."""

from __future__ import annotations

import io
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_jcg  # noqa: E402
import parse_jcg  # noqa: E402


def _row(day, time, text, observer="海上保安庁"):
    return (f'<div class="actbox">\n<div class="act_td">{day}</div>\n<div class="act_td">{time}</div>\n'
            f'<div class="act_td">{text}</div>\n<div class="act_td">{observer}</div>\n</div>\n')


def _page(*tables):
    body = "".join(f'<h2 id="activity{i or ""}">「{site}」活動記録</h2>\n<div class="acttable">\n'
                   + "".join(_row(*r) for r in rows) + "</div>\n"
                   for i, (site, rows) in enumerate(tables))
    return ('<html><head><meta charset="utf-8" /></head><body>\n<h2 id="outline">概要</h2>\n'
            f"<!-- <h2 id=\"activity_old\">「古い表」活動記録</h2> -->\n{body}"
            '<h2 id="picture">写真</h2>\n</body></html>\n')


ISLAND = [
    ("２０２２／６／１", "10:00-10:20", "南岸に黄緑色の変色水域が分布していた。"),
    ("2021/3/2-4", "", "特異事象は認められなかった。"),
    ("2020/12/30-1/2", "", "天候が悪く視認できなかった。"),
    ("2019/5/1<br />2019/5/3", "", "噴気は認められなかった。"),
    ("2018/7/1～2018/8/1", "", "航空機により観測した。"),
    ("2017/4", "", "変色水を認めず、特異事象なし。"),
    ("2013年", "", "2013年3月25日，7月1日 変色水を認めず，特異事象なし．"),
    ("2012/9/9", "", "変色水を認めた。"),
]
NEARBY = [("2016年5月6日", "9:00", "噴火浅根付近に気泡を認めた。")]
OTHER = [("2023/1/1", "", "変色水を認めた。"), ("2001/1/1", "", "噴煙を認めた。")]

SITES = [
    dict(volcano_id="V1", jcg_page="kaiyo1-2.htm", site_ja="テスト島", site_en="Test Island", match="summit",
         zones="V1-A", note=""),
    dict(volcano_id="V1", jcg_page="kaiyo1-2.htm", site_ja="近くの瀬", site_en="Near Bank", match="nearby",
         zones="", note=""),
]


@pytest.fixture
def pages(tmp_path):
    (tmp_path / "kaiyo1-2.htm").write_text(_page(("テスト島", ISLAND), ("近くの瀬", NEARBY)), encoding="utf-8")
    (tmp_path / "kaiyo2-2.htm").write_text(_page(("別の火山", OTHER)), encoding="utf-8")
    (tmp_path / "copyright.html").write_text("<html><body>terms</body></html>", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("raw, day, year", [
    ("2022/6/1", "2022-06-01", 2022),
    ("２０２２／６／１", "2022-06-01", 2022),
    ("2021/3/2-4", "2021-03-02/2021-03-04", 2021),
    ("2021/3/2～4", "2021-03-02/2021-03-04", 2021),
    ("2020/12/30-1/2", "2020-12-30/2021-01-02", 2020),
    ("2018/7/1～2018/8/1", "2018-07-01/2018-08-01", 2018),
    ("2019/5/1 2019/5/3", "2019-05-01/2019-05-03", 2019),
    ("2017/4", "2017-04", 2017),
    ("2013", "2013", 2013),
    ("２０１３年", "2013", 2013),
    ("2016年5月6日", "2016-05-06", 2016),
    ("2016年5月", "2016-05", 2016),
    ("2015年頃", None, 2015),
    ("不明", None, None),
])
def test_dates(raw, day, year):
    assert parse_jcg.parse_date(raw) == (day, year)


def test_sections_skip_comments_and_clean_cells(pages):
    secs = list(parse_jcg.sections(pages / "kaiyo1-2.htm"))
    assert [s for s, _ in secs] == ["テスト島", "近くの瀬"]
    assert secs[0][1][3][0] == "2019/5/1 2019/5/3"
    assert all(len(r) == 4 for r in secs[0][1])


def test_category_rules():
    c = parse_jcg.categorise
    assert c("南岸に黄緑色の変色水域が分布していた。") == ("anomaly", "dw")
    assert c("変色水域及び浮遊物を認めた。噴気は認められなかった。") == ("anomaly", "dw+fl")
    assert c("特異事象は認められなかった。") == ("none", "")
    assert c("変色水を認めず、特異事象なし。") == ("none", "")
    assert c("天候が悪く視認できなかった。") == ("not_visible", "")
    assert c("航空機により観測した。") == ("other", "")
    # a place name with a phenomenon word in it is not a phenomenon
    assert c("噴火浅根付近に気泡を認めた。") == ("anomaly", "bubbles")
    assert c("噴火浅根西ノ瀬付近を観測した。") == ("other", "")


def test_a_hand_set_category_wins():
    text = "航空機により観測した。"
    assert parse_jcg.categorise(text, {text: ("anomaly", "dw")}) == ("anomaly", "dw")
    assert parse_jcg.categorise("天候が悪く視認できなかった。", {text: ("anomaly", "dw")})[0] == "not_visible"


def test_records_of_the_named_tables(pages):
    overrides = {"航空機により観測した。": ("not_visible", "")}
    recs, others = parse_jcg.records(pages, SITES, overrides)
    assert list(recs[0]) == parse_jcg.FIELDS
    island = [r for r in recs if r["jcg_site"] == "テスト島"]
    assert [r["date"] for r in island] == ["2013", "2017-04", "2018-07-01/2018-08-01", "2019-05-01/2019-05-03",
                                           "2020-12-30/2021-01-02", "2021-03-02/2021-03-04", "2022-06-01"]
    assert [r["category"] for r in island] == ["none", "none", "not_visible", "none", "not_visible", "none",
                                               "anomaly"]
    assert {r["match"] for r in island} == {"summit"}
    near = [r for r in recs if r["jcg_site"] == "近くの瀬"]
    assert near == [dict(volcano_id="V1", jcg_page="kaiyo1-2.htm", jcg_site="近くの瀬", match="nearby",
                         date="2016-05-06", time="9:00", observer="海上保安庁", category="anomaly",
                         phenomena="bubbles", text_ja="噴火浅根付近に気泡を認めた。")]
    # a table the site table does not name is reported with its rows since 2013, not read
    assert others == [("kaiyo2-2.htm", "別の火山", 1)]
    assert parse_jcg.check(pages, SITES, overrides) == 0


def test_a_named_table_that_is_missing_stops(pages):
    with pytest.raises(SystemExit):
        parse_jcg.records(pages, [dict(SITES[0], site_ja="無い島")], {})
    with pytest.raises(SystemExit):
        parse_jcg.records(pages, [dict(SITES[0], jcg_page="kaiyo9-2.htm")], {})


class _Response(io.BytesIO):
    class headers:  # noqa: N801
        @staticmethod
        def get_content_charset():
            return "utf-8"


def _opener(pages: dict, seen: list):
    def opener(req, timeout=None):
        seen.append((req.full_url, req.get_header("User-agent")))
        name = req.full_url.rsplit("/", 1)[-1]
        if name not in pages:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        return _Response(pages[name].encode("utf-8"))
    return opener


def test_download_plan_and_pause(tmp_path):
    plan = parse_jcg.fetch_plan(SITES)
    assert plan == [(parse_jcg.BASE + "list-2.htm", "list-2.htm", False),
                    (parse_jcg.BASE + "kaiyo1-2.htm", "kaiyo1-2.htm", True),
                    ("https://www1.kaiho.mlit.go.jp/copyright.html", "copyright.html", False)]
    seen, waits = [], []
    served = {"list-2.htm": "<html>list</html>", "kaiyo1-2.htm": _page(("テスト島", ISLAND)),
              "copyright.html": "<html>terms</html>"}
    assert parse_jcg.download(plan, tmp_path, _opener(served, seen), sleep=waits.append) == 3
    assert [u for u, _ in seen] == [u for u, _, _ in plan]
    assert {a for _, a in seen} == {parse_jcg.USER_AGENT}
    assert waits == [parse_jcg.WAIT, parse_jcg.WAIT]
    assert [s for s, _ in parse_jcg.sections(tmp_path / "kaiyo1-2.htm")] == ["テスト島"]


def test_download_stops_at_an_error_or_a_page_without_table(tmp_path):
    plan = parse_jcg.fetch_plan(SITES)
    seen = []
    with pytest.raises(SystemExit, match="HTTP 404"):
        parse_jcg.download(plan, tmp_path, _opener({"list-2.htm": "<html></html>"}, seen), sleep=lambda s: None)
    assert len(seen) == 2 and not (tmp_path / "kaiyo1-2.htm").exists()
    with pytest.raises(SystemExit, match="no record table"):
        parse_jcg.download(plan, tmp_path, _opener({"list-2.htm": "", "kaiyo1-2.htm": "<html>moved</html>"}, []),
                           sleep=lambda s: None)
    assert not (tmp_path / "kaiyo1-2.htm").exists()


def _csv(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_summaries_fall_back_to_the_present_table(tmp_path):
    previous = _csv(tmp_path / "jcg_observations.csv",
                    "text_ja,summary_en\nA,Old summary of A\nB,Old summary of B\nC,\n")
    summaries = _csv(tmp_path / "jcg_summaries.csv", "text_ja,summary_en\nB,New summary of B\nD,Summary of D\n")
    got = import_jcg.load_summaries(summaries, previous)
    assert got == {"A": "Old summary of A", "B": "New summary of B", "D": "Summary of D"}
    assert import_jcg.load_summaries(tmp_path / "none.csv", previous) == {"A": "Old summary of A",
                                                                         "B": "Old summary of B"}
