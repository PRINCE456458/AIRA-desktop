import queue
import threading

# Voice output (text to speech)
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Voice input (speech to text)
try:
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel
    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False

SAMPLE_RATE = 16000


class Speaker:
    """Speaks text in a background thread so the window never freezes."""

    def __init__(self):
        self.queue = queue.Queue()
        self.engine = None
        self.rate = 175
        if TTS_AVAILABLE:
            threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            text = self.queue.get()
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                self.engine = engine
                engine.say(text)
                engine.runAndWait()
            except Exception as error:
                print("Speech error:", error)
            finally:
                self.engine = None

    def speak(self, text):
        text = text.replace("*", "").replace("#", "").replace("`", "").strip()
        if TTS_AVAILABLE and text:
            self.stop()
            self.queue.put(text)

    def stop(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        try:
            if self.engine:
                self.engine.stop()
        except Exception:
            pass


class Listener:
    """Records from the microphone, then turns the audio into text."""

    def __init__(self):
        self.model = None
        self.frames = []
        self.stream = None

    def start(self):
        self.frames = []

        def callback(indata, frame_count, time_info, status):
            self.frames.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback
        )
        self.stream.start()

    def stop_and_transcribe(self):
        self.stream.stop()
        self.stream.close()
        self.stream = None
        if not self.frames:
            return ""
        audio = np.concatenate(self.frames, axis=0).flatten()
        if self.model is None:  # loaded only the first time (downloads ~150 MB)
            self.model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = self.model.transcribe(audio, beam_size=1, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()