# This is a sample Python script.
import os

from pulp import *
from typing import Dict, Any, Tuple
from src.fantacy_analysis import *
from src.fantacy_api import get_fpl_data

def get_player_data_for_xi(player_id: int, player_data: Dict[int, Dict[str, Any]]) -> Dict[str, Any] | None:
    """Utility to safely retrieve a COPY of a player's full data dictionary by ID."""
    if player_id in player_data:
        player_details = player_data[player_id]
        return player_details.copy()
    return None

def report_mgo_strategy(
        problem: LpProblem,
        all_player_data: List[Dict[str, Any]],
        mgo_gw_ids: List[int],
        optimised_player_data: Dict[int, Dict[str, Any]],
        mgo_scores: Dict[tuple, float]
):
    """
    Analyzes the solved MGO problem to report the optimal strategy across the horizon.
    """
    if LpStatus[problem.status] != 'Optimal':
        print(f"MGO solution is not optimal. Status: {LpStatus[problem.status]}")
        return

    # --- Setup Mapping and Variables ---
    player_map = {p['id']: p.get('name', f"ID {p['id']}") for p in optimised_player_data.values()}
    variables = problem.variablesDict()
    gameweek_reports = collections.OrderedDict()

    # --- Iterate through each Gameweek in the MGO Horizon ---
    for t_current in mgo_gw_ids:
        report = {}
        squad_ids = set()
        optimal_squad_data = []

        for i in player_map.keys():  # Loop over the entire player universe
            x_key = f"X_{i}_{t_current}"
            score_key = (i, t_current)
            if x_key in variables and value(variables[x_key]) > 0.5:
                # squad_ids.add(i)
                player_details = get_player_data_for_xi(i, optimised_player_data)
                if player_details:
                    # ** CRITICAL STEP: LOOKUP MATR SCORE DIRECTLY FROM MGO_SCORES **
                    matr_score = mgo_scores.get(score_key, 0.0)
                    # Inject the score into the 'matr' key for the XI solver
                    player_details['matr'] = matr_score
                    optimal_squad_data.append(player_details)
                    if matr_score == 0.0:
                        print(
                            f"Warning: Score missing in mgo_scores for {player_details.get('web_name', i)} in GW {t_current}. Using 0.")

        if len(optimal_squad_data) == 15:
            # CALL THE XI OPTIMIZATION METHOD
            xi_result = run_starting_xi_optimization(optimal_squad_data)
            #

        else:
            xi_result = {"status": f"Squad Size Error ({len(optimal_squad_data)} players)", "max_xi_score": 0,
                         "starting_xi": [], "bench": [], "captain": None, "vice_captain": None}

        # 2. Determine STARTING XI and Captain (S, C)
        # starting_xi = []
        # captain_id = None
        # for i in squad_ids:  # Loop only over the 15 players currently owned
        #     s_key = f"S_{i}_{t_current}"
        #     c_key = f"C_{i}_{t_current}"
        #
        #     if s_key in variables and value(variables[s_key]) > 0.5:
        #         starting_xi.append(player_map[i])
        #
        #     if c_key in variables and value(variables[c_key]) > 0.5:
        #         captain_id = i
        #
        # report['Squad'] = sorted([player_map[i] for i in squad_ids])
        # report['XI'] = starting_xi
        # report['Captain'] = player_map.get(captain_id, "N/A")

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

        if xi_result['status'] == 'Optimal':
            report['XI_Status'] = 'Optimal'
            report['Total_Score'] = xi_result['max_xi_score']
            current_starting_xi = xi_result.get('starting_xi', [])
            current_bench = xi_result.get('bench', [])

            # --- CRITICAL FIX: Create a map of the full squad (starters + bench) by ID ---
            all_squad_players = current_starting_xi + current_bench
            squad_map_by_id = {p['id']: p for p in all_squad_players}

            # -------------------------------------------------------------
            # NEW LOGIC: Look up Captain and Vice-Captain using the IDs
            # -------------------------------------------------------------

            captain_id = xi_result.get('captain')
            vice_captain_id = xi_result.get('vice_captain')

            # Look up the full player dictionary using the ID
            captain_player = squad_map_by_id.get(captain_id)
            vice_captain_player = squad_map_by_id.get(vice_captain_id)

            report['Squad_Names'] = sorted([p.get('name', str(p['id'])) for p in all_squad_players])
            report['Starting_XI_Names'] = [p.get('name', str(p['id'])) for p in current_starting_xi]
            report['Bench_Names'] = [p.get('name', str(p['id'])) for p in current_bench]

            # Use the found player dictionary (which is guaranteed to be a dict or None)
            # The .get('name') call is now SAFE because captain_player is a dictionary.
            report['Captain'] = captain_player.get('name', str(captain_player['id'])) if captain_player else "N/A"
            report['Vice_Captain'] = vice_captain_player.get('name', str(
                vice_captain_player['id'])) if vice_captain_player else "N/A"

        else:
            # Handle the non-optimal case cleanly (using the squad from MGO, optimal_squad_data)
            report['XI_Status'] = xi_result['status']
            report['Total_Score'] = 0.0
            report['Squad_Names'] = sorted([p.get('name', str(p['id'])) for p in optimal_squad_data])
            report['Captain'] = 'N/A'
            report['Vice_Captain'] = 'N/A'
            report['Starting_XI_Names'] = []
            report['Bench_Names'] = []

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

        if is_transfer_gw:
            if report.get('Transfers In'):
                print(f"✅ Transfers IN: {', '.join(report['Transfers In'])}")
                print(f"❌ Transfers OUT: {', '.join(report['Transfers Out'])}")
                print(f"💰 Point Hit: {report['Hit']} points")
            else:
                print("➡️ **HOLD** (0 Transfers Made)")
            print(f"ℹ️ FT Available Next GW: {report['FT Available']}")

        if report['XI_Status'] == 'Optimal':
            print(f"⭐ **Captain:** {report['Captain']}")
            print(f"©️ **Vice-Captain:** {report['Vice_Captain']}")
            print(f"📈 **Expected XI Score:** {report['Total_Score']:.2f}")

            print(f"⚽ **Starting XI (11):**")
            print(f"   {', '.join(report['Starting_XI_Names'])}")
            print(f"🛋️ **Bench (4):**")
            print(f"   {', '.join(report['Bench_Names'])}")
        else:
            print(f"❌ **XI Selection Failed:** Status: {report['XI_Status']}")

    print("\n" + "=" * 80)

