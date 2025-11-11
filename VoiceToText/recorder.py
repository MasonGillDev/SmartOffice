#!/usr/bin/env python3
"""
Simple audio recorder with Whisper transcription (using Apple MPS)
Triggered after wake word detection
"""

import sys
import time
import numpy as np
from pvrecorder import PvRecorder
import whisper
import torch
import wave
import struct
import tempfile
import os
import requests
import json

def record_until_silence(silence_threshold=500, silence_duration=1.5, max_duration=30):
    """Record audio until silence detected"""
    print("🎤 Listening...")
    
    recorder = PvRecorder(device_index=-1, frame_length=512)
    recorder.start()
    
    audio_frames = []
    silence_start = None
    start_time = time.time()
    
    try:
        while True:
            # Max recording limit
            if time.time() - start_time > max_duration:
                print("Max recording time reached")
                break
            
            # Read audio
            frame = recorder.read()
            audio_frames.append(frame)
            
            # Calculate volume (RMS)
            rms = np.sqrt(np.mean(np.square(frame)))
            
            # Check for silence
            if rms < silence_threshold:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > silence_duration:
                    print("Silence detected, stopping")
                    break
            else:
                silence_start = None
                print(".", end="", flush=True)
                
    finally:
        recorder.stop()
        recorder.delete()
    
    return audio_frames

def save_audio_to_wav(frames, sample_rate=16000):
    """Save audio frames to temporary WAV file"""
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    
    with wave.open(temp_file.name, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for frame in frames:
            wav_file.writeframes(struct.pack('%dh' % len(frame), *frame))
    
    return temp_file.name

def transcribe_audio(wav_path):
    """Transcribe audio using Whisper with Apple MPS acceleration"""
    print("\n🔄 Transcribing...")
    
    # Use MPS (Metal Performance Shaders) if available on Apple Silicon
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # Load Whisper model on MPS for Apple Silicon acceleration
    # "base" model for speed, "small" for better accuracy
    model = whisper.load_model("base", device=device)
    
    # Transcribe with optimizations
    result = model.transcribe(
        wav_path,
        language="en",  # Skip language detection for speed
        fp16=(device == "mps")  # Use FP16 on MPS for speed, FP32 on CPU
    )
    
    # Ensure we return a string (whisper always returns text as string, but type checker doesn't know)
    text = result.get("text", "")
    return text.strip() if isinstance(text, str) else ""

def send_to_server(text, server_url="http://192.168.1.197:5000"):
    """Send transcribed text to the Flask server"""
    try:
        url = f"{server_url}/build_prompt"
        payload = {"prompt": text}
        headers = {"Content-Type": "application/json"}
        
        print(f"📤 Sending to server: {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            print("✅ Successfully sent to server")
            return True
        else:
            print(f"❌ Server returned status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to server at {server_url}")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except Exception as e:
        print(f"❌ Error sending to server: {e}")
        return False

def main():
    """Main function - called when wake word detected"""
    # Record audio
    frames = record_until_silence()
    
    if not frames:
        print("No audio recorded")
        return None
    
    # Save to WAV
    wav_path = save_audio_to_wav(frames)
    
    try:
        # Transcribe
        text = transcribe_audio(wav_path)
        print(f"\n📝 You said: \"{text}\"")
        
        # Send to server instead of saving to file
        success = send_to_server(text)
        
        if success:
            return text
        else:
            print("Failed to send to server")
            return None
        
    finally:
        # Cleanup temp file
        os.unlink(wav_path)

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)