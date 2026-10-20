
import json
import logging

from app.services.ai_recommendation_service import (
    get_ai_recommendations,
)

logger = logging.getLogger(__name__)


def create_travel_plan(
    budget: float,
    destination: str,
    start_date: str,
    end_date: str,
    preferences: list[str],
    hotels: list[dict],
) -> dict | None:
    """Generate a travel plan using the existing Gemini integration."""

    try:
        from google import genai
        from google.genai import types
        import os

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        prompt = f"""
Create a practical travel plan using the available hotels below.
Return valid JSON only in this format:
{{
  "destination": "{destination}",
  "start_date": "{start_date}",
  "end_date": "{end_date}",
  "suggestions": ["destination or activity suggestion"],
  "hotel_suggestions": [
    {{"hotel_id": 1, "reason": "short reason"}}
  ],
  "itinerary": ["Day 1: activity"]
}}

Budget: {budget}
Destination: {destination}
Dates: {start_date} to {end_date}
Preferences: {json.dumps(preferences)}
Available hotels: {json.dumps(hotels, default=str)}

Use only the supplied hotel IDs. Do not invent hotels or prices.
"""

        response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.3,
    ),
)

        result = json.loads(response.text or "{}")

        available_ids = {hotel["hotel_id"] for hotel in hotels}
        result["hotel_suggestions"] = [
            item
            for item in result.get("hotel_suggestions", [])
            if item.get("hotel_id") in available_ids
        ]

        return result

    except Exception:
        logger.warning("Travel plan generation failed.", exc_info=True)
        return None
