# install first:
# pip install pvporcupine pvrecorder

import pvporcupine
from pvrecorder import PvRecorder

access_key = "JfYOI8ILb8hMUxuFtieWXlWNV+qvDrilX+cFKSn+F0ovHf66p4kI3A=="
# Initialize Porcupine with a built-in wake word
# Available built-ins: "porcupine", "alexa", "bumblebee", "computer", "hey google", "jarvis", etc.
porcupine = pvporcupine.create(access_key=access_key,keyword_paths=None, keywords=["jarvis"])

recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
recorder.start()

print("Listening for 'Jarvis'... (Ctrl+C to stop)")

try:
    while True:
        pcm = recorder.read()
        result = porcupine.process(pcm)
        if result >= 0:
            print("Wake word detected!")
except KeyboardInterrupt:
    print("Stopping...")
finally:
    recorder.stop()
    recorder.delete()
    porcupine.delete()
