import requests
from typing import Dict, Any

# --- CONSTANTS ---
BASE_URL = "https://fantasy.premierleague.com/api/"
HEADERS = {
    'User-Agent': 'FPL-Project-Starter-Kit',
    'Cache-Control': 'no-cache, no-store, must-revalidate'
}

# --- GETTER FUNCTION ---
def get_fpl_data(endpoint: str) -> Dict[str, Any] | None:
    """
    Fetches data from a specified Fantasy Premier League API endpoint.

    Args:
        endpoint: The specific FPL API endpoint (e.g., 'bootstrap-static/').

    Returns:
        A dictionary containing the JSON response data, or None if the request failed.
    """
    full_url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(full_url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {full_url}: {e}")
        return None


