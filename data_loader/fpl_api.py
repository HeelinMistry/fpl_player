import json
import os
from typing import Dict, Any, List, Optional, Set

import requests

# --- CONSTANTS ---
BASE_URL = "https://fantasy.premierleague.com/api/"
PLAYER_DIR = 'player_history_dumps'
HEADERS = {
    'User-Agent': 'FPL-Player-Kit',
    'Cache-Control': 'no-cache, no-store, must-revalidate'
}

# --- MAIN GETTER FUNCTION ---
def get_fpl_data(endpoint: str) -> Optional[Dict[str, Any]]:
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

# -------------------------------------------------------------------

# --- ENDPOINTS ---
def fetch_bootstrap_data() -> Dict[str, Any]:
    """
    Fetches the bootstrap-static data (players, teams, gameweeks).
    :rtype: Dict[str, Any]
    """
    print("-> Fetching FPL bootstrap-static data...")
    cache_bootstrap_filename = 'fpl_bootstrap_data.json'
    fpl_data = None
    if os.path.exists(cache_bootstrap_filename):
        with open(cache_bootstrap_filename, 'r') as f:
            fpl_data = json.load(f)
            print(f"✅ Data loaded successfully from local cache: {cache_bootstrap_filename}")
    if fpl_data is None:
        fpl_endpoint = "bootstrap-static/"
        fpl_data = get_fpl_data(fpl_endpoint)
        with open(cache_bootstrap_filename, 'w') as f:
            json.dump(fpl_data, f, indent=4)
        print(f"\nData saved to {cache_bootstrap_filename}")
    return fpl_data if fpl_data else {}


def fetch_fixtures() -> List[Dict[str, Any]]:
    """
    Fetches the full list of all fixtures for the season.
    """
    print("-> Fetching FPL fixtures data...")
    fixtures_data = None
    cache_fixture_filename = 'fpl_fixture_data.json'
    if os.path.exists(cache_fixture_filename):
        with open(cache_fixture_filename, 'r') as f:
            fixtures_data = json.load(f)
            print(f"✅ Data loaded successfully from local cache: {cache_fixture_filename}")
    if fixtures_data is None:
        fixtures_endpoint = "fixtures"
        fixtures_data = get_fpl_data(fixtures_endpoint)
        with open(cache_fixture_filename, 'w') as f:
            json.dump(fixtures_data, f, indent=4)
        print(f"\nFixtures saved to {cache_fixture_filename}")
    return fixtures_data if fixtures_data else []

def fetch_players(player_ids: Set[int]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Fetches the full list of all fixtures for the season.
    """
    print("-> Fetching FPL player data...")
    player_history_data: Dict[int, List[Dict[str, Any]]] = {}

    for player_id in player_ids:
        cache_player_filename = f'fpl_player_{player_id}_data.json'
        player_summary = None
        file_path = os.path.join(PLAYER_DIR, cache_player_filename)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                player_summary = json.load(f)
                print(f"✅ Data loaded successfully from local cache: {file_path}")
        if player_summary is None:
            history_endpoint = f"element-summary/{player_id}/"
            player_summary = get_fpl_data(history_endpoint)
            with open(file_path, 'w') as f:
                json.dump(player_summary, f, indent=4)
            print(f"\nData saved to {file_path}")

        if player_summary and 'history' in player_summary:
            player_history_data[player_id] = player_summary['history']

    print(f"Successfully fetched history for {len(player_history_data)} players.")
    return player_history_data

def fetch_manager(manager_id: int, current_gw: int) -> tuple[list[int], float, float, int]:
    cache_filename = f'fpl_manager_{manager_id}_data.json'
    manager_starting_xi = None

    if os.path.exists(cache_filename):
        with open(cache_filename, 'r') as f:
            manager_starting_xi = json.load(f)
            print(f"✅ Data loaded successfully from local cache: {cache_filename}")

    if manager_starting_xi is None:
        picks_url = f"entry/{manager_id}/event/{current_gw}/picks/"
        manager_starting_xi = get_fpl_data(picks_url)

        with open(cache_filename, 'w') as f:
            json.dump(manager_starting_xi, f, indent=4)
        print(f"\nData saved to {cache_filename}")

    entry_history = manager_starting_xi.get('entry_history', {})
    money_itb = entry_history.get('bank', 0) / 10
    total_value = entry_history.get('value', 0) / 10
    total_team_value = total_value - money_itb

    squad_ids = [pick['element'] for pick in manager_starting_xi.get('picks', [])]

    free_transfers = 1  # Replace with actual logic

    return squad_ids, money_itb, total_team_value, free_transfers