from typing import Dict, Any, List, Set


def get_position_lookup(bootstrap_data: Dict[str, Any]) -> Dict[int, str]:
    """Creates a mapping from element_type ID (e.g., 1, 2, 3, 4) to position short name (GKP, DEF, MID, FWD)."""
    # This block MUST correctly use 'element_types' from the bootstrap data
    position_map = {
        element_type['id']: element_type['singular_name_short']
        for element_type in bootstrap_data.get('element_types', [])
    }
    return position_map

# --- CORE LOGIC: TEAM STRENGTH REPORT (AGGREGATION ONLY) ---
def generate_team_strength_report(bootstrap_data: Dict[str, Any], sort_by: str = 'FPL_POINTS'):
    """
    Analyzes team statistics by aggregating player data only, avoiding
    fixture data complications.
    """

    all_teams = bootstrap_data['teams']
    all_players = bootstrap_data['elements']

    team_stats: Dict[int, Dict[str, Any]] = {}

    # 1. Initialize team data structure
    for team in all_teams:
        team_id = team['id']
        team_stats[team_id] = {
            'name': team['name'],
            'short_name': team['short_name'],
            # Player-aggregated FPL Metrics
            'total_fpl_points': 0,
            'goals_and_assists': 0,
            'total_team_cost': 0,

            # FPL's internal FDR (Fixture Difficulty Rating / Strength)
            'fdr_att': team['strength_attack_home'] + team['strength_attack_away'],
            'fdr_def': team['strength_defence_home'] + team['strength_defence_away'],
            'fdr_overall': team['strength_overall_home'] + team['strength_overall_away'],
        }

    # 2. Aggregate player data to team level (The reliable step)
    for player in all_players:
        team_id = player['team']

        # Only aggregate if the team_id is valid
        if team_id not in team_stats:
            continue

        # Overall Performance
        team_stats[team_id]['total_fpl_points'] += player['total_points']

        # Offensive Contribution
        team_stats[team_id]['goals_and_assists'] += player['goals_scored'] + player['assists']

        # Team Cost (now_cost is in tenths of a million, e.g., 82 means 8.2m)
        team_stats[team_id]['total_team_cost'] += player['now_cost']

    # 3. Prepare for sorting and display
    report_list = list(team_stats.values())

    # --- DYNAMIC SORTING LOGIC ---
    sort_key_map = {
        'FPL_POINTS': ('total_fpl_points', True, "Overall FPL Performance (Highest Pts)"),
        'ATTACK': ('goals_and_assists', True, "Offensive Output (Goals + Assists)"),
        'FDR_DEF': ('fdr_def', True, "FDR Defensive Strength (FPL's Rating)"),
        'COST': ('total_team_cost', False, "Total Team Cost (Lowest Cost)"),
    }

    key_name, reverse_sort, sort_description = sort_key_map.get(
        sort_by,
        ('total_fpl_points', True, "Overall FPL Performance (Highest Pts)")
    )

    report_list_sorted = sorted(
        report_list,
        key=lambda t: t[key_name],
        reverse=reverse_sort
    )

    # --- DISPLAY ---
    print(f"\n--- FPL Team Strength Report: Sorted by {sort_description} ---")
    print("-" * 105)

    # Define the output format
    print("{:<4} {:<10} | {:<12} {:<12} {:<15} | {:<7} {:<7} {:<7}".format(
        "Rank", "Team", "Total FPL Pts", "Goals+Assists", "Total Team Value",
        "FDR Att", "FDR Def", "FDR Tot"
    ))
    print("-" * 105)

    # Print the report
    for i, team in enumerate(report_list_sorted, 1):
        # Format team cost back to millions
        team_cost_m = f"£{team['total_team_cost'] / 10.0:.1f}m"

        # Display FDR as an average (dividing the full total by 2)
        fdr_att_avg = team['fdr_att'] // 2
        fdr_def_avg = team['fdr_def'] // 2
        fdr_tot_avg = team['fdr_overall'] // 2

        print("{:<4} {:<10} | {:<12} {:<12} {:<15} | {:<7} {:<7} {:<7}".format(
            i,
            team['short_name'],
            team['total_fpl_points'],
            team['goals_and_assists'],
            team_cost_m,
            fdr_att_avg,
            fdr_def_avg,
            fdr_tot_avg
        ))
    print("-" * 105)

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