# --- MGO CONFIGURATION ---
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
                                      all_team_ids: List[int],
                                      initial_money_itb: float,  # e.g., 0.6
                                      initial_team_value: float,
                                      initial_fts: int) -> LpProblem:
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
    gw_pairs = list(zip(ALL_GWS[1:], ALL_GWS[:-1]))

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

    B = LpVariable.dicts("Bench_Boost", all_gws, 0, 1, LpBinary)

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
    t_start = ALL_GWS[0]
    # A. Squad Continuity: X_i_t == X_i_t-1 - O_i_t + I_i_t
    for i in PLAYERS:
        for t_current, t_prev in gw_pairs:
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
        if t_prev == t_start:  # This is the first transition (e.g., GW 22 -> GW 23)
            # FT[23] = initial_fts - T_Free[23] + 1
            # T_Free[t_current] is used for transfers INTO X[t_current].
            problem += FT[t_current] - initial_fts + T_Free[t_current] == 1, f"FT_Carryover_Initial_GW{t_current}"
        else:
            # This logic assumes T_Free[t_prev] is the FT used in the previous transfer window (t_prev)
            # This is complex due to indexing; we will keep the original implementation assuming T_Free is indexed
            # to the period *before* the transfer:
            problem += FT[t_current] - FT[t_prev] + T_Free[t_prev] == 1, f"FT_Carryover_Standard_GW{t_current}"
    # --- 4. Static FPL Constraints (Applied Every GW) ---

    # F. Initial Squad Fix (GW1 Base)
    first_gw = ALL_GWS[0]  # This will be 23
    # H. Initial Squad Fix Constraint: X[i][first_gw] must be fixed based on current team
    for i in PLAYERS:
        # Use the actual GW ID (23) instead of the conceptual index (1)
        if i in initial_squad_ids:
            problem += X[i][first_gw] == 1, f"Initial_Squad_Fix_P{i}_GW{first_gw}"
        else:
            problem += X[i][first_gw] == 0, f"Initial_Squad_Fix_P{i}_GW{first_gw}"

    # G. Budget Limit (Assuming static player prices)
    t_start = ALL_GWS[0]
    total_buying_power = initial_team_value + initial_money_itb
    problem += lpSum(
        X[i][t_start] * player_costs[i] for i in PLAYERS) <= total_buying_power, f"Budget_Limit_GW{t_start}"

    t_transfer_1 = TRANSFER_GWS[0]  # e.g., 23
    # Initial Bank ITB can be used for the first transfer set only.
    initial_money_in_bank = initial_money_itb

    problem += lpSum(I[i][t_transfer_1] * player_costs[i] for i in PLAYERS) \
               <= lpSum(O[i][t_transfer_1] * player_costs[i] for i in PLAYERS) + initial_money_in_bank, \
        f"Dynamic_Budget_T1_GW{t_transfer_1}"

    # Constraint for SUBSEQUENT TRANSFER GWs (GW 24, 25...):
    # For subsequent weeks, transfers must be budget-neutral (Buys <= Sells).
    for t in TRANSFER_GWS[1:]:  # Iterates over GW 24, 25
        problem += lpSum(I[i][t] * player_costs[i] for i in PLAYERS) \
                   <= lpSum(O[i][t] * player_costs[i] for i in PLAYERS), f"Dynamic_Budget_Subsequent_GW{t}"
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
    prob = LpProblem("FPL_Starting_XI_Optimization", LpMaximize)

    player_ids = [p['id'] for p in optimal_squad]
    player_data_map = {p['id']: p for p in optimal_squad}

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

    prob.solve()
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
            "max_xi_score": value(prob.objective),
            "captain": captain_id,  # <-- MUST be present
            "vice_captain": vice_captain_id
        }
    else:
        return {
            "status": LpStatus[prob.status],
            "max_xi_score": 0,
            "starting_xi": [],
            "bench": [],
            "captain": None,
            "vice_captain": None
        }

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

    prob.solve()
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

    player_to_team_id = {p['id']: p['team'] for p in elements}
    player_data_dict: Dict[int, Dict[str, Any]] = {}

    for p in adjusted_rating:
        player_id = p.get('id')
        if not player_id: continue

        team_id = player_to_team_id.get(player_id)

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
    print(f"DEBUG: Total players successfully prepared for PuLP: {len(player_data_dict)}")
    return player_data_dict

