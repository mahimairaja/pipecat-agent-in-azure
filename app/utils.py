import datetime
import io
import os
import wave

import aiofiles
from dotenv import load_dotenv
from fastapi import WebSocket
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.azure.llm import AzureLLMService
from pipecat.services.azure.stt import AzureSTTService
from pipecat.services.azure.tts import AzureTTSService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

load_dotenv()


async def save_audio(
    server_name: str, audio: bytes, sample_rate: int, num_channels: int
):
    if audio:
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y/%m/%d_%H:%M:%S")
        wav_name = f"{server_name}_recording_{timestamp}.wav"
        buffer = io.BytesIO()
        with wave.open(buffer, mode="wb") as wav_file:
            wav_file.setsampwidth(2)
            wav_file.setnchannels(num_channels)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio)
        buffer.seek(0)
        async with aiofiles.open(wav_name, mode="wb") as out_file:
            await out_file.write(buffer.read())
        print(f"Audio file saved at {wav_name}")
    else:
        print("No audio data to save")


async def handle_voice_agent(
    websocket_client: WebSocket,
    stream_sid: str,
):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )

    llm = AzureLLMService(
        api_key=os.getenv("AZURE_API_KEY"),
        model="o3-mini",
        api_version="2024-12-01-preview",
        endpoint="https://my-foundary.cognitiveservices.azure.com/",
    )

    stt = AzureSTTService(
        api_key=os.getenv("AZURE_API_KEY"),
        region=os.getenv("AZURE_REGION"),
        language="en-US",
    )

    tts = AzureTTSService(
        api_key=os.getenv("AZURE_API_KEY"),
        region=os.getenv("AZURE_REGION"),
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant named Vicky."
                "Your output will be converted to audio so don't include special characters in your answers."
                "Respond with a short short sentence."
            ).join(" "),
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    audiobuffer = AudioBufferProcessor()

    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            stt,  # Speech-To-Text
            context_aggregator.user(),
            llm,  # LLM
            tts,  # Text-To-Speech
            transport.output(),  # Websocket output to client
            audiobuffer,  # Used to buffer the audio in the pipeline
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            allow_interruptions=True,
        ),
    )

    # 1. Defines when the client connects to the server
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await audiobuffer.start_recording()
        messages.append(
            {"role": "system", "content": "Please introduce yourself to the user."}
        )
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    # 2. Defines when the audio data is being received from the client
    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        server_name = f"server_{websocket_client.client.port}"
        await save_audio(server_name, audio, sample_rate, num_channels)

    # 3. Defines when the client disconnects from the server
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False, force_gc=True)
    await runner.run(task)
