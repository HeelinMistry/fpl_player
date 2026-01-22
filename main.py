from data_loader.fpl_api import fetch_bootstrap_data, fetch_fixtures, fetch_players, fetch_manager
from data_processing.data_transformer import (create_lookup_maps, get_impacted_player_list, get_player_value_list,
                                              get_available_player_list, get_current_gameweek_info,
                                              process_team_strength_indices, get_all_player_ids, get_remaining_gws,
                                              get_playing_player_list, get_optimized_player_stats, assign_squad_roles,
                                              get_squad_value)
from data_processing.feature_engineering import (calculate_team_historical_features, calculate_team_fixture_features,
                                                 calculate_momentum_scores, prepare_player_optimisation)
from optimization_solvers.solve_squad_optimization import optimize_squad
from optimization_solvers.transfer_optimization import optimise_transfer_strategy
from reporting.result_reporter import (summarize_fpl, report_team_strength_analysis, report_injury_suspension_status,
                                       report_player_value, report_available_players, report_fixture_analysis,
                                       report_historical_fixture_analysis, report_upcoming_fixture_analysis,
                                       report_fixture_ticker, report_player_momentum_windows,
                                       report_playing_player_stats,
                                       report_selected_optimised_squad, report_final_lineup,
                                       report_multi_week_transfers)
from src.fantacy_logger import setup_user_output

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    setup_user_output()
    fpl = fetch_bootstrap_data()
    fpl_fixtures = fetch_fixtures()
    all_player_ids = get_all_player_ids(fpl)
    fpl_players = fetch_players(all_player_ids)

    summarize_fpl(fpl)
    # Pre season start before gw1 ends
    team_scores = process_team_strength_indices(fpl)
    report_team_strength_analysis(team_scores)

    # Bootstrap
    pos_map, team_map = create_lookup_maps(fpl)
    unavailable_player_list = get_impacted_player_list(fpl)
    report_injury_suspension_status(unavailable_player_list, pos_map, team_map)
    available_player_list = get_available_player_list(fpl)
    report_available_players(available_player_list, pos_map, team_map)
    player_value_list = get_player_value_list(fpl)
    report_player_value(player_value_list, pos_map, team_map)
    # key stats filtered

    # Fixtures
    current_gw = get_current_gameweek_info(fpl)
    remaining_gw = get_remaining_gws(fpl)
    report_fixture_analysis(current_gw, fpl_fixtures, team_map)
    historical_fixtures = calculate_team_historical_features(fpl_fixtures, team_map)
    report_historical_fixture_analysis(historical_fixtures, team_map)
    upcoming_fixtures = calculate_team_fixture_features(current_gw, fpl_fixtures, team_scores, team_map)
    report_upcoming_fixture_analysis(upcoming_fixtures, team_map)
    report_fixture_ticker(upcoming_fixtures, team_map, remaining_gw)
    report_fixture_ticker(upcoming_fixtures, team_map, 3)


    # Players
    MOMENTUM_WINDOWS = [3]
    playing_player_list = get_playing_player_list(fpl)
    report_playing_player_stats(playing_player_list, pos_map, team_map)
    player_momentum = calculate_momentum_scores(fpl_players, MOMENTUM_WINDOWS)
    report_player_momentum_windows(player_momentum, team_map)

    optimised_player_list = get_optimized_player_stats(playing_player_list, player_momentum, MOMENTUM_WINDOWS)
    report_playing_player_stats(optimised_player_list, pos_map, team_map)
    optimised_player_list = prepare_player_optimisation(player_momentum, MOMENTUM_WINDOWS, upcoming_fixtures, fpl)
    report_playing_player_stats(optimised_player_list, pos_map, team_map)


    FDR_WEIGHTING = 0.001
    next_gw_id = current_gw['id'] + 1
    selected_squad = optimize_squad(optimised_player_list)
    report_selected_optimised_squad(selected_squad, fpl)
    starters, bench, captain, vice_captain = assign_squad_roles(selected_squad)
    report_final_lineup(starters, bench, captain, vice_captain, fpl, next_gw_id)

    suggested_squad = list()
    for player in starters:
        suggested_squad.append(player['id'])
    for player in bench:
        suggested_squad.append(player['id'])
    future_gws = list(range(next_gw_id, next_gw_id + 5))
    # future_gws = list(range(next_gw_id, next_gw_id + remaining_gw))

    # squad_value = get_squad_value(selected_squad)
    # money_itb = 100 - squad_value
    # plan = optimise_transfer_strategy(selected_squad, optimised_player_list, future_gws, money_itb)
    # report_multi_week_transfers(plan, fpl)

    MANAGER_ID = 12788203
    print(f'Manager: {MANAGER_ID}')
    initial_squad_ids, money_itb, total_team_value, initial_fts = fetch_manager(MANAGER_ID, current_gw['id'])
    player_lookup = {p['id']: p for p in optimised_player_list}
    manager_starting_xi = [player_lookup[pid] for pid in initial_squad_ids if pid in player_lookup]
    report_selected_optimised_squad(manager_starting_xi, fpl)
    managers_plan = optimise_transfer_strategy(manager_starting_xi, optimised_player_list, money_itb, transfers_available=1)
    report_multi_week_transfers(managers_plan, fpl)

    updated_ids_set = set(initial_squad_ids) - set(managers_plan['out'])
    updated_ids_set.update(managers_plan['in'])
    new_squad_ids = list(updated_ids_set)
    next_starting_xi = [player_lookup[pid] for pid in new_squad_ids if pid in player_lookup]

    starters, bench, captain, vice_captain = assign_squad_roles(next_starting_xi)
    report_selected_optimised_squad(next_starting_xi, fpl)
    report_final_lineup(starters, bench, captain, vice_captain, fpl, next_gw_id)
