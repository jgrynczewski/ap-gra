"""Record the narrator: every text of the scenarios -> <key>.wav (engine.voice).

In the Docker build (audio stage, needs piper-tts):

    python -m tools.nagraj --models /cache/models --cache /cache/wav --out /app/audio scenariusz/*.md

From code (the game creator, docs/kreator-gier.md) - the same voice, the
model is in the image (/app/models):

    narrator = Narrator(models, cache)
    narrator.recording("Jaką grę chcesz stworzyć?")   # -> Path of the .wav
    narrator.record_all(voice.texts(scenario), out)   # a whole game

Recordings already in the cache are reused (unchanged text = no new
recording); out gets exactly the recordings asked for.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import threading
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import voice  # noqa: E402
from engine.scenario import load  # noqa: E402

MODELS_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/{name}/{quality}/{voice}.onnx"


def model_path(models: Path) -> Path:
    return models / f"{voice.VOICE}.onnx"


def download_model(models: Path) -> Path:
    lang, name, quality = voice.VOICE.split("-")  # pl_PL-mc_speech-medium
    url = MODELS_URL.format(name=name, quality=quality, voice=voice.VOICE)
    models.mkdir(parents=True, exist_ok=True)
    model = model_path(models)
    for suffix in ("", ".json"):
        target = Path(str(model) + suffix)
        if not target.exists():
            print("pobieram", target.name, flush=True)
            urllib.request.urlretrieve(url + suffix, target)
    return model


def record(piper_voice, text: str, path: Path) -> None:
    from piper import SynthesisConfig

    config = SynthesisConfig(length_scale=voice.LENGTH_SCALE)
    rate = piper_voice.config.sample_rate
    silence = bytes(int(rate * voice.SENTENCE_SILENCE) * 2)  # 16-bit mono
    partial = path.with_suffix(".part")
    with wave.open(str(partial), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for i, chunk in enumerate(piper_voice.synthesize(text, syn_config=config)):
            if i:  # pause between sentences, none at the end - the client spaces recordings
                wav.writeframes(silence)
            wav.writeframes(chunk.audio_int16_bytes)
    partial.replace(path)


class Narrator:
    """Recordings in the narrator's voice, kept in a cache directory.

    The voice model is loaded on the first recording that is not in the
    cache, and only once. Safe to use from several threads (one recording at
    a time - Piper uses all cores anyway)."""

    def __init__(self, models: Path, cache: Path):
        self.models = models
        self.cache = cache
        self._voice = None
        self._lock = threading.Lock()

    def _piper(self):
        if self._voice is None:
            from piper import PiperVoice

            self._voice = PiperVoice.load(download_model(self.models))
        return self._voice

    def recording(self, text: str) -> Path:
        """The .wav of the text, recorded now if it is not in the cache."""
        path = self.cache / f"{voice.key(text)}.wav"
        with self._lock:
            if not path.exists():
                self.cache.mkdir(parents=True, exist_ok=True)
                record(self._piper(), text, path)
        return path

    def record_all(self, texts, out: Path, progress=None) -> int:
        """Recordings of all texts copied to out; returns how many were new."""
        texts = list(dict.fromkeys(t for t in texts if t.strip()))
        new = 0
        out.mkdir(parents=True, exist_ok=True)
        for n, text in enumerate(texts, start=1):
            cached = (self.cache / f"{voice.key(text)}.wav").exists()
            path = self.recording(text)
            shutil.copy2(path, out / path.name)
            if not cached:
                new += 1
                if progress:
                    progress(n, len(texts), text)
        return new


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    texts = [text for path in args.scenarios for text in voice.texts(load(path))]
    narrator = Narrator(args.models, args.cache)
    new = narrator.record_all(
        texts, args.out, progress=lambda n, total, text: print(f"  {n}/{total} {text[:60]}", flush=True))
    print(f"nagrania: {len(set(texts))}, nowe: {new}", flush=True)


if __name__ == "__main__":
    main()