# --- CORE LOGIC: FIND NEXT GAMEWEEK ---
def get_next_gameweek_info(bootstrap_data: Dict[str, Any]) -> Dict[str, Any] | None:
    """Identifies the next Gameweek ID and deadline from the bootstrap data."""
    if 'events' not in bootstrap_data:
        print("Bootstrap data is missing 'events' key.")
        return None

    next_gameweek = next(
        (gw for gw in bootstrap_data['events'] if gw['is_next']),
        None
    )

    return next_gameweek

# --- VIEWER FUNCTION: DISPLAY FIXTURES ---
def view_gameweek_fixtures(gameweek_id: int, fixtures_data: List[Dict[str, Any]], teams_data: List[Dict[str, Any]]):
    """
    Displays the list of fixtures for a given gameweek.
    Uses the teams_data from bootstrap to map team IDs to names.
    """
    if not fixtures_data or not teams_data:
        print("No fixture or team data to display.")
        return

    # Create a quick map from team ID to team short name for easier reading
    team_map = {team['id']: team['name'] for team in teams_data}

    print(f"\n--- Gameweek {gameweek_id} Fixtures ---")

    # Fixture data also contains the difficulty rating
    print("Match | Kick-off Time (UTC) | H-Diff | A-Diff")
    print("-" * 60)

    for fixture in fixtures_data:
        home_team_id = fixture['team_h']
        away_team_id = fixture['team_a']

        home_team_name = team_map.get(home_team_id, f"Team_{home_team_id}")
        away_team_name = team_map.get(away_team_id, f"Team_{away_team_id}")

        kickoff_time = fixture['kickoff_time']

        # Difficulty is crucial for insight
        home_difficulty = fixture['team_h_difficulty']
        away_difficulty = fixture['team_a_difficulty']

        print(
            f"{home_team_name} vs {away_team_name}: "
            f"{kickoff_time[:16].replace('T', ' ')} | "  # Format datetime for cleaner view
            f"{home_difficulty} | {away_difficulty}"
        )
    print("-" * 60)

# --- VIEWER FUNCTION ---
def view_fpl_data_summary(data: Dict[str, Any]):
    """
    Provides a simple summary of the 'bootstrap-static/' data.
    """
    if not data:
        print("No data to view.")
        return

    # 1. Game Status
    current_gameweek = next(
        (gw['id'] for gw in data['events'] if gw['is_current']),
        'N/A'
    )
    next_deadline = next(
        (gw['deadline_time'] for gw in data['events'] if gw['is_next']),
        'N/A'
    )

    print("\n--- FPL Data Summary ---")
    print(f"Number of Teams: {len(data['teams'])}")
    print(f"Number of Players: {len(data['elements'])}")
    print(f"Current Gameweek: {current_gameweek}")
    print(f"Next Deadline: {next_deadline} (UTC)")
    print("-" * 30)

    # 2. Team Overview
    print("\nPremier League Teams:")
    for team in data['teams']:
        print(f"  - {team['name']} ({team['short_name']})")
    print("-" * 30)

    # 3. Sample Player Data
    # Get the top 5 players by total points
    top_players = sorted(
        data['elements'],
        key=lambda p: p['total_points'],
        reverse=True
    )[:5]

    print("\nTop 5 Players by Total Points:")
    for i, player in enumerate(top_players, 1):
        team_name = data['teams'][player['team'] - 1]['short_name']
        print(
            f"  {i}. {player['web_name']} "
            f"({team_name}, £{player['now_cost'] / 10:.1f}m): "
            f"{player['total_points']} pts"
        )
    print("-" * 30)


def get_next_gw_teams(bootstrap_data: Dict[str, Any], fixtures_data: List[Dict[str, Any]]) -> Set[int]:
    """
    Extracts the set of all team IDs participating in the next gameweek.
    """
    playing_team_ids = set()
    for fixture in fixtures_data:
        # team_h and team_a are team IDs
        playing_team_ids.add(fixture['team_h'])
        playing_team_ids.add(fixture['team_a'])
    return playing_team_ids


