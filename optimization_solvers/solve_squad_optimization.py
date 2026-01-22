import pulp


def optimize_squad(player_data, budget=100.0):
    # 1. Initialize the Problem
    prob = pulp.LpProblem("FPL_Squad_Optimization", pulp.LpMaximize)

    # 2. Decision Variables: 1 if player is selected, 0 otherwise
    player_vars = pulp.LpVariable.dicts("player", [p['id'] for p in player_data], cat=pulp.LpBinary)
    for p in player_data:
        if p['status'] != 'a':
            # This forces the decision variable to be 0 (Not Selected)
            prob += player_vars[p['id']] == 0
    # 3. Objective Function
    # We maximize: RPPM + (Fixture_Score * Weight)
    # Adjust fixture_weight to prioritize long-term form vs immediate fixtures
    prob += pulp.lpSum([
        player_vars[p['id']] * (p['rppm'])
        # player_vars[p['id']] * (p['rppm'])
        for p in player_data
    ])

    # 4. Constraints
    # Total Players = 15
    prob += pulp.lpSum([player_vars[p['id']] for p in player_data]) == 15

    # Budget Constraint
    prob += pulp.lpSum([player_vars[p['id']] * p['price'] for p in player_data]) <= budget

    # Position Constraints
    prob += pulp.lpSum([player_vars[p['id']] for p in player_data if p['position_id'] == 1]) == 2  # GKs
    prob += pulp.lpSum([player_vars[p['id']] for p in player_data if p['position_id'] == 2]) == 5  # DEFs
    prob += pulp.lpSum([player_vars[p['id']] for p in player_data if p['position_id'] == 3]) == 5  # MIDs
    prob += pulp.lpSum([player_vars[p['id']] for p in player_data if p['position_id'] == 4]) == 3  # FWDs

    # Team Constraint (Max 3 players per team)
    teams = set(p['team_id'] for p in player_data)
    for t_id in teams:
        prob += pulp.lpSum([player_vars[p['id']] for p in player_data if p['team_id'] == t_id]) <= 3

    # 5. Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # 6. Extract Results
    selected_ids = [p_id for p_id in player_vars if player_vars[p_id].varValue == 1]
    selected_players = [p for p in player_data if p['id'] in selected_ids]

    return selected_players
