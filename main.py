import os
import logging
import asyncio
import sys
from typing import List, Optional
from dotenv import load_dotenv

import chainlit as cl
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent

from read import read_documents
from audio import convert_raw_pcm_to_wav
from detect_format import detect_audio_format
from prompts import prompt
from seek import crawl_page_advanced
from seek import analyze_page_content
from seek import get_site_statistics
# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Centralized configuration"""
    
    # Audio settings
    WHISPER_MODEL = "whisper-large-v3"
    MAX_AUDIO_SIZE_MB = 25
    MIN_AUDIO_SIZE_KB = 0.001
    
    # LLM settings
    LLM_MODEL = "llama-3.1-8b-instant"
    LLM_TEMPERATURE = 0.7
    MAX_HISTORY_MESSAGES = 20
    REQUEST_TIMEOUT = 30
    MAX_INPUT_LENGTH = 10000
    
    # System prompt
    SYSTEM_PROMPT = prompt


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("chatbot.log")
        ]
    )
    return logging.getLogger("QuestoHive")

logger = setup_logging()


# ============================================================================
# INITIALIZATION
# ============================================================================

def validate_environment() -> None:
    """Validate required environment variables"""
    required_vars = ["GROQ_API_KEY", "TAVILY_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.critical(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(
            f"Cannot start without required environment variables.\n"
            f"Missing: {', '.join(missing)}\n"
            f"Please set them in your .env file"
        )


def initialize_services():
    """Initialize all required services"""
    load_dotenv()
    validate_environment()
    
    try:
        # Initialize Groq client
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Initialize web search tool
        search_tool = TavilySearch(
            api_key=os.getenv("TAVILY_API_KEY"),
            max_results=3
        )
        tools = [search_tool, get_site_statistics, crawl_page_advanced, analyze_page_content ]
        
        # Initialize LLM with tools
        llm_model = ChatGroq(
            temperature=Config.LLM_TEMPERATURE,
            model_name=Config.LLM_MODEL,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            timeout=Config.REQUEST_TIMEOUT,
            streaming=True
        )
        
        # Create agent
        agent = create_react_agent(
            model=llm_model,
            tools=tools,  
            prompt=Config.SYSTEM_PROMPT
        )
        
        logger.info("All services initialized successfully")
        return groq_client, agent
    
    except Exception as e:
        logger.critical(f"Failed to initialize services: {e}", exc_info=True)
        raise SystemExit(f"Service initialization failed: {e}")


# Initialize global services
groq_client, llm_agent = initialize_services()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def trim_history(history: List[BaseMessage]) -> List[BaseMessage]:
    """Keep conversation history within limits"""
    if len(history) > Config.MAX_HISTORY_MESSAGES:
        logger.info(f"Trimming history from {len(history)} to {Config.MAX_HISTORY_MESSAGES}")
        return history[-Config.MAX_HISTORY_MESSAGES:]
    return history


def get_user_friendly_error(error: Exception) -> str:
    """Convert technical errors to user-friendly messages"""
    error_str = str(error).lower()
    
    if "rate limit" in error_str or "429" in error_str:
        return "⚠️ API rate limit reached. Please wait a moment and try again."
    
    if "authentication" in error_str or "401" in error_str or "403" in error_str:
        return "⚠️ API authentication failed. Please contact support."
    
    if "timeout" in error_str:
        return "⚠️ Request timed out. Please try with a shorter recording."
    
    if "invalid" in error_str or "format" in error_str:
        return "⚠️ Audio format issue. Please try recording again."
    
    return f"⚠️ An error occurred. Please try again.\n\n*Details: {str(error)[:100]}*"


# ============================================================================
# AUDIO PROCESSING
# ============================================================================

async def process_audio(audio_data: bytes) -> tuple[str, bytes, str]:
    """
    Process audio: validate, convert if needed, and transcribe
    
    Returns:
        Tuple of (transcription_text, playback_audio, playback_mime)
    
    Raises:
        ValueError: If audio is invalid
        Exception: If transcription fails
    """
    # Validate audio size
    size_mb = len(audio_data) / (1024 * 1024)
    logger.info(f"Processing audio: {size_mb:.2f} MB")
    
    if size_mb > Config.MAX_AUDIO_SIZE_MB:
        raise ValueError(
            f"Audio file too large ({size_mb:.1f}MB). "
            f"Maximum size is {Config.MAX_AUDIO_SIZE_MB}MB."
        )
    
    if size_mb < Config.MIN_AUDIO_SIZE_KB:
        raise ValueError("Audio too short. Please record a longer message.")
    
    # Detect and convert audio format
    mime_type, filename, is_raw_pcm = detect_audio_format(audio_data)
    logger.info(f"Detected format: {mime_type}, is_raw_pcm={is_raw_pcm}")
    
    if is_raw_pcm:
        logger.info("Converting raw PCM to WAV")
        converted_audio = convert_raw_pcm_to_wav(audio_data)
        playback_audio = converted_audio
        playback_mime = "audio/wav"
        filename = "audio.wav"
    else:
        converted_audio = audio_data
        playback_audio = audio_data
        playback_mime = mime_type
    
    # Transcribe
    import io
    audio_file = io.BytesIO(converted_audio)
    
    logger.info("Starting transcription...")
    transcription = await asyncio.to_thread(
        groq_client.audio.transcriptions.create,
        file=(filename, audio_file),
        model=Config.WHISPER_MODEL,
        response_format="text",
        language="en"
    )
    
    text = transcription if isinstance(transcription, str) else transcription.text
    
    if not text or not text.strip():
        raise ValueError("No speech detected in audio")
    
    logger.info(f"Transcription successful: '{text[:50]}...'")
    return text.strip(), playback_audio, playback_mime