def get_key_player_stats_filtered(bootstrap_data: Dict[str, Any], playing_team_ids: Set[int], top_n: int = 15):
    """
    Filters players to those playing AND fully available, then sorts and displays the top N.
    """
    all_players = bootstrap_data['elements']

    # 1. Create mapping dictionaries
    pos_map = {p['id']: p['singular_name_short'] for p in bootstrap_data['element_types']}
    team_map = {t['id']: t['short_name'] for t in bootstrap_data['teams']}

    # 2. Initial Filter: Playing in the next GW
    playing_players = [
        player for player in all_players
        if player['team'] in playing_team_ids
    ]

    # 3. CRITICAL FILTER: Availability Check (status must be 'a' AND 100% chance of playing)
    available_players = []
    for player in playing_players:
        # We only consider players who are fully available or have a known 100% chance
        is_available = (player['status'] == 'a') and (player.get('chance_of_playing_next_round', 100) == 100)

        if is_available:
            # Prepare numeric fields for sorting
            try:
                player['form_float'] = float(player['form'])
                player['ict_float'] = float(player['ict_index'])
            except ValueError:
                player['form_float'] = 0.0
                player['ict_float'] = 0.0

            available_players.append(player)

    print(f"Total available players in next GW: {len(available_players)}")
    if not available_players:
        print("No fully available players found in the next gameweek teams.")
        return

    # 4. Sort by the metric (e.g., Form)
    key_players = sorted(
        available_players,
        key=lambda p: p['form_float'],
        reverse=True
    )[:top_n]

    print(f"\n--- Top {top_n} *FULLY FIT* Players in Next Gameweek (Sorted by Form) ---")
    print("{:<4} {:<20} {:<10} {:<6} {:<8} {:<8} {:<8} {:<8}".format(
        "Pos", "Name", "Team", "Price", "Form", "ICT", "Total Pts", "TSB%"
    ))
    print("-" * 75)

    for player in key_players:
        team_short = team_map.get(player['team'], 'N/A')
        position = pos_map.get(player['element_type'], 'N/A')

        print("{:<4} {:<20} {:<10} £{:<5.1f} {:<8.1f} {:<8.1f} {:<8} {:<7}".format(
            position,
            player['web_name'],
            team_short,
            player['now_cost'] / 10.0,
            player['form_float'],
            player['ict_float'],
            player['total_points'],
            player['selected_by_percent']
        ))
    print("-" * 75)


# --- CORE LOGIC: INJURY REPORT ---
def generate_injury_report(bootstrap_data: Dict[str, Any]):
    """
    Generates a report of all injured, doubtful, or suspended players.
    """
    all_players = bootstrap_data['elements']

    # 1. Create mapping dictionaries
    pos_map = {p['id']: p['singular_name_short'] for p in bootstrap_data['element_types']}
    team_map = {t['id']: t['short_name'] for t in bootstrap_data['teams']}

    # 2. Filter for unavailable or doubtful players
    injured_doubtful_players = []

    for player in all_players:
        # Condition 1: Status is not 'a' (Available)
        # Condition 2: Chance of playing is known and less than 100%
        is_unavailable = (player['status'] != 'a') or \
                         (player.get('chance_of_playing_next_round') is not None and
                          player['chance_of_playing_next_round'] < 100)

        if is_unavailable:
            # Prepare numeric fields for display
            try:
                player['ppg_float'] = float(player['points_per_game'])
            except ValueError:
                player['ppg_float'] = 0.0

            # Use 0 if the field is missing or the player is 'a' but chance is not 100
            chance = player.get('chance_of_playing_next_round')
            player['chance'] = f"{chance}%" if chance is not None else "N/A"

            injured_doubtful_players.append(player)

    # 3. Sort the list (e.g., by total points to see the most impactful absences)
    impactful_absences = sorted(
        injured_doubtful_players,
        key=lambda p: p['total_points'],
        reverse=True
    )

    print(f"\n--- FPL Injury & Suspension Report ({len(impactful_absences)} Players) ---")
    print("Sorted by Total Points (Most Impactful Absences First)")
    print("-" * 110)

    # Define the output format (Note: 'news' can be long, so we truncate it)
    print("{:<4} {:<20} {:<8} {:<8} {:<8} {:<8} {:<7} {:<6} {:<40}".format(
        "Pos", "Name", "Team", "Status", "Chance", "Price", "PPG", "TSB%", "News"
    ))
    print("-" * 110)

    # 4. Print the report
    for player in impactful_absences:
        team_short = team_map.get(player['team'], 'N/A')
        position = pos_map.get(player['element_type'], 'N/A')

        # Truncate news to fit the table width
        news_snippet = player['news'][:40].replace('\n', ' ')

        print("{:<4} {:<20} {:<8} {:<8} {:<8} £{:<5.1f} {:<7.1f} {:<6} {:<40}".format(
            position,
            player['web_name'],
            team_short,
            player['status'].upper(),
            player['chance'],
            player['now_cost'] / 10.0,
            player['ppg_float'],
            player['selected_by_percent'],
            news_snippet
        ))
    print("-" * 110)


