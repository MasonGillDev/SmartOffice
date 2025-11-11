"""
Google Text-to-Speech Module
Converts text to speech using Google Cloud TTS API
"""

import os
import wave
from typing import Optional
import pygame
import tempfile
from google.cloud import texttospeech

class GoogleTTS:
    """Handle text-to-speech conversion using Google Cloud TTS API"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Google TTS
        
        Args:
            credentials_path: Path to Google Cloud service account JSON file
                            (if not provided, will look for GOOGLE_APPLICATION_CREDENTIALS env var)
        """
        # Set credentials path if provided
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        
        try:
            # Initialize the TTS client
            self.client = texttospeech.TextToSpeechClient()
            
            # Configure voice parameters
            self.voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Standard-A",  # Use standard voice for now
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
            )
            
            # Configure audio parameters
            self.audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=1.0,
                pitch=0.0
            )
            
            # Initialize pygame mixer for audio playback
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=512)
            print("✅ Google Cloud TTS initialized")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize Google TTS client: {e}")
            print("Make sure GOOGLE_APPLICATION_CREDENTIALS points to your service account JSON file")
            self.client = None
    
    def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        Convert text to speech using Google Cloud TTS API
        
        Args:
            text: The text to convert to speech
            
        Returns:
            Audio data as bytes, or None if failed
        """
        
        if not self.client:
            print("❌ TTS client not initialized")
            return None
        
        try:
            print(f"🔊 Synthesizing speech for: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Perform the text-to-speech request
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config
            )
            
            # The response's audio_content is binary
            if response.audio_content:
                print("✅ Speech synthesized successfully")
                return response.audio_content
            else:
                print("❌ No audio content in response")
                return None
                
        except Exception as e:
            print(f"❌ Error synthesizing speech: {e}")
            return None
    
    def play_audio(self, audio_bytes: bytes):
        """
        Play audio bytes using pygame
        
        Args:
            audio_bytes: Raw audio data (LINEAR16 format)
        """
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write WAV header and data
                self._write_wav_file(temp_file.name, audio_bytes)
                
                # Load and play audio
                pygame.mixer.music.load(temp_file.name)
                pygame.mixer.music.play()
                
                print("🔊 Playing audio...")
                
                # Wait for audio to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                
                print("✅ Audio playback complete")
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
        except Exception as e:
            print(f"❌ Error playing audio: {e}")
    
    def _write_wav_file(self, filename: str, audio_bytes: bytes):
        """
        Write raw LINEAR16 audio to WAV file
        
        Args:
            filename: Output WAV file path
            audio_bytes: Raw audio data
        """
        # LINEAR16 is 16-bit PCM at 24kHz
        sample_rate = 24000
        channels = 1
        sample_width = 2  # 16-bit = 2 bytes
        
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
    
    def speak(self, text: str) -> bool:
        """
        Synthesize and play speech (convenience method)
        
        Args:
            text: Text to speak
            
        Returns:
            True if successful, False otherwise
        """
        audio_bytes = self.synthesize_speech(text)
        
        if audio_bytes:
            self.play_audio(audio_bytes)
            return True
        else:
            return False
    
    def save_audio(self, text: str, output_file: str) -> bool:
        """
        Synthesize speech and save to file
        
        Args:
            text: Text to convert
            output_file: Path to save audio file
            
        Returns:
            True if successful, False otherwise
        """
        audio_bytes = self.synthesize_speech(text)
        
        if audio_bytes:
            try:
                self._write_wav_file(output_file, audio_bytes)
                print(f"✅ Audio saved to: {output_file}")
                return True
            except Exception as e:
                print(f"❌ Error saving audio: {e}")
                return False
        else:
            return False
    
    def set_voice(self, name: str = "en-US-Standard-A", language_code: str = "en-US", 
                   gender: str = "FEMALE"):
        """
        Change the voice settings
        
        Args:
            name: Voice name (e.g., "en-US-Standard-A", "en-US-Wavenet-F")
            language_code: Language code (e.g., "en-US")
            gender: Voice gender ("FEMALE", "MALE", "NEUTRAL")
        """
        gender_map = {
            "FEMALE": texttospeech.SsmlVoiceGender.FEMALE,
            "MALE": texttospeech.SsmlVoiceGender.MALE,
            "NEUTRAL": texttospeech.SsmlVoiceGender.NEUTRAL
        }
        
        self.voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=name,
            ssml_gender=gender_map.get(gender, texttospeech.SsmlVoiceGender.NEUTRAL)
        )
        print(f"✅ Voice changed to: {name}")
    
    def set_audio_config(self, pitch: float = 0.0, speaking_rate: float = 1.0):
        """
        Adjust audio configuration
        
        Args:
            pitch: Pitch adjustment (-20.0 to 20.0)
            speaking_rate: Speaking rate (0.25 to 4.0)
        """
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=speaking_rate,
            pitch=pitch
        )
        print(f"✅ Audio config updated: pitch={pitch}, rate={speaking_rate}")


def main():
    """Test the TTS module"""
    tts = GoogleTTS()
    
    # Test text
    test_text = "Hello! I'm your AI assistant. How can I help you today?"
    
    # Synthesize and play
    success = tts.speak(test_text)
    
    if not success:
        print("Failed to synthesize speech. Check your API key.")


if __name__ == "__main__":
    main()