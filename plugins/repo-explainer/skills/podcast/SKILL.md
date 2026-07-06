---
name: podcast
description: >
  Turn a repository's analysis into a two-host audio podcast that explains the whole topic as a
  story, with open-source voice synthesis, embedded as a player in the docsite. Used by explain-repo
  when the user opts into a podcast. Use when asked to produce a podcast/audio explainer from analyzed
  source, compose a two-host script, or synthesize narration locally.
allowed-tools: Read, Write, Edit, Bash
model: sonnet
---

# Produce a Podcast from the Analysis

This skill turns the grounded analysis (from `analyze-repo`) into a **two-host audio episode** that explains the whole topic as a listenable story, then embeds it as a player in the docsite. It has three parts: **compose the script**, **produce the audio**, **embed the player**.

Bundled script: `$PLUGIN_PATH/scripts/podcast_tts.py` (the synthesis pipeline). Reference it by `$PLUGIN_PATH`.

Inputs from `explain-repo`: the analysis notes, the **podcast language** code (e.g. `cs`, `en` — independent of the docs language), the **workspace path** (`~/repo-explains/<slug>`), and the **page files** to embed the player into.

Hard rule (inherited): never invent. The script only narrates what the analysis established; every claim is grounded in the real source. A podcast is more conversational than the docs, but it must not introduce facts the analysis did not support.

---

## Part A — Compose the script

Write a **two-host dialogue**. Two roles, held consistently:

- **Host A — the explainer** (the one who understands the system; walks through it).
- **Host B — the curious proxy for the listener** (asks, voices the obvious confusion, demands the analogy, summarises back). B is the listener's stand-in — if B is confused, the listener is too.

The hosts **build on each other**: short affirmations ("right", "exactly", "good question"), reframes, and reciprocal hand-offs. One poses, the other resolves.

### Composition — the parts, in order

This ordering is the point of the skill. It is synthesised from how strong explainer/technical podcasts are built (3-act setup→confrontation→resolution, educational "learning-promise" structure, and NotebookLM-style two-host audio overviews).

1. **Cold open / hook (≈first 20–30 s).** A provocative line or the central tension *before* any intro — "why is X surprising / hard / built this weird way?". The first 1–3 lines decide whether the listener stays. Do **not** open with "today we'll talk about…".
2. **Intro + learning promise.** Who the hosts are, the topic in one line, and an explicit promise: "by the end you'll understand X". Set the audience level here.
3. **Why it matters (stakes / context).** The "why" before the "what" — what problem this solves, why it's worth caring about.
4. **The big picture first (mental model).** For a technical topic, give the high-level map — the core idea / architecture in one breath — *before* any detail. Top-down, not bottom-up.
5. **2–4 learning blocks, one idea per block (the body).** Each block follows the same shape: **concept → analogy ("it's like…") → one concrete example or number → a one-line mini-recap.** Order blocks by dependency (foundations first). This pairs naturally with `rebuild-from-scratch` depth: one block per build stage.
6. **Signposted transitions between blocks.** Verbal cues that keep orientation: "now that we've got X, let's see how Y…", "so we've established…".
7. **Micro tension → "aha" inside each block.** B surfaces the confusion or the naive guess; A resolves it. This is the 3-act confrontation→resolution applied at small scale, and it's what keeps an explainer alive.
8. **Synthesis — how it all fits.** Zoom back out and connect the blocks into the whole; the broader implication.
9. **Recap / key takeaways.** An explicit list of the 2–4 things to remember (listeners multitask — spell it out for retention).
10. **One durable lesson + a reflection question.** The single most portable idea, and a forward-looking thought.
11. **Sign-off / pointer.** Thank, point back to the interactive docs/assistant, close.

### Cross-cutting rules

- **One main topic per episode; one concept per block.** No hour-long lecture without breaks.
- **Refresh attention every ≈8–12 min** — a new block, a question, or a fresh analogy.
- **Analogy before precision** for every hard concept.
- **Open loops:** tease something you resolve later to hold momentum; "plan with the end in mind" and don't reveal the payoff too early.
- **Technical specifics:** show the *shape* before the parts; name the **misconception** and correct it; always say **why it's built that way**, not just what it is.
- **Length:** target the depth the user chose — a full deep-dive episode is ~20–35 min of speech (≈4,500–6,000 words for Czech/English). A "brisk" version is ~10–12 min.

