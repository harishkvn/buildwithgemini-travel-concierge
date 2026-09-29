# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

PROJECT_ID = "qwiklabs-gcp-01-7b5a1e1dd905"
BUCKET_NAME = "travel-concierge-media-qwiklabs-gcp-01-7b5a1e1dd905"


def _get_maps_api_key() -> str:
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GOOGLE_MAPS_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    os.environ["GOOGLE_MAPS_API_KEY"] = key
                    break
    return key or ""


def search_destinations(city: str = "", category: str = "") -> list[dict]:
    """Search for travel destinations in the catalog by city or category.

    Args:
        city: Optional city name to filter destinations (e.g., 'San Francisco', 'Tokyo', 'New York').
        category: Optional category to filter destinations (e.g., 'Attraction', 'Food & Market', 'Park').

    Returns:
        List of destination dictionaries matching the search criteria.
    """
    db = firestore.Client(project=PROJECT_ID)
    docs = db.collection("destinations").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if city and city.lower() not in data.get("city", "").lower():
            continue
        if category and category.lower() not in data.get("category", "").lower():
            continue
        results.append(data)
    return results


def add_destination(
    id: str,
    name: str,
    city: str,
    category: str,
    description: str,
    budget_tier: str = "$$",
    rating: float = 4.5,
) -> str:
    """Add a new travel destination or venue to the catalog.

    Args:
        id: Unique document ID for the destination (e.g. 'sf-golden-gate-bridge').
        name: Name of the destination.
        city: City where the destination is located.
        category: Category of venue (e.g. 'Attraction', 'Park', 'Hotel', 'Food & Market').
        description: Brief description of the destination.
        budget_tier: Cost tier indicator (e.g. '$', '$$', '$$$').
        rating: Rating out of 5.0.

    Returns:
        Confirmation string indicating successful addition.
    """
    db = firestore.Client(project=PROJECT_ID)
    doc_ref = db.collection("destinations").document(id)
    item = {
        "id": id,
        "name": name,
        "city": city,
        "category": category,
        "description": description,
        "budget_tier": budget_tier,
        "rating": rating,
    }
    doc_ref.set(item)
    return f"Successfully added destination '{name}' ({id}) to the catalog."


def calculate_trip_budget(
    daily_budget: float,
    num_days: int,
    num_travelers: int = 1,
    accommodation_tier: str = "moderate",
) -> dict:
    """Calculates an itemized estimated trip budget breakdown.

    Args:
        daily_budget: Per-person estimated daily spending budget in USD.
        num_days: Total number of days for the trip.
        num_travelers: Total number of people traveling.
        accommodation_tier: Level of accommodation ('budget', 'moderate', 'luxury').

    Returns:
        Dictionary containing estimated cost breakdowns for lodging, food, activities, transit, and total cost.
    """
    multiplier = 1.0
    tier_lower = accommodation_tier.lower()
    if "budget" in tier_lower:
        multiplier = 0.7
    elif "luxury" in tier_lower:
        multiplier = 1.6

    total_base = daily_budget * num_days * num_travelers
    lodging = round(total_base * 0.45 * multiplier, 2)
    food = round(total_base * 0.30, 2)
    activities = round(total_base * 0.15, 2)
    transit = round(total_base * 0.10, 2)
    total_estimated = round(lodging + food + activities + transit, 2)

    return {
        "num_days": num_days,
        "num_travelers": num_travelers,
        "accommodation_tier": accommodation_tier,
        "lodging_estimated_usd": lodging,
        "food_estimated_usd": food,
        "activities_estimated_usd": activities,
        "transit_estimated_usd": transit,
        "total_estimated_usd": total_estimated,
    }


def get_live_weather(city: str) -> str:
    """Fetches current real-time weather conditions for any city globally using the Open-Meteo public API.

    Args:
        city: Name of the city to get live weather for (e.g. 'Tokyo', 'Paris', 'San Francisco', 'New York').

    Returns:
        String describing the current temperature, wind speed, and weather condition.
    """
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "TravelConciergeApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode())

        if not geo_data.get("results"):
            return f"Could not find coordinates for city '{city}'."

        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        city_name = loc.get("name", city)
        country = loc.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "TravelConciergeApp/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp_w:
            w_data = json.loads(resp_w.read().decode())

        curr = w_data.get("current_weather", {})
        temp_c = curr.get("temperature", 0.0)
        temp_f = round(temp_c * 9 / 5 + 32, 1)
        wind = curr.get("windspeed", 0.0)

        return f"Live Weather in {city_name}, {country}: {temp_c}°C ({temp_f}°F), Wind: {wind} km/h."
    except Exception as e:
        return f"Error fetching live weather for {city}: {str(e)}"


