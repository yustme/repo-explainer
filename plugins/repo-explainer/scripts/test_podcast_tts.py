"""Unit tests for the pure helpers in podcast_tts.py (respell / parse / concat).

Run: pytest scripts/test_podcast_tts.py
The synthesis itself (XTTS/say/ffmpeg) is an integration concern and not unit tested.
"""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "podcast_tts", Path(__file__).resolve().parent / "podcast_tts.py"
)
pt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pt)


class TestRespell:
    def test_acronyms_uppercase_word_bounded(self):
        assert pt.respell("vrací JSON", "cs") == "vrací džejson"
        assert pt.respell("volá MCP a API", "cs") == "volá em cé pé a á pí"

    def test_acronym_not_matched_inside_word(self):
        # lowercase 'api' inside a Czech word must not be rewritten
        assert "á pí" not in pt.respell("rapidně", "cs")
        # uppercase CI rule must not touch lowercase 'ci' inside words
        assert pt.respell("funkci", "cs") == "funkci"

    def test_stem_keeps_czech_suffix(self):
        assert pt.respell("příkaz kbagentu", "cs") == "příkaz ká bé agentu"
        assert pt.respell("ten firewall", "cs") == "ten fajrvól"

    def test_serve_vs_server_word_boundary(self):
        assert pt.respell("příkaz serve", "cs") == "příkaz sérv"
        assert pt.respell("běžící server", "cs") == "běžící servr"

    def test_multiword_before_single(self):
        assert pt.respell("Claude Code je nástroj", "cs") == "klód kód je nástroj"

    def test_english_lang_unchanged(self):
        s = "It returns JSON over HTTP via the API."
        assert pt.respell(s, "en") == s

    def test_unknown_lang_is_identity(self):
        assert pt.respell("JSON API", "de") == "JSON API"


class TestParseScript:
    def test_parses_speakers_and_skips_noise(self, tmp_path):
        p = tmp_path / "s.txt"
        p.write_text(
            "A: první replika\n"
            "\n"
            "B: druhá: s dvojtečkou uvnitř\n"
            "nějaký řádek bez prefixu\n"
            "C: cizí mluvčí se ignoruje\n"
            "A:    \n"  # empty text -> skipped
            "a: malé a se taky bere\n",
            encoding="utf-8",
        )
        turns = pt.parse_script(p)
        assert turns == [
            ("A", "první replika"),
            ("B", "druhá: s dvojtečkou uvnitř"),
            ("A", "malé a se taky bere"),
        ]


class TestBuildConcatList:
    def test_gaps_between_clips_longer_on_speaker_change(self):
        out = pt.build_concat_list(
            speakers=["A", "A", "B"],
            clip_names=["c0.wav", "c1.wav", "c2.wav"],
            gap_same="same.wav",
            gap_turn="turn.wav",
        )
        lines = out.strip().split("\n")
        assert lines == [
            "file 'c0.wav'",
            "file 'same.wav'",   # A -> A
            "file 'c1.wav'",
            "file 'turn.wav'",   # A -> B
            "file 'c2.wav'",
        ]

    def test_single_clip_has_no_trailing_gap(self):
        out = pt.build_concat_list(["A"], ["only.wav"], "same.wav", "turn.wav")
        assert out.strip() == "file 'only.wav'"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
