from reel2rules.cli import paragraphs, parse_vtt, safe, sub_langs

VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
<c>buy the</c> breakout

00:00:02.000 --> 00:00:04.000
buy the breakout

00:00:04.000 --> 00:00:06.000
of the &amp; range

00:01:05.000 --> 00:01:07.000
exit at close
"""


def test_parse_vtt_strips_tags_and_rolling_duplicates():
    lines = parse_vtt(VTT)
    assert [s for _, s in lines] == ["buy the breakout", "of the   range", "exit at close"]
    assert lines[-1][0] == 65


def test_paragraphs_chunk_by_minute():
    txt = paragraphs([(0, "a"), (30, "b"), (65, "c")])
    assert txt == "[00:00] a b\n\n[01:05] c"


def test_sub_langs_never_wildcard():
    assert all("*" not in x for x in sub_langs("en"))
    assert sub_langs("de") == ["de", "de-orig"]


def test_safe_names():
    assert safe("a/b c?") == "a_b_c_"
    assert safe("") == "video"
