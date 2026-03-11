import logging
from typing import Tuple

logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s : %(message)s"
    )

logger = logging.getLogger("GroqSTTBot")

def detect_audio_format(audio_data: bytes) -> Tuple[str, str, bool]:
    """
    Detect audio format from magic bytes.
    
    Args:
        audio_data: Raw audio bytes
    
    Returns:
        Tuple of (mime_type, filename, is_raw_pcm)
    """
    if len(audio_data) < 4:
        logger.warning("Audio data too short to detect format")
        return "audio/wav", "audio.wav", True
    
    magic_bytes = audio_data[:4]
    hex_magic = magic_bytes.hex()
    
    # Check for raw PCM (all zeros or no recognizable header)
    if magic_bytes == b'\x00\x00\x00\x00' or hex_magic == "00000000":
        logger.info("Detected raw PCM audio data")
        return "audio/wav", "audio.wav", True
    
    # WebM: 1A 45 DF A3
    if magic_bytes == b'\x1a\x45\xdf\xa3':
        return "audio/webm", "audio.webm", False
    
    # WAV: RIFF
    elif magic_bytes[:4] == b'RIFF':
        return "audio/wav", "audio.wav", False
    
    # MP4/M4A: ftyp (at offset 4)
    elif len(audio_data) > 8 and audio_data[4:8] == b'ftyp':
        return "audio/mp4", "audio.mp4", False
    
    # OGG: OggS
    elif magic_bytes[:4] == b'OggS':
        return "audio/ogg", "audio.ogg", False
    
    # MP3: ID3 or FF FB/FF F3
    elif magic_bytes[:3] == b'ID3' or magic_bytes[:2] in [b'\xff\xfb', b'\xff\xf3']:
        return "audio/mp3", "audio.mp3", False
    
    else:
        logger.warning(f"Unknown audio format (magic bytes: {hex_magic}), treating as raw PCM")
        return "audio/wav", "audio.wav", True
    
if __name__ == "__main__":
    logger.info("cannot import this module")
