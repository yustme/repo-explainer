#!/usr/bin/env python3
"""Two-voice podcast synthesis for repo-explainer.

Parses a two-host script (lines prefixed `A:` / `B:`), synthesizes each turn with
the right voice, phonetically respells foreign/technical terms for the target
language, normalizes + concatenates the clips, encodes an mp3, writes a progress
file the docsite player polls, and publishes the mp3 into the workspace.

Engines:
  xtts  (default) Coqui XTTS-v2, two built-in studio speakers, multilingual.
  say             macOS `say`; one system voice per language (lower quality).

Pure helpers (respell / parse_script / build_concat_list) are import-safe and unit
tested in test_podcast_tts.py.

Usage:
  podcast_tts.py --script S.txt --workspace WS --lang cs --engine xtts --out WS/x-podcast.mp3
  podcast_tts.py ... --sample 8          # preview first 8 turns only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# --- Phonetic respelling maps, keyed by target language ---------------------
# Each entry: (regex, replacement, flags). Longer/multi-word entries first.
# A voice speaking language L mispronounces terms from other languages; respell
# them into L's phonetics BEFORE synthesis. Extend per project vocabulary.
RESPELL_MAPS: dict[str, list[tuple[str, object, int]]] = {
    "cs": [
        (r"CLAUDE\.md", "klód tečka em dé", 0),
        (r"CONTRIBUTING\.md", "kontribjúting tečka em dé", 0),
        (r"OutputFormatter", "autput formátr", re.I),
        (r"Agent Tasks?", "agent tásks", re.I),
        (r"Claude Code", "klód kód", re.I),
        (r"auto-expand", "auto ikspand", re.I),
        (r"self-review", "self revjú", re.I),
        (r"\bkbagent", "ká bé agent", re.I),
        (r"\bClaude\b", "klód", re.I),
        (r"\bCodex\b", "kódex", re.I),
        (r"\bGemini\b", "džemini", re.I),
        (r"\bCursor\b", "kurzr", re.I),
        (r"\bReact\b", "rijekt", re.I),
        (r"\bStorage\b", "storidž", re.I),
        (r"\bManage\b", "menydž", re.I),
        (r"\bfirewall", "fajrvól", re.I),
        (r"\bpermission", "permišn", re.I),
        (r"\bconfig", "konfig", re.I),
        (r"\bbucket", "baket", re.I),
        (r"\bserver\b", "servr", re.I),
        (r"\bserve\b", "sérv", re.I),
        (r"\bplugin", "plagin", re.I),
        (r"\bwheel\b", "víl", re.I),
        (r"\bcron\b", "kron", re.I),
        (r"\bhttp\b", "há té té pé", re.I),
        (r"\bJSON\b", "džejson", 0),
        (r"\bMCP\b", "em cé pé", 0),
        (r"\bAPI\b", "á pí", 0),
        (r"\bCLI\b", "cé el í", 0),
        (r"\bCI\b", "cí aj", 0),
        (r"\bAI\b", "ej aj", 0),
    ],
    # English voice reads English technical terms fine — no respelling needed.
    "en": [],
}

# macOS `say` voice per language (fallback engine).
SAY_VOICES = {"cs": "Zuzana", "en": "Samantha", "de": "Anna", "fr": "Thomas",
              "es": "Monica", "it": "Alice", "pl": "Zosia", "sk": "Laura"}

RATE = 24000  # output sample rate (XTTS native)


# --- pure helpers (unit tested) ---------------------------------------------
def compile_map(lang: str):
    return [(re.compile(p, fl), r) for p, r, fl in RESPELL_MAPS.get(lang, [])]


def respell(text: str, lang: str) -> str:
    """Rewrite foreign/technical terms into the target language's phonetics."""
    for rx, rep in compile_map(lang):
        text = rx.sub(rep, text)
    return text


def parse_script(path: Path) -> list[tuple[str, str]]:
    """Parse a two-host script into [(speaker, text)]; speaker is 'A' or 'B'."""
    turns: list[tuple[str, str]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        spk, text = line.split(":", 1)
        spk, text = spk.strip().upper(), text.strip()
        if spk in ("A", "B") and text:
            turns.append((spk, text))
    return turns


def build_concat_list(speakers: list[str], clip_names: list[str],
                      gap_same: str, gap_turn: str) -> str:
    """ffmpeg concat-demuxer list: clips joined by gaps (longer between speakers)."""
    lines: list[str] = []
    n = len(clip_names)
    for i in range(n):
        lines.append(f"file '{clip_names[i]}'")
        if i < n - 1:
            gap = gap_turn if speakers[i + 1] != speakers[i] else gap_same
            lines.append(f"file '{gap}'")
    return "\n".join(lines) + "\n"


# --- side-effecting helpers --------------------------------------------------
def run(cmd: list) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"FAIL {' '.join(str(c) for c in cmd)}\n{r.stderr}\n")
        raise SystemExit(1)
    return r


def normalize(src: Path, dst: Path):
    run(["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", str(RATE),
         "-af", "loudnorm=I=-18:TP=-2:LRA=11", "-c:a", "pcm_s16le", str(dst)])


def make_silence(dst: Path, seconds: float):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"anullsrc=channel_layout=mono:sample_rate={RATE}",
         "-t", str(seconds), "-c:a", "pcm_s16le", str(dst)])


