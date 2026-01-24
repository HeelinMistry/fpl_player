from typing import Dict, Any, List

import numpy as np
import pandas as pd

def summarize_fpl(data: Dict[str, Any]):
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

    top_players = sorted(
        data['elements'],
        key=lambda p: p['total_points'],
        reverse=True
    )[:15]

    print("\nTop 15 Players by Total Points:")
    for i, player in enumerate(top_players, 1):
        team_name = data['teams'][player['team'] - 1]['short_name']
        print(
            f"  {i}. {player['web_name']} "
            f"({team_name}, £{player['now_cost'] / 10:.1f}m): "
            f"{player['total_points']} pts"
        )
    print("-" * 30)


def report_team_strength_analysis(
        team_strength_data: Dict[int, Dict[str, Any]]
) -> None:
    """
    Generates a clear, comparative report for team strength indices,
    focusing on the Composite Strength Score (CSS).

    Args:
        team_strength_data: The dictionary mapping Team ID to its strength metrics,
                            including 'name' and 'composite_strength_score'.
    """
    if not team_strength_data:
        print("🔴 ERROR: Team strength data is empty or missing.")
        return

    print("==================================================")
    print("🏆 FPL Team Strength Comparison Report")
    print("==================================================")

    # Convert the nested dictionary into a list of dictionaries for easier DataFrame creation
    report_data = []
    for team_id, data in team_strength_data.items():
        # Ensure we have a score to report
        if 'composite_strength_score' in data:
            report_data.append({
                'Name': data.get('name', f"ID {team_id}"),
                'CSS': data['composite_strength_score'],
                'Att_H': data.get('strength_attack_home'),
                'Def_A': data.get('strength_defence_away'),
                # Add other key metrics you want to show
            })

    if not report_data:
        print("🔴 ERROR: No usable composite strength scores found.")
        return

    # Use Pandas to create a clean, sortable table
    df = pd.DataFrame(report_data)
    df_sorted = df.sort_values(by='CSS', ascending=False).reset_index(drop=True)
    df_sorted.index = df_sorted.index + 1
    df_sorted = df_sorted.rename_axis('Rank')

    # Format the table for display
    print("### Combined Team Strength Index (Higher CSS = Stronger Team)")
    print("> CSS = Average of all FPL Home/Away Attack/Defense Strength Ratings.")

    # Display the top 10 rows
    print(df_sorted.head(10).to_markdown(floatfmt=(".2f")))

    print("\n" + "---" * 15 + "\n")

    # Display the bottom 5 rows
    print("### Weakest Teams (Potential Opponents/Transfer Targets)")
    print(df_sorted.tail(5).to_markdown(floatfmt=(".2f")))


def report_injury_suspension_status(
        impacted_players: List[Dict[str, Any]],
        pos_map: Dict[int, str],
        team_map: Dict[int, str],
        max_players_to_show: int = 15
) -> None:
    """
    Prints a formatted report of the most impactful unavailable players.
    """
    # Take only the top N most impactful (already sorted by total_points in processing)
    report_list = impacted_players[:max_players_to_show]

    if not report_list:
        print("\n🟢 All key players appear to be available (status 'a').")
        return

    print("\n==================================================")
    print("🚑 **FPL Injury & Suspension Report** 🚑")
    print("==================================================")
    print(f"Unavailable players {len(impacted_players)}")
    print(f"Showing Top {len(report_list)} Most Impactful Absences (Sorted by Total Points)")
    print("-" * 110)

    # Define the output format
    header = "{:<4} {:<20} {:<8} {:<8} {:<8} {:<8} {:<7} {:<6} {:<40}"
    print(header.format(
        "Pos", "Name", "Team", "Status", "Chance", "Price", "PPG", "TSB%", "News Snippet"
    ))
    print("-" * 110)

    # Print the report
    for player in report_list:
        team_short = team_map.get(player['team_id'], 'N/A')
        position = pos_map.get(player['position_id'], 'N/A')

        # Truncate news to fit the table width
        news_snippet = player['news'][:40].replace('\n', ' ')

        print("{:<4} {:<20} {:<8} {:<8} {:<8} £{:<5.1f} {:<7.1f} {:<6}  {:<6} {:<40}".format(
            position,
            player['web_name'],
            team_short,
            player['status'],
            player['chance'],
            player['now_cost'],  # Already divided by 10 in the processor
            player['points_per_game'],
            player['points_per_minute'],
            player['selected_by_percent'],
            news_snippet
        ))
    print("-" * 110)

