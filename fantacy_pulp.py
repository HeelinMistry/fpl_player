# This is a sample Python script.

from pulp import *
from typing import Dict, Any, Tuple
from src.fantacy_analysis import *
from src.fantacy_api import get_fpl_data


def report_mgo_strategy(
        problem: LpProblem,
        all_player_data: List[Dict[str, Any]],
        mgo_gw_ids: List[int],
        initial_squad_ids: List[int]
):
    """
    Analyzes the solved MGO problem to report the optimal strategy across the horizon.
    """
    if LpStatus[problem.status] != 'Optimal':
        print(f"MGO solution is not optimal. Status: {LpStatus[problem.status]}")
        return

    # --- Setup Mapping and Variables ---
    player_map = {p['id']: p.get('web_name', f"ID {p['id']}") for p in all_player_data}

    # Extract PuLP Variables (accessing the variables dictionary by name and index)
    variables = problem.variablesDict()

    # Lists to store aggregated information
    gameweek_reports = collections.OrderedDict()

    # --- Initial Squad (Before any transfers are made) ---
    current_squad_ids = set(initial_squad_ids)

    # --- Iterate through each Gameweek in the MGO Horizon ---
    for t_current in mgo_gw_ids:
        report = {}

        # 1. Determine the SQUAD (X) - Always based on the optimal result
        squad_ids = {
            i for i in current_squad_ids
            if value(variables.get(f"X_{i}_{t_current}", 0)) > 0.5
        }
        current_squad_ids = squad_ids  # Update the tracker for the next GW's report

        # 2. Determine STARTING XI and Captain (S, C)
        starting_xi = []
        captain_id = None
        for i in squad_ids:
            s_key = f"S_{i}_{t_current}"
            c_key = f"C_{i}_{t_current}"

            if s_key in variables and value(variables[s_key]) > 0.5:
                starting_xi.append(player_map[i])

            if c_key in variables and value(variables[c_key]) > 0.5:
                captain_id = i

        report['Squad'] = sorted([player_map[i] for i in squad_ids])
        report['XI'] = starting_xi
        report['Captain'] = player_map.get(captain_id, "N/A")

        # 3. TRANSFER and FINANCES Analysis (For GWs after the start)
        if t_current > mgo_gw_ids[0]:
            transfers_in = []
            transfers_out = []

            # Check for transfers (I, O)
            for i in player_map.keys():
                i_key = f"I_{i}_{t_current}"
                o_key = f"O_{i}_{t_current}"

                if i_key in variables and value(variables[i_key]) > 0.5:
                    transfers_in.append(player_map[i])
                if o_key in variables and value(variables[o_key]) > 0.5:
                    transfers_out.append(player_map[i])

            # Check for Financial Variables (P, T_Free)
            p_key = f"P_{t_current}"
            ft_key = f"FT_{t_current}"

            hit_value = int(round(value(variables.get(p_key, 0)), 0))
            ft_available = int(round(value(variables.get(ft_key, 0)), 0))

            report['Transfers In'] = transfers_in
            report['Transfers Out'] = transfers_out
            report['Hit'] = hit_value * 4
            report['FT Available'] = ft_available

        # 4. Store the report for the current GW
        gameweek_reports[t_current] = report

    # --- 5. PRINT THE DETAILED REPORT ---
    print("\n" + "=" * 80)
    print(
        f"🏆 OPTIMAL MGO PLAN: GW {mgo_gw_ids[0]} to GW {mgo_gw_ids[-1]} | Total S-MATR Score: {value(problem.objective):.2f}")
    print("=" * 80)

    for gw, report in gameweek_reports.items():
        is_transfer_gw = gw > mgo_gw_ids[0]

        print(f"\n--- 📅 GAMEWEEK {gw} ---")

        # Transfers Summary (for Transfer GWs)
        if is_transfer_gw:
            if report['Transfers In']:
                print(f"✅ Transfers IN: {', '.join(report['Transfers In'])}")
                print(f"❌ Transfers OUT: {', '.join(report['Transfers Out'])}")
                print(f"💰 Point Hit: {report['Hit']} points")
            else:
                print("➡️ **HOLD** (0 Transfers Made)")
            print(f"ℹ️ FT Available Next GW: {report['FT Available']}")

        # Selection Summary (for all GWs)
        print(f"⭐ **Captain:** {report['Captain']}")

        # Displaying the starting XI
        print(f"⚽ **Starting XI:**")
        # For a more readable format, you can categorize by position here if you have position data.
        print(f"   {', '.join(report['XI'])}")

    print("\n" + "=" * 80)

