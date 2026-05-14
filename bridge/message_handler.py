import asyncio
import logging

from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from pyrogram import Client, filters
from pyrogram.types import Message

from app.deep_search import research_pipeline
from core.user_store import UserStore

logger = logging.getLogger(__name__)


async def execute_research_pipeline_task(
    client: Client, telegram_id: str, report_id: int, plan_content: str
):
    """Background task to execute the full research pipeline."""
    try:
        await client.send_message(
            chat_id=int(telegram_id),
            text="⏳ Starting deep search execution. This may take a few minutes...",
        )

        session_service = InMemorySessionService()
        runner = Runner(
            agent=research_pipeline,
            session_service=session_service,
            app_name="talkmate",
        )
        session = await session_service.create_session("talkmate", telegram_id)

        # Inject the approved plan into the session state to kick off the pipeline
        session.state["research_plan"] = plan_content
        await session_service.update_session_state(
            "talkmate", telegram_id, session.id, session.state
        )

        # Start the pipeline (the prompt forces it to use the research_plan in state)
        response = await runner.run(
            user_id=telegram_id,
            session_id=session.id,
            messages=[
                {
                    "role": "user",
                    "parts": [{"text": "Execute the approved research plan."}],
                }
            ],
        )

        # Fetch the final report
        updated_session = await session_service.get_session(
            "talkmate", telegram_id, session.id
        )
        final_report = updated_session.state.get("final_report_with_citations", "")

        if (
            not final_report
            and response
            and response.content
            and response.content.parts
        ):
            final_report = response.content.parts[0].text

        if not final_report:
            final_report = "Error: Failed to generate the final report."

        # Update database
        user_store = UserStore()
        await user_store.update_search_report(report_id, final_report, "completed")

        # Send the final report back via Telegram
        await client.send_message(
            chat_id=int(telegram_id),
            text=f"✅ **Deep Search Complete**\n\nHere is your final report:\n\n{final_report}",
        )
        logger.info(
            f"Successfully delivered final research report to user {telegram_id}"
        )

    except Exception as e:
        logger.error(f"Error during deep search execution for user {telegram_id}: {e}")
        await client.send_message(
            chat_id=int(telegram_id),
            text="❌ Sorry, an error occurred while executing the deep search.",
        )


def register_message_handlers(app: Client):
    """Register text message handlers for the Telegram client."""

    @app.on_message(filters.private & filters.text)
    async def handle_private_text(client: Client, message: Message):
        user_id = str(message.chat.id)
        text = message.text.lower().strip()

        user_store = UserStore()
        pending_report = await user_store.get_pending_search_report(user_id)

        if pending_report:
            # Check if user is approving the plan
            if any(
                phrase in text
                for phrase in [
                    "approve",
                    "looks good",
                    "yes",
                    "go ahead",
                    "do it",
                    "start",
                ]
            ):
                await message.reply_text(
                    "✅ Plan approved! I'm starting the deep search now. I'll send you the final report here when it's ready. You can continue your voice call normally."
                )

                # Update status to in_progress (to avoid double-triggering)
                await user_store.update_search_report(
                    pending_report["id"], "", "in_progress"
                )

                # Launch execution in background
                asyncio.create_task(
                    execute_research_pipeline_task(
                        client,
                        user_id,
                        pending_report["id"],
                        pending_report["plan_content"],
                    )
                )
            # Check if user wants to cancel
            elif any(phrase in text for phrase in ["cancel", "stop", "no", "abort"]):
                await user_store.update_search_report(
                    pending_report["id"], "", "cancelled"
                )
                await message.reply_text("❌ Deep search cancelled.")
            else:
                # Let them know they have a pending plan
                await message.reply_text(
                    "You have a pending deep search plan. Please reply with 'Approved' to start it, or 'Cancel' to abort."
                )
        else:
            # No pending report, could just be a normal text message
            # For now we'll just ignore it or send a generic reply
            pass
