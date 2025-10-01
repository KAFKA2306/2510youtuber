import logging
import os
import subprocess
import requests
from typing import Optional
import pyttsx3
from gtts import gTTS
from io import BytesIO

# Conditional import for openai
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None

class TTSFallbackManager:
    """音声合成のフォールバックシステム"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pyttsx3_engine = None
        self.voicevox_nemo_port = 50121 # Default port for VOICEVOX Nemo
        self.openai_client = None
        if openai and os.getenv('OPENAI_API_KEY'):
            self.openai_client = OpenAI()
        
    async def synthesize_with_fallback(self, text: str, output_path: str, elevenlabs_synthesizer=None) -> bool:
        """複数の方法で音声合成を試行"""

        # Method 1: ElevenLabs (Primary) - requires external synthesizer instance
        if elevenlabs_synthesizer:
            try:
                self.logger.info("Attempting synthesis with ElevenLabs (primary)")
                # This assumes elevenlabs_synthesizer is an async function
                # that returns True on success and saves to output_path
                if await elevenlabs_synthesizer(text, output_path):
                    return True
            except Exception as e:
                self.logger.warning(f"ElevenLabs failed: {e}")
            
        # Method 2: VOICEVOX Nemo (Free, High Quality)
        if self._voicevox_nemo_synthesize(text, output_path):
            return True
            
        # Method 3: OpenAI TTS (If API key available)
        if self._openai_tts_synthesize(text, output_path):
            return True
            
        # Method 4: Google TTS Free (gTTS)
        if self._gtts_synthesize(text, output_path):
            return True
            
        # Method 5: Coqui TTS (Local)
        if self._coqui_tts_synthesize(text, output_path):
            return True
            
        # Final Fallback: pyttsx3 (Always works)
        self.logger.warning("All primary TTS methods failed, using pyttsx3 as final fallback.")
        return self._pyttsx3_synthesize(text, output_path)
    
    def _voicevox_nemo_synthesize(self, text: str, output_path: str) -> bool:
        """VOICEVOX Nemo による音声合成"""
        try:
            # Check if VOICEVOX Nemo is running
            health_response = requests.get(f'http://localhost:{self.voicevox_nemo_port}/health', timeout=3)
            if health_response.status_code != 200:
                raise Exception("VOICEVOX Nemo not running or unhealthy")
            
            # Generate audio query
            query_params = {'text': text, 'speaker': 1}  # Speaker 1 for Nemo
            query_response = requests.post(
                f'http://localhost:{self.voicevox_nemo_port}/audio_query', 
                params=query_params,
                timeout=10
            )
            
            if query_response.status_code != 200:
                raise Exception(f"Query failed: {query_response.status_code}")
            
            # Synthesize audio
            synthesis_params = {'speaker': 1}
            synthesis_response = requests.post(
                f'http://localhost:{self.voicevox_nemo_port}/synthesis',
                params=synthesis_params,
                json=query_response.json(),
                timeout=30
            )
            
            if synthesis_response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(synthesis_response.content)
                self.logger.info("VOICEVOX Nemo synthesis successful")
                return True
            else:
                self.logger.error(f"VOICEVOX Nemo synthesis failed with status {synthesis_response.status_code}: {synthesis_response.text}")
                
        except requests.exceptions.ConnectionError:
            self.logger.warning("VOICEVOX Nemo server is not reachable.")
        except Exception as e:
            self.logger.warning(f"VOICEVOX Nemo failed: {e}")
        
        return False
    
    def _gtts_synthesize(self, text: str, output_path: str) -> bool:
        """Google TTS (gTTS) による音声合成"""
        try:
            tts = gTTS(text=text, lang='ja')
            
            # Save to BytesIO first, then to file
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            with open(output_path, 'wb') as f:
                f.write(audio_buffer.read())
            
            self.logger.info("gTTS synthesis successful")
            return True
            
        except Exception as e:
            self.logger.warning(f"gTTS failed: {e}")
        
        return False
    
    def _coqui_tts_synthesize(self, text: str, output_path: str) -> bool:
        """Coqui TTS による音声合成"""
        try:
            # Try using Coqui TTS CLI
            # This assumes 'tts' command is in PATH and model is downloaded
            result = subprocess.run([
                'tts', '--text', text, '--out_path', output_path,
                '--model_name', 'tts_models/ja/kokoro/tacotron2-DDC' # Example model
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(output_path):
                self.logger.info("Coqui TTS synthesis successful")
                return True
            else:
                self.logger.error(f"Coqui TTS CLI failed. Stderr: {result.stderr}")
                
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.warning(f"Coqui TTS CLI not found or timed out: {e}")
        except Exception as e:
            self.logger.warning(f"Coqui TTS failed: {e}")
        
        return False
    
    def _openai_tts_synthesize(self, text: str, output_path: str) -> bool:
        """OpenAI TTS による音声合成"""
        if not self.openai_client:
            self.logger.debug("OpenAI client not initialized. Skipping OpenAI TTS.")
            return False

        try:
            response = self.openai_client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text
            )
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info("OpenAI TTS synthesis successful")
            return True
            
        except Exception as e:
            self.logger.warning(f"OpenAI TTS failed: {e}")
        
        return False
    
    def _pyttsx3_synthesize(self, text: str, output_path: str) -> bool:
        """pyttsx3 による音声合成（最終フォールバック）"""
        try:
            if self.pyttsx3_engine is None:
                self.pyttsx3_engine = pyttsx3.init()
                
            # Configure voice settings
            voices = self.pyttsx3_engine.getProperty('voices')
            if voices:
                # Try to find a Japanese voice, fallback to first available
                japanese_voice = None
                for voice in voices:
                    if 'japanese' in voice.name.lower() or 'ja' in voice.id.lower():
                        japanese_voice = voice
                        break
                
                if japanese_voice:
                    self.pyttsx3_engine.setProperty('voice', japanese_voice.id)
                else:
                    self.pyttsx3_engine.setProperty('voice', voices[0].id)
            
            # Set speech rate and volume
            self.pyttsx3_engine.setProperty('rate', 150)
            self.pyttsx3_engine.setProperty('volume', 0.9)
            
            # Save to file
            self.pyttsx3_engine.save_to_file(text, output_path)
            self.pyttsx3_engine.runAndWait()
            
            self.logger.info("pyttsx3 synthesis successful")
            return True
            
        except Exception as e:
            self.logger.error(f"pyttsx3 failed (final fallback): {e}")
        
        return False

# グローバルインスタンス
tts_fallback_manager = TTSFallbackManager()
