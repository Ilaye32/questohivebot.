import os
import logging
import asyncio
from typing import List, TypedDict, Union, Optional
import json
import sys
from firecrawl import Firecrawl
import re
from dotenv import load_dotenv

import chainlit as cl
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_tavily import TavilySearch
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from google import genai
from google.genai import types
from langgraph.prebuilt import create_react_agent, tool_node, tools_condition

from elevenlabs import play, VoiceSettings
from elevenlabs.client import ElevenLabs
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from read import read_documents
from audio import convert_raw_pcm_to_wav
from detect_format import detect_audio_format
load_dotenv()
# ============================================================================
# CONFIGURATION
# ============================================================================
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
@tool
def get_ai_response(query: str) -> str:
    """This is the tool used to get knowledge from about the knowledge base."""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents= query ,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=["fileSearchStores/vitjm1dcimsg-wdjru7cw5d6y"]
                        )
                    )
                ]
            )
        )
        return response.text
    except Exception as e:
        return f"Information not available: {str(e)}"




# 1. Define your global configurations (Proxies, Headless, etc.)
browser_config = BrowserConfig(
    headless=True,
    proxy_config={
        "server": "http://proxy.example.com:8080", # Replace with actual or env var
        "username": "user",
        "password": "pass"
    }
)

# 2. Wrap the logic in a dynamic tool
@tool
async def deep_scrape_tool(url: str) -> str:
    """
    An advanced web scraper. Use this when you need to bypass bot detection 
    or read complex websites that standard tools can't handle.
    
    Args:
        url (str): The specific URL the agent wants to investigate.
    """
    # We use a session_id to maintain state (useful if the agent 
    # scrapes multiple pages on the same site).
    run_config = CrawlerRunConfig(session_id="agent_session")

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            
            if result.success:
                # Return the markdown—it's the best format for AI to process
                return result.markdown
            else:
                return f"Scrape failed: {result.error_message}"
                
    except Exception as e:
        return f"An error occurred while scraping: {str(e)}"

# Initialize the client once outside the function so it can be reused
firecrawl = Firecrawl(api_key=os.getenv('FIRECRAWL_API_KEY'))

@tool
def scrape_with_firecrawl(url: str) -> str:
    """
    Scrapes the text content of a website. 
    Use this tool when you need to read a specific URL to gather real-time information.
    
    Args:
        url (str): The exact URL of the website to scrape.
    """
    # The 'url' variable is passed in by the AI Agent dynamically
    try:
        response = firecrawl.crawl(
            url, 
            limit=1, # Keep limit low for simple single-page agent reads
            scrape_options={
                'formats': ['markdown'], # Markdown is easiest for LLMs to read
                'proxy': 'auto',
                'only_main_content': True 
            }
        )
        
        # Return the markdown text back to the LLM's "brain"
        # Adjust the key based on how your specific version of firecrawl structures the dict
        return str(response) 
        
    except Exception as e:
        return f"Error scraping the website: {str(e)}"

def tavily_fuction():
    search_tool = TavilySearch(api_key=os.getenv("TAVILY_API_KEY"),
        search_depth="advanced")
    return search_tool

class Config:
    """Centralized configuration"""
    
    # Audio settings
    WHISPER_MODEL = "whisper-large-v3"
    MAX_AUDIO_SIZE_MB = 25
    MIN_AUDIO_SIZE_KB = 0.001
    
    # LLM settings
    LLM_MODEL = "gemini-2.5-flash-lite"
    LLM_TEMPERATURE = 0
    MAX_HISTORY_MESSAGES = 20
    REQUEST_TIMEOUT = 120 # seconds
    MAX_INPUT_LENGTH = 10000
    
    # System prompt
    SYSTEM_PROMPT = f"""
    You are Ella, Ilaye’s AI assistant.

Rules (Mandatory):

Introduce yourself as “Ella, Ilaye’s AI assistant.”
Say you were created by Ilaye to help answer questions.
Speak naturally like a human (clear, friendly, conversational).
Never say you were trained by Google or any company.
If your knowledge may be outdated, use {tavily_function} to verify information.

Style:

Keep answers clear and helpful.
Avoid robotic or overly technical language unless asked.
     """

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
    required_vars = ["GROQ_API_KEY", "TAVILY_API_KEY", "GOOGLE_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.critical(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(
            f"Cannot start without required environment variables.\n"
            f"Missing: {', '.join(missing)}\n"
            f"Please set them in your .env file"
        )


search_tool = tavily_fuction()