PLAYER_DIR = 'player_history_dumps'
def calculate_matr(fpl_data, fixtures_data, available_player_ids, fdr_window = 5) -> list[dict[str, Any]] | None:
    current_gw = get_current_gameweek_info(fpl_data)
    if current_gw is None:
        print("FATAL ERROR: Could not determine the current Gameweek. Cannot proceed.")
    else:
        print(f"Current Gameweek determined: {current_gw['id']}")

        fixture_run_score = calculate_fixture_run_score(fixtures_data, fpl_data, current_gw['id'], fdr_window)
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
                # Store only the 'history' part which contains GW-by-GW data
                player_history_data[player_id] = player_summary['history']

        print(f"Successfully fetched history for {len(player_history_data)} players.")

        player_momentum = calculate_momentum_scores(player_history_data, current_gw['id'])
        return calculate_multi_window_matr(player_momentum, fixture_run_score, fpl_data)


# Press the green button in the gutter to run the script.
FDR_LKFWD = 5       # Limit to 5
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

    if not fpl_data:
        print("Failed to load core FPL data. Cannot continue.")
    else:
        view_fpl_data_summary(fpl_data)
        current_gw_info = get_current_gameweek_info(fpl_data)
        if not current_gw_info:
            print("Could not identify the next gameweek. It might be the end of the season.")
        else:
            gw_id = current_gw_info['id']
            print(f"✅ Current Gameweek Identified: **Gameweek {gw_id}**")
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

            print(f'window={FDR_LKFWD}')
            if fixtures_data:
                available_player_ids = get_available_player_ids(fpl_data)
                available_matr_rating = calculate_matr(fpl_data, fixtures_data, available_player_ids, FDR_LKFWD)
                adjusted_matr_rating = calculate_s_matr_score(available_matr_rating)

                optimised_player_data = prepare_optimization_data(adjusted_matr_rating, fpl_data)
                optimization_result = run_pulp_optimization(optimised_player_data)
                if optimization_result['status'] == 'Optimal':
                    optimal_squad_gw1 = optimization_result['squad']
                    initial_squad_ids = [p['id'] for p in optimal_squad_gw1]

                    print(f"\n--- ✅ GW{gw_id} Optimal Squad Selected. Moving to MGO... ---")
                    print(f"\n--- {initial_squad_ids} ---")
                    optimal_squad = optimization_result['squad']
                    total_matr_score = optimization_result['total_matr_score']
                    total_cost_used = sum(p['price'] for p in optimal_squad)

                    initial_gw_s_matr_scores = {}
                    for p in adjusted_matr_rating:
                        # Key is (player_id, gw_id)
                        initial_gw_s_matr_scores[(p['id'], gw_id)] = p['s_matr_score']

                    all_gws = list(range(gw_id, gw_id + (FDR_LKFWD+1)))
                    gws_to_forecast = list(range(gw_id + 1, gw_id + (FDR_LKFWD+1)))
                    mgo_forecasted_scores = forecast_s_matr_for_mgo(fpl_data, fixtures_data, available_matr_rating, gws_to_forecast)
                    mgo_scores = {**initial_gw_s_matr_scores, **mgo_forecasted_scores}
                    player_costs, player_positions, player_teams, all_team_ids = prepare_mgo_utility_data(fpl_data)

                    # makes sure players are playing
                    scored_player_ids = {p_id for p_id, gw_t in mgo_scores.keys()}
                    player_ids_selection = [
                        p_id for p_id in scored_player_ids
                        if p_id in available_player_ids
                    ]
                    # C. Run MGO
                    mgo_problem = solve_multi_gameweek_optimization(
                        all_gws=all_gws,
                        all_player_ids=player_ids_selection,
                        initial_squad_ids=initial_squad_ids,
                        player_scores_matr=mgo_scores,
                        player_costs=player_costs,
                        player_positions=player_positions,
                        player_teams=player_teams,
                        all_team_ids=all_team_ids,
                        initial_money_itb=100-total_cost_used,
                        initial_team_value=total_cost_used,
                        initial_fts=1
                    )

                    # D. Solve MGO
                    mgo_problem.solve()

                    print(f"\n--- 🏆 MGO Solution Status: {LpStatus[mgo_problem.status]} ---")

                    if LpStatus[mgo_problem.status] == 'Optimal':
                        report_mgo_strategy(
                            problem=mgo_problem,
                            all_player_data=fpl_data.get('elements', []),  # Assuming fpl_data is your main data source
                            mgo_gw_ids=all_gws,
                            optimised_player_data=optimised_player_data,
                            mgo_scores=mgo_scores,
                        )
                    else:
                        print("MGO failed to find an optimal solution.")
                else:
                    print(f"Optimization failed. Status: {optimization_result['status']}")
            else:
                print("Failed to load fixtures data.")

