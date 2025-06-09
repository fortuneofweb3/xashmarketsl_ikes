from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import requests
from requests_oauthlib import OAuth1
from dotenv import load_dotenv
import os
import time
from cachetools import TTLCache

# Create the FastAPI app
app = FastAPI(title="Tweet Likers Service")

# Allow cross-origin requests (for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Kept as is
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

# Throttling and caching
REQUEST_INTERVAL = 300  # 5 minutes in seconds
last_request_time = 0
cache = TTLCache(maxsize=100, ttl=900)  # Cache for 15 minutes

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != VALID_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/likers/{tweet_id}")
async def get_tweet_likers(tweet_id: str, next_token: str | None = None, api_key: str = Depends(verify_api_key)):
    """Fetch users who liked the specified tweet, one X API request every 5 minutes, always return cached responses during cooldown."""
    global last_request_time
    cache_key = f"{tweet_id}_{next_token or 'none'}"

    # Return cached response if available
    if cache_key in cache:
        return JSONResponse({
            "likers": cache[cache_key].get("data", []),
            "meta": cache[cache_key].get("meta", {}),
            "next_token": cache[cache_key].get("meta", {}).get("next_token"),
            "cached": True
        })

    # Check throttling
    current_time = time.time()
    time_since_last = current_time - last_request_time
    if time_since_last < REQUEST_INTERVAL:
        wait_time = int(REQUEST_INTERVAL - time_since_last)
        return JSONResponse({
            "likers": [],
            "meta": {"result_count": 0},
            "next_token": None,
            "cached": False,
            "message": f"Please wait {wait_time} seconds for updated data."
        }, status_code=429, headers={"Retry-After": str(wait_time)})

    try:
        params = {
            "user.fields": "id,username,name,profile_image_url",
            "max_results": 100
        }
        if next_token:
            params["pagination_token"] = next_token

        # Make X API request
        last_request_time = current_time
        response = requests.get(
            f"{X_API_URL}/tweets/{tweet_id}/liking_users",
            auth=auth,
            params=params
        )

        # Handle all non-200 responses
        if response.status_code != 200:
            wait_time = int(REQUEST_INTERVAL - (time.time() - last_request_time))
            if wait_time < 0:
                wait_time = REQUEST_INTERVAL
            return JSONResponse({
                "likers": [],
                "meta": {"result_count": 0},
                "next_token": None,
                "cached": False,
                "message": f"Please wait {wait_time} seconds for updated data."
            }, status_code=429, headers={"Retry-After": str(wait_time)})

        data = response.json()
        cache[cache_key] = data  # Update cache
        return JSONResponse({
            "likers": data.get("data", []),
            "meta": data.get("meta", {}),
            "next_token": data.get("meta", {}).get("next_token"),
            "cached": False
        })

    except requests.RequestException as e:
        wait_time = int(REQUEST_INTERVAL - (time.time() - last_request_time))
        if wait_time < 0:
            wait_time = REQUEST_INTERVAL
        return JSONResponse({
            "likers": [],
            "meta": {"result_count": 0},
            "next_token": None,
            "cached": False,
            "message": f"Please wait {wait_time} seconds for updated data."
        }, status_code=429, headers={"Retry-After": str(wait_time)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
