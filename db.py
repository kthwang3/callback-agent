import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

async def save_call(call_data: dict) -> None:
    async with await psycopg.AsyncConnection.connect(os.getenv("DATABASE_URL")) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO call_summary (caller_name, callback_number, reason, new_or_returning, day_preference) VALUES (%s, %s, %s, %s, %s)",
                (
                    call_data["caller_name"],
                    call_data["callback_number"],
                    call_data["reason"],
                    call_data["new_or_returning"],
                    call_data["day_preference"],
                ),
            )
