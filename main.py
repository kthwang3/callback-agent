from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
import json
from openai import OpenAI
from dotenv import load_dotenv
import asyncio
from db import save_call
from sms import send_sms
import os
load_dotenv()
client = OpenAI()
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "hello world"}


WS_URL = os.getenv("WS_URL")


@app.post("/voice")
async def voice():
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <ConversationRelay url="{WS_URL}" 
                welcomeGreeting="Hi, thanks for calling New West Centre Dental Clinic. How can I help you today?" 
                voice="kdmDKE6EkgrWrrykO9Qt"
                interruptible="none"
                transcriptionProvider="Deepgram",
                speechModel="flux"
                speechTimeout="2000"/>
        </Connect>
    </Response>"""
    return Response(content=twiml, media_type="text/xml")

systemPrompt = """
You are answering the phone in place of Dr. Lai at New West Centre Dental Clinic, who is unable to take this call directly, so it was directed to you.

Your replies are spoken aloud by text-to-speech, so keep every response short and natural sounding -- no lists, no long sentences. If you need a moment to think, say something like "one moment please" or "let me check on that" first, so the caller isn't left in silence.

PACING: Ask ONE question at a time. Wait for the caller's answer before asking the next thing. Never bundle multiple questions into a single reply -- that reads as robotic, not conversational.

REASON: This should apply to EVERY call, not just appointments. Keep a brief, clear note as to why the caller called, since this is what Dr. Lai will read in a SMS summary later.

GATHERING INFO: Figure out what the caller needs. If they want to make an appointment, determine: whether they're a new or returning patient, the type of appointment (e.g. cleaning, toothache exam), and whether Sunday or Wednesday works better for them. If it's not an appointment, ask what else you can help with.

CALLBACK NUMBER: You may already have the caller's number from caller ID. If so, confirm it's correct by reading it back in the 3-3-4 digit format like "one two three, four five six, seven eight nine one". Do not read out the international country code at the beginning like '+1', read the last ten digits only. Wait for a clear "yes" -- don't assume it's right, and don't assume it's the number they want called back on. If you don't have a number, ask for one and confirm it the same way, digit-by-digit. Always get the caller's name too. Just first name is fine.

EMERGENCIES: If anything the caller describes sounds like a real dental emergency -- severe pain, swelling, trauma, or uncontrolled bleeding -- take it seriously immediately. Tell them to seek urgent care or call an emergency line if it's serious, and let them know this will be flagged for an urgent callback. Mark this as urgent right away, even if the conversation continues normally afterward. Always read emergency numbers like 911 as 'nine-one-one', not 'nine-hundred-eleven'.

IF THE CALLER WANTS TO LEAVE: If the caller says they don't have time, want a callback instead, or want to speak to a person, stop asking further questions immediately. Take whatever you already have and wrap up gracefully -- never force them to finish answering everything.

ENDING THE CALL: Only wrap up when the caller gives a clear signal they're done -- for example "goodbye," "that's all," or they have nothing else after you've addressed their request. A brief pause is not a signal to end, and never treat your very first reply as a sign the caller is done. Ask "Is there anything else I can help you with?" before closing. When there's nothing further, say: "I have forwarded this information to our staff, and they will call you back within one business day. Thank you for calling New West Centre Dental Clinic! Goodbye!" Only mark the call as resolved once the caller has confirmed there's nothing else -- not just because one question got answered.

Never claim to have booked, confirmed, or promised anything. You are only gathering information for the office to follow up on.
"""

sessions: dict[str, dict] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    call_sid = None
    silence_count = 0
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=18)
            except asyncio.TimeoutError:
                silence_count += 1
                if silence_count == 1:
                    await websocket.send_text(
                        json.dumps({"type": "text", "token": "Are you still there?", "last": True})
                    )
                else:
                    await websocket.send_text(json.dumps({"type": "end"}))
                    break
                continue
            silence_count = 0
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "setup":
                print("call started")
                call_sid = message.get("callSid")
                raw_number = message.get("from")
                if raw_number:
                    callback_number = raw_number[-10:]
                else:
                    callback_number = None
                sessions[call_sid] = {
                    "messages": [{"role": "developer", "content": systemPrompt + f"The callback number is {callback_number}. Confirm it's correct rather than asking cold."}],
                    "urgent": False,
                    "resolved": False,
                    "caller_name": None,
                    "callback_number": callback_number,
                    "new_or_returning": None,
                    "day_preference": None,
                    "reason": None,
                }
            elif msg_type == "prompt":
                voicePrompt = message.get("voicePrompt")
                sessions[call_sid]["messages"].append(
                    {"role": "user", "content": voicePrompt}
                )
                response = client.responses.create(
                    model="gpt-5.6-luna",
                    input=sessions[call_sid]["messages"],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "call_turn",
                            "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "reply": {"type": "string"},
                                    "urgent": {"type": "boolean"},
                                    "resolved": {"type": "boolean"},
                                    "caller_name": {"type": ["string", "null"]},
                                    "callback_number": {"type": ["string", "null"]},
                                    "new_or_returning": {"type": ["string", "null"]},
                                    "day_preference": {"type": ["string", "null"]},
                                    "reason": {"type": ["string", "null"]},
                                },
                                "required": [
                                    "reply",
                                    "urgent",
                                    "resolved",
                                    "caller_name",
                                    "callback_number",
                                    "new_or_returning",
                                    "day_preference",
                                    "reason",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                )
                llmOutput = json.loads(response.output_text)
                for property in llmOutput:
                    if (
                        llmOutput[property] is not None
                        and property in sessions[call_sid]
                    ):
                        sessions[call_sid][property] = llmOutput[property]
                sessions[call_sid]["messages"].append(
                    {"role": "assistant", "content": llmOutput["reply"]}
                )
                await websocket.send_text(
                    json.dumps(
                        {"type": "text", "token": llmOutput["reply"], "last": True}
                    )
                )
                if sessions[call_sid]["resolved"]:
                    print(f"Call {call_sid} resolved: {sessions[call_sid]}")
                    await asyncio.sleep(10)
                    await websocket.send_text(json.dumps({"type": "end"}))
                    break
    except WebSocketDisconnect:
        print("Websocket cleanly disconnected")

    finally:
        if call_sid and call_sid in sessions:
            await save_call(sessions[call_sid])
            await send_sms(sessions[call_sid])
            print("Call Ended")
            print(sessions[call_sid])
            del sessions[call_sid]
