from typing import Any

import pulp


def optimise_transfer_strategy(
        current_squad:  list[dict[str, Any]],
        all_players: list[dict[str, Any]],
        money_itb=0.0,
        transfers_available=1):
    # 1. Setup Data
    current_ids = [p['id'] for p in current_squad]
    # Total Value = Cash ITB + Selling value of current players
    total_budget = money_itb + sum(p['price'] for p in current_squad)

    player_ids = [p['id'] for p in all_players]
    p_stats = {p['id']: p for p in all_players}

    prob = pulp.LpProblem("Single_Week_Transfer_Optimization", pulp.LpMaximize)

    # 2. Decision Variables
    x = pulp.LpVariable.dicts("squad", player_ids, cat=pulp.LpBinary)  # Owned (15)
    s = pulp.LpVariable.dicts("starter", player_ids, cat=pulp.LpBinary)  # Plays (11)
    tin = pulp.LpVariable.dicts("transfer_in", player_ids, cat=pulp.LpBinary)
    tout = pulp.LpVariable.dicts("transfer_out", player_ids, cat=pulp.LpBinary)

    # 3. Objective: Maximize Starting 11 RPPM
    # We add a tiny bonus for bench players so the bench isn't "random"
    prob += pulp.lpSum([
        s[p_id] * p_stats[p_id]['rppm'] for p_id in player_ids
        if p_stats[p_id]['status'] == 'a'
    ]) + pulp.lpSum([x[p_id] * 0.001 for p_id in player_ids])

    # 4. Constraints
    # Squad Size & Budget
    prob += pulp.lpSum([x[p_id] for p_id in player_ids]) == 15
    prob += pulp.lpSum([x[p_id] * p_stats[p_id]['price'] for p_id in player_ids]) <= total_budget

    # Linkage: Can only start if owned
    for p_id in player_ids:
        prob += s[p_id] <= x[p_id]

    # Transfers Available (Usually 1)
    prob += pulp.lpSum([tin[p_id] for p_id in player_ids]) <= transfers_available
    # Ensure In count matches Out count to keep squad at 15
    prob += pulp.lpSum([tin[p_id] for p_id in player_ids]) == pulp.lpSum([tout[p_id] for p_id in player_ids])

    # FIXED OWNERSHIP LOGIC
    for p_id in player_ids:
        is_in_current = 1 if p_id in current_ids else 0
        # New Squad = Old Squad + In - Out
        prob += x[p_id] == is_in_current + tin[p_id] - tout[p_id]

    # Position Constraints (Squad)
    for pos, req in {1: 2, 2: 5, 3: 5, 4: 3}.items():
        prob += pulp.lpSum([x[p_id] for p_id in player_ids if p_stats[p_id]['position_id'] == pos]) == req

    # Formation Constraints (Starting 11)
    prob += pulp.lpSum([s[p_id] for p_id in player_ids]) == 11
    prob += pulp.lpSum([s[p_id] for p_id in player_ids if p_stats[p_id]['position_id'] == 1]) == 1
    prob += pulp.lpSum([s[p_id] for p_id in player_ids if p_stats[p_id]['position_id'] == 2]) >= 3
    prob += pulp.lpSum([s[p_id] for p_id in player_ids if p_stats[p_id]['position_id'] == 3]) >= 3
    prob += pulp.lpSum([s[p_id] for p_id in player_ids if p_stats[p_id]['position_id'] == 4]) >= 1

    # Team Constraint
    teams = set(p['team_id'] for p in all_players)
    for t_id in teams:
        prob += pulp.lpSum([x[p_id] for p_id in player_ids if p_stats[p_id]['team_id'] == t_id]) <= 3

    # Uncomment to remove unavailable people
    # Availability: Cannot buy injured/unavailable players
    # prob += pulp.lpSum([tin[p_id] for p_id in player_ids if p_stats[p_id]['status'] != 'a']) == 0

    # 5. Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # 6. Result Extraction
    return {
        "in": [p_id for p_id in player_ids if tin[p_id].varValue == 1],
        "out": [p_id for p_id in player_ids if tout[p_id].varValue == 1]
    }