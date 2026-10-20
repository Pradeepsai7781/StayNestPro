
import json
import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)


def generate_support_answer(
    question: str,
    category: str,
    context: dict,
) -> str:
    """Answer support questions using verified context and safe fallbacks."""

    fallback_answers = {
        "hotel": (
            "I can help with hotel information. Please check the hotel's "
            "details page for its amenities, location, and policies."
        ),
        "booking": (
            "You can review your booking details in your reservations. "
            "Contact support if you need help with a specific reservation."
        ),
        "payment": (
            "You can check your payment status in your payment details. "
            "Never share your password, full card number, CVV, or OTP."
        ),
        "cancellation": (
            "Cancellation eligibility depends on your reservation status "
            "and the applicable policy. Please review your booking details."
        ),
        "general": (
            "I can help with hotel, booking, payment, and cancellation "
            "questions. Please provide more details about your query."
        ),
    }

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback_answers.get(category, fallback_answers["general"])

    prompt = f"""
You are the StayNestPro customer support assistant.

Answer the customer's question clearly and politely.
Use only the verified context supplied below for customer-specific facts.
Never invent booking, payment, refund, or cancellation statuses.
Never reveal other customers' information, passwords, tokens, OTPs,
full card numbers, CVVs, or secret credentials.
Do not perform or claim to perform a booking cancellation or payment.

Category: {category}
Customer question: {question}
Verified context: {json.dumps(context, default=str)}

If the context does not contain enough information, explain what the
customer can check next instead of guessing.
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_SUPPORT_MODEL", "gemini-3.8-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )

        answer = (response.text or "").strip()
        if answer:
            return answer[:4000]

    except Exception:
        logger.warning("Support chatbot AI unavailable.", exc_info=True)

    return fallback_answers.get(category, fallback_answers["general"])