# --- UPDATED CORE LOGIC: VALUE ANALYSIS ---
def get_value_players_next_gw(bootstrap_data: Dict[str, Any], playing_team_ids: Set[int], top_n: int = 15):
    """
    Filters players to those available and playing, calculates a Value Score (Form/Price),
    and sorts by it to find the best value-for-money options.
    """
    all_players = bootstrap_data['elements']

    # 1. Create mapping dictionaries
    pos_map = {p['id']: p['singular_name_short'] for p in bootstrap_data['element_types']}
    team_map = {t['id']: t['short_name'] for t in bootstrap_data['teams']}

    available_players = []

    # 2. Filter for availability and fixture
    for player in all_players:
        # Filter 1: Playing in the next GW
        if player['team'] not in playing_team_ids:
            continue

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

                available_players.append(player)
            except ValueError:
                # Skip players with bad data in 'form' or 'now_cost'
                continue

    # 3. Sort by the calculated Value Score
    best_value_players = sorted(
        available_players,
        key=lambda p: p['value_score'],
        reverse=True
    )[:top_n]

    print(f"\n--- Top {top_n} Value-for-Money Players in Next Gameweek (Form/Price) ---")
    print("These players have the highest recent points return per £1M spent.")
    print("-" * 75)
    print("{:<4} {:<20} {:<10} {:<6} {:<8} {:<8} {:<8}".format(
        "Pos", "Name", "Team", "Price", "Form", "Value Score", "TSB%"
    ))
    print("-" * 75)

    # 4. Display the results
    for player in best_value_players:
        team_short = team_map.get(player['team'], 'N/A')
        position = pos_map.get(player['element_type'], 'N/A')

        print("{:<4} {:<20} {:<10} £{:<5.1f} {:<8.1f} {:<11.3f} {:<7}".format(
            position,
            player['web_name'],
            team_short,
            player['now_cost'] / 10.0,
            player['form_float'],
            player['value_score'],
            player['selected_by_percent']
        ))
    print("-" * 75)


# --- NEW CORE LOGIC: FILTERING PLAYERS FOR HISTORY FETCH ---
def get_relevant_player_ids(bootstrap_data: Dict[str, Any]) -> Set[int]:
    """
    Filters players based on FPL relevance metrics and returns a set of their IDs.
    Criteria: Total Points >= 20 AND Form > 3.0
    """
    all_players = bootstrap_data['elements']
    relevant_ids = set()

    MIN_TOTAL_POINTS = 20
    MIN_FORM = 3.0

    for player in all_players:
        try:
            total_points = player.get('total_points', 0)
            form = float(player.get('form', 0.0))

            if total_points >= MIN_TOTAL_POINTS and form >= MIN_FORM:
                relevant_ids.add(player['id'])
        except (ValueError, TypeError):
            # Skip players with malformed point/form data
            continue

    # As a safeguard, include the top 10 players overall just in case their 'form' is temporarily low
    top_10_overall = sorted(
        all_players,
        key=lambda p: p.get('total_points', 0),
        reverse=True
    )[:10]

    for player in top_10_overall:
        relevant_ids.add(player['id'])

    return relevant_ids

def get_available_player_ids(bootstrap_data: Dict[str, Any]) -> Set[int]:
    """
       Filters players based on FPL relevance metrics and returns a set of their IDs.
       Criteria: Total Points >= 20 AND Form > 3.0
       """
    all_players = bootstrap_data['elements']
    relevant_ids = set()

    MIN_TOTAL_POINTS = 20
    MIN_FORM = 3.0

    for player in all_players:
        try:
            total_points = player.get('total_points', 0)
            form = float(player.get('form', 0.0))

            is_available = (player['status'] == 'a') and (player.get('chance_of_playing_next_round', 100) == 100)
            if total_points >= MIN_TOTAL_POINTS and form >= MIN_FORM and is_available:
                relevant_ids.add(player['id'])
        except (ValueError, TypeError):
            # Skip players with malformed point/form data
            continue

    # As a safeguard, include the top 10 players overall just in case their 'form' is temporarily low
    top_10_overall = sorted(
        all_players,
        key=lambda p: p.get('total_points', 0),
        reverse=True
    )[:10]

    for player in top_10_overall:
        relevant_ids.add(player['id'])

    return relevant_ids


