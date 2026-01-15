from typing import Dict, Any, List
from collections import defaultdict


def calculate_team_historical_features(
        fixtures_data: List[Dict[str, Any]],
        team_map: Dict[int, str],
) -> Dict[int, Dict[str, Any]]:
    """
    Processes finished fixtures to calculate team-level features
    (Goals For/Against, Clean Sheet Ratio) over all played matches.
        :param fixtures_data: List of all fixture dictionaries.
        :param team_map: List of all teams
        :return: Dictionary of team-level features
    """
    team_ids = team_map.keys()
    team_stats: Dict[int, Dict[str, Any]] = {
        team_id: defaultdict(lambda: 0) for team_id in team_ids
    }

    # Use lists to store scores per team for easy average calculation later
    team_goals_for = {team_id: [] for team_id in team_ids}
    team_goals_against = {team_id: [] for team_id in team_ids}

    # 1. Aggregate statistics from finished games
    for fixture in fixtures_data:
        if not fixture.get('finished', False):
            continue

        # Home Team Data
        team_h = fixture['team_h']
        score_h = fixture['team_h_score']
        score_a = fixture['team_a_score']
        team_goals_for[team_h].append(score_h)
        team_goals_against[team_h].append(score_a)

        if score_a == 0:
            team_stats[team_h]['clean_sheets'] += 1

        # Away Team Data
        team_a = fixture['team_a']
        team_goals_for[team_a].append(score_a)
        team_goals_against[team_a].append(score_h)

        if score_h == 0:
            team_stats[team_a]['clean_sheets'] += 1

    # 2. Calculate Averages and Probabilities
    for team_id in team_ids:
        played = len(team_goals_for[team_id])

        if played == 0:
            continue

        total_goals_for = sum(team_goals_for[team_id])
        total_goals_against = sum(team_goals_against[team_id])

        gsa = total_goals_for / played
        gca = total_goals_against / played
        csp = team_stats[team_id]['clean_sheets'] / played

        # Store the calculated features
        team_stats[team_id]['played'] = played
        team_stats[team_id]['GSA'] = round(gsa, 2)
        team_stats[team_id]['GCA'] = round(gca, 2)
        team_stats[team_id]['CSP'] = round(csp * 100, 2)  # Stored as percentage

    return team_stats

def calculate_team_fixture_features(
        current_gw_info: Dict[str, Any],
        fixtures_data: List[Dict[str, Any]],
        team_scores: Dict[int, Dict[str, float]],
        team_map: Dict[int, str]
)-> Dict[int, List[Dict[str, Any]]]:

    current_gw = current_gw_info['id']
    start_gw = current_gw + 1
    end_gw = fixtures_data[-1]['event']
    upcoming_fixtures_ticker = defaultdict(list)

    for fixture in fixtures_data:
        gw_id = fixture.get('event')

        if fixture.get('finished', True) or not gw_id or not (start_gw <= gw_id <= end_gw):
            continue

        team_h = fixture['team_h']
        team_a = fixture['team_a']

        # Opponent ID and Home/Away Status for Team H
        opp_a_id = team_a
        opp_a_short = team_map.get(opp_a_id, '???')

        # Opponent ID and Home/Away Status for Team A
        opp_h_id = team_h
        opp_h_short = team_map.get(opp_h_id, '???')

        # Fixture details for the Home Team (team_h)
        upcoming_fixtures_ticker[team_h].append({
            'gw': gw_id,
            'opponent': opp_a_short,
            'location': 'H',
            'fdr': fixture['team_h_difficulty'],
            'home_attack': team_scores[opp_h_id]['strength_attack_home'],
            'home_defence': team_scores[opp_h_id]['strength_defence_home'],
            'away_attack': team_scores[opp_a_id]['strength_attack_away'],
            'away_defence': team_scores[opp_a_id]['strength_defence_away'],
        })

        # Fixture details for the Away Team (team_a)
        upcoming_fixtures_ticker[team_a].append({
            'gw': gw_id,
            'opponent': opp_h_short,
            'location': 'A',
            'fdr': fixture['team_a_difficulty'],
            'home_attack': team_scores[opp_h_id]['strength_attack_home'],
            'home_defence': team_scores[opp_h_id]['strength_defence_home'],
            'away_attack': team_scores[opp_a_id]['strength_attack_away'],
            'away_defence': team_scores[opp_a_id]['strength_defence_away'],
        })
    return upcoming_fixtures_ticker

