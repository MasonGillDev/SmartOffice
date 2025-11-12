"""
Audio cue module for providing feedback sounds
"""

import os
import subprocess
import platform

class AudioCue:
    """Provides audio feedback cues for recording states"""
    
    def __init__(self):
        self.system = platform.system()
        
    def play_start_listening(self):
        """Play a sound when starting to listen"""
        try:
            if self.system == "Darwin":  # macOS
                # Use system sound for start
                subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"], check=False, capture_output=True)
            elif self.system == "Linux":
                # Try multiple methods for Linux
                if os.path.exists("/usr/bin/paplay"):
                    # Use PulseAudio
                    subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/message.oga"], 
                                 check=False, capture_output=True)
                elif os.path.exists("/usr/bin/aplay"):
                    # Use ALSA - create a simple beep
                    subprocess.run(["speaker-test", "-t", "sine", "-f", "800", "-l", "1"], 
                                 check=False, capture_output=True, timeout=0.2)
                else:
                    # Terminal bell as fallback
                    print("\a", end="", flush=True)
            else:  # Windows
                import winsound
                winsound.Beep(800, 200)  # 800Hz for 200ms
        except Exception as e:
            print(f"Could not play start sound: {e}")
    
    def play_stop_listening(self):
        """Play a sound when stopping listening"""
        try:
            if self.system == "Darwin":  # macOS
                # Use system sound for stop
                subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False, capture_output=True)
            elif self.system == "Linux":
                if os.path.exists("/usr/bin/paplay"):
                    # Use PulseAudio
                    subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], 
                                 check=False, capture_output=True)
                elif os.path.exists("/usr/bin/aplay"):
                    # Use ALSA - create a simple beep (lower tone)
                    subprocess.run(["speaker-test", "-t", "sine", "-f", "400", "-l", "1"], 
                                 check=False, capture_output=True, timeout=0.2)
                else:
                    # Terminal bell as fallback
                    print("\a", end="", flush=True)
            else:  # Windows
                import winsound
                winsound.Beep(400, 200)  # 400Hz for 200ms
        except Exception as e:
            print(f"Could not play stop sound: {e}")
    
    def play_error(self):
        """Play an error sound"""
        try:
            if self.system == "Darwin":  # macOS
                subprocess.run(["afplay", "/System/Library/Sounds/Basso.aiff"], check=False, capture_output=True)
            elif self.system == "Linux":
                if os.path.exists("/usr/bin/paplay"):
                    subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/dialog-error.oga"], 
                                 check=False, capture_output=True)
                else:
                    # Double bell for error
                    print("\a\a", end="", flush=True)
            else:  # Windows
                import winsound
                winsound.Beep(200, 300)  # 200Hz for 300ms (low tone)
        except Exception as e:
            print(f"Could not play error sound: {e}")
    
    def play_thinking(self):
        """Play a sound to indicate processing/thinking"""
        try:
            if self.system == "Darwin":  # macOS
                subprocess.run(["afplay", "/System/Library/Sounds/Morse.aiff"], check=False, capture_output=True)
            elif self.system == "Linux":
                if os.path.exists("/usr/bin/paplay"):
                    subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"], 
                                 check=False, capture_output=True)
                else:
                    print("\a", end="", flush=True)
            else:  # Windows
                import winsound
                winsound.Beep(600, 100)  # Quick beep
        except Exception as e:
            print(f"Could not play thinking sound: {e}")