import os
from twilio.rest import Client
from dotenv import load_dotenv
import asyncio

load_dotenv()

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

async def send_sms(call_data: dict) -> None:
    if call_data["urgent"]:
        urgent = "Yes"
    else:
         urgent = "No"
    if call_data["new_or_returning"] == None:
        new_or_returning = "n/a"
    else: new_or_returning = call_data["new_or_returning"]
    if call_data["day_preference"] == None:
        day_preference = "n/a"
    else: day_preference = call_data["day_preference"]
    message = await asyncio.to_thread(client.messages.create,
            body=f"Missed Patient Call from: {call_data["caller_name"]} Number: {call_data["callback_number"]} Urgent: {urgent} Reason: {call_data["reason"]} New or Returning: {new_or_returning} Day Preference: {day_preference}",
            from_=os.environ["TWILIO_NUMBER"],
            to=os.environ["RECEIVING_NUMBER"]
    )
