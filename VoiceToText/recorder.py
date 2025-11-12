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
from audio_cues import AudioCue

def record_until_silence(silence_threshold=500, silence_duration=1.5, max_duration=30, audio_cue=None):
    """Record audio until silence detected"""
    # Initialize recorder first (this takes time)
    recorder = PvRecorder(device_index=-1, frame_length=512)
    recorder.start()
    
    # NOW play the audio cue and show message - we're actually listening
    if audio_cue:
        audio_cue.play_start_listening()
    
    print("🎤 Listening...")
    
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
                    # Play stop listening cue
                    if audio_cue:
                        audio_cue.play_stop_listening()
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

def wait_for_tts_completion(task_id, server_url="http://192.168.1.197:5000"):
    """Wait for TTS playback to complete using long polling"""
    try:
        url = f"{server_url}/wait_for_tts/{task_id}"
        print(f"⏳ Waiting for TTS to complete (task: {task_id})...")
        
        # Long polling request - server will hold connection until TTS completes
        response = requests.get(url, timeout=35)  # 35 seconds (5 more than server timeout)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("tts_complete"):
                print("✅ TTS playback complete")
                return True
            elif data.get("timeout"):
                print("⏱️ TTS wait timeout - proceeding anyway")
                return False
        else:
            print(f"❌ Error waiting for TTS: status {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏱️ TTS wait timeout")
        return False
    except Exception as e:
        print(f"❌ Error waiting for TTS: {e}")
        return False

def send_to_server(text, server_url="http://192.168.1.197:5000"):
    """Send transcribed text to the Flask server and get conversation mode status"""
    try:
        url = f"{server_url}/build_prompt"
        payload = {"prompt": text}
        headers = {"Content-Type": "application/json"}
        
        print(f"📤 Sending to server: {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)  # Increased timeout for AI response
        
        if response.status_code == 200:
            print("✅ Successfully sent to server")
            response_data = response.json()
            
            # Get task ID for TTS tracking
            task_id = response_data.get("task_id")
            
            # Check conversation mode flag
            conversation_mode = response_data.get("conversation_mode", False)
            action = response_data.get("action", "end_conversation")
            
            print(f"📍 Task ID: {task_id}")
            print(f"📍 Conversation mode: {conversation_mode}")
            print(f"📍 Action: {action}")
            
            # Wait for TTS to complete using long polling
            if task_id:
                wait_for_tts_completion(task_id, server_url)
            
            return True, conversation_mode
        else:
            print(f"❌ Server returned status: {response.status_code}")
            print(f"Response: {response.text}")
            return False, False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to server at {server_url}")
        return False, False
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False, False
    except Exception as e:
        print(f"❌ Error sending to server: {e}")
        return False, False

def conversation_loop(audio_cue):
    """Handle continuous conversation until ended"""
    print("\n💬 Entering conversation mode - no wake word needed")
    
    while True:
        # Small delay before next recording (TTS is already complete due to long polling)
        time.sleep(0.5)  # Reduced from 3.0 since we now wait for TTS properly
        
        print("\n🎤 Listening for your response...")
        
        # Record with a timeout for conversation mode
        frames = record_until_silence(silence_duration=2.0, max_duration=20, audio_cue=audio_cue)
        
        if not frames:
            print("No audio detected - ending conversation")
            break
        
        # Process audio
        wav_path = save_audio_to_wav(frames)
        
        try:
            # Transcribe
            text = transcribe_audio(wav_path)
            
            if not text or text.strip() == "":
                print("No speech detected - continuing to listen...")
                continue
                
            print(f"\n📝 You said: \"{text}\"")
            
            # Send to server and check if conversation should continue
            success, continue_conversation = send_to_server(text)
            
            if not success:
                print("Failed to communicate with server")
                break
                
            if not continue_conversation:
                print("\n👋 Conversation ended - returning to wake word mode")
                break
                
            # Continue the loop for next interaction
            
        finally:
            # Cleanup temp file
            if os.path.exists(wav_path):
                os.unlink(wav_path)
    
    print("🔚 Exiting conversation mode")

def main():
    """Main function - called when wake word detected"""
    # Initialize audio cue system
    audio_cue = AudioCue()
    
    # Record initial audio
    frames = record_until_silence(audio_cue=audio_cue)
    
    if not frames:
        print("No audio recorded")
        audio_cue.play_error()
        return None
    
    # Save to WAV
    wav_path = save_audio_to_wav(frames)
    
    try:
        # Play thinking sound before transcribing
        audio_cue.play_thinking()
        
        # Transcribe
        text = transcribe_audio(wav_path)
        print(f"\n📝 You said: \"{text}\"")
        
        # Send to server and check conversation mode
        success, continue_conversation = send_to_server(text)
        
        if not success:
            print("Failed to send to server")
            audio_cue.play_error()
            return None
        
        # If server indicates conversation mode, enter the loop
        if continue_conversation:
            conversation_loop(audio_cue)
        
        return text
        
    finally:
        # Cleanup temp file
        if os.path.exists(wav_path):
            os.unlink(wav_path)

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)