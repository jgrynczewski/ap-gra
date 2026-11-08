"""Recording from code (tools.nagraj.Narrator) with the real voice.

Runs in the Docker test stage (Piper and the model in /app/models);
skipped where Piper or the model is missing.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import voice  # noqa: E402
from tools.nagraj import Narrator, model_path  # noqa: E402

MODELS = Path(os.environ.get("AP_GRA_MODELS", "/app/models"))

try:
    import piper  # noqa: F401
    READY = model_path(MODELS).exists()
except ImportError:
    READY = False


@unittest.skipUnless(READY, "brak Pipera albo modelu głosu (działa w obrazie Docker)")
class NarratorTest(unittest.TestCase):
    def setUp(self):
        self.cache = Path(tempfile.mkdtemp())
        self.narrator = Narrator(MODELS, self.cache)

    def test_recording_in_the_voice_and_cached(self):
        text = "Jaką grę chcesz stworzyć?"
        path = self.narrator.recording(text)
        self.assertEqual(path, self.cache / f"{voice.key(text)}.wav")
        self.assertGreater(voice.duration(path), 0.5)
        recorded = path.stat().st_mtime_ns
        self.assertEqual(self.narrator.recording(text), path)
        self.assertEqual(path.stat().st_mtime_ns, recorded)  # not recorded again

    def test_record_all(self):
        out = Path(tempfile.mkdtemp()) / "audio"
        texts = ["Wejdź do wieży.", "Odejdź.", "Wejdź do wieży.", "  "]
        self.assertEqual(self.narrator.record_all(texts, out), 2)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         sorted(f"{voice.key(t)}.wav" for t in ("Wejdź do wieży.", "Odejdź.")))
        self.assertEqual(self.narrator.record_all(texts, out), 0)  # all from the cache


if __name__ == "__main__":
    unittest.main()
