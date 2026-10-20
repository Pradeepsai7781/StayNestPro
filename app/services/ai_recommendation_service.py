
import json
import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)


def get_ai_recommendations(
    hotels: list[dict],
    budget: float | None = None,
    city: str | None = None,
) -> list[dict] | None:
    """Return Gemini recommendations, or None if AI is unavailable."""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    if not hotels:
        return []

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
Recommend hotels from this supplied list only.
Do not invent hotels or change their details.
Prioritize the user's preferences, budget, and location.
Return valid JSON only, with this format:
{{"recommendations": [{{"hotel_id": 1, "reason": "short reason"}}]}}

Budget per night: {budget}
Preferred city: {city}
Available hotels:
{json.dumps(hotels, default=str)}
"""

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        data = json.loads(response.text or "{}")
        valid_ids = {hotel["hotel_id"] for hotel in hotels}

        recommendations = []
        for item in data.get("recommendations", []):
            hotel_id = item.get("hotel_id")
            if hotel_id not in valid_ids:
                continue

            hotel = next(
                hotel for hotel in hotels
                if hotel["hotel_id"] == hotel_id
            )
            recommendations.append({
                **hotel,
                "ai_reason": str(item.get("reason", ""))[:300],
            })

        return recommendations

    except Exception:
        logger.warning(
            "Gemini recommendations unavailable; use rule-based fallback.",
            exc_info=True,
        )
        return None