def report_available_players(
        available_players: List[Dict[str, Any]],
        pos_map: Dict[int, str],
        team_map: Dict[int, str],
        max_players_to_show: int = 5
) -> None:
    """
    Prints a formatted report of the most impactful unavailable players.
    """
    # Take only the top N most impactful (already sorted by total_points in processing)

    print("\n==================================================")
    print(" ***FPL Available Report***")
    print("==================================================")
    print(f"Available players {len(available_players)}")
    print(f"Showing Top {max_players_to_show} Most Impactful players (Sorted by Total Points)")
    print("-" * 110)
    available_list = pd.DataFrame(data=available_players)
    for key, value in pos_map.items():
        print(f"Showing Top {max_players_to_show} Most points - {value}")
        available_list['team'] = available_list['team_id'].map(team_map)
        available_list['position'] = available_list['position_id'].map(pos_map)
        positional_players = available_list[available_list['position_id'] == key].copy()
        columns_to_drop = ['team_id', 'position_id']
        positional_players.drop(columns=columns_to_drop, axis=1, inplace=True)
        print(positional_players[:max_players_to_show].to_markdown(floatfmt=".2f"))
    print("-" * 110)


def report_player_value(player_value_list: List[Dict[str, Any]],
                        pos_map: Dict[int, str],
                        team_map: Dict[int, str],
                        max_players_to_show: int = 5
                        ) -> None:
    player_df = pd.DataFrame(data=player_value_list)
    print("\n==================================================")
    print(f" ***FPL Player Value(Form/Price) *** ")
    print("==================================================")
    for key, value in pos_map.items():
        print(f"Showing Top {max_players_to_show} Most Value - {value}")
        player_df['team'] = player_df['team_id'].map(team_map)
        player_df['position'] = player_df['position_id'].map(pos_map)
        positional_players = player_df[player_df['position_id'] == key].copy()
        columns_to_drop = ['team_id', 'position_id']
        positional_players.drop(columns=columns_to_drop, axis=1, inplace=True)
        print(positional_players[:max_players_to_show].to_markdown(floatfmt=".2f"))
    print("-" * 110)

def report_fixture_analysis(current_gameweek_info: Dict[str, Any],
                            fixtures: List[Dict[str, Any]],
                            team_map: Dict[int, str]
                            ) -> None:
    fixtures_df = pd.DataFrame(data=fixtures)
    print("\n==================================================")
    print(f" ***FPL Fixture Analysis*** ")
    print("==================================================")
    print(fixtures_df[fixtures_df['event']==current_gameweek_info['id']].to_markdown(floatfmt=".2f"))

def report_historical_fixture_analysis(
        fixtures:  Dict[int, Dict[str, Any]],
        team_map: Dict[int, str]
        ) -> None:
    named_features: Dict[str, Dict[str, Any]] = {}
    print("\n==================================================")
    print(f" ***FPL Season Team Stats*** ")
    print("==================================================")
    for key, value in fixtures.items():
        team_name = team_map.get(key)
        if team_name:
            named_features[team_name] = value

    fixtures_df = pd.DataFrame(data=named_features)
    print(fixtures_df.to_markdown(floatfmt=".2f"))


def report_upcoming_fixture_analysis(
        fixtures:  Dict[int, List[Dict[str, Any]]],
        team_map: Dict[int, str]
        ) -> None:
    named_features: Dict[str, List[Dict[str, Any]]] = {}
    print("\n==================================================")
    print(f" ***FPL Upcoming Fixtures*** ")
    print("==================================================")
    for key, value in fixtures.items():
        team_name = team_map.get(key)
        if team_name:
            named_features[team_name] = value

    fixtures_df = pd.DataFrame(data=named_features)
    print(fixtures_df.to_markdown(floatfmt=".2f"))


