# This is a sample Python script.
import json
import os

from src.fantacy_analysis import *
from src.fantacy_api import get_fpl_data
from src.fantacy_logger import setup_user_output

PLAYER_DIR = 'player_history_dumps'
FDR_WINDOW = 5
def print_matr(fpl_data, fixtures_data):
    current_gw = get_current_gameweek_info(fpl_data)

    if current_gw is None:
        print("FATAL ERROR: Could not determine the current Gameweek. Cannot proceed.")
        # Handle error or use a safe fallback GW ID
    else:
        print(f"Current Gameweek determined: {current_gw['id']}")

        fixture_run_score = calculate_fixture_run_score(fixtures_data, fpl_data, current_gw['id'], FDR_WINDOW)
        available_player_ids = get_available_player_ids(fpl_data)
        print(f"Found {len(available_player_ids)} relevant player IDs for history fetching.")

        # Prepare to store the history data
        player_history_data: Dict[int, List[Dict[str, Any]]] = {}

        # Using a subset of IDs for demonstration/API safety if the full list is huge
        ids_to_fetch = list(available_player_ids)
        print(f"Fetching history for {len(ids_to_fetch)} players...")

        for player_id in ids_to_fetch:
            history_endpoint = f"element-summary/{player_id}/"
            player_summary = get_fpl_data(history_endpoint)

            if player_summary and 'history' in player_summary:
                file_path = os.path.join(PLAYER_DIR, f'fpl_{player_id}_data.json')
                try:
                    with open(file_path, 'w') as f:
                        json.dump(player_summary, f, indent=4)
                    # print(f"Player data saved to {file_path}")
                except IOError as e:
                    print(f"Error saving file for player {player_id}: {e}")
                # Store only the 'history' part which contains GW-by-GW data
                player_history_data[player_id] = player_summary['history']

        print(f"Successfully fetched history for {len(player_history_data)} players.")

        player_momentum = calculate_momentum_scores(player_history_data, current_gw['id'])
        # adjusted_rating = calculate_momentum_adjusted_rating(player_momentum, fixture_run_score, fpl_data, PRIMARY_MATR_WINDOW)
        adjusted_rating = calculate_multi_window_matr(player_momentum, fixture_run_score, fpl_data)
        generate_positional_matr_reports(adjusted_rating, fpl_data, FDR_WINDOW)
        over_under_score = calculate_multi_window_over_under_achiever_score(adjusted_rating)
        generate_over_under_reports(over_under_score, fdr_window=FDR_WINDOW)

