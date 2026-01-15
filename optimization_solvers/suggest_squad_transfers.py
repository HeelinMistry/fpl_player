def suggest_transfers(current_ids, all_players, future_gws, num_transfers=1, weight=0.1):
    def get_window_ev(p, gws):
        fixture_sum = sum(p['fixture_comparison'].get(gw, 0) for gw in gws)
        return p['rppm'] + (fixture_sum * weight)

    # 2. Separate current squad from the rest of the pool
    current_squad = [p for p in all_players if p['id'] in current_ids]
    available_pool = [p for p in all_players if p['id'] not in current_ids and p['status'] == 'a']

    # 3. Calculate EV for everyone
    for p in current_squad: p['window_ev'] = get_window_ev(p, future_gws)
    for p in available_pool: p['window_ev'] = get_window_ev(p, future_gws)

    # 4. Sort current squad by weakest links (lowest EV)
    current_squad_sorted = sorted(current_squad, key=lambda x: x['window_ev'])

    # 5. Find the best replacements
    transfer_suggestions = []

    # Simple logic: Try to replace the N weakest players
    for i in range(num_transfers):
        weak_player = current_squad_sorted[i]

        # Find best available player in same position and within budget
        # We assume selling price = current_price for simplicity
        candidates = [
            p for p in available_pool
            if p['position_id'] == weak_player['position_id']
               and p['price'] <= weak_player['price']
        ]

        if candidates:
            best_replacement = max(candidates, key=lambda x: x['window_ev'])
            gain = best_replacement['window_ev'] - weak_player['window_ev']

            if gain > 0:
                transfer_suggestions.append({
                    "OUT": weak_player,
                    "IN": best_replacement,
                    "Net_Gain": round(gain, 2)
                })

    return transfer_suggestions