MOMENTUM_WINDOWS = [3, 6, 9]
def calculate_momentum_scores(player_history_data: Dict[int, List[Dict[str, Any]]],
                              current_gw: int) -> Dict[int, Dict[str, float | int]]:
    """Calculates Points Per Match (PPM) for individual players over defined windows."""

    player_momentum: Dict[int, Dict[str, float | int]] = {}

    for player_id, history in player_history_data.items():
        player_momentum[player_id] = {'id': player_id}

        # Filter history to only include games that have been played
        finished_history = [h for h in history if h.get('round', 0) <= current_gw and h.get('finished', True)]

        if not finished_history:
            continue

        for window in MOMENTUM_WINDOWS:
            # Select the most recent 'window' number of finished gameweeks
            recent_history = finished_history[-window:]

            # Count games played (minutes > 0)
            games_played = sum(1 for h in recent_history if h.get('minutes', 0) > 0)
            total_points = sum(h.get('total_points', 0) for h in recent_history)

            if games_played > 0:
                ppm_score = total_points / games_played
            else:
                ppm_score = 0.0

            player_momentum[player_id][f'GW{window}_PPM'] = round(ppm_score, 2)
            player_momentum[player_id][f'GW{window}_Pts'] = total_points
            player_momentum[player_id][f'GW{window}_Games'] = games_played

    return player_momentum


