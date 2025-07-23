import json

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from utils import handle_voice_agent

app = FastAPI(
    title="Pipecat AI Agent in Azure",
    description="A voice agent built with Pipecat AI and deployed to Azure Container Apps",
    version="0.1.0",
    contact={
        "name": "Mahimai Raja",
        "url": "https://github.com/mahimairaja",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/")
async def init_call():
    return HTMLResponse(
        content=open("templates/streams.xml").read(), media_type="application/xml"
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    init_data = websocket.iter_text()
    await init_data.__anext__()
    call_data = json.loads(await init_data.__anext__())
    print(call_data, flush=True)
    stream_sid = call_data["start"]["streamSid"]
    print(f"WebSocket connected to the call: {stream_sid}")
    await handle_voice_agent(websocket, stream_sid)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