# ============================================================================
# CONVERSATION PROCESSING - FIXED VERSION
# ============================================================================

async def process_user_input(content: str) -> None:
    """
    Process user input using the agent with tool support.
    """
    # Validate input (unchanged)
    if not content or not content.strip():
        await cl.Message(content="⚠️ Empty message received.").send()
        return
    
    if len(content) > Config.MAX_INPUT_LENGTH:
        await cl.Message(
            content=f"⚠️ Message too long. Please keep it under {Config.MAX_INPUT_LENGTH:,} characters."
        ).send()
        return
    
    # Get conversation history (as messages)
    history = cl.user_session.get("history", [])
    history.append(HumanMessage(content=content))
    history = trim_history(history)
    cl.user_session.set("history", history)
    
    # Initialize streaming message
    response_msg = cl.Message(content="")
    await response_msg.send()
    
    try:
        full_response = ""
        
        # Use the global agent for invocation
        # Prepare input as a dict with messages (LangGraph format)
        input_dict = {"messages": history}
        
        # Stream from agent (use astream_events for tool-aware streaming)
        async for event in llm_agent.astream_events(input_dict, version="v1"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    await response_msg.stream_token(chunk.content)
                    full_response += chunk.content
            elif kind == "on_tool_start":
                # Optional: Log or display tool usage (e.g., "Searching web...")
                logger.info(f"Tool started: {event['name']}")
            elif kind == "on_tool_end":
                # Optional: Handle tool outputs if needed
                logger.info(f"Tool ended: {event['name']}, output={event['data'].get('output')}")
        
        # Finalize response
        await response_msg.update()
        
        # Update history with AI response
        if full_response:
            history.append(AIMessage(content=full_response))
            history = trim_history(history)
            cl.user_session.set("history", history)
            logger.info(f"Response generated: {len(full_response)} chars")
        else:
            response_msg.content = "⚠️ No response generated. Please try again."
            await response_msg.update()
    
    except asyncio.TimeoutError:
        logger.error("Agent request timed out")
        response_msg.content = "⚠️ Request timed out. Please try again."
        await response_msg.update()
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        response_msg.content = get_user_friendly_error(e)
        await response_msg.update()




# ============================================================================
# CHAINLIT EVENT HANDLERS
# ============================================================================

@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize a new chat session"""
    cl.user_session.set("history", [])
    cl.user_session.set("audio_buffer", [])
    logger.info("New chat session started")
    
    await cl.Message(
        content=(
            "🎓 **Welcome to QuestoHive!**\n\n"
            "I'm here to help you learn and understand past exam questions.\n\n"
            "You can:\n"
            "- 🎙️ Click the microphone to ask questions with your voice\n"
            "- ⌨️ Type your questions below\n"
            "- 📄 Upload documents for me to analyze\n\n"
            "How can I help you today?"
        )
    ).send()


@cl.on_audio_start
async def on_audio_start() -> bool:
    """Handle start of audio recording"""
    logger.info("Audio recording started")
    return True


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk) -> None:
    """Collect incoming audio chunks"""
    audio_buffer = cl.user_session.get("audio_buffer")
    audio_buffer.append(chunk.data)
    cl.user_session.set("audio_buffer", audio_buffer)
    
    # Log first chunk for debugging
    if len(audio_buffer) == 1 and len(chunk.data) > 4:
        hex_start = chunk.data[:4].hex()
        logger.debug(f"First chunk: {len(chunk.data)} bytes, magic={hex_start}")


@cl.on_audio_end
async def on_audio_end() -> None:
    """Process complete audio recording"""
    audio_buffer = cl.user_session.get("audio_buffer")
    
    if not audio_buffer:
        await cl.Message(content="⚠️ No audio recorded. Please try again.").send()
        return
    
    # Combine all chunks
    full_audio = b''.join(audio_buffer)
    
    try:
        # Process and transcribe audio
        transcription, playback_audio, playback_mime = await process_audio(full_audio)
        
        # Display transcription with playable audio
        await cl.Message(
            content=f"**You said:** {transcription}",
            elements=[
                cl.Audio(
                    name="Your Recording",
                    content=playback_audio,
                    mime=playback_mime,
                    display="inline"
                )
            ]
        ).send()
        
        # Process the transcribed text
        await process_user_input(transcription)
    
    except ValueError as e:
        # User-facing validation errors
        await cl.Message(content=str(e)).send()
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Audio processing error: {e}", exc_info=True)
        await cl.Message(content=get_user_friendly_error(e)).send()
    
    finally:
        # Always clear the buffer
        cl.user_session.set("audio_buffer", [])


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle text messages and file uploads"""
    content = message.content
    
    # Process file uploads if present
    if message.elements:
        uploaded_files = [
            file for file in message.elements 
            if isinstance(file, cl.File)
        ]
        
        if uploaded_files:
            logger.info(f"Processing {len(uploaded_files)} uploaded file(s)")
            
            try:
                document_content = read_documents(uploaded_files)
                
                if document_content.strip():
                    # Prepend document context to user message
                    content = (
                        f"{message.content}\n\n"
                        f"**Context from uploaded documents:**\n{document_content}"
                    )
                    await cl.Message(
                        content=f"✅ Processed {len(uploaded_files)} document(s)"
                    ).send()
                else:
                    await cl.Message(
                        content="⚠️ No content could be extracted from the documents"
                    ).send()
            
            except Exception as e:
                logger.error(f"Document processing error: {e}", exc_info=True)
                await cl.Message(
                    content=f"⚠️ Error processing documents: {str(e)}"
                ).send()
                return
    
    # Process the user's message
    await process_user_input(content)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting QuestoHive Voice Chatbot...")
    logger.info(f"Configuration: Model={Config.LLM_MODEL}, Temp={Config.LLM_TEMPERATURE}")