# Player enhancement

# can adjust it will average it out and use rppm
MOMENTUM_WINDOWS = [3]
def calculate_momentum_scores(player_history_data: Dict[int, List[Dict[str, Any]]]) -> Dict[int, Dict[str, float | int]]:
    """
    Calculates Points Per 90 Minutes (PP90M) for individual players over defined windows,
    using minutes played for a more accurate efficiency measure.
    """
    player_momentum: Dict[int, Dict[str, float | int]] = {}
    for player_id, history in player_history_data.items():
        player_momentum[player_id] = {'id': player_id}
        finished_history = [h for h in history if h.get('finished', True)]
        if not finished_history:
            continue
        for window in MOMENTUM_WINDOWS:
            # Select the most recent 'window' number of finished gameweeks
            recent_history = finished_history[-window:]
            # New: Sum total minutes and total points
            total_minutes = sum(h.get('minutes', 0) for h in recent_history)
            total_points = sum(h.get('total_points', 0) for h in recent_history)

            # Count games played (useful for diagnostics)
            games_played = sum(1 for h in recent_history if h.get('minutes', 0) > 0)

            # --- CORRECTED PP90M LOGIC ---
            if total_minutes > 0:
                # Calculate PP90M: (Total Points / Total Minutes) * 90
                # This correctly accounts for players who play < 90 minutes across the window.
                minutes_played = window * 90
                pp90m_score = total_points * (total_minutes/minutes_played)
            else:
                # If total_minutes is 0 (player was absent/not in the squad), set score to 0.
                pp90m_score = 0.0
            # Update the dictionary keys to reflect the PP90M calculation
            player_momentum[player_id][f'GW{window}_PP90M'] = round(pp90m_score, 2)
            player_momentum[player_id][f'GW{window}_Pts'] = total_points
            player_momentum[player_id][f'GW{window}_Games'] = games_played
            player_momentum[player_id][f'GW{window}_Mins'] = total_minutes  # New: Track total minutes

    return player_momentum


def prepare_player_optimisation(player_momentum: Dict[int, Dict[str, float | int]],
                                fixture_run_score: dict[int, list[dict[str, Any]]],
                                bootstrap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Calculates all defined MOMENTUM_WINDOWS and combines the results.
    """
    player_elements = {p['id']: p for p in bootstrap_data.get('elements', [])}

    # Start with a report based on player info, adding momentum metrics later
    master_report: Dict[int, Dict[str, Any]] = {}

    for player_id, p_momentum in player_momentum.items():
        player_info = player_elements.get(player_id, {})
        team_id = player_info.get('team')
        if not team_id: continue
        fixture_summary = dict()
        for fixture in fixture_run_score[team_id]:
            if fixture['location'] == 'A':
                away_strength = fixture['away_attack'] + fixture['away_defence']
                home_strength = fixture['home_attack'] + fixture['home_defence']
                team_diff = away_strength - home_strength
            else:
                away_strength = fixture['away_attack'] + fixture['away_defence']
                home_strength = fixture['home_attack'] + fixture['home_defence']
                team_diff = home_strength - away_strength
            fixture_summary[fixture['gw']] = team_diff
        # Initialize the player's entry in the master report
        if player_id not in master_report:
            master_report[player_id] = {
                'id': player_id,
                'team_id': team_id,
                'position_id': player_info.get('element_type'),
                'status': player_info.get('status'),
                'fixture_comparison': fixture_summary,
                'price': player_info.get('now_cost', 0) / 10.0  # Add price for over/under calc later
            }

        rppm = 0.0
        rppm_report_key = f'rppm'
        for window in MOMENTUM_WINDOWS:
            ppm_key_from_momentum = f'GW{window}_PP90M'  # e.g., 'GW6_PP90M'
            player_ppm = p_momentum[ppm_key_from_momentum]

            # Calculate MATR for this window
            # matr_score = player_ppm / (team_fdr_score + 0.1)
            rppm += player_ppm

            # Store the PPM and MATR for this specific window
            # master_report[player_id][ppm_report_key] = round(player_ppm, 2)
        master_report[player_id][rppm_report_key] = round(rppm, 4)
    # Convert the dictionary back to a list of reports and sort by the GW6 score (as a default primary)
    final_report_list = list(master_report.values())

    return sorted(final_report_list, key=lambda x: x.get(rppm_report_key, 0), reverse=True)