def progress_writer(progress_path: Path | None):
    def write(**kw):
        if not progress_path:
            return
        kw.setdefault("updated", time.time())
        try:
            progress_path.write_text(json.dumps(kw, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return write


# --- engines -----------------------------------------------------------------
def synth_turn_xtts(tts, spoken, voice_kwargs, lang, out_wav, prosody):
    # voice_kwargs is either {"speaker": "<builtin>"} or {"speaker_wav": "<ref.wav>"}
    tts.tts_to_file(text=spoken, language=lang, file_path=str(out_wav),
                    split_sentences=True, **voice_kwargs, **prosody)


def synth_turn_say(spoken, voice, out_aiff, tmp_txt):
    tmp_txt.write_text(spoken, encoding="utf-8")
    run(["say", "-v", voice, "-r", "182", "-o", str(out_aiff), "-f", str(tmp_txt)])


def main():
    ap = argparse.ArgumentParser(description="Two-voice podcast synthesis.")
    ap.add_argument("--script", required=True, type=Path)
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--engine", choices=["xtts", "say"], default="xtts")
    ap.add_argument("--out", type=Path, help="output mp3 path (default: <workspace>/podcast.mp3)")
    ap.add_argument("--sample", type=int, default=0, help="render only first N turns (preview)")
    ap.add_argument("--speaker-a", default="Damien Black", help="XTTS built-in speaker for host A")
    ap.add_argument("--speaker-b", default="Daisy Studious", help="XTTS built-in speaker for host B")
    ap.add_argument("--speaker-wav-a", type=Path, help="reference wav to CLONE for host A (overrides --speaker-a)")
    ap.add_argument("--speaker-wav-b", type=Path, help="reference wav to CLONE for host B (overrides --speaker-b)")
    ap.add_argument("--temperature", type=float, default=0.72)
    ap.add_argument("--repetition-penalty", type=float, default=3.5)
    ap.add_argument("--top-p", type=float, default=0.85)
    ap.add_argument("--top-k", type=int, default=50)
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()

    workspace = args.workspace.expanduser().resolve()
    out_mp3 = (args.out or (workspace / "podcast.mp3")).expanduser().resolve()
    clips = workspace / "podcast" / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    sample = args.sample > 0
    progress_path = None if sample else (workspace / "podcast-progress.json")
    write_progress = progress_writer(progress_path)

    turns = parse_script(args.script)
    if sample:
        turns = turns[: args.sample]
    total = len(turns)
    print(f"engine={args.engine} lang={args.lang} turns={total} sample={sample}")
    if not total:
        sys.stderr.write("no A:/B: turns found in script\n")
        raise SystemExit(1)
    write_progress(status="running", phase="loading", done=0, total=total,
                   label="Loading TTS…", engine=args.engine)

    # engine setup
    tts = None
    if args.engine == "xtts":
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        from TTS.api import TTS  # noqa: E402
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
        try:
            names = list(tts.synthesizer.tts_model.speaker_manager.speakers.keys())
            spk_a = args.speaker_a if args.speaker_a in names else names[0]
            spk_b = args.speaker_b if args.speaker_b in names else names[1]
        except Exception:
            spk_a, spk_b = args.speaker_a, args.speaker_b
        voice_a = {"speaker_wav": str(args.speaker_wav_a.expanduser())} if args.speaker_wav_a else {"speaker": spk_a}
        voice_b = {"speaker_wav": str(args.speaker_wav_b.expanduser())} if args.speaker_wav_b else {"speaker": spk_b}
        print(f"A={voice_a}  B={voice_b}")
        prosody = dict(temperature=args.temperature, repetition_penalty=args.repetition_penalty,
                       top_p=args.top_p, top_k=args.top_k, speed=args.speed)
    else:
        say_voice = SAY_VOICES.get(args.lang)
        if not say_voice:
            sys.stderr.write(f"no `say` voice configured for lang={args.lang}\n")
            raise SystemExit(1)

    # synthesize each turn
    speakers: list[str] = []
    clip_names: list[str] = []
    for i, (spk, text) in enumerate(turns):
        spoken = respell(text, args.lang)
        raw = clips / f"raw_{i:03d}"
        norm = clips / f"clip_{i:03d}.wav"
        if args.engine == "xtts":
            wav = raw.with_suffix(".wav")
            synth_turn_xtts(tts, spoken, voice_a if spk == "A" else voice_b, args.lang, wav, prosody)
            normalize(wav, norm)
        else:
            aiff = raw.with_suffix(".aiff")
            synth_turn_say(spoken, say_voice, aiff, raw.with_suffix(".txt"))
            normalize(aiff, norm)
        speakers.append(spk)
        clip_names.append(norm.name)
        print(f"  [{i+1}/{total}] {spk}: {spoken[:60]}")
        write_progress(status="running", phase="synthesizing", done=i + 1, total=total,
                       label=f"{'A' if spk=='A' else 'B'}: {text[:60]}", engine=args.engine)

    # join + encode
    write_progress(status="running", phase="encoding", done=total, total=total,
                   label="Joining & encoding…", engine=args.engine)
    gap_same, gap_turn = clips / "_gap_same.wav", clips / "_gap_turn.wav"
    make_silence(gap_same, 0.28)
    make_silence(gap_turn, 0.55)
    concat = clips / "_concat.txt"
    concat.write_text(build_concat_list(speakers, clip_names, gap_same.name, gap_turn.name),
                      encoding="utf-8")
    joined = clips / "joined.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
         "-c:a", "pcm_s16le", str(joined)])
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-i", str(joined), "-c:a", "libmp3lame", "-q:a", "4", str(out_mp3)])

    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(joined)]).stdout.strip())

    # publish into workspace root so the docsite bridge serves it
    published = workspace / out_mp3.name
    if published != out_mp3:
        shutil.copyfile(out_mp3, published)
    if not sample:
        write_progress(status="done", phase="done", done=total, total=total, label="Done",
                       file=published.name, engine=args.engine,
                       duration=round(dur), minutes=int(dur // 60), seconds=int(dur % 60))
    print(f"DONE duration={int(dur//60)}m{int(dur%60):02d}s out={out_mp3} published={published.name}")


if __name__ == "__main__":
    main()
