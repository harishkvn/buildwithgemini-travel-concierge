from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-7b5a1e1dd905"

SEED_DESTINATIONS = [
    {
        "id": "sf-coit-tower",
        "name": "Coit Tower",
        "city": "San Francisco",
        "category": "Attraction",
        "description": "Historic 210-foot tower in Telegraph Hill offering panoramic city and bay views.",
        "budget_tier": "$",
        "rating": 4.6,
    },
    {
        "id": "sf-ferry-building",
        "name": "Ferry Building Marketplace",
        "city": "San Francisco",
        "category": "Food & Market",
        "description": "Vibrant food hall and artisan market along the Embarcadero waterfront.",
        "budget_tier": "$$",
        "rating": 4.7,
    },
    {
        "id": "nyc-central-park",
        "name": "Central Park",
        "city": "New York",
        "category": "Park",
        "description": "Iconic 843-acre urban park featuring walking paths, boat rentals, and gardens.",
        "budget_tier": "$",
        "rating": 4.9,
    },
    {
        "id": "nyc-the-high-line",
        "name": "The High Line",
        "city": "New York",
        "category": "Attraction",
        "description": "Elevated linear park and greenway built on a historic freight rail line.",
        "budget_tier": "$",
        "rating": 4.8,
    },
    {
        "id": "tokyo-sensoji",
        "name": "Senso-ji Temple",
        "city": "Tokyo",
        "category": "Attraction",
        "description": "Ancient Buddhist temple in Asakusa with iconic red lanterns and shopping street.",
        "budget_tier": "$",
        "rating": 4.8,
    },
    {
        "id": "tokyo-skytree",
        "name": "Tokyo Skytree",
        "city": "Tokyo",
        "category": "Attraction",
        "description": "Broadcasting and observation tower offering sweeping views of Mount Fuji.",
        "budget_tier": "$$$",
        "rating": 4.7,
    },
]

def seed():
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("destinations")
    
    print(f"Seeding {len(SEED_DESTINATIONS)} destinations to Firestore project '{PROJECT_ID}'...")
    for item in SEED_DESTINATIONS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  - Added/updated destination: {item['name']} ({doc_id})")

    print("Seeding complete!")

if __name__ == "__main__":
    seed()