# --- MGO CONFIGURATION ---
FDR_LKFWD = 4
HIT_COST = 4.0
MAX_BUDGET = 100.0  # £100M
POS_LIMITS = {1: 2, 2: 5, 3: 5, 4: 3}  # Max squad limits (1=GKP, 2=DEF, 3=MID, 4=FWD)
FORMATION_MIN = {1: 1, 2: 3, 3: 2, 4: 1}  # Min starting XI (1 GKP, 3 DEF, 2 MID, 1 FWD)
FORMATION_MAX = {1: 1, 2: 5, 3: 5, 4: 3}  # Max starting XI (1 GKP, 5 DEF, 5 MID, 3 FWD)
def solve_multi_gameweek_optimization(all_gws: List[int],
                                      all_player_ids: List[int],
                                      initial_squad_ids: List[int],
                                      player_scores_matr: Dict[Tuple[int, int], float],
                                      player_costs: Dict[int, float],
                                      player_positions: Dict[int, int],
                                      player_teams: Dict[int, int],
                                      all_team_ids: List[int]) -> LpProblem:
    """
    Sets up and solves the Multi-Gameweek Optimization (MGO) problem.

    Args:
        all_player_data: List of all player dictionaries.
        initial_squad_ids: IDs of the 15 players in the GW1 starting squad.
        player_scores_matr: Dict mapping (player_id, gw) to forecasted S-MATR score.
        player_costs: Dict mapping player_id to current cost.
        player_positions: Dict mapping player_id to position ID (1-4).
        player_teams: Dict mapping player_id to team ID.
        all_team_ids: List of all team IDs.

    Returns:
        The solved PuLP problem object.
    """

    problem = LpProblem("FPL_MGO_Aggressive", LpMaximize)

    # --- Time and Player Dimensions ---
    ALL_GWS = all_gws
    TRANSFER_GWS = ALL_GWS[1:]
    gw_pairs = list(zip(TRANSFER_GWS[1:], TRANSFER_GWS[:-1]))

    PLAYERS = all_player_ids

    # --- 1. Define Variables ---

    # Squad, Starters, Captain
    X = LpVariable.dicts("X", (PLAYERS, ALL_GWS), 0, 1, LpBinary)
    S = LpVariable.dicts("S", (PLAYERS, ALL_GWS), 0, 1, LpBinary)
    C = LpVariable.dicts("C", (PLAYERS, ALL_GWS), 0, 1, LpBinary)

    # Transfers
    I = LpVariable.dicts("I", (PLAYERS, TRANSFER_GWS), 0, 1, LpBinary)
    O = LpVariable.dicts("O", (PLAYERS, TRANSFER_GWS), 0, 1, LpBinary)

    # Transfer Tracking
    FT = LpVariable.dicts("FT", TRANSFER_GWS, lowBound=1, upBound=2, cat=LpInteger)
    T_Free = LpVariable.dicts("T_Free", TRANSFER_GWS, lowBound=0, cat=LpInteger)
    P = LpVariable.dicts("P", TRANSFER_GWS, lowBound=0, cat=LpInteger)  # Paid Transfers (Hits)

    # --- 2. Define Objective Function ---

    objective = []
    for t in ALL_GWS:
        # XI Score + Captain Bonus
        xi_score = lpSum(S[i][t] * player_scores_matr[(i, t)] for i in PLAYERS)
        captain_bonus = lpSum(C[i][t] * player_scores_matr[(i, t)] for i in PLAYERS)

        transfer_penalty = 0
        if t in TRANSFER_GWS:
            # Transfer Penalties: -4 points per hit (P_t)
            transfer_penalty = -HIT_COST * P[t]

        objective.append(xi_score + captain_bonus + transfer_penalty)

    problem += lpSum(objective), "Total_Cumulative_S_MATR_Score"

    # --- 3. Linking Constraints (Transfer Logic) ---

    # A. Squad Continuity: X_i_t == X_i_t-1 - O_i_t + I_i_t
    for i in PLAYERS:
        for t_current, t_prev in gw_pairs:  # Iterates (23, 22), (24, 23), etc.
            # This accesses the variables using only the defined GW IDs (22, 23, 24, 25)
            problem += X[i][t_current] - X[i][t_prev] + O[i][t_current] - I[i][
                t_current] == 0, f"Squad_Continuity_P{i}_GW{t_current}"

    # B. Transfer Balance: Buys = Sells
    for t in TRANSFER_GWS:
        problem += lpSum(I[i][t] for i in PLAYERS) == lpSum(O[i][t] for i in PLAYERS), f"Transfer_Balance_GW{t}"

    # C. Total Transfers Link: Buys = T_Free + P_t
    for t in TRANSFER_GWS:
        problem += lpSum(I[i][t] for i in PLAYERS) == T_Free[t] + P[t], f"Total_Transfers_Link_GW{t}"

    # D. Free Transfer Usage Limit
    for t in TRANSFER_GWS:
        problem += T_Free[t] <= FT[t], f"FT_Usage_Limit_GW{t}"

    # E. Carryover Logic
    for t_current, t_prev in gw_pairs:
        problem += FT[t_current] - FT[t_prev] + T_Free[t_prev] == 1, f"FT_Carryover_GW{t_current}"

    # --- 4. Static FPL Constraints (Applied Every GW) ---

    # F. Initial Squad Fix (GW1 Base)
    first_gw = TRANSFER_GWS[0]  # This will be 23
    # H. Initial Squad Fix Constraint: X[i][first_gw] must be fixed based on current team
    for i in PLAYERS:
        # Use the actual GW ID (23) instead of the conceptual index (1)
        if i in initial_squad_ids:
            problem += X[i][first_gw] == 1, f"Initial_Squad_Fix_P{i}_GW{first_gw}"
        else:
            problem += X[i][first_gw] == 0, f"Initial_Squad_Fix_P{i}_GW{first_gw}"

    # G. Budget Limit (Assuming static player prices)
    for t in ALL_GWS:
        problem += lpSum(X[i][t] * player_costs[i] for i in PLAYERS) <= MAX_BUDGET, f"Budget_Limit_GW{t}"

    # H. Squad Size and Positional Limits
    for t in ALL_GWS:
        problem += lpSum(X[i][t] for i in PLAYERS) == 15, f"Squad_Size_GW{t}"  # Must have 15 players

        for pos_id, limit in POS_LIMITS.items():
            problem += lpSum(
                X[i][t] for i in PLAYERS if player_positions[i] == pos_id) <= limit, f"Max_Pos_Limit_{pos_id}_GW{t}"

    # I. Team Limits (Max 3 players per team)
    for team_id in all_team_ids:
        for t in ALL_GWS:
            problem += lpSum(X[i][t] for i in PLAYERS if player_teams[i] == team_id) <= 3, f"Team_Limit_{team_id}_GW{t}"

    # J. Starting XI and Captain Constraints
    for t in ALL_GWS:
        problem += lpSum(S[i][t] for i in PLAYERS) == 11, f"XI_Size_GW{t}"  # Must have 11 starters
        problem += lpSum(C[i][t] for i in PLAYERS) == 1, f"Captain_Count_GW{t}"  # Must have 1 captain

        for pos_id in POS_LIMITS:
            sum_starters = lpSum(S[i][t] for i in PLAYERS if player_positions[i] == pos_id)
            problem += sum_starters >= FORMATION_MIN[pos_id], f"Min_Form_P{pos_id}_GW{t}"
            problem += sum_starters <= FORMATION_MAX[pos_id], f"Max_Form_P{pos_id}_GW{t}"

        # C and S must be subsets of X, and C must be a subset of S
        for i in PLAYERS:
            problem += S[i][t] <= X[i][t], f"Starter_In_Squad_P{i}_GW{t}"
            problem += C[i][t] <= S[i][t], f"Captain_Is_Starter_P{i}_GW{t}"

    return problem