def report_fixture_ticker(
        fixtures: Dict[int, List[Dict[str, Any]]],
        team_map: Dict[int, str],
        window_size: int  # Default window size for reporting
) -> None:
    """
    Generates a neat, comparative report of upcoming fixtures for all teams,
    sorted by average difficulty (FDR) over the window.
    """
    if not fixtures:
        print("🔴 No upcoming fixtures found in the specified window.")
        return

    print("\n==================================================")
    print(f"🗓️ **FPL Upcoming Fixture Ticker (Next {window_size} GWs)** 🗓️")
    print("==================================================")

    ticker_rows = []

    # Sort teams by their short name for stable reporting order
    sorted_team_ids = sorted(
        fixtures.keys(),
        key=lambda id: team_map.get(id, '')
    )

    for team_id in sorted_team_ids:
        team_name = team_map.get(team_id, f"ID {team_id}")
        fixture_list = fixtures[team_id]

        # Focus on the first 'window_size' fixtures in case your data contains more
        relevant_fixtures = fixture_list[:window_size]

        if not relevant_fixtures:
            continue

        # Calculate Average FDR for the window
        avg_fdr = np.mean([f['fdr'] for f in relevant_fixtures])

        row = {
            'Team': team_name,
            'Avg. FDR': avg_fdr,
        }

        # Dynamically create GW columns
        for fixture in relevant_fixtures:
            gw_col = f"GW {fixture['gw']}"
            location = fixture['location']

            # Format the display string: Opponent (H/A, FDR)
            row[gw_col] = f"{fixture['opponent']} ({location}, {fixture['fdr']})"

        ticker_rows.append(row)

    # Create DataFrame and Sort
    df = pd.DataFrame(ticker_rows)

    # Sort the table by Average FDR (easiest runs at the top)
    df_sorted = df.sort_values(by='Avg. FDR', ascending=True).reset_index(drop=True)

    # Ensure 'Avg. FDR' is the second column
    cols = df_sorted.columns.tolist()
    if 'Avg. FDR' in cols:
        cols.insert(1, cols.pop(cols.index('Avg. FDR')))
        df_sorted = df_sorted[cols]

    # Output the final, clean Markdown table
    print("### Fixture Difficulty Ranking (Lower Avg. FDR = Easier Run)")
    print("> Format: Opponent (Location, FDR Score)")

    print(df_sorted.to_markdown(index=False, floatfmt=(".2f")))

def report_enhanced_player_stats(
        players: List[Any],
        team_map: Dict[int, str],
) -> None:
    print("\n==================================================")
    print(f"***FPL player stats for optimisation***")
    print("==================================================")
    updated_players = Dict[int, Dict[str, Any]]
    df = pd.DataFrame(players)
    df_sorted = df.sort_values(by='points_per_min', ascending=True)

    print(df_sorted[:15].to_markdown(floatfmt=".2f"))


def report_playing_player_stats(playing_player_list: List[Dict[str, Any]],
                                pos_map: Dict[int, str],
                                team_map: Dict[int, str],
                                max_players_to_show: int = 5
                                ) -> None:
    player_df = pd.DataFrame(data=playing_player_list)
    print("\n==================================================")
    print(f"***FPL playing player stats***")
    print("==================================================")
    print(f"Playing players: {len(playing_player_list)}")
    for key, value in pos_map.items():
        print(f"Showing Top {max_players_to_show} Most Value - {value}")
        player_df['team'] = player_df['team_id'].map(team_map)
        player_df['position'] = player_df['position_id'].map(pos_map)
        positional_players = player_df[player_df['position_id'] == key].copy()
        columns_to_drop = ['team_id', 'position_id']
        positional_players.drop(columns=columns_to_drop, axis=1, inplace=True)
        print(positional_players[:max_players_to_show].to_markdown(floatfmt=".2f"))
    print("-" * 110)

