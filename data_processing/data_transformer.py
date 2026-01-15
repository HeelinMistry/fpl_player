from typing import Dict, Any, List, Tuple, Set

import pandas as pd


def create_lookup_maps(bootstrap_data: Dict[str, Any]) -> Tuple[Dict[int, str], Dict[int, str]]:
    """
    Creates the position and team ID-to-name lookup maps.
    """
    pos_map = {p['id']: p['singular_name_short'] for p in bootstrap_data['element_types']}
    team_map = {t['id']: t['short_name'] for t in bootstrap_data['teams']}
    return pos_map, team_map


def get_current_gameweek_info(bootstrap_data: Dict[str, Any]) -> Dict[str, Any] | None:
    """Identifies the ID of the current Gameweek from the bootstrap data."""
    if 'events' not in bootstrap_data:
        print("Bootstrap data is missing 'events' key.")
        return None
    current_gameweek = next(
        (gw for gw in bootstrap_data['events'] if gw.get('is_current')),
        None
    )
    return current_gameweek


def get_all_player_ids(bootstrap_data: Dict[str, Any]) -> Set[int]:
    """
       Filters players based on FPL relevance metrics and returns a set of their IDs.
       Criteria: Total Points >= 20 AND Form > 3.0
       """
    all_players = bootstrap_data['elements']
    relevant_ids = set()

    for player in all_players:
        try:
            relevant_ids.add(player['id'])
        except (ValueError, TypeError):
            # Skip players with malformed point/form data
            continue
    return relevant_ids

def get_remaining_gws(bootstrap_data: Dict[str, Any]) -> int:
    if 'events' not in bootstrap_data:
        print("Bootstrap data is missing 'events' key.")
        return None
    current_gameweek = next(
        (gw for gw in bootstrap_data['events'] if gw.get('is_current')),
        None
    )

    start_gw = current_gameweek['id']
    end_gw = bootstrap_data['events'][-1]['id']
    return end_gw - start_gw