def get_mgo_gameweeks(bootstrap_data: Dict[str, Any], current_gw: int, window: int) -> List[int]:
    """Returns a list of GW IDs for the optimization window (e.g., [6, 7, 8, 9, 10])."""
    # Find the maximum GW ID available in the event data
    max_gw = max(e['id'] for e in bootstrap_data.get('events', []))

    # Return the list of GWs from current_gw + 1 up to the window limit or max_gw
    return [gw for gw in range(current_gw + 1, min(current_gw + window + 1, max_gw + 1))]


def forecast_s_matr_for_mgo(fpl_data: Dict[str, Any], fixtures_data_all: List[Dict[str, Any]],
                            matr_rating: List[Dict[str, Any]], mgo_gws: List[int]) -> Dict[Tuple[int, int], float]:
    """
    Forecasts the S-MATR score for every player for every GW in the MGO window.

    ASSUMPTION: Player PP90M (momentum) remains constant at its current value (calculated for GW1).
    Only the Fixture Difficulty (FDR) changes over time.
    """
    s_matr_current = calculate_s_matr_score(matr_rating)

    player_pp90m = {p['id']: p.get('s_matr_score', 0.0) for p in s_matr_current}

    mgo_scores: Dict[Tuple[int, int], float] = {}

    for gw_t in mgo_gws:
        window_size = mgo_gws[-1] - gw_t + 1  # Dynamic window size for the calculation (GWt to GW_End)

        # 2. Calculate Time-Weighted FDR (S-MATR DENOMINATOR) for the run starting at GW_t
        #    NOTE: We treat GW_t-1 as the 'current_gw' for the FDR calculation function
        fixture_run_score_t = calculate_fixture_run_score(
            fixtures_data_all, fpl_data, current_gw=gw_t, window=window_size
        )

        # 3. Combine constant PP90M with dynamic FDR
        for player_id, pp90m in player_pp90m.items():
            player_team_id = next(p['team'] for p in fpl_data.get('elements', []) if p['id'] == player_id)

            # The FDR score for the current GW window
            fdr_score_t = fixture_run_score_t.get(player_team_id, 999.0)

            # Recalculate S-MATR for GW_t: PP90M / (Weighted FDR + 0.1)
            if fdr_score_t == 999.0 or fdr_score_t == 0.0:
                s_matr_t = 0.0
            else:
                s_matr_t = pp90m / (fdr_score_t + 0.1)

            mgo_scores[(player_id, gw_t)] = round(s_matr_t, 4)

    return mgo_scores