def geocode_address(address: str) -> dict:
    """Converts an address or location name into geographic coordinates (latitude, longitude) using Google Maps Geocoding API.

    Args:
        address: The address or landmark string to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'Eiffel Tower').

    Returns:
        Dictionary containing formatted_address, latitude, and longitude.
    """
    api_key = _get_maps_api_key()
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return {"error": f"Geocoding failed with status: {data.get('status')}"}

        result = data["results"][0]
        loc = result["geometry"]["location"]
        return {
            "formatted_address": result.get("formatted_address"),
            "latitude": loc.get("lat"),
            "longitude": loc.get("lng"),
        }
    except Exception as e:
        return {"error": str(e)}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> list[dict]:
    """Finds nearby places of a given type around coordinates using the Google Places API (New).

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        place_type: Type of place to search for (e.g. 'restaurant', 'cafe', 'tourist_attraction', 'museum', 'park').
        radius_meters: Search radius in meters (default: 1000.0).

    Returns:
        List of place dictionaries containing name, address, and location coordinates.
    """
    api_key = _get_maps_api_key()
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}]

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        }
        body = json.dumps({
            "includedTypes": [place_type],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": float(radius_meters),
                }
            },
        }).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        places = []
        for p in data.get("places", []):
            display_name = p.get("displayName", {}).get("text", "")
            address = p.get("formattedAddress", "")
            loc = p.get("location", {})
            places.append({
                "name": display_name,
                "address": address,
                "location": {
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                },
            })
        return places
    except Exception as e:
        return [{"error": str(e)}]


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city or query to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def generate_destination_image(
    prompt: str,
    filename: str = "destination.jpg",
    tool_context: ToolContext = None,
) -> str:
    """Generates an image for a travel destination using gemini-3.1-flash-lite-image in the global region. Saves the image artifact to the Playground and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed description of the destination image to generate (e.g. 'A vibrant sunset view of the Golden Gate Bridge').
        filename: Target filename for the image artifact and Cloud Storage object (e.g. 'golden_gate.jpg').
        tool_context: ADK ToolContext instance for saving Playground artifacts.

    Returns:
        Public HTTPS URL of the uploaded image in Cloud Storage (https://storage.googleapis.com/<bucket>/<object>).
    """
    try:
        gen_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        resp = gen_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        if not resp.candidates or not resp.candidates[0].content.parts:
            return "Error: Image generation model did not return output."

        part = resp.candidates[0].content.parts[0]
        if not hasattr(part, "inline_data") or not part.inline_data:
            return "Error: Model output did not contain inline image data."

        image_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or "image/jpeg"

        # 1. Save artifact with tool_context.save_artifact
        if tool_context is not None and hasattr(tool_context, "save_artifact"):
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public GCS bucket (no local file writing)
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Error generating image: {str(e)}"


def generate_destination_video(
    prompt: str,
    filename: str = "destination.mp4",
    tool_context: ToolContext = None,
) -> str:
    """Generates a short video for a travel destination using Google's Omni model (gemini-omni-flash-preview) in the global region. Saves the video artifact to the Playground and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed description of the destination video to generate (e.g. 'A short video clip of a serene cherry blossom path in Tokyo').
        filename: Target filename for the video artifact and Cloud Storage object (e.g. 'tokyo_cherry_blossom.mp4').
        tool_context: ADK ToolContext instance for saving Playground artifacts.

    Returns:
        Public HTTPS URL of the uploaded video in Cloud Storage (https://storage.googleapis.com/<bucket>/<object>).
    """
    try:
        gen_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        interaction = gen_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        mime_type = "video/mp4"

        # Extract video bytes from interaction output
        if hasattr(interaction, "output_video") and interaction.output_video:
            raw_data = getattr(interaction.output_video, "data", None)
            if raw_data:
                if isinstance(raw_data, str):
                    video_bytes = base64.b64decode(raw_data)
                elif isinstance(raw_data, bytes):
                    video_bytes = raw_data

        if not video_bytes and hasattr(interaction, "steps") and interaction.steps:
            for step in interaction.steps:
                content_list = getattr(step, "content", []) or []
                for item in content_list:
                    item_type = getattr(item, "type", None) or (
                        item.get("type") if isinstance(item, dict) else None
                    )
                    if item_type == "video":
                        b64_data = getattr(item, "data", None) or (
                            item.get("data") if isinstance(item, dict) else None
                        )
                        mime_type = (
                            getattr(item, "mime_type", None)
                            or (item.get("mime_type") if isinstance(item, dict) else None)
                            or "video/mp4"
                        )
                        if b64_data:
                            if isinstance(b64_data, str):
                                video_bytes = base64.b64decode(b64_data)
                            elif isinstance(b64_data, bytes):
                                video_bytes = b64_data

        if not video_bytes:
            return "Error: Video generation model did not return video data."

        # 1. Save artifact with tool_context.save_artifact
        if tool_context is not None and hasattr(tool_context, "save_artifact"):
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public GCS bucket (no local file writing)
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Error generating video: {str(e)}"



DEPLOYMENT_METADATA_FILE = Path(__file__).resolve().parent.parent / "deployment_metadata.json"
_agent_engine_resource_name = None
if DEPLOYMENT_METADATA_FILE.exists():
    try:
        _meta_data = json.loads(DEPLOYMENT_METADATA_FILE.read_text())
        _agent_engine_resource_name = _meta_data.get("remote_agent_runtime_id")
    except Exception:
        pass

MEMORY_BANK_ID = _agent_engine_resource_name.split("/")[-1] if _agent_engine_resource_name else "4532916455657701376"

async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None

def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-central1",
        agent_engine_id=MEMORY_BANK_ID,
    )

memory_service = memory_bank_service_builder()

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=_agent_engine_resource_name
)


a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = a2ui_schema_manager.generate_system_prompt(
    role_description=(
        "You are a Smart Travel & Local Discovery Concierge. "
        "You assist travelers with geocoding locations, discovering nearby venues using Google Maps, "
        "generating destination visuals, checking live weather, calculating travel budgets, and searching/managing their destination catalog. "
        "You pay special attention to and remember all user allergies (e.g. food, environmental, medical, dietary restrictions) and preferences stated across conversations, "
        "using recalled memories to strictly customize travel, dining, and venue recommendations. "
        "You can also execute Python code in a secure sandbox when calculations or data processing are required."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        PreloadMemoryTool(),
        generate_destination_image,
        generate_destination_video,
        geocode_address,
        find_nearby_places,
        search_destinations,
        add_destination,
        calculate_trip_budget,
        get_live_weather,
        get_weather,
        get_current_time,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

