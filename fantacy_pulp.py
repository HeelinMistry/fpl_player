# This is a sample Python script.
import json
import os

import pulp

from src.fantacy_analysis import *
from src.fantacy_api import get_fpl_data


def format_optimal_squad_report(optimal_squad: List[Dict[str, Any]], total_matr_score: float, total_cost: float):
    """Prints the final optimal squad in a clean, categorized format."""

    # Define position mapping for display
    POS_MAP = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}

    # Sort the squad by position, then by MATR score within each position
    optimal_squad.sort(key=lambda x: (x['pos'], x['matr']), reverse=True)

    print("\n" + "=" * 80)
    print("🏆 OPTIMAL 15-PLAYER SQUAD SELECTED BY PuLP")
    print(f"MAXIMUM MATR Score (GW6): {total_matr_score:.4f}")
    print(f"TOTAL BUDGET USED: £{total_cost:.1f}M")
    print("=" * 80)

    # Table Header
    print("{:<5} {:<15} {:<5} {:<8} {:<10} {:<10}".format(
        "POS", "Player Name", "Team", "Price", "MATR (GW6)", "ID"
    ))
    print("-" * 80)

    current_pos = None

    # Print Players
    for player in optimal_squad:
        if player['pos'] != current_pos:
            current_pos = player['pos']
            print(
                f"\n--- {POS_MAP.get(current_pos)} ({len([p for p in optimal_squad if p['pos'] == current_pos])} Selected) ---")

        print("{:<5} {:<15} {:<5} £{:<6.1f} {:<10.4f} {:<10}".format(
            POS_MAP.get(player['pos']),
            player['name'],
            player['team_name'][:5],  # Truncate team name for display
            player['price'],
            player['matr'],
            player['id']
        ))
    print("-" * 80)

    # Sanity check on the number of players selected
    print(f"\nTotal Players Selected: {len(optimal_squad)}")

    # Team Limit Check (Optional, but good for diagnostics)
    team_counts = {}
    for player in optimal_squad:
        team = player['team_name']
        team_counts[team] = team_counts.get(team, 0) + 1

    print("\nTeam Count Summary:")
    for team, count in sorted(team_counts.items(), key=lambda item: item[1], reverse=True):
        print(f"  {team:<15}: {count}")

def run_pulp_optimization(player_data_dict: Dict[int, Dict[str, Any]], budget_cap: int = 100):
    """
    Finds the optimal 15-player squad maximizing MATR score within FPL constraints.
    """

    player_ids = list(player_data_dict.keys())

    # 1. Initialize the LP Problem
    prob = pulp.LpProblem("FPL Squad Optimization", pulp.LpMaximize)

    # 2. Define Decision Variables
    # The variable keys are now the Player IDs
    player_vars = pulp.LpVariable.dicts("Select", player_ids, 0, 1, pulp.LpBinary)

    # 3. Define the Objective Function
    # Use player_ids for iteration
    prob += pulp.lpSum([player_data_dict[i]['matr'] * player_vars[i] for i in player_ids]), "Total_MATR_Score"

    # 4. Define Constraints

    # A. Squad Size Constraint (Total players must be 15)
    prob += pulp.lpSum([player_vars[i] for i in player_ids]) == 15, "Squad_Size_Constraint"

    # B. Budget Constraint
    prob += pulp.lpSum(
        [player_data_dict[i]['price'] * player_vars[i] for i in player_ids]) <= budget_cap, "Budget_Constraint"

    # C. Positional Constraints
    POSITION_LIMITS = {1: 2, 2: 5, 3: 5, 4: 3}
    for pos_id, limit in POSITION_LIMITS.items():
        # Iterate through players whose position matches the pos_id
        prob += pulp.lpSum([
            player_vars[i] for i in player_ids
            if player_data_dict[i]['pos'] == pos_id
        ]) == limit, f"Position_Constraint_{pos_id}"

    # D. Team Limit Constraint
    team_ids = {d['team_id'] for d in player_data_dict.values()}
    for team_id in team_ids:
        # Iterate through players whose team_id matches the current team_id
        prob += pulp.lpSum([
            player_vars[i] for i in player_ids
            if player_data_dict[i]['team_id'] == team_id
        ]) <= 3, f"Team_Limit_Constraint_{team_id}"

    # 5. Solve the problem
    prob.solve()

    # 6. Extract Results
    if prob.status == pulp.LpStatusOptimal:
        optimal_squad = []
        for i in player_ids:
            if player_vars[i].varValue == 1.0:
                optimal_squad.append(player_data_dict[i])

        total_cost = pulp.value(prob.objective)  # The objective function value (total MATR score)

        return {
            "status": pulp.LpStatus[prob.status],
            "total_matr_score": total_cost,
            "squad": optimal_squad
        }
    else:
        return {"status": pulp.LpStatus[prob.status], "squad": []}