def prepare_mgo_utility_data(fpl_data: Dict[str, Any]) -> Tuple[Dict, Dict, Dict, List]:
    """Extracts essential player/team data for MGO constraints."""
    player_costs = {}
    player_positions = {}
    player_teams = {}

    for p in fpl_data.get('elements', []):
        player_id = p['id']
        player_costs[player_id] = p['now_cost'] / 10.0  # Convert price to float
        player_positions[player_id] = p['element_type']
        player_teams[player_id] = p['team']

    all_team_ids = [t['id'] for t in fpl_data.get('teams', [])]

    return player_costs, player_positions, player_teams, all_team_ids


def run_starting_xi_optimization(optimal_squad: List[Dict[str, Any]]):
    """
    Solves for the optimal Starting XI and Captain from the chosen 15-player squad.
    Maximizes MATR score based on starting formation rules.
    """

    # 1. Initialize the LP Problem
    prob = LpProblem("FPL_Starting_XI_Optimization", LpMaximize)

    # Get the player IDs for the 15 players
    player_ids = [p['id'] for p in optimal_squad]
    player_data_map = {p['id']: p for p in optimal_squad}  # Map for easy data lookup

    # 2. Define Decision Variables (Y_i for Starter, Z_i for Captain)

    # Y_i: 1 if player i is a Starter, 0 otherwise
    starter_vars = LpVariable.dicts("Starter", player_ids, 0, 1, LpBinary)

    # Z_i: 1 if player i is the Captain, 0 otherwise
    captain_vars = LpVariable.dicts("Captain", player_ids, 0, 1, LpBinary)
    vice_captain_vars = LpVariable.dicts("ViceCaptain", player_ids, 0, 1, LpBinary)
    # 3. Define the Objective Function
    # Maximize: Sum(MATR_i * Y_i) + Sum(MATR_i * Z_i)  (Doubles Captain's score)
    prob += lpSum([
        player_data_map[i]['matr'] * starter_vars[i] + player_data_map[i]['matr'] * captain_vars[i]
        for i in player_ids
    ]), "Total_Starting_XI_Score"

    # 4. Define Constraints

    # A. Starting XI Size Constraint (Exactly 11 players must start)
    prob += lpSum([starter_vars[i] for i in player_ids]) == 11, "C_Starting_XI_Size"

    # B. Captain Constraints
    prob += lpSum([captain_vars[i] for i in player_ids]) == 1, "C_One_Captain"  # Exactly one captain
    for i in player_ids:
        # Captain must be one of the starters
        prob += captain_vars[i] <= starter_vars[i], f"C_Captain_Is_Starter_{i}"

        # C. Formation Constraints (1 GKP, and variable limits for others)
    POSITION_MAP = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
    prob += lpSum([vice_captain_vars[i] for i in player_ids]) == 1, "C_One_ViceCaptain"

    for i in player_ids:
        # 2. Vice Captain must be one of the starters
        prob += vice_captain_vars[i] <= starter_vars[i], f"C_VC_Is_Starter_{i}"

        # 3. Captain and Vice Captain cannot be the same player
        # Z_i + V_i <= 1 means that for any player i, they can be EITHER captain OR vice captain, but not both (1+1 <= 1 is false).
        prob += captain_vars[i] + vice_captain_vars[i] <= 1, f"C_C_and_VC_are_Different_{i}"

    # 1. GKP: Must start exactly 1 Goalkeeper
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 1
    ]) == 1, "C_GKP_Must_Start_One"

    # 2. DEF: 3 to 5 Defenders
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 2
    ]) >= 3, "C_DEF_Min_3"
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 2
    ]) <= 5, "C_DEF_Max_5"

    # 3. MID: 2 to 5 Midfielders
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 3
    ]) >= 2, "C_MID_Min_2"
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 3
    ]) <= 5, "C_MID_Max_5"

    # 4. FWD: 1 to 3 Forwards
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 4
    ]) >= 1, "C_FWD_Min_1"
    prob += lpSum([
        starter_vars[i] for i in player_ids if player_data_map[i]['pos'] == 4
    ]) <= 3, "C_FWD_Max_3"

    # 5. Solve the problem
    prob.solve()

    # 6. Extract Results
    if prob.status == LpStatusOptimal:
        starting_xi = []
        captain_id = None
        vice_captain_id = None
        for i in player_ids:
            player = player_data_map[i]

            if starter_vars[i].varValue == 1.0:
                is_captain = captain_vars[i].varValue == 1.0
                is_vice_captain = vice_captain_vars[i].varValue == 1.0
                starting_xi.append({
                    **player,
                    'is_captain': is_captain,
                    'is_vice_captain': is_vice_captain
                })
                if is_captain:
                    captain_id = i
                if is_vice_captain:
                    vice_captain_id = i

        return {
            "status": LpStatus[prob.status],
            "starting_xi": starting_xi,
            "bench": [p for p in optimal_squad if p['id'] not in [s['id'] for s in starting_xi]],
            "max_xi_score": value(prob.objective)
        }
    else:
        return {"status": LpStatus[prob.status], "starting_xi": [], "bench": [], "max_xi_score": 0}