### Output format

Write the script to `<workspace>/podcast/script.txt`, **one turn per line**, prefixed by speaker:

```
A: <host A line>
B: <host B line>
```

Keep punctuation simple (it drives TTS prosody). Write technical identifiers as they are — the production step handles pronunciation (Part B). Save the script as a real artifact so it can be re-synthesised or edited later.

---

## Part B — Produce the audio

Synthesis is delegated to the bundled `scripts/podcast_tts.py`. It parses `script.txt`, synthesises each turn with the right voice, normalises and concatenates the clips (small gaps, longer between speaker changes), encodes an mp3, writes `<workspace>/podcast-progress.json` as it goes, and publishes the finished mp3 into the workspace.

### Engine choice (open-source, ranked)

- **XTTS-v2 (Coqui, default).** Most natural multilingual neural voice; supports Czech, English and many others; two distinct built-in studio speakers for the two hosts; optional voice cloning from a reference clip for a native accent. Heavy (~1.8 GB model) and slow on CPU. License: **CPML, non-commercial**.
- **Piper (fallback, fast & fully local).** Good, fast neural TTS, but a limited voice roster per language (e.g. Czech has only `cs_CZ-jirka-*`, so a true two-voice split needs a second engine).
- **macOS `say` (last resort).** Zero install; lower quality; useful only as a second voice or when nothing else is available.

For a two-voice episode where the language has only one good neural voice, combine engines (e.g. XTTS for host A, `say` for host B) — but a single engine with two speakers (XTTS) sounds the most coherent.

### Pronunciation of foreign/technical terms

A voice speaking language L mispronounces terms from another language (e.g. a Czech voice butchering `JSON`, `OutputFormatter`, `serve`, `API`). Fix it with **phonetic respelling**: rewrite each offending term into the target language's phonetics *before* synthesis (e.g. for Czech: `JSON`→"džejson", `serve`→"sérv", `API`→"á pí", `cache`→"keš"). `podcast_tts.py` carries a per-language respelling map and applies it automatically; extend the map for the project's specific vocabulary. This is the single biggest quality win for mixed-language technical content and is engine-independent.

### Prosody knobs (XTTS)

`temperature` (≈0.7–0.75 for livelier intonation), `repetition_penalty` (raise to ~3–5 to suppress stutters/loops), `speed`, `top_p`/`top_k`. All are flags on `podcast_tts.py`.

### Running it

```bash
python3 "$PLUGIN_PATH/scripts/podcast_tts.py" \
  --script   <workspace>/podcast/script.txt \
  --workspace <workspace> \
  --lang     <cs|en|...> \
  --engine   xtts \
  --out      <workspace>/<slug>-podcast.mp3
```

Useful flags: `--sample N` (render only the first N turns for a quick preview before the long full run — always preview before committing to a full CPU run), `--speaker-a` / `--speaker-b`, `--temperature`, `--repetition-penalty`, `--speed`.

**Run the full synthesis in the background** (it can take tens of minutes on CPU) and let the docsite player poll progress. `podcast_tts.py` writes `<workspace>/podcast-progress.json` (`{status, phase, done, total, label, ...}` → `{status:"done", file, minutes, seconds}`) and copies the finished mp3 into the workspace root so the bridge serves it.

### First-time environment setup (XTTS)

XTTS has a few sharp edges; set them up once in an isolated venv:

```bash
uv venv --python 3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install coqui-tts "transformers>=4.57,<5" torch torchaudio torchcodec
```

- **`transformers<5`** — newer coqui-tts pins `transformers>=4.57` but transformers 5.x removed `isin_mps_friendly`, which its vendored Tortoise code imports. Stay on the 4.57 line.
- **`torchcodec`** — required for audio IO on PyTorch ≥ 2.9.
- Set `COQUI_TOS_AGREED=1` to accept the CPML license non-interactively (allows the model auto-download).
- Use **CPU** (`device="cpu"`); XTTS hits unsupported-op errors on Apple MPS.
- `ffmpeg` must be on PATH (clip normalisation, concatenation, mp3 encode).

`podcast_tts.py` handles the in-code quirks (e.g. espeak data-dir handling for the Piper path); the items above are install-time.

---

## Part C — Embed the player in the docsite

