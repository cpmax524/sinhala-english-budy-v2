"""
Audio bridging logic linking Telegram and Gemini Live API.
"""

import asyncio
import logging

from google.adk import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from core.config import AppConfig

logger = logging.getLogger(__name__)


async def bridge_audio_to_gemini(
    runner: Runner,
    config: AppConfig,
    user_id: str,
    session_id: str,
    record_port: int,
    play_port: int,
    ready_event: asyncio.Event | None = None,
) -> None:
    """
    The core bidirectional bridge between Telegram's audio stream and Gemini via TCP sockets.

    Args:
        runner: The configured ADK Runner.
        config: Application configuration.
        user_id: The Telegram User ID.
        session_id: The ADK Session ID.
        record_port: Port where FFmpeg streams incoming Telegram audio.
        play_port: Port where FFmpeg reads Gemini generated audio.
        ready_event: Signals when TCP servers are successfully bound and listening.
    """
    logger.info("Starting TCP Audio Bridge for session: %s", session_id)
    logger.info("Using runner app_name=%s", runner.app_name)

    queue = LiveRequestQueue()

    # Configure the Gemini Live voice.
    # Female voices: "Aoede", "Kore", "Leda"
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
        proactivity=types.ProactivityConfig(proactive_audio=True),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Leda"
                )
            )
        )
    )

    client_connected = asyncio.Event()
    writer_ref = []

    async def record_handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Receives audio from Telegram (FFmpeg) and sends to Gemini."""
        logger.info("Record client connected from %s", writer.get_extra_info('peername'))
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    logger.warning("Record client reader returned empty bytes! EOF reached.")
                    break
                queue.send_realtime(
                    types.Blob(
                        mime_type=config.audio.mime_type,
                        data=data,
                    )
                )
        except asyncio.CancelledError:
            logger.warning("Record client task cancelled!")
        except Exception as e:
            logger.exception("Record client error: %s", e)
        finally:
            logger.info("Closing record writer and live queue...")
            writer.close()
            await writer.wait_closed()
            queue.close()
            logger.info("Queue closed.")

    async def play_handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Keeps connection open to send Gemini audio to Telegram (FFmpeg)."""
        writer_ref.append(writer)
        client_connected.set()
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Play client disconnected: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, OSError) as e:
                logger.debug("Play writer close error (expected on call end): %s", e)

    # Start TCP Servers
    try:
        record_server = await asyncio.start_server(record_handle_client, '127.0.0.1', record_port)
        play_server = await asyncio.start_server(play_handle_client, '127.0.0.1', play_port)
        logger.info("TCP bridge servers started on ports %s (rec) and %s (play)", record_port, play_port)
        if ready_event:
            ready_event.set()
    except Exception as e:
        logger.error("Failed to start TCP bridge servers: %s", e)
        return

    async def downstream_task() -> None:
        """Stream events from Gemini and pipe audio back to Telegram."""
        try:
            # Wait for FFmpeg to connect
            await client_connected.wait()
            target_writer = writer_ref[0]

            stream_gen = runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=queue,
                run_config=run_config,
            )

            async for event in stream_gen:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith('audio/pcm'):
                            target_writer.write(part.inline_data.data)
                            await target_writer.drain()
                        elif part.text:
                            logger.debug("Gemini [Text]: %s", part.text.strip())
                if getattr(event, "turn_complete", False):
                    logger.debug("--- Turn Complete ---")

        except asyncio.CancelledError:
            logger.info("Downstream task cancelled")
        except Exception as e:
            logger.error("Downstream task error: %s", e, exc_info=True)

    # Run downstream loop
    downstream = asyncio.create_task(downstream_task())

    try:
        await downstream
    finally:
        record_server.close()
        play_server.close()
        await record_server.wait_closed()
        await play_server.wait_closed()
        logger.info("TCP Audio Bridge ended for session: %s", session_id)