def format_starting_xi_report(xi_result: Dict[str, Any]):
    """Prints the optimized starting XI and bench."""

    # Define position mapping for display
    POS_MAP = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}

    # 1. Starting XI Report
    starters = xi_result['starting_xi']
    starters.sort(key=lambda x: x['pos'])  # Sort by position for clean display

    # Calculate formation (e.g., 4-4-2)
    def_count = sum(1 for p in starters if p['pos'] == 2)
    mid_count = sum(1 for p in starters if p['pos'] == 3)
    fwd_count = sum(1 for p in starters if p['pos'] == 4)
    formation = f"{def_count}-{mid_count}-{fwd_count}"

    print("\n" + "=" * 80)
    print("⚽ OPTIMAL STARTING XI & CAPTAIN SELECTION 🌟")
    print(f"MAXIMUM EXPECTED SCORE (XI + Captain): {xi_result['max_xi_score']:.4f}")
    print(f"OPTIMAL FORMATION: {formation}")
    print("=" * 80)

    # Table Header
    print("{:<5} {:<15} {:<15} {:<8} {:<10} {:<10}".format(
        "POS", "Player Name", "Team", "Price", "MATR (S)", "Status"
    ))
    print("-" * 80)

    current_pos = None
    for player in starters:
        if player['pos'] != current_pos:
            current_pos = player['pos']
            print(f"\n--- {POS_MAP.get(current_pos)} ---")

        status_string = ''
        if player['is_captain']:
            status_string = '(C)'
        elif player['is_vice_captain']:  # NEW
            status_string = '(VC)'

        print("{:<5} {:<15} {:<15} {:<8} {:<10} {:<10}".format(
            POS_MAP.get(player['pos']),
            player['name'],
            player['team_name'],
            player['price'],
            player['matr'],
            status_string
        ))

    # 2. Bench Report
    bench = xi_result['bench']
    # Standard FPL bench ordering is GKP, DEF, MID, FWD (by position ID)
    bench.sort(key=lambda x: x['pos'])

    print("\n\n--- 🧍 SUBSTITUTES (Bench Order) ---")
    print("{:<5} {:<15} {:<15} {:<8} {:<10}".format(
        "POS", "Player Name", "Team", "Price", "MATR (S)"
    ))
    print("-" * 55)

    for player in bench:
        print("{:<5} {:<15} {:<15} {:<8} {:<10}".format(
            POS_MAP.get(player['pos']),
            player['name'],
            player['team_name'],
            player['price'],
            player['matr']
        ))
    print("-" * 55)

