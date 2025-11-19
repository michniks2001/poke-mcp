"""Thin wrapper around Google's Generative AI Gemini client."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from dotenv import load_dotenv

# Load default .env first, then overlay .env.local so user-specific keys win.
load_dotenv()
load_dotenv(".env.local", override=True)


class GeminiClient:
    """Convenience client for Gemini 2.5 Flash prompts."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
    ) -> None:
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def summarize_team(self, payload: Dict[str, Any]) -> str:
        """Generate a narrative summary for the given team report payload."""

        prompt = self._build_prompt(payload)
        response = self.model.generate_content(prompt)
        return response.text.strip() if response and response.text else ""

    def _build_prompt(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        summary = payload.get("summary", "")
        threats = payload.get("threats", [])
        insights = payload.get("pokemon_insights", [])
        recommendations = payload.get("recommendations", [])

        parts = [
            {
                "role": "system",
                "parts": [
                    "You are an expert Pokemon VGC analyst. Summarize the team assessment "
                    "succinctly, highlighting key threats, coverage gaps, and adjustments."
                ],
            },
            {
                "role": "user",
                "parts": [
                    f"Overall summary: {summary}",
                    f"Threats: {threats}",
                    f"Per-Pokemon insights: {insights}",
                    f"Recommendations: {recommendations}",
                ],
            },
        ]
        return parts
