# Smart Travel & Local Discovery Concierge

![Demo](demo.gif)

An intelligent, context-aware travel concierge built with the **Google Agent Development Kit (ADK)**. The agent assists travelers with geocoding, Google Places discovery, live weather forecasts, travel budget calculations in a secure code sandbox, multi-session memory recall, and AI-generated visual media (images & short video clips).

---

## Key Features & Implemented Capabilities

### 📍 Local Discovery & Maps Integration
- **Google Maps Geocoding (`geocode_address`):** Resolves addresses and location names to precise latitude/longitude coordinates using the Google Maps Geocoding API.
- **Google Places Search (`find_nearby_places`):** Searches for venues, cafes, restaurants, and attractions near specific coordinates using Google Places Web Services.

### 🧠 Cross-Session Long-Term Memory
- **Vertex AI Memory Bank (`VertexAiMemoryBankService`):** Retains facts, allergies, dietary restrictions, and travel preferences across user sessions, ensuring customized venue and dining recommendations.
- **Preload Memory Tool (`PreloadMemoryTool`):** Automatically preloads relevant past memories before generating responses.

### 💰 Secure Code Sandbox Budgeting
- **Agent Engine Sandbox Executor (`AgentEngineSandboxCodeExecutor`):** Calculates multi-day trip budgets (lodging, transit, food, activities) by executing Python code within a secure containerized sandbox environment (`calculate_trip_budget`).

### 🎨 Visual Media Generation & Hosting
- **AI Image Generation (`generate_destination_image`):** Generates high-quality destination preview images using Google's `gemini-3.1-flash-lite-image` model in the `global` region.
- **AI Short Video Generation (`generate_destination_video`):** Generates short destination video clips using Google's Omni model (`gemini-omni-flash-preview`) in the `global` region.
- **Public Cloud Storage Hosting:** Uploads generated images and videos directly to a public Google Cloud Storage bucket and returns public `https://storage.googleapis.com/...` URLs.

### 🗄️ Firestore Destination Catalog
- **Google Cloud Firestore (`search_destinations`, `add_destination`):** Queries and manages a persistent custom destination database in Google Cloud Firestore.

### 🌦️ Real-Time Weather & Time
- **Live Weather Forecasts (`get_live_weather`):** Retrieves current temperature and weather conditions via Open-Meteo.
- **Timezone Info (`get_current_time`):** Looks up localized time across major global timezones.

### 🎨 Agent-to-UI (A2UI) Rendering
- **Structured UI Protocol (`a2ui`):** Formats recommendations into compact, structured A2UI visual cards (Card, Column, Row, Text, Image) for native UI display.

---

## Google Cloud Architecture & Services

- **Agent Development Kit (ADK):** `google-adk` framework (`Agent`, `App`, `Gemini`).
- **Agent Engine Runtime:** Deployed to Vertex AI Reasoning Engines (`us-central1`).
- **Vertex AI Memory Bank:** Managed cross-session memory service.
- **Google Cloud Storage:** Bucket hosting for generated visual media assets.
- **Google Cloud Firestore:** NoSQL database for destination catalog persistence.
- **Vertex AI Gemini Models:**
  - `gemini-2.5-flash` for agent reasoning and tool orchestration.
  - `gemini-3.1-flash-lite-image` for AI image generation.
  - `gemini-omni-flash-preview` for AI video generation.

---

## Local Setup & Run Instructions

### Prerequisites
- Python 3.11+
- Node.js (v18+)
- Google Cloud CLI (`gcloud`) with active authentication
- Google Maps API key set in `GOOGLE_MAPS_API_KEY`

### 1. Installation
Clone the repository and install the Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in the project root:

```bash
GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>"
```

### 3. Run Agent Locally
Launch the ADK development web UI:

```bash
adk web
```

Or deploy to Agent Engine:

```bash
agents-cli deploy --project <your-gcp-project-id> --no-confirm-project
```

### 4. Deploy Frontend
Deploy the FastAPI frontend service to Cloud Run:

```bash
gcloud run deploy travel-concierge-frontend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="AGENT_ENGINE_RESOURCE_NAME=<your-agent-runtime-id>,AGENT_DIRECTORY=app"
```