def format_optimal_squad_report(optimal_squad: List[Dict[str, Any]], total_matr_score: float, total_cost: float):
    """Prints the final optimal squad in a clean, categorized format."""

    # Define position mapping for display
    POS_MAP = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}

    # Sort the squad by position, then by MATR score within each position
    optimal_squad.sort(key=lambda x: (x['pos'], x['matr']), reverse=True)

    print("\n" + "=" * 80)
    print("🏆 OPTIMAL 15-PLAYER SQUAD SELECTED BY PuLP")
    print(f"MAXIMUM MATR Score (S): {total_matr_score:.4f}")
    print(f"TOTAL BUDGET USED: £{total_cost:.1f}M")
    print("=" * 80)

    # Table Header
    print("{:<5} {:<15} {:<15} {:<8} {:<10} {:<10}".format(
        "POS", "Player Name", "Team", "Price", "MATR (S)", "ID"
    ))
    print("-" * 80)

    current_pos = None

    # Print Players
    for player in optimal_squad:
        if player['pos'] != current_pos:
            current_pos = player['pos']
            print(
                f"\n--- {POS_MAP.get(current_pos)} ({len([p for p in optimal_squad if p['pos'] == current_pos])} Selected) ---")

        print("{:<5} {:<15} {:<15} {:<8} {:<10} {:<10}".format(
            POS_MAP.get(player['pos']),
            player['name'],
            player['team_name'],  # Truncate team name for display
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
    prob = LpProblem("FPL Squad Optimization", LpMaximize)

    # 2. Define Decision Variables
    # The variable keys are now the Player IDs
    player_vars = LpVariable.dicts("Select", player_ids, 0, 1, LpBinary)

    # 3. Define the Objective Function
    # Use player_ids for iteration
    prob += lpSum([player_data_dict[i]['matr'] * player_vars[i] for i in player_ids]), "Total_MATR_Score"

    # 4. Define Constraints

    # A. Squad Size Constraint (Total players must be 15)
    prob += lpSum([player_vars[i] for i in player_ids]) == 15, "Squad_Size_Constraint"

    # B. Budget Constraint
    prob += lpSum(
        [player_data_dict[i]['price'] * player_vars[i] for i in player_ids]) <= budget_cap, "Budget_Constraint"

    # C. Positional Constraints
    POSITION_LIMITS = {1: 2, 2: 5, 3: 5, 4: 3}
    for pos_id, limit in POSITION_LIMITS.items():
        # Iterate through players whose position matches the pos_id
        prob += lpSum([
            player_vars[i] for i in player_ids
            if player_data_dict[i]['pos'] == pos_id
        ]) == limit, f"Position_Constraint_{pos_id}"

    # D. Team Limit Constraint
    team_ids = {d['team_id'] for d in player_data_dict.values()}
    for team_id in team_ids:
        # Iterate through players whose team_id matches the current team_id
        prob += lpSum([
            player_vars[i] for i in player_ids
            if player_data_dict[i]['team_id'] == team_id
        ]) <= 3, f"Team_Limit_Constraint_{team_id}"

    # 5. Solve the problem
    prob.solve()

    # 6. Extract Results
    if prob.status == LpStatusOptimal:
        optimal_squad = []
        for i in player_ids:
            if player_vars[i].varValue == 1.0:
                optimal_squad.append(player_data_dict[i])

        total_cost = value(prob.objective)  # The objective function value (total MATR score)

        return {
            "status": LpStatus[prob.status],
            "total_matr_score": total_cost,
            "squad": optimal_squad
        }
    else:
        return {"status": LpStatus[prob.status], "squad": []}


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
            'matr': p.get('s_matr_score', 0.0)
        }

    # Sanity check is crucial here
    print(f"DEBUG: Total players successfully prepared for PuLP: {len(player_data_dict)}")

    return player_data_dict

FDR_WINDOW = 3
def calculate_matr(fpl_data, fixtures_data, available_player_ids) -> list[dict[str, Any]] | None:
    current_gw = get_current_gameweek_info(fpl_data)

    if current_gw is None:
        print("FATAL ERROR: Could not determine the current Gameweek. Cannot proceed.")
        # Handle error or use a safe fallback GW ID
    else:
        print(f"Current Gameweek determined: {current_gw['id']}")

        fixture_run_score = calculate_fixture_run_score(fixtures_data, fpl_data, current_gw['id'], FDR_WINDOW)
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
            fixtures_endpoint = "fixtures"
            # fixtures_endpoint = f"fixtures/?event={gw_id}"
            fixtures_data = get_fpl_data(fixtures_endpoint)

            if fixtures_data:
                available_player_ids = get_available_player_ids(fpl_data)
                available_matr_rating = calculate_matr(fpl_data, fixtures_data, available_player_ids)
                adjusted_matr_rating = calculate_s_matr_score(available_matr_rating)
                cleaned_data = prepare_optimization_data(adjusted_matr_rating, fpl_data)
                optimization_result = run_pulp_optimization(cleaned_data)
                if optimization_result['status'] == 'Optimal':
                    optimal_squad_gw1 = optimization_result['squad']
                    initial_squad_ids = [p['id'] for p in optimal_squad_gw1]

                    print(f"\n--- ✅ GW{gw_id} Optimal Squad Selected. Moving to MGO... ---")

                    gw1_s_matr_scores = {}
                    # 'adjusted_matr_rating' is the list of player dicts containing the GW1 's_matr_score'
                    for p in adjusted_matr_rating:
                        # Key is (player_id, gw_id)
                        gw1_s_matr_scores[(p['id'], gw_id)] = p['s_matr_score']

                    next_gw = gw_id  # e.g., 1

                    all_gws = list(range(next_gw, next_gw + FDR_LKFWD))
                    gws_to_forecast = list(range(next_gw + 1, next_gw + FDR_LKFWD))

                    # all_player_ids = get_all_player_ids(fpl_data)
                    # matr_rating = calculate_matr(fpl_data, fixtures_data, all_player_ids)

                    # Then call the forecast function:
                    mgo_forecasted_scores = forecast_s_matr_for_mgo(fpl_data, fixtures_data, available_matr_rating, gws_to_forecast)

                    # D. Combine GW1 and Forecasted Scores
                    mgo_scores = {**gw1_s_matr_scores, **mgo_forecasted_scores}

                    # B. Prepare Utility Data for Constraints
                    player_costs, player_positions, player_teams, all_team_ids = prepare_mgo_utility_data(fpl_data)

                    # Remove to use all players
                    scored_player_ids = {p_id for p_id, gw_t in mgo_scores.keys()}
                    MGO_PLAYERS_TEST = [
                        p_id for p_id in scored_player_ids
                        if p_id in available_player_ids
                    ]
                    # C. Run MGO
                    mgo_problem = solve_multi_gameweek_optimization(
                        all_gws=all_gws,
                        # all_player_data=fpl_data.get('elements', []),
                        all_player_ids=MGO_PLAYERS_TEST,
                        initial_squad_ids=initial_squad_ids,
                        player_scores_matr=mgo_scores,
                        player_costs=player_costs,
                        player_positions=player_positions,
                        player_teams=player_teams,
                        all_team_ids=all_team_ids
                    )

                    # D. Solve MGO
                    mgo_problem.solve()

                    print(f"\n--- 🏆 MGO Solution Status: {LpStatus[mgo_problem.status]} ---")

                    if LpStatus[mgo_problem.status] == 'Optimal':
                        report_mgo_strategy(
                            problem=mgo_problem,
                            all_player_data=fpl_data.get('elements', []),  # Assuming fpl_data is your main data source
                            mgo_gw_ids=all_gws,
                            initial_squad_ids=initial_squad_ids
                        )
                    else:
                        print("MGO failed to find an optimal solution.")

                    optimal_squad = optimization_result['squad']
                    total_matr_score = optimization_result['total_matr_score']
                    total_cost_used = sum(p['price'] for p in optimal_squad)
                    format_optimal_squad_report(optimal_squad, total_matr_score, total_cost_used)
                    xi_result = run_starting_xi_optimization(optimal_squad)
                    if xi_result['status'] == 'Optimal':
                        # 🌟 NEW CALL: Format and display the Starting XI
                        format_starting_xi_report(xi_result)
                    else:
                        print(f"Starting XI optimization failed. Status: {xi_result['status']}")
                    # You would then format and print the list of players by position.
                else:
                    print(f"Optimization failed. Status: {optimization_result['status']}")
            else:
                print("Failed to load fixtures data.")

