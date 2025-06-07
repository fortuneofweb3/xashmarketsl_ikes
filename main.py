from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import requests
from requests_oauthlib import OAuth1
from dotenv import load_dotenv
import os

# Create the FastAPI app
app = FastAPI(title="Tweet Likers Service")

# Allow cross-origin requests (for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # We'll restrict this later
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Load credentials from .env file
load_dotenv()
API_KEY = os.getenv("X_API_KEY")
API_KEY_SECRET = os.getenv("X_API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
X_API_URL = "https://api.x.com/2"

# Set up OAuth 1.0a for X API
auth = OAuth1(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

# Require an API key for client requests
api_key_header = APIKeyHeader(name="X-API-Key")
VALID_API_KEY = os.getenv("API_KEY")

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != VALID_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/likers/{tweet_id}")
async def get_tweet_likers(tweet_id: str, next_token: str | None = None, api_key: str = Depends(verify_api_key)):
    """Fetch users who liked the specified tweet."""
    try:
        params = {
            "user.fields": "id,username,name,profile_image_url",
            "max_results": 100
        }
        if next_token:
            params["pagination_token"] = next_token

        response = requests.get(
            f"{X_API_URL}/tweets/{tweet_id}/liking_users",
            auth=auth,
            params=params
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"X API error: {response.json().get('detail', 'Unknown error')}"
            )

        data = response.json()
        return JSONResponse({
            "likers": data.get("data", []),
            "meta": data.get("meta", {}),
            "next_token": data.get("meta", {}).get("next_token")
        })

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)