def calculate_multi_window_matr(player_momentum: Dict[int, Dict[str, float | int]],
                                fixture_run_score: Dict[int, float],
                                bootstrap_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Calculates MATR for all defined MOMENTUM_WINDOWS and combines the results.
    """
    player_elements = {p['id']: p for p in bootstrap_data.get('elements', [])}
    team_short_names = {t['id']: t['short_name'] for t in bootstrap_data.get('teams', [])}

    # Start with a report based on player info, adding momentum metrics later
    master_report: Dict[int, Dict[str, Any]] = {}

    for player_id, p_momentum in player_momentum.items():
        player_info = player_elements.get(player_id, {})
        team_id = player_info.get('team')

        if not team_id: continue

        # Initialize the player's entry in the master report
        if player_id not in master_report:
            master_report[player_id] = {
                'player_name': player_info.get('web_name', f"ID {player_id}"),
                'id': player_id,
                'element_type_id': player_info.get('element_type'),
                'team': team_short_names.get(team_id, "UNK"),
                'fdr_score': fixture_run_score.get(team_id, 999),
                'total_points': player_info.get('total_points', 0),
                'current_price': player_info.get('now_cost', 0) / 10.0  # Add price for over/under calc later
            }

        team_fdr_score = master_report[player_id]['fdr_score']

        for window in MOMENTUM_WINDOWS:
            ppm_key_from_momentum = f'GW{window}_PPM'  # e.g., 'GW6_PPM'
            games_key = f'GW{window}_Games'

            # Key to store the data in the report
            ppm_report_key = f'gw{window}_ppm'
            matr_report_key = f'matr_score_gw{window}'

            if p_momentum.get(games_key, 0) < 1 or ppm_key_from_momentum not in p_momentum:
                player_ppm = 0.0
            else:
                player_ppm = p_momentum[ppm_key_from_momentum]

            # Calculate MATR for this window
            matr_score = player_ppm / (team_fdr_score + 0.1)

            # Store the PPM and MATR for this specific window
            master_report[player_id][ppm_report_key] = round(player_ppm, 2)
            master_report[player_id][matr_report_key] = round(matr_score, 4)

    # Convert the dictionary back to a list of reports and sort by the GW6 score (as a default primary)
    final_report_list = list(master_report.values())

    # Sort by GW6 MATR for standard positional reports
    return sorted(final_report_list, key=lambda x: x.get('matr_score_gw6', 0), reverse=True)

def aggregate_team_momentum(player_momentum: Dict[int, Dict[str, float | int]],
                            bootstrap_data: Dict[str, Any],
                            num_assets: int = 3,  # Use top 3 assets for aggregation
                            window: int = 6) -> List[Dict[str, Any]]:
    """Aggregates individual player momentum scores to a team level."""

    team_map = {player['id']: player['team'] for player in bootstrap_data.get('elements', [])}
    team_names = {team['id']: team['short_name'] for team in bootstrap_data.get('teams', [])}

    team_scores: Dict[int, List[float]] = {team_id: [] for team_id in team_names.keys()}

    ppm_key = f'GW{window}_PPM'

    # 1. Map player scores to their respective teams
    for player_id, score_data in player_momentum.items():
        team_id = team_map.get(player_id)
        if team_id and ppm_key in score_data:
            # Only consider players who have actually played in the window
            if score_data.get(f'GW{window}_Games', 0) > 0:
                team_scores[team_id].append(score_data[ppm_key])

    # 2. Calculate Team Momentum Score (Sum of top N assets' PPM)
    team_momentum_report: List[Dict[str, Any]] = []

    for team_id, scores in team_scores.items():
        # Sort scores and select the top N for a robust team score
        top_scores = sorted(scores, reverse=True)[:num_assets]

        team_momentum_report.append({
            'team_id': team_id,
            'team_name': team_names.get(team_id, f"Team {team_id}"),
            'momentum_score': round(sum(top_scores), 2),
            'num_assets_used': len(top_scores)
        })

    # 3. Sort the final report by momentum score
    return sorted(team_momentum_report, key=lambda x: x['momentum_score'], reverse=True)


# --- REPORT GENERATION ---
def generate_momentum_report(team_momentum_report: List[Dict[str, Any]],
                             window: int, num_assets: int):
    """Prints the formatted team momentum report."""

    print(f"\n--- 🚀 Team Momentum Report (Last {window} GWs) ---")
    print(f"| Aggregated using the sum of top {num_assets} assets' Points Per Match (PPM) |")
    print("-" * 50)
    print("{:<4} {:<10} {:<10} {:<10}".format("Rank", "Team", "Momentum", "Assets"))
    print("-" * 50)

    for i, team in enumerate(team_momentum_report, 1):
        print("{:<4} {:<10} {:<10.2f} {:<10}".format(
            i,
            team['team_name'],
            team['momentum_score'],
            team['num_assets_used']
        ))
    print("-" * 50)


# --- NEW CORE LOGIC: CALCULATE FUTURE DIFFICULTY ---
def calculate_fixture_run_score(fixtures_data: List[Dict[str, Any]],
                                bootstrap_data: Dict[str, Any],
                                current_gw: int,
                                window: int) -> Dict[int, float]:
    """
    Calculates the combined difficulty score for the next 'window' of gameweeks
    for every team. Lower score is better.
    """
    team_ids = {team['id'] for team in bootstrap_data.get('teams', [])}
    team_fixture_scores: Dict[int, List[int]] = {tid: [] for tid in team_ids}

    # Define the range of Gameweeks we care about
    start_gw = current_gw + 1
    try:
        window_size = int(window)
    except ValueError:
        print(f"Error: Fixture window '{window}' is not a valid number. Using default of 5.")
        window_size = 5
    end_gw = current_gw + int(window_size)

    # 1. Filter fixtures to the upcoming window
    upcoming_fixtures = [
        f for f in fixtures_data
        if f.get('event') and start_gw <= f['event'] <= end_gw
    ]

    # 2. Extract difficulty scores for each team
    for fixture in upcoming_fixtures:
        # Check if the fixture is finished or has a pending event
        if fixture.get('finished', False) or not fixture.get('event'):
            continue

        team_h = fixture['team_h']
        team_a = fixture['team_a']

        # Home team: Difficulty against team_a
        team_fixture_scores[team_h].append(fixture['team_h_difficulty'])

        # Away team: Difficulty against team_h
        team_fixture_scores[team_a].append(fixture['team_a_difficulty'])

    # 3. Calculate the total (sum) difficulty for the fixture run
    fixture_run_score: Dict[int, float] = {}

    for team_id, scores in team_fixture_scores.items():
        # Sum the difficulty scores. A lower sum is a better (easier) run.
        fixture_run_score[team_id] = sum(scores)

        # Optional: Normalize the score if the team has played fewer than 'window' games (e.g., due to blanks)
        # For simplicity, we will just use the sum of difficulties for scheduled games.

    return fixture_run_score


# --- NEW CORE LOGIC: COMBINE MOMENTUM AND FDR (MATR) ---
def calculate_momentum_adjusted_rating(player_momentum: Dict[int, Dict[str, float | int]],
                                       fixture_run_score: Dict[int, float],
                                       bootstrap_data: Dict[str, Any],
                                       momentum_window: int) -> List[Dict[str, Any]]:
    """
    Calculates a combined rating for each player: Momentum / Fixture Difficulty.
    Higher rating is better.
    """

    # Get necessary lookups
    player_elements = {p['id']: p for p in bootstrap_data.get('elements', [])}
    team_short_names = {t['id']: t['short_name'] for t in bootstrap_data.get('teams', [])}

    transfer_rating_report: List[Dict[str, Any]] = []

    ppm_key_from_momentum = f'GW{momentum_window}_PPM'  # This is what calculate_momentum_scores returns
    games_key = f'GW{momentum_window}_Games'

    # 🌟 FIX 4: Use lowercase for the key stored in the report, to match the reporting function
    dynamic_ppm_report_key = f'gw{momentum_window}_ppm'

    for player_id, p_momentum in player_momentum.items():
        player_info = player_elements.get(player_id, {})
        team_id = player_info.get('team')

        if not team_id or ppm_key_from_momentum not in p_momentum:
            continue

        team_fdr_score = fixture_run_score.get(team_id, 999)

        # Players must have played enough recently to have a valid PPM
        if p_momentum.get(games_key, 0) < 1:  # Use dynamic games_key
            continue

        player_ppm = p_momentum[ppm_key_from_momentum]

        # The key formula: MATR = PPM / FDR Score. Lower FDR gives a higher MATR.
        matr_score = player_ppm / (team_fdr_score + 0.1)

        transfer_rating_report.append({
            'player_name': player_info.get('web_name', f"ID {player_id}"),
            'element_type_id': player_info.get('element_type'),
            'team': team_short_names.get(team_id, "UNK"),

            # 🌟 FIX 2: Store the PPM using a dynamic key
            dynamic_ppm_report_key: player_ppm,

            'fdr_score': team_fdr_score,
            'matr_score': round(matr_score, 4),
            'total_points': player_info.get('total_points', 0)
        })

    # Sort by the final calculated rating
    return sorted(transfer_rating_report, key=lambda x: x['matr_score'], reverse=True)

# --- REPORT GENERATION (for MATR) ---

def generate_positional_matr_reports(matr_report: List[Dict[str, Any]], bootstrap_data: Dict[str, Any],
                                     fdr_window: int):
    """Prints the formatted multi-window MATR report, separated by position."""

    position_lookup = get_position_lookup(bootstrap_data)
    position_ids = [1, 2, 3, 4]

    print("\n" + "=" * 120)
    print("🚀 MULTI-WINDOW MOMENTUM-ADJUSTED TRANSFER RATING (MATR) - BY POSITION 🚀")
    print(f"| FDR Score calculated over next {fdr_window} GWs. PPM and MATR shown for GW3, GW6, and GW9 lookback. |")
    print("=" * 120)

    for element_type_id in position_ids:
        position_name = position_lookup.get(element_type_id, "UNKNOWN")
        position_report = [
            p for p in matr_report
            if p.get('element_type_id') == element_type_id
        ]

        # Sort by GW6 MATR score for the positional report ranking
        position_report.sort(key=lambda x: x.get('matr_score_gw6', 0), reverse=True)
        top_players = position_report[:10]

        if not top_players:
            continue

        print(f"\n--- ⚽ TOP {len(top_players)} {position_name} MATR Candidates (Ranked by GW6 MATR) ---")
        print("-" * 120)

        # New, wider column format for multiple PPM/MATR values
        print("{:<4} {:<15} {:<5} {:<10} {:<6} {:<6} {:<6} {:<8} {:<8} {:<8} {:<10}".format(
            "Rank", "Player", "Team", "FDR", "PPM(3)", "PPM(6)", "PPM(9)", "MATR(3)", "MATR(6)", "MATR(9)", "Total Pts"
        ))
        print("-" * 120)

        for i, p in enumerate(top_players, 1):
            print("{:<4} {:<15} {:<5} {:<10.0f} {:<6.2f} {:<6.2f} {:<6.2f} {:<8.4f} {:<8.4f} {:<8.4f} {:<10}".format(
                i,
                p['player_name'],
                p['team'],
                p['fdr_score'],
                p.get('gw3_ppm', 0.0),  # Retrieve all 3 PPMs
                p.get('gw6_ppm', 0.0),
                p.get('gw9_ppm', 0.0),
                p.get('matr_score_gw3', 0.0),  # Retrieve all 3 MATRs
                p.get('matr_score_gw6', 0.0),
                p.get('matr_score_gw9', 0.0),
                p['total_points']
            ))
        print("-" * 120)

    print("\n" + "=" * 120)


def calculate_multi_window_over_under_achiever_score(matr_report: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculates the ValueScore_MATR for all momentum windows: MATR Score / Price.
    Higher score indicates a better *Overachiever* (Undervalued player).

    NOTE: This function assumes the matr_report list is the output from calculate_multi_window_matr
    and already contains 'current_price' and the three 'matr_score_gwx' keys.
    """

    enhanced_report = []

    for player_data in matr_report:

        current_price = player_data.get('current_price')
        if not current_price or current_price == 0:
            continue

        # Initialize the Value Scores
        player_values = {}

        for window in MOMENTUM_WINDOWS:
            matr_report_key = f'matr_score_gw{window}'
            value_score_key = f'value_score_matr_gw{window}'

            matr_score = player_data.get(matr_report_key, 0)

            # Calculation: ValueScore_MATR = MATR / Price
            if matr_score > 0:
                value_score = matr_score / current_price
            else:
                value_score = 0.0

            player_values[value_score_key] = round(value_score, 4)

        # The main sorting key for the Over/Under report is based on GW6 value
        primary_value_score = player_values.get('value_score_matr_gw6', 0.0)

        enhanced_report.append({
            **player_data,
            **player_values,
            'primary_value_score': primary_value_score  # Key to sort the final list
        })

    # 2. Sort by the new Primary ValueScore_MATR (GW6) descending
    return sorted(enhanced_report, key=lambda x: x['primary_value_score'], reverse=True)


def generate_over_under_reports(achiever_report: List[Dict[str, Any]], fdr_window: int):
    """Prints the top Overachievers and Underachievers based on multi-window ValueScore_MATR."""

    TOP_N = 10

    # 🌟 Header now reflects the multi-window approach
    print("\n" + "=" * 130)
    print("💎 MATR-ADJUSTED OVER/UNDER-ACHIEVER REPORT 📉")
    print(
        f"| Value Score = MATR / Price. Scores shown for GW3, GW6, and GW9 lookback. FDR over next {fdr_window} GWs. |")
    print("=" * 130)

    # --- TOP OVERACHIEVERS (Most Undervalued) ---
    top_overachievers = achiever_report[:TOP_N]

    print(f"\n--- 🚀 TOP {TOP_N} OVERACHIEVERS (Ranked by GW6 Value Score) ---")
    print("-" * 130)
    # New, wider column headers
    print("{:<4} {:<15} {:<5} {:<6} {:<8} {:<8} {:<8} {:<8} {:<8} {:<8} {:<10}".format(
        "Rank", "Player", "Team", "Price",
        "MATR(6)", "VAL(3)", "VAL(6)", "VAL(9)",
        "FDR", "PPM(6)", "Total Pts"
    ))
    print("-" * 130)

    for i, p in enumerate(top_overachievers, 1):
        # We display GW6 MATR and PPM for context, and all three Value Scores (VAL)
        print("{:<4} {:<15} {:<5} £{:<5.1f} {:<8.4f} {:<8.4f} {:<8.4f} {:<8.4f} {:<8.0f} {:<8.2f} {:<10}".format(
            i,
            p['player_name'],
            p['team'],
            p['current_price'],
            # MATR (GW6)
            p.get('matr_score_gw6', 0.0),
            # Value Scores (VAL)
            p.get('value_score_matr_gw3', 0.0),
            p.get('value_score_matr_gw6', 0.0),
            p.get('value_score_matr_gw9', 0.0),
            # Context Metrics (FDR and GW6 PPM)
            p.get('fdr_score', 0.0),
            p.get('gw6_ppm', 0.0),
            p['total_points']
        ))
    print("-" * 130)

    # --- TOP UNDERACHIEVERS (Least Value, Highest Sell Priority) ---
    bottom_underachievers = achiever_report[-TOP_N:]
    bottom_underachievers.reverse()

    print(f"\n--- 🔻 TOP {TOP_N} UNDERACHIEVERS (Ranked by GW6 Value Score) ---")
    print("-" * 130)
    # Use the same new, wider column headers
    print("{:<4} {:<15} {:<5} {:<6} {:<8} {:<8} {:<8} {:<8} {:<8} {:<8} {:<10}".format(
        "Rank", "Player", "Team", "Price",
        "MATR(6)", "VAL(3)", "VAL(6)", "VAL(9)",
        "FDR", "PPM(6)", "Total Pts"
    ))
    print("-" * 130)

    for i, p in enumerate(bottom_underachievers, 1):
        print("{:<4} {:<15} {:<5} £{:<5.1f} {:<8.4f} {:<8.4f} {:<8.4f} {:<8.4f} {:<8.0f} {:<8.2f} {:<10}".format(
            i,
            p['player_name'],
            p['team'],
            p['current_price'],
            p.get('matr_score_gw6', 0.0),
            p.get('value_score_matr_gw3', 0.0),
            p.get('value_score_matr_gw6', 0.0),
            p.get('value_score_matr_gw9', 0.0),
            p.get('fdr_score', 0.0),
            p.get('gw6_ppm', 0.0),
            p['total_points']
        ))
    print("-" * 130)