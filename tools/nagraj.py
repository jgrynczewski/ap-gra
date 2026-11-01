"""Record the narrator: every text of the scenarios -> <key>.wav (engine.voice).

Runs in the Docker build (audio stage, needs piper-tts):

    python -m tools.nagraj --models /models --cache /cache --out /app/audio scenariusz/*.md

Recordings already in --cache are reused (unchanged text = no new
recording); --out gets exactly the recordings the scenarios need.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import voice  # noqa: E402
from engine.scenario import load  # noqa: E402

MODELS_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/{name}/{quality}/{voice}.onnx"


def download_model(models: Path) -> Path:
    lang, name, quality = voice.VOICE.split("-")  # pl_PL-mc_speech-medium
    url = MODELS_URL.format(name=name, quality=quality, voice=voice.VOICE)
    models.mkdir(parents=True, exist_ok=True)
    model = models / f"{voice.VOICE}.onnx"
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    texts = {}
    for path in args.scenarios:
        for text in voice.texts(load(path)):
            texts[voice.key(text)] = text

    args.cache.mkdir(parents=True, exist_ok=True)
    missing = {k: t for k, t in texts.items() if not (args.cache / f"{k}.wav").exists()}
    print(f"nagrania: {len(texts)}, nowe: {len(missing)}", flush=True)
    if missing:
        from piper import PiperVoice

        piper_voice = PiperVoice.load(download_model(args.models))
        for n, (k, text) in enumerate(missing.items(), start=1):
            record(piper_voice, text, args.cache / f"{k}.wav")
            print(f"  {n}/{len(missing)} {text[:60]}", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    for k in texts:
        shutil.copy2(args.cache / f"{k}.wav", args.out / f"{k}.wav")


if __name__ == "__main__":
    main()