def report_player_momentum_windows(
        player_stats: Dict[int, Dict[str, float | int]],
        team_map: Dict[int, str]
) -> None:
    print("\n==================================================")
    print(f"***FPL player stats gw windows***")
    print("==================================================")
    df = pd.DataFrame.from_dict(player_stats, orient='index')

    # 4. Organize and Sort
    # Put 'Name' at the start for readability
    # cols = [c for c in df.columns]
    # df = df[cols].sort_values(by='GW3_PP90M', ascending=False)

    # Use floatfmt to control decimal places across the whole table
    print(df.head(15).to_markdown(index=False, floatfmt=".0f"))


def report_selected_optimised_squad(selected_squad: List[Dict[str, Any]],
                                    bootstrap_data: Dict[str, Any]) -> None:
    # 1. Create Lookup Maps
    player_map = {p['id']: p['web_name'] for p in bootstrap_data['elements']}
    team_map = {t['id']: t['name'] for t in bootstrap_data['teams']}
    pos_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}

    # 2. Build the display list
    report_data = []
    for p in selected_squad:
        report_data.append({
            "Name": player_map.get(p['id'], "Unknown"),
            "Pos": pos_map.get(p['position_id'], "???"),
            "Team": team_map.get(p['team_id'], "Unknown"),
            "Status": p['status'],
            "Price": p['price'],
            "RPPM": p['rppm']
        })

    # 3. Create DataFrame and Sort
    df = pd.DataFrame(report_data)

    # Custom sort to ensure GKP is at the top, followed by DEF, etc.
    df['Pos'] = pd.Categorical(df['Pos'], categories=['GKP', 'DEF', 'MID', 'FWD'], ordered=True)
    df = df.sort_values(by=['Pos', 'RPPM'], ascending=[True, False])

    # 4. Print Header and Table
    print("\n" + "=" * 60)
    print(f"🏆 PULP OPTIMISED SQUAD")
    print("=" * 60)
    print(df.to_markdown(index=False, floatfmt=".1f"))

    # 5. Summary Stats
    total_cost = df['Price'].sum()
    avg_rppm = df['RPPM'].mean()
    print("=" * 60)
    print(f"TOTAL SQUAD COST: £{total_cost:.1f}m | AVG RPPM: {avg_rppm:.2f}")
    print("=" * 60)


def report_final_lineup(starters, bench, captain, vice_captain, bootstrap_data, target_gw):
    player_map = {p['id']: p['web_name'] for p in bootstrap_data['elements']}
    team_map = {t['id']: t['name'] for t in bootstrap_data['teams']}
    pos_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}

    print(f"\n🚀 FINAL LINEUP FOR GW{target_gw}")
    print("=" * 75)

    combined = []
    for i, p in enumerate(starters):
        role = " (C)" if p['id'] == captain['id'] else " (VC)" if p['id'] == vice_captain['id'] else ""
        combined.append({
            "Selection": f"STARTING",
            "Name": player_map[p['id']] + role,
            "Pos": pos_map[p['position_id']],
            "Team": team_map[p['team_id']],
            "RPPM": round(p['rppm'], 1)
        })

    for i, p in enumerate(bench):
        combined.append({
            "Selection": f"BENCH {i + 1}",
            "Name": player_map[p['id']],
            "Pos": pos_map[p['position_id']],
            "Team": team_map[p['team_id']],
            "RPPM": round(p['rppm'], 1)
        })

    df = pd.DataFrame(combined)
    print(df.to_markdown(index=False))


def report_multi_week_transfers(plan, bootstrap_data):
    all_players = bootstrap_data['elements']
    p_map = {p['id']: p['web_name'] for p in all_players}

    print("\n🗓️ TRANSFER ROADMAP")
    print("=" * 50)
    if not plan['in'] and not plan['out']:
        print(f"😴 No transfers recommended (Hold)")
    else:
        for i in range(len(plan['in'])):
            p_in = p_map[plan['in'][i]]
            p_out = p_map[plan['out'][i]]
            print(f"🔄 {p_out} ➡️ {p_in}")
    print("=" * 50)