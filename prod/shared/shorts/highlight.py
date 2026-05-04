"""Find video highlights using GPT-4."""

import json
import logging
from typing import Any

from openai import OpenAI
from app.core.config import api_settings

logger = logging.getLogger(__name__)


def find_highlights(transcript_json: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    """Identify interesting segments for shorts based on transcript."""
    if not api_settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return []

    client = OpenAI(api_key=api_settings.OPENAI_API_KEY)
    
    # Prepare a condensed version of transcript for GPT
    segments = transcript_json.get("segments", [])
    text_data = "\n".join([f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments])
    
    prompt = f"""
    Below is a transcript of a video with timestamps. 
    Identify the top {limit} most engaging, funny, or viral-potential segments that are between 15 and 50 seconds long.
    For each segment, provide:
    1. Start time
    2. End time
    3. A catchy title for a YouTube Short
    4. A brief reason why it was chosen
    
    Transcript:
    {text_data[:10000]} # Limit transcript size for context window
    
    Respond ONLY with a JSON list of objects:
    [
        {{"start": 12.5, "end": 42.0, "title": "Catchy Title", "reason": "Reasoning"}},
        ...
    ]
    """

    try:
        logger.info("Requesting GPT highlights for transcript")
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a professional social media content creator specializing in YouTube Shorts and TikTok."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        
        # GPT might return {"highlights": [...]} or just [...]
        # response_format="json_object" usually forces a root object.
        highlights = None
        if isinstance(data, list):
            highlights = data
        elif isinstance(data, dict):
            # Try to find a list within the dict
            for key in ["highlights", "segments", "items", "clips"]:
                if isinstance(data.get(key), list):
                    highlights = data[key]
                    break
            if highlights is None:
                # If no list found, maybe the dict itself is the result wrapped in a key
                # or it's a single item.
                vals = list(data.values())
                if vals and isinstance(vals[0], list):
                    highlights = vals[0]
                else:
                    highlights = [data]
        
        if not isinstance(highlights, list):
            return []
            
        return highlights[:limit]
    except Exception as e:
        logger.error("Failed to find highlights using GPT: %s", e)
        return []
