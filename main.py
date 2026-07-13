from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
import json

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "hello world"}


WS_URL = "wss://convenience-ist-listings-klein.trycloudflare.com/ws"


@app.post("/voice")
async def voice():
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <ConversationRelay url="{WS_URL}" welcomeGreeting="Hi, thanks for calling ABC dental office. How can I help you today?" />
        </Connect>
    </Response>"""
    return Response(content=twiml, media_type="text/xml")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "setup":
                print("call started")
            elif msg_type == "prompt":
                await websocket.send_text(
                    json.dumps(
                        {"type": "text", "token": "hello you liga", "last": True}
                    )
                )
    except WebSocketDisconnect:
        print("Call Ended")