# --- CORE LOGIC: INJURY REPORT ---
def get_impacted_player_list(bootstrap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filters the bootstrap data to identify all players who are injured, doubtful,
    or suspended (i.e., status != 'a' or chance_of_playing < 100).
    Prepares necessary data points for reporting.
    """
    all_players = bootstrap_data['elements']
    impacted_players = []

    for player in all_players:
        # Condition 1: Status is not 'a' (Available)
        # Condition 2: Chance of playing is known and less than 100%
        is_unavailable = (player['status'] != 'a') or \
                         (player.get('chance_of_playing_next_round') is not None and
                          player['chance_of_playing_next_round'] < 100)

        if is_unavailable:
            # Prepare numeric fields for display and sorting
            try:
                ppg_float = float(player['points_per_game'])
            except ValueError:
                ppg_float = 0.0

            chance = player.get('chance_of_playing_next_round')

            # Create a simplified dictionary for the reporter
            impacted_players.append({
                'id': player['id'],
                'web_name': player['web_name'],
                'team_id': player['team'],
                'position_id': player['element_type'],
                'status': player['status'].upper(),
                'chance': f"{chance}%" if chance is not None else "N/A",
                'now_cost': player['now_cost'] / 10.0,  # Convert to actual price (e.g., 50 -> 5.0)
                'ppg': ppg_float,
                'total_points': player['total_points'],
                'selected_by_percent': player['selected_by_percent'],
                'news': player['news'],
            })

    # Sort the list by total points for impact analysis and return the full list
    return sorted(
        impacted_players,
        key=lambda p: p['total_points'],
        reverse=True
    )

def get_player_value_list(bootstrap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    all_players = bootstrap_data['elements']
    player_value_list = []
    for player in all_players:
        # Filter 2: Availability Check (Correctly handles None/100% chance for available players)
        raw_chance = player.get('chance_of_playing_next_round', 100)
        safe_chance = raw_chance if raw_chance is not None else 100

        is_available = (player['status'] == 'a') and (safe_chance == 100)

        if is_available:
            try:
                form_float = float(player['form'])
                price_float = player['now_cost'] / 10.0  # Convert from tenths to millions (e.g., 65 -> 6.5)

                # CRITICAL CALCULATION: Value Score (Form per Million)
                # We protect against price_float being 0.0, although unlikely in FPL
                if price_float > 0 and form_float > 0:
                    player['value_score'] = form_float / price_float
                else:
                    player['value_score'] = 0.0

                player['form_float'] = form_float

                player_value_list.append({
                    'id': player['id'],
                    'web_name': player['web_name'],
                    'team_id': player['team'],
                    'position_id': player['element_type'],
                    'form': player['form_float'],
                    'price': player['now_cost'] / 10.0,
                    'value_score': player['value_score'],
                    'total_points': player['total_points'],
                    'event_points': player['event_points'],
                })
            except ValueError:
                # Skip players with bad data in 'form' or 'now_cost'
                continue

        # 3. Sort by the calculated Value Score
    return sorted(
        player_value_list,
        key=lambda p: p['value_score'],
        reverse=True
    )

def get_available_player_list(bootstrap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filters the bootstrap data to identify all players who are available, then sorts
    Prepares necessary data points for reporting.
    """
    all_players = bootstrap_data['elements']
    available_players = []

    for player in all_players:
        # Condition 1: Status is not 'a' (Available)
        # Condition 2: Chance of playing is known and less than 100%
        is_available = (player['status'] == 'a') or \
                         (player['chance_of_playing_next_round'] == 100)

        if is_available:
            # Prepare numeric fields for display and sorting
            try:
                ppg_float = float(player['points_per_game'])
            except ValueError:
                ppg_float = 0.0

            # Create a simplified dictionary for the reporter
            available_players.append({
                'id': player['id'],
                'web_name': player['web_name'],
                'team_id': player['team'],
                'position_id': player['element_type'],
                'form': player['form'],
                'price': player['now_cost'] / 10.0,
                'ppg': ppg_float,
                'total_points': player['total_points'],
                'event_points': player['event_points'],
                'selected_by_percent': player['selected_by_percent'],
            })

    # Sort the list by total points for impact analysis and return the full list
    return sorted(
        available_players,
        key=lambda p: p['total_points'],
        reverse=True
    )


def get_playing_player_list(bootstrap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filters the bootstrap data to identify all players who are available, then sorts
    Prepares necessary data points for reporting.
    """
    all_players = bootstrap_data['elements']
    df = pd.DataFrame(all_players)
    median_mins = df['minutes'].median()
    # top_half_players_df = df[df['minutes'] >= median_mins]
    reliable_players = df.to_dict('records')
    available_players = []
    for player in reliable_players:
        try:
            ppg_float = float(player['points_per_game'])
        except ValueError:
            ppg_float = 0.0
        available_players.append({
            'id': player['id'],
            'web_name': player['web_name'],
            'team_id': player['team'],
            'position_id': player['element_type'],
            'status': player['status'],
            'form': player['form'],
            'price': player['now_cost'] / 10.0,
            'ppg': ppg_float,
            'total_points': player['total_points'],
            'event_points': player['event_points'],
            'selected_by_percent': player['selected_by_percent'],
        })

    # Sort the list by total points for impact analysis and return the full list
    return sorted(
        available_players,
        key=lambda p: p['total_points'],
        reverse=True
    )


def process_team_strength_indices(bootstrap_data: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
    """
    Extracts and standardizes the FPL strength indices for team comparison.
    Creates a Composite Score by averaging the different strength metrics.
    """
    team_comparison_data: Dict[int, Dict[str, float]] = {}

    # These fields are the main reliable indicators before GW1 is finished
    strength_fields = [
        'strength_overall_home', 'strength_overall_away',
        'strength_attack_home', 'strength_attack_away',
        'strength_defence_home', 'strength_defence_away'
    ]

    for team in bootstrap_data.get('teams', []):
        team_id = team['id']
        team_data: Dict[str, float] = {}

        # Extract and store individual strength ratings
        for field in strength_fields:
            team_data[field] = float(team.get(field, 0))

            # Calculate a Composite Strength Score (CSS)
        # This gives a single, averaged metric for comparison
        total_strength = sum(team_data.values())
        count = len(strength_fields)

        team_data['composite_strength_score'] = round(total_strength / count, 2)
        team_data['name'] = team['name']
        team_comparison_data[team_id] = team_data
    return team_comparison_data

def get_optimized_player_stats(playing_player_stats: List[Dict[str, Any]],
                               player_momentum: Dict[int, Dict[str, float | int]]) -> List[Dict[str, Any]]:
    optimized_players = []
    for player in playing_player_stats:
        player['GW3_PP90M'] = player_momentum[player['id']]['GW3_PP90M']
        # if player['GW3_PP90M'] > player['ppg']:
        optimized_players.append(player)
    return sorted(
        optimized_players,
        key=lambda p: p['GW3_PP90M'],
        reverse=True
    )


def assign_squad_roles(selected_squad: List[Dict[str, Any]]):
    # 1. Calculate the 'Expected Score' for this specific GW
    # for p in selected_squad:
    #     p['gw_score'] = p['rppm'] + (p['fixture_comparison'].get(target_gw, 0) * weight)

    # 2. Sort all players by score (highest first)
    sorted_players = sorted(selected_squad, key=lambda x: x['rppm'], reverse=True)

    # 3. Assign Captain and Vice-Captain
    captain = sorted_players[0]
    vice_captain = sorted_players[1]

    # 4. Select Starting 11
    starters = []
    bench = []

    # Mandatory picks first
    gkps = [p for p in sorted_players if p['position_id'] == 1]
    defs = [p for p in sorted_players if p['position_id'] == 2]
    mids = [p for p in sorted_players if p['position_id'] == 3]
    fwds = [p for p in sorted_players if p['position_id'] == 4]

    starters.append(gkps[0])  # Best GK starts
    starters.extend(defs[:3])  # Min 3 Defs
    starters.extend(fwds[:1])  # Min 1 Fwd

    # Fill remaining 6 spots with best available outfielders
    remaining_pool = defs[3:] + mids + fwds[1:]
    remaining_pool = sorted(remaining_pool, key=lambda x: x['rppm'], reverse=True)

    for p in remaining_pool:
        # Check formation limits
        current_defs = len([s for s in starters if s['position_id'] == 2])
        current_mids = len([s for s in starters if s['position_id'] == 3])
        current_fwds = len([s for s in starters if s['position_id'] == 4])

        if len(starters) < 11:
            if p['position_id'] == 2 and current_defs < 5:
                starters.append(p)
            elif p['position_id'] == 3 and current_mids < 5:
                starters.append(p)
            elif p['position_id'] == 4 and current_fwds < 3:
                starters.append(p)
            else:
                bench.append(p)
        else:
            bench.append(p)

    # Ensure backup GK is last on bench
    bench.append(gkps[1])

    return starters, bench, captain, vice_captain

def get_squad_value(current_squad: list) -> float:
    squad_value = 0.0
    for player in current_squad:
        squad_value += player['price']
    return round(squad_value, 1)