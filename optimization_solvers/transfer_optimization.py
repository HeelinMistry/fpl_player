import pulp


def optimise_transfer_strategy(current_squad, all_players, future_gws, money_itb=100.0, weight=0.1):
    # Calculate starting budget
    budget = money_itb
    current_squad_ids = []
    for squad_player in current_squad:
        budget += squad_player['price']
        current_squad_ids.append(squad_player['id'])

    prob = pulp.LpProblem("Multi_Period_Transfer_Optimization", pulp.LpMaximize)
    player_ids = [p['id'] for p in all_players]

    # Map for easy status/points lookup
    player_stats = {p['id']: p for p in all_players}

    # 1. Decision Variables
    x = pulp.LpVariable.dicts("squad", (player_ids, future_gws), cat=pulp.LpBinary)
    tin = pulp.LpVariable.dicts("transfer_in", (player_ids, future_gws), cat=pulp.LpBinary)
    tout = pulp.LpVariable.dicts("transfer_out", (player_ids, future_gws), cat=pulp.LpBinary)

    # 2. Objective Function
    # We only count points if status == 'a'.
    # We subtract a small penalty (0.01) for holding an unavailable player
    # to force the solver to prefer 'a' players even on the bench.
    prob += pulp.lpSum([
        x[p_id][gw] * (
            (player_stats[p_id]['rppm'] + (player_stats[p_id]['fixture_comparison'].get(gw, 0) * weight))
            if player_stats[p_id]['status'] == 'a' else -0.01
        )
        for p_id in player_ids for gw in future_gws
    ])

    # 3. Constraints
    prev_gw = None
    for gw in future_gws:
        # Basic Squad Constraints
        prob += pulp.lpSum([x[p_id][gw] for p_id in player_ids]) == 15
        prob += pulp.lpSum([x[p_id][gw] * player_stats[p_id]['price'] for p_id in player_ids]) <= budget

        # Position Constraints
        for pos in [1, 2, 3, 4]:
            req = {1: 2, 2: 5, 3: 5, 4: 3}[pos]
            prob += pulp.lpSum([x[p_id][gw] for p_id in player_ids if player_stats[p_id]['position_id'] == pos]) == req

        # NEW: Availability Policy - Cannot TRANSFER IN an unavailable player
        prob += pulp.lpSum([
            tin[p_id][gw] for p_id in player_ids if player_stats[p_id]['status'] != 'a'
        ]) == 0

        # Transfer Limit: Max 1 per week
        prob += pulp.lpSum([tin[p_id][gw] for p_id in player_ids]) <= 1

        # Logic: Ownership Flow
        for p_id in player_ids:
            if prev_gw is None:
                is_in_initial = 1 if p_id in current_squad_ids else 0
                prob += x[p_id][gw] == is_in_initial + tin[p_id][gw] - tout[p_id][gw]
            else:
                prob += x[p_id][gw] == x[p_id][prev_gw] + tin[p_id][gw] - tout[p_id][gw]

        prev_gw = gw

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # 4. Extract Plan
    transfer_plan = {}
    for gw in future_gws:
        transfer_plan[gw] = {
            "in": [p_id for p_id in player_ids if tin[p_id][gw].varValue == 1],
            "out": [p_id for p_id in player_ids if tout[p_id][gw].varValue == 1]
        }
    return transfer_plan