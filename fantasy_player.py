from fantacy_pulp import *
from src.fantacy_analysis import *
from src.fantacy_analysis import get_available_player_ids
from src.fantacy_api import get_fpl_data

MANAGER_ID = 79432

def get_initial_squad_from_fpl(manager_id: int, current_gw: int) -> tuple[list[int], float, float, int]:
    cache_filename = 'fpl_manager_xi_data.json'
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

# --- MGO CONFIGURATION ---
FDR_LKFWD = 5
HIT_COST = 4.0
MAX_BUDGET = 100.0
POS_LIMITS = {1: 2, 2: 5, 3: 5, 4: 3}  # Max squad limits (1=GKP, 2=DEF, 3=MID, 4=FWD)
FORMATION_MIN = {1: 1, 2: 3, 3: 2, 4: 1}  # Min starting XI (1 GKP, 3 DEF, 2 MID, 1 FWD)
FORMATION_MAX = {1: 1, 2: 5, 3: 5, 4: 3}  # Max starting XI (1 GKP, 5 DEF, 5 MID, 3 FWD)
if __name__ == '__main__':
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

    current_gw = get_current_gameweek_info(fpl_data)
    initial_squad_ids, money_itb, total_team_value, initial_fts = get_initial_squad_from_fpl(MANAGER_ID, current_gw['id'])

    if not current_gw:
        print("Could not identify the next gameweek. It might be the end of the season.")
    else:
        gw_id = current_gw['id']
        print(f"✅ Next Gameweek Identified: **Gameweek {gw_id}**")

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

        all_player_ids = get_all_player_ids(fpl_data)
        matr_rating = calculate_matr(fpl_data, fixtures_data, all_player_ids)
        adjusted_matr_rating = calculate_s_matr_score(matr_rating)
        optimised_player_data = prepare_optimization_data(adjusted_matr_rating, fpl_data)

        print(f"\n--- ✅ GW{gw_id} Optimal Squad Selected. Moving to MGO... ---")
        print(f"\n--- {initial_squad_ids} ---")

        initial_gw_s_matr_scores = {}
        for p in adjusted_matr_rating:
            # Key is (player_id, gw_id)
            initial_gw_s_matr_scores[(p['id'], gw_id)] = p['s_matr_score']

        all_gws = list(range(gw_id, gw_id + (FDR_LKFWD + 1)))
        gws_to_forecast = list(range(gw_id + 1, gw_id + (FDR_LKFWD + 1)))

        # Then call the forecast function:
        mgo_forecasted_scores = forecast_s_matr_for_mgo(fpl_data, fixtures_data, matr_rating, gws_to_forecast)

        # D. Combine GW1 and Forecasted Scores
        mgo_scores = {**initial_gw_s_matr_scores, **mgo_forecasted_scores}

        # B. Prepare Utility Data for Constraints
        player_costs, player_positions, player_teams, all_team_ids = prepare_mgo_utility_data(fpl_data)

        scored_player_ids = {p_id for p_id, gw_t in mgo_scores.keys()}
        available_player_ids = get_available_player_ids(fpl_data)
        high_value_targets = scored_player_ids.intersection(available_player_ids)
        owned_players = set(initial_squad_ids)
        MGO_PLAYERS_FINAL = high_value_targets.union(owned_players)

        # C. Run MGO
        mgo_problem = solve_multi_gameweek_optimization(
            all_gws=all_gws,
            all_player_ids=list(MGO_PLAYERS_FINAL),
            initial_squad_ids=initial_squad_ids,
            player_scores_matr=mgo_scores,
            player_costs=player_costs,
            player_positions=player_positions,
            player_teams=player_teams,
            all_team_ids=all_team_ids,
            initial_money_itb=money_itb,
            initial_team_value=total_team_value,
            initial_fts=initial_fts
        )

        # D. Solve MGO
        mgo_problem.solve()

        print(f"\n--- 🏆 MGO Solution Status: {LpStatus[mgo_problem.status]} ---")
        if LpStatus[mgo_problem.status] == 'Optimal':
            report_mgo_strategy(
                problem=mgo_problem,
                mgo_gw_ids=all_gws,
                optimised_player_data=optimised_player_data,
                mgo_scores=mgo_scores,
            )
        else:
            print("MGO failed to find an optimal solution.")

        mgo_scores = forecast_s_matr_for_chips(fpl_data, fixtures_data, matr_rating, gws_to_forecast)
        chip_results = evaluate_squad_chip_potential(initial_squad_ids, mgo_scores, gws_to_forecast)
        team_names_map = extract_team_names_map(fpl_data)
        report_chip_optimization_results(chip_results, optimised_player_data, fixtures_data, team_names_map)