def prepare_optimization_data(adjusted_rating: List[Dict[str, Any]], bootstrap_data: Dict[str, Any]):
    """Extracts and maps necessary data for the PuLP model, keyed by player ID."""

    elements = bootstrap_data.get('elements', [])
    team_map = {t['id']: t['name'] for t in bootstrap_data.get('teams', [])}

    # 🌟 FIX 1: Create a reliable map from Player ID to Team ID
    # This ensures we use the correct team ID stored in the FPL data for that player.
    player_to_team_id = {p['id']: p['team'] for p in elements}

    player_data_dict: Dict[int, Dict[str, Any]] = {}

    for p in adjusted_rating:
        player_id = p.get('id')
        if not player_id: continue

        team_id = player_to_team_id.get(player_id)

        # Ensure player has essential data before adding
        if team_id is None:
            continue

        player_data_dict[player_id] = {
            'name': p['player_name'],
            'id': player_id,
            'pos': p['element_type_id'],
            'team_id': team_id,  # Use the correctly looked-up ID
            'team_name': team_map.get(team_id),  # Use the correct team name from the map
            'price': p['current_price'],
            'matr': p.get('matr_score_gw6', 0.0)
        }

    # Sanity check is crucial here
    print(f"DEBUG: Total players successfully prepared for PuLP: {len(player_data_dict)}")

    return player_data_dict

PLAYER_DIR = 'player_history_dumps'
FDR_WINDOW = 3
def calculate_matr(fpl_data, fixtures_data) -> list[dict[str, Any]] | None:
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
        return calculate_multi_window_matr(player_momentum, fixture_run_score, fpl_data)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    fpl_endpoint = "bootstrap-static/"
    # 2. Get the data
    fpl_data = get_fpl_data(fpl_endpoint)
    view_fpl_data_summary(fpl_data)
    if not fpl_data:
        print("Failed to load core FPL data. Cannot continue.")
    else:
        next_gw_info = get_next_gameweek_info(fpl_data)
        if not next_gw_info:
            print("Could not identify the next gameweek. It might be the end of the season.")
        else:
            gw_id = next_gw_info['id']
            print(f"✅ Next Gameweek Identified: **Gameweek {gw_id}**")
            # 2. Second Call: Get Fixtures for the specific GW ID
            fixtures_endpoint = f"fixtures/?event={gw_id}"
            fixtures_data = get_fpl_data(fixtures_endpoint)

            if fixtures_data:
                matr_rating = calculate_matr(fpl_data, fixtures_data)
                cleaned_data = prepare_optimization_data(matr_rating, fpl_data)
                optimization_result = run_pulp_optimization(cleaned_data)
                if optimization_result['status'] == 'Optimal':
                    print("\n" + "=" * 50)
                    print("🏆 OPTIMAL 15-PLAYER SQUAD SELECTED BY PuLP")
                    print(f"Total Optimal MATR Score (GW6): {optimization_result['total_matr_score']:.4f}")
                    print(f"Total Budget Used: {sum(p['price'] for p in optimization_result['squad']):.1f}M")
                    print("=" * 50)

                    optimal_squad = optimization_result['squad']
                    total_matr_score = optimization_result['total_matr_score']

                    # Calculate the exact cost of the selected squad
                    total_cost_used = sum(p['price'] for p in optimal_squad)

                    # Call the new formatting function
                    format_optimal_squad_report(optimal_squad, total_matr_score, total_cost_used)
                    # You would then format and print the list of players by position.
                else:
                    print(f"Optimization failed. Status: {optimization_result['status']}")
            else:
                print("Failed to load fixtures data.")

