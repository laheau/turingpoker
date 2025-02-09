import itertools
import pickle
from treys import Deck, Card, Evaluator

evaluator = Evaluator()

def simulate_hand_equity(hand, num_opponents=1, num_simulations=1000):
    wins = 0
    for _ in range(num_simulations):
        deck = Deck()
        deck.shuffle()
        deck.cards = [card for card in deck.cards if card not in hand]
        # try:
        # deck.cards.remove(hand[0])
        # deck.cards.remove(hand[1])
        # except ValueError:
        #     pass  # Shouldn't happen with correct combinations
        community = deck.draw(5)
        opponents = [deck.draw(2) for _ in range(num_opponents)]
        # print(hand, community, opponents)
        our_rank = evaluator.evaluate((hand), community)
        opponent_ranks = [evaluator.evaluate(opp, community) for opp in opponents]
        if all(our_rank < opp_rank for opp_rank in opponent_ranks):
            wins += 1
    return wins / num_simulations if num_simulations > 0 else 0.0

def precompute_equity_table(num_opponents=1, num_simulations=10000):
    deck = Deck()
    all_cards = deck.cards
    all_combinations = itertools.combinations(all_cards, 2)
    equity_table = {}
    total = 1326  # C(52,2)
    count = 0
    for hand in all_combinations:
        hand = list(hand)
        key = tuple(sorted(hand))
        if key not in equity_table:
            equity = simulate_hand_equity(hand, num_opponents, num_simulations)
            equity_table[key] = equity
            count += 1
            if count % 10 == 0:
                print(f"Progress: {count}/{total} ({count/total*100:.2f}%) - {key}: {equity:.4f}")
    with open('equity_table.pkl', 'wb') as f:
        pickle.dump(equity_table, f)
    return equity_table

if __name__ == "__main__":
    precompute_equity_table(num_simulations=1000)