def initialize_services():
    """Initialize all required services"""
    load_dotenv()
    validate_environment()
    
    try:
        # Initialize Groq client
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Initialize web search tool

        tools = [search_tool, scrape_with_firecrawl, deep_scrape_tool, get_ai_response]
        
        # Initialize LLM with tools
        llm_model = ChatGoogleGenerativeAI(
            temperature=Config.LLM_TEMPERATURE,
            model=Config.LLM_MODEL,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
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

# ----------------------------------------------------
# Eleven labs configuration
# ----------------------------------------------------

def play_audio(text: str) -> bytes:
    """Convert text to speech using ElevenLabs and return audio bytes"""
    
    audio = elevenlabs_client.text_to_speech.convert(
        voice_id="FGY2WhTYpPnrIDTdsKH5",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_turbo_v2_5",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    
    audio_bytes = b"".join(audio)
    return audio_bytes


async def process_user_input(content: str) -> None:
    """Process user input using the agent with tool support."""
    
    if not content or not content.strip():
        await cl.Message(content="⚠️ Empty message received.").send()
        return
    
    if len(content) > Config.MAX_INPUT_LENGTH:
        await cl.Message(
            content=f"⚠️ Message too long. Please keep it under {Config.MAX_INPUT_LENGTH:,} characters."
        ).send()
        return
    
    history = cl.user_session.get("history", [])
    history.append(HumanMessage(content=content))
    history = trim_history(history)
    cl.user_session.set("history", history)
    
    thinking_msg = cl.Message(
        content="""
        <div class="thinking-dots">
            <span></span><span></span><span></span>
        </div>
        """
    )
    await thinking_msg.send()
    
    response_msg = cl.Message(content="")
    first_chunk = True
    
    try:
        full_response = ""
        input_dict = {"messages": history}
        
        async for event in llm_agent.astream_events(input_dict, version="v2"):
            kind = event["event"]
            
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    
                    if first_chunk:
                        await thinking_msg.remove()
                        await response_msg.send()
                        first_chunk = False
                    
                    content = chunk.content
                    if isinstance(content, list):
                        content = "".join(
                            part.get("text", "") if isinstance(part, dict) else str(part)
                            for part in content
                        )
                    await response_msg.stream_token(content)
                    full_response += content
            
            elif kind == "on_tool_start":
                logger.info(f"Tool started: {event['name']}")
            
            elif kind == "on_tool_end":
                logger.info(f"Tool ended: {event['name']}, output={event['data'].get('output')}")
        
        await response_msg.update()
        
        if full_response:
            history.append(AIMessage(content=full_response))
            history = trim_history(history)
            cl.user_session.set("history", history)
            logger.info(f"Response generated: {len(full_response)} chars")
            
            # Send TTS audio response
            try:
                audio_bytes = play_audio(full_response)
                await cl.Message(
                    content="",
                    elements=[
                        cl.Audio(
                            name="Response",
                            content=audio_bytes,
                            mime="audio/mpeg",
                            display="inline",
                            auto_play=True
                        )
                    ]
                ).send()
            except Exception as e:
                logger.warning(f"TTS failed: {e}")
        
        else:
            await thinking_msg.remove()
            response_msg.content = "⚠️ No response generated. Please try again."
            await response_msg.send()
    
    except asyncio.TimeoutError:
        logger.error("Agent request timed out")
        await thinking_msg.remove()
        response_msg.content = "⚠️ Request timed out. Please try again."
        await response_msg.send()
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await thinking_msg.remove()
        response_msg.content = get_user_friendly_error(e)
        await response_msg.send()


# ============================================================================
# CHAINLIT EVENT HANDLERS
# ============================================================================

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Morning routine ideation",
            message="Can you help me create a personalized morning routine that would help increase my productivity throughout the day? Start by asking me about my current habits and what activities energize me in the morning.",
         #   icon="/public/idea.svg",
        ),

        cl.Starter(
            label="Explain superconductors",
            message="Explain superconductors like I'm five years old.",
         #   icon="/public/learn.svg",
        ),
        cl.Starter(
            label="How Mercor hires",
            message="Can you explain the hiring process at Mercor?",
         #   icon="/public/terminal.svg",
        ),
        cl.Starter(
            label="Text inviting friend to wedding",
            message="Write a text asking a friend to be my plus-one at a wedding next month. I want to keep it super short and casual, and offer an out.",
          #  icon="/public/write.svg",
        )
    ]
# ...


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize a new chat session"""
    cl.user_session.set("history", [])
    cl.user_session.set("audio_buffer", [])
    cl.user_session.set("message_history", [])
    logger.info("New chat session started")


    
@cl.on_chat_start
async def start():
    cl.user_session.set("message_history", [])


@cl.on_audio_start
async def on_audio_start() -> bool:
    """Handle start of audio recording"""
    logger.info("Audio recording started")
    return True

def prompt_decision(conversation):
    if  len(conversation) == 1:
        return Config.SYSTEM_PROMPT
    return Config.welcome_prompt


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk) -> None:
    """Collect incoming audio chunks"""
    audio_buffer = cl.user_session.get("audio_buffer")
    
    # Guard: initialize buffer if session was reset or not yet set
    if audio_buffer is None:
        audio_buffer = []
        cl.user_session.set("audio_buffer", audio_buffer)
    
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
            if isinstance(file, (cl.File,cl.Image))
        ]
        
        if uploaded_files:
            logger.info(f"Processing {len(uploaded_files)} uploaded file(s)")
            
            try:
                document_content = document_content = read_documents(uploaded_files)
                
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



