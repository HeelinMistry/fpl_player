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
    else:
        print(f"Current Gameweek determined: {current_gw['id']}")

        fixture_run_score = calculate_fixture_run_score(fixtures_data, fpl_data, current_gw['id'], FDR_WINDOW)
        available_player_ids = get_available_player_ids(fpl_data)
        print(f"Found {len(available_player_ids)} relevant player IDs for history fetching.")
        ids_to_fetch = list(available_player_ids)
        print(f"Fetching history for {len(ids_to_fetch)} players...")

        player_history_data: Dict[int, List[Dict[str, Any]]] = {}

        for player_id in ids_to_fetch:
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
                file_path = os.path.join(PLAYER_DIR, f'fpl_{player_id}_data.json')
                try:
                    with open(file_path, 'w') as f:
                        json.dump(player_summary, f, indent=4)
                    # print(f"Player data saved to {file_path}")
                except IOError as e:
                    print(f"Error saving file for player {player_id}: {e}")
                player_history_data[player_id] = player_summary['history']
        print(f"Successfully fetched history for {len(player_history_data)} players.")

        player_momentum = calculate_momentum_scores(player_history_data, current_gw['id'])
        adjusted_rating = calculate_multi_window_matr(player_momentum, fixture_run_score, fpl_data)
        generate_positional_matr_reports(adjusted_rating, fpl_data, FDR_WINDOW)
        over_under_score = calculate_multi_window_over_under_achiever_score(adjusted_rating)
        generate_over_under_reports(over_under_score, fdr_window=FDR_WINDOW)

def print_core():
    fpl_endpoint = "bootstrap-static/"
    fpl_data = get_fpl_data(fpl_endpoint)
    if fpl_data:
        with open('fpl_bootstrap_data.json', 'w') as f:
            json.dump(fpl_data, f, indent=4)
        print("\nFull data saved to fpl_bootstrap_data.json")
    if not fpl_data:
        print("Failed to load core FPL data. Cannot continue.")
    else:
        view_fpl_data_summary(fpl_data)
        generate_injury_report(fpl_data)
        generate_team_strength_report(fpl_data, sort_by='FPL_POINTS')
        generate_team_strength_report(fpl_data, sort_by='ATTACK')
        generate_team_strength_report(fpl_data, sort_by='FDR_DEF')

        next_gw_info = get_next_gameweek_info(fpl_data)
        if not next_gw_info:
            print("Could not identify the next gameweek. It might be the end of the season.")
        else:
            gw_id = next_gw_info['id']
            gw_deadline = next_gw_info['deadline_time']

            print(f"✅ Next Gameweek Identified: **Gameweek {gw_id}**")
            print(f"   Transfer Deadline: **{gw_deadline} (UTC)**")

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
                print(f"\nData saved to {cache_fixture_filename}")

            if fixtures_data:
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