def print_momentum(fpl_data):
    if not os.path.exists(PLAYER_DIR):
        os.makedirs(PLAYER_DIR)
        print(f"Created directory: {PLAYER_DIR}")
    relevant_ids = get_relevant_player_ids(fpl_data)

    # Output the IDs found
    print(f"Found {len(relevant_ids)} relevant player IDs for history fetching.")

    # --- STEP 2: FETCH HISTORY FOR EACH ID ---

    # We need the current Gameweek to ensure our momentum windows are correct
    events_data = fpl_data['events']
    current_gw = next((event['id'] for event in events_data if event['is_current']), None)

    if not current_gw:
        print("Could not determine current Gameweek. Aborting history fetch.")
        relevant_ids = set()  # Clear IDs to stop the next step

    # Prepare to store the history data
    player_history_data: Dict[int, List[Dict[str, Any]]] = {}

    # Using a subset of IDs for demonstration/API safety if the full list is huge
    ids_to_fetch = list(relevant_ids)
    print(f"Fetching history for {len(ids_to_fetch)} players...")

    for player_id in ids_to_fetch:
        history_endpoint = f"element-summary/{player_id}/"
        player_summary = get_fpl_data(history_endpoint)

        if player_summary and 'history' in player_summary:
            file_path = os.path.join(PLAYER_DIR, f'fpl_{player_id}_data.json')
            try:
                with open(file_path, 'w') as f:
                    json.dump(player_summary, f, indent=4)
                # print(f"Player data saved to {file_path}")
            except IOError as e:
                print(f"Error saving file for player {player_id}: {e}")
            # Store only the 'history' part which contains GW-by-GW data
            player_history_data[player_id] = player_summary['history']

    print(f"Successfully fetched history for {len(player_history_data)} players.")

    player_momentum = calculate_momentum_scores(player_history_data, current_gw)
    TOP_N = 3  # We choose the top 3 players' PPM to define the team's momentum score

    for window in MOMENTUM_WINDOWS:
        team_momentum_report = aggregate_team_momentum(
            player_momentum,
            fpl_data,
            num_assets=TOP_N,
            window=window
        )
        generate_momentum_report(team_momentum_report, window, TOP_N)

    # 5. Show Top Player Momentum (The individual component)

    # Filter for players who played in the last 6 GWs and sort by GW6 PPM
    top_individual_momentum = sorted(
        [p for p in player_momentum.values() if p.get('GW6_Games', 0) > 0],
        key=lambda p: p.get('GW6_PPM', 0.0),
        reverse=True
    )[:15]

    print("\n--- ⭐ Top 15 Individual Player Momentum (Last 6 GWs) ---")
    print("-" * 65)
    print("{:<15} {:<5} {:<8} {:<8} {:<8} {:<8}".format(
        "Player", "Team", "GW3 PPM", "GW6 PPM", "GW9 PPM", "Total Pts"
    ))
    print("-" * 65)

    # Create a reverse lookup for names from player ID
    player_names = {p['id']: p['web_name'] for p in fpl_data.get('elements', [])}
    team_short_names = {t['id']: t['short_name'] for t in fpl_data.get('teams', [])}
    player_team_map = {p['id']: p['team'] for p in fpl_data.get('elements', [])}

    for p_data in top_individual_momentum:
        player_id = p_data['id']
        team_id = player_team_map.get(player_id)

        # Fetch total season points from bootstrap data (or estimate)
        try:
            total_pts = next(p['total_points'] for p in fpl_data['elements'] if p['id'] == player_id)
        except StopIteration:
            total_pts = "N/A"

        print("{:<15} {:<5} {:<8.2f} {:<8.2f} {:<8.2f} {:<8}".format(
            player_names.get(player_id, f"ID {player_id}"),
            team_short_names.get(team_id, "UNK"),
            p_data.get('GW3_PPM', 0.0),
            p_data.get('GW6_PPM', 0.0),
            p_data.get('GW9_PPM', 0.0),
            total_pts
        ))
    print("-" * 65)


def print_core():
    # 1. Define the endpoint to use
    fpl_endpoint = "bootstrap-static/"

    # 2. Get the data
    fpl_data = get_fpl_data(fpl_endpoint)
    view_fpl_data_summary(fpl_data)

    # You can now save 'fpl_data' to a file for deeper analysis
    if fpl_data:
        with open('fpl_bootstrap_data.json', 'w') as f:
            json.dump(fpl_data, f, indent=4)
        print("\nFull data saved to fpl_bootstrap_data.json")

    if not fpl_data:
        print("Failed to load core FPL data. Cannot continue.")
    else:
        generate_injury_report(fpl_data)
        generate_team_strength_report(fpl_data, sort_by='FPL_POINTS')
        generate_team_strength_report(fpl_data, sort_by='ATTACK')
        generate_team_strength_report(fpl_data, sort_by='FDR_DEF')

        # print_momentum(fpl_data)


        next_gw_info = get_next_gameweek_info(fpl_data)
        if not next_gw_info:
            print("Could not identify the next gameweek. It might be the end of the season.")
        else:
            gw_id = next_gw_info['id']
            gw_deadline = next_gw_info['deadline_time']

            print(f"✅ Next Gameweek Identified: **Gameweek {gw_id}**")
            print(f"   Transfer Deadline: **{gw_deadline} (UTC)**")

            # 2. Second Call: Get Fixtures for the specific GW ID
            fixtures_endpoint = f"fixtures/?event={gw_id}"
            fixtures_data = get_fpl_data(fixtures_endpoint)

            if fixtures_data:
                with open('fpl_fixture_data.json', 'w') as f:
                    json.dump(fixtures_data, f, indent=4)
                print("\nData saved to fpl_fixture_data.json")

                teams_data = fpl_data['teams']
                view_gameweek_fixtures(gw_id, fixtures_data, teams_data)
                playing_team_ids = get_next_gw_teams(fpl_data, fixtures_data)
                get_key_player_stats_filtered(fpl_data, playing_team_ids, top_n=25)
                get_value_players_next_gw(fpl_data, playing_team_ids, top_n=25)

                print_matr(fpl_data, fixtures_data)
            else:
                print("Failed to load fixtures data.")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    setup_user_output()
    print_core()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