Add a player so the podcast is playable **inside the documentation**, not just as a file. The bridge serves the workspace statically, so a relative `<audio src>` and a `fetch` of `podcast-progress.json` work from any page.

For each page (the hub `index.html` and each repo's pages), insert this **inside the content markers** (`<!-- REPO_EXPLAINER:CONTENT -->` … `<!-- /REPO_EXPLAINER:CONTENT -->`), near the top, as its own `<section>` (a meaningful `<h2>` also adds it to the page's "On this page" menu). Reuse the existing design classes; this is the only place this skill adds a `<script>`.

```html
<section class="section" id="podcast">
  <p class="eyebrow">PODCAST</p>
  <h2>Listen to the whole story</h2>
  <p>A two-host episode that explains how it all fits together. Generated locally with open-source voice synthesis.</p>
  <div class="card" style="max-width:680px;">
    <audio id="pcAudio" controls preload="none" src="<slug>-podcast.mp3" style="width:100%;"></audio>
    <a class="go" href="<slug>-podcast.mp3" download style="margin-top:0.85rem;display:inline-flex;">Download MP3 <span class="arrow">↓</span></a>
    <div id="pcNote" style="font-family:var(--font-mono);font-size:0.68rem;color:var(--faint);margin-top:0.7rem;"></div>
  </div>
  <script>
  (function(){
    var note=document.getElementById('pcNote'), audio=document.getElementById('pcAudio');
    function tick(){
      fetch('podcast-progress.json?_='+Date.now()).then(function(r){return r.json();}).then(function(d){
        if(d && d.status==='done'){
          note.textContent='Length '+(d.minutes||0)+' min '+(d.seconds||0)+' s';
          if(audio.getAttribute('data-loaded')!=='1'){ audio.src=(d.file||audio.getAttribute('src'))+'?_='+Date.now(); audio.setAttribute('data-loaded','1'); }
          return;
        }
        if(d){ note.textContent='Generating the podcast ('+(d.done||0)+'/'+(d.total||0)+')… '+(d.label||''); audio.removeAttribute('src'); setTimeout(tick,2000); }
      }).catch(function(){ setTimeout(tick,3000); });
    }
    tick();
  })();
  </script>
</section>
```

Notes:
- Replace `<slug>-podcast.mp3` with the actual published filename. Cache-bust the audio `src` (`?_=<ts>`) so a regenerated episode is not served stale from cache.
- While synthesis runs, the player shows live progress and polls; once `status:"done"` it swaps in the finished audio and stops polling.
- Seed `podcast-progress.json` with `{"status":"running","done":0,"total":<N>}` before serving so the player has something to show on first load.
- Keep the wording in the **documentation** language (the page language), even though the audio is in the podcast language — they can differ.

---

## Operating notes

- **Preview first.** Always render a `--sample` (a handful of turns that include the hardest terms) and let the user approve voices + pronunciation before the full run.
- **Re-runs are cheap after setup.** The model is cached; tweaking the script, respelling map, voices, or prosody and re-synthesising does not re-download anything.
- **Multi-repo / multi-language.** One episode per repo (or a combined one) — keep each script under `<workspace>/podcast/` with a clear name; publish distinct mp3 filenames and point each page's player at the right one.

### Known gotchas

- **Czech (and similar) ordinals crash XTTS.** XTTS's number expansion calls `num2words`, whose Czech `to_ordinal` is **not implemented** — so a digit immediately followed by `.` (read as an ordinal, e.g. `1.`) raises `NotImplementedError` mid-synthesis. Spell numbers out in the script (`"jedna"`, not `"1."`), or avoid `<digit>.` patterns, for Czech and any language whose `num2words` ordinal is missing.
- **Built-in XTTS speakers carry a non-native accent** when reading non-English languages. For a language with no good native option, audition several built-in speakers on one line (a quick numbered comparison clip) and let the user pick by ear, rather than guessing — name origin (e.g. Slavic-sounding) is only a weak hint.
- **Voice cloning needs a clean, reasonably loud reference.** A faint/distant recording (e.g. mean ≈ -40 dB) clones poorly (hollow/noisy). Boost + denoise the reference (`highpass`, `afftdn`, `dynaudnorm`/`loudnorm`) before use, or re-record closer; clarity/SNR matters more than absolute level.
