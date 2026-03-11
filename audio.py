from io import BytesIO
import wave

# Audio parameters for raw PCM conversion
SAMPLE_RATE = 24000 
CHANNELS = 1  # Mono
SAMPLE_WIDTH = 2  # 16-bit audio

import logging
logging.basicConfig(
    level = logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s",
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler("chatbot.log")
        ]
)
logger = logging.getLogger("GroqSTTBot")

def convert_raw_pcm_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE, 
                           channels: int = CHANNELS, sample_width: int = SAMPLE_WIDTH) -> bytes:
    """
    Convert raw PCM audio data to WAV format.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default: 48000)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Bytes per sample (default: 2 for 16-bit)
    
    Returns:
        WAV formatted audio bytes
    """
    logger.info(f"Converting {len(pcm_data)} bytes of raw PCM to WAV "
                f"({sample_rate}Hz, {channels}ch, {sample_width*8}bit)")
    
    wav_buffer = BytesIO()
    
    try:
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        wav_bytes = wav_buffer.getvalue()
        logger.info(f"WAV conversion successful: {len(wav_bytes)} bytes")
        return wav_bytes
    
    except Exception as e:
        logger.error(f"WAV conversion failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Starting Groq STT Chatbot...")
