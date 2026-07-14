from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "hello world"}


WS_URL = "wss://hist-receipt-evidence-managed.trycloudflare.com/ws"


@app.post("/voice")
async def voice():
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <ConversationRelay url="{WS_URL}" welcomeGreeting="Hi, thanks for calling New West Centre Dental Clinic. How can I help you today?" />
        </Connect>
    </Response>"""
    return Response(content=twiml, media_type="text/xml")


systemPrompt = """
Note that your replies get spoken aloud by TTS, so keep it short and natural sounding. Always get their name and callback number
You are acting in place of Dr. Lai, who is unable to answer the patient's phonecall, so it directed to you, where we are now.
Before the call ends, make sure you figure out from the patient whether they would like to make an appointment and if so determine: New patient?, name, type of appointment eg. cleaning, toothache exam, prefer appointment Sunday or Wednesday
If what the patient is describing appears to be a real dental emergency severe pain, swelling, trauma, uncontrolled bleeding, tell them to seek urgent care or call an emergency line, and flag it for an urgent human callback.
Always inform the patient with filler dialogue such as "one second/moment please or let me think" if you are to take extra time to think before answering to avoid long periods of silence
If the answer is no appointment, then ask what else you can do for them.
Finally ask, "Is there anything else I can help you with?"
Then when no further inquiries say, "I have forwarded this information to Dr. Lai, our staff will call you back within one business day. Thank you for calling New West Centre Dental Clinic."
Never claim to have booked or promised anything.
"""
sessions: dict[str, list] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    call_sid = None
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "setup":
                print("call started")
                call_sid = message.get("callSid")
                sessions[call_sid] = [{"role": "developer", "content": systemPrompt}]
            elif msg_type == "prompt":
                voicePrompt = message.get("voicePrompt")
                sessions[call_sid].append({"role": "user", "content": voicePrompt})
                response = client.responses.create(
                    model="gpt-5.6-luna", input=sessions[call_sid]
                )
                llmOutput = response.output_text
                sessions[call_sid].append({"role": "assistant", "content": llmOutput})
                await websocket.send_text(
                    json.dumps({"type": "text", "token": llmOutput, "last": True})
                )
    except WebSocketDisconnect:
        print("Call Ended")

    finally:
        if call_sid and call_sid in sessions:
            del sessions[call_sid]
