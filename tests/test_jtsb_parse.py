from __future__ import annotations

from marine_claims_ai.ingest.jtsb import apply_limit, parse_jtsb_list_page

SAMPLE_TR = """
<table>
<tr>
<td>2026年 01月27日</td>
<td>阪神港堺泉北区浜寺航路</td>
<td>押船第八新生丸バージしんせい衝突（灯標）</td>
<td>事故 衝突（単）</td>
<td>2026年 08月27日 <a href="https://jtsb.mlit.go.jp/ship/rep-acci/2026/MA2026-1.pdf">公表</a></td>
</tr>
<tr>
<td>nav</td><td>x</td><td>y</td><td>z</td>
<td><a href="https://jtsb.mlit.go.jp/iken.pdf">other</a></td>
</tr>
</table>
"""


def test_apply_limit_zero_means_all():
    items = list(range(10))
    assert apply_limit(items, 0) == items
    assert apply_limit(items, -1) == items
    assert apply_limit(items, 3) == [0, 1, 2]


def test_parse_jtsb_list_page_extracts_report_rows():
    rows = parse_jtsb_list_page(SAMPLE_TR)
    assert len(rows) == 1
    assert rows[0]["title"].startswith("押船第八新生丸")
    assert "rep-acci" in rows[0]["url"]
    assert "衝突" in rows[0]["accident_type"]


def test_strip_ignores_script_noise():
    html = (
        "<script>var x='</tr><td>fake</td>';</script>"
        + SAMPLE_TR
        + "<script type='text/javascript'>\nalert(1)\n</script >"
    )
    rows = parse_jtsb_list_page(html)
    assert len(rows) == 1
