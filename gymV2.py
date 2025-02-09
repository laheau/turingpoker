import gym
from gym import spaces
import numpy as np
import random
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from tg.types import *
from treys import Card as TreysCard, Evaluator

# --- Gym Environment Implementation ---

class PokerGymEnv(gym.Env):
    """
    An RL Gym environment for Texas Hold'em poker with the following features:
      1) Uses the treys package to evaluate hands at showdown.
      2) Tracks previous actions in self.history.
      3) Plays multiple hands (rounds) in one episode.
      4) Rotates the dealer and blind positions after each hand.
    """
    metadata = {"render.modes": ["human"]}

    def __init__(self,
                 timeout_interval: float = 5.0,
                 small_blind: int = 10,
                 big_blind: int = 20,
                 num_hands: int = 100,
                 default_stack: int = 1000,
                 max_players: int = 6):
        super(PokerGymEnv, self).__init__()

        # Configurable parameters
        self.timeout_interval = timeout_interval
        self.config = PokerConfig(
            dealer_position=0,  # initial dealer (index 0)
            small_blind=small_blind,
            big_blind=big_blind,
            max_players=max_players
        )
        self.num_hands = num_hands
        self.default_stack = default_stack

        # Create observation space.
        # Observation includes:
        #   - pot size, target bet, current round (as index),
        #   - each player's stack (padded to max_players),
        #   - and community cards (as integer codes; padded to 5 cards).
        self.observation_space = spaces.Dict({
            'pot': spaces.Discrete(10000),
            'target_bet': spaces.Discrete(10000),
            'round': spaces.Discrete(len(PokerRound)),
            'players_stack': spaces.Box(low=0, high=10000, shape=(self.config.max_players,), dtype=np.int32),
            'cards': spaces.MultiDiscrete([52] * 5)
        })

        # Define action space.
        # Actions are a dict with:
        #   - action_type: 0 (fold), 1 (call), 2 (raise)
        #   - raise_amount: additional amount (if raising)
        self.action_space = spaces.Dict({
            'action_type': spaces.Discrete(3),
            'raise_amount': spaces.Discrete(10000)
        })

        # Internal variables to track game progress
        self.history: List[dict] = []  # To store previous actions
        self.current_hand = 0         # Number of hands played so far
        self.done = False

        # Will hold the current game state, players’ hole cards, and deck.
        self.state: PokerSharedState = None
        self.hands: Dict[PlayerID, Tuple[Card, Card]] = {}
        self.deck: List[Card] = []

        # Initialize the game (players, positions, etc.)
        self._init_game()

    def _init_game(self):
        """Initialize players and game state (only once per episode)."""
        players = []
        for i in range(self.config.max_players):
            players.append(PokerPlayer(id=str(i),
                                       stack=self.default_stack,
                                       folded=False,
                                       current_bet=0))
        # Initialize shared state.
        self.state = PokerSharedState(
            dealer_position=self.config.dealer_position,
            small_blind=self.config.small_blind,
            big_blind=self.config.big_blind,
            pot=0,
            target_bet=self.config.big_blind,
            players=players,
            round=PokerRound.PRE_FLOP,
            done=False,
            cards=[]
        )
        # Initialize history and hand counter.
        self.history = []
        self.current_hand = 0

        # Start the first hand.
        self._start_new_hand()

    def reset(self):
        """Resets the environment (i.e. starts a new episode)."""
        self._init_game()
        return self._get_obs()

    def _init_deck(self) -> List[Card]:
        """Return a new, shuffled deck of 52 cards."""
        deck = [Card(rank=rank, suit=suit) for suit in Suit for rank in Rank]
        random.shuffle(deck)
        return deck

    def _treys_card_str(self, card: Card) -> str:
        """Converts our Card to a string representation for treys (e.g., 'Ah' for Ace of hearts)."""
        rank_map = {
            Rank.ACE: 'A',
            Rank.TWO: '2',
            Rank.THREE: '3',
            Rank.FOUR: '4',
            Rank.FIVE: '5',
            Rank.SIX: '6',
            Rank.SEVEN: '7',
            Rank.EIGHT: '8',
            Rank.NINE: '9',
            Rank.TEN: 'T',
            Rank.JACK: 'J',
            Rank.QUEEN: 'Q',
            Rank.KING: 'K'
        }
        suit_map = {
            Suit.HEARTS: 'h',
            Suit.DIAMONDS: 'd',
            Suit.CLUBS: 'c',
            Suit.SPADES: 's'
        }
        return f"{rank_map[card.rank]}{suit_map[card.suit]}"

    def _get_obs(self):
        """Construct the observation from the current state."""
        # Get player stacks (pad if necessary)
        players_stack = np.array([p.stack for p in self.state.players], dtype=np.int32)
        if len(players_stack) < self.config.max_players:
            players_stack = np.pad(players_stack, (0, self.config.max_players - len(players_stack)), 'constant')

        # Convert community cards to integer codes (0-51). Use the following mapping:
        # code = (rank - 1)*4 + suit_index. Define suit order as: clubs, diamonds, hearts, spades.
        suit_order = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3}

        def card_to_int(card: Card) -> int:
            return (card.rank - 1) * 4 + suit_order[card.suit]

        cards_obs = [card_to_int(card) for card in self.state.cards]
        # Pad to 5 cards if needed.
        while len(cards_obs) < 5:
            cards_obs.append(0)

        obs = {
            'pot': self.state.pot,
            'target_bet': self.state.target_bet,
            'round': list(PokerRound).index(self.state.round),
            'players_stack': players_stack,
            'cards': np.array(cards_obs, dtype=np.int32)
        }
        return obs

    def _rotate_positions(self):
        """Rotate the dealer button (and implicitly the blinds) after each hand."""
        num_players = len(self.state.players)
        # Rotate dealer: move to the next player (assume all players still play).
        self.config.dealer_position = (self.config.dealer_position + 1) % num_players
        self.state.dealer_position = self.config.dealer_position

    def _start_new_hand(self):
        """Prepare a new hand while keeping persistent game state (e.g. stacks, history, etc.)."""
        if self.current_hand > 0:
            # Rotate positions only after the first hand.
            self._rotate_positions()

        # Reset hand-specific state.
        for p in self.state.players:
            p.current_bet = 0
            p.folded = False
        self.state.pot = 0
        self.state.cards = []

        # Initialize a new deck and deal hole cards.
        self.deck = self._init_deck()
        self.hands = {}
        for p in self.state.players:
            self.hands[p.id] = (self.deck.pop(), self.deck.pop())

        # Post blinds.
        num_players = len(self.state.players)
        small_blind_position = (self.config.dealer_position + 1) % num_players
        big_blind_position = (self.config.dealer_position + 2) % num_players
        self.small_blind_position = small_blind_position
        self.big_blind_position = big_blind_position

        small_blind_player = self.state.players[small_blind_position]
        big_blind_player = self.state.players[big_blind_position]

        sb = min(self.config.small_blind, small_blind_player.stack)
        small_blind_player.stack -= sb
        small_blind_player.current_bet = sb

        bb = min(self.config.big_blind, big_blind_player.stack)
        big_blind_player.stack -= bb
        big_blind_player.current_bet = bb

        self.state.pot += (sb + bb)
        self.state.target_bet = bb  # The current bet to call is the big blind

        # Set the betting round and whose turn (first to act is the player after big blind).
        self.state.round = PokerRound.PRE_FLOP
        self.state.whose_turn = self.state.players[(big_blind_position + 1) % num_players].id

        self.current_hand += 1

    def step(self, action: Dict) -> Tuple[dict, float, bool, dict]:
        """
        Process one agent action and advance the hand.
        
        The agent is assumed to be player '0'. This method:
          - Processes the agent’s action (fold, call, or raise).
          - Logs the action in history.
          - Advances the betting round.
          - If the round reaches showdown, evaluates hands using treys,
            splits the pot, and then (if not at the final hand) starts a new hand.
        """
        if self.done:
            return self._get_obs(), 0.0, True, {}

        # For simplicity, we process only the agent’s action (player 0).
        agent = self.state.players[0]

        # Record the action in history.
        self.history.append({
            'hand': self.current_hand,
            'round': self.state.round.value,
            'player': agent.id,
            'action': action
        })

        action_type = action.get('action_type')
        raise_amount = action.get('raise_amount', 0)
        reward = 0.0

        # If the agent is already folded, assign a negative reward.
        if agent.folded:
            reward = -1.0
        else:
            if action_type == 0:  # Fold
                agent.folded = True
                reward = -1.0
            elif action_type == 1:  # Call
                call_amount = self.state.target_bet - agent.current_bet
                call_amount = min(call_amount, agent.stack)
                agent.stack -= call_amount
                agent.current_bet += call_amount
                self.state.pot += call_amount
            elif action_type == 2:  # Raise
                call_amount = self.state.target_bet - agent.current_bet
                total_bet = call_amount + raise_amount
                if total_bet > agent.stack:
                    total_bet = agent.stack  # all-in if insufficient chips
                agent.stack -= total_bet
                agent.current_bet += total_bet
                self.state.pot += total_bet
                self.state.target_bet = agent.current_bet
            else:
                # If action is not recognized, treat it as a fold.
                agent.folded = True
                reward = -1.0

        # (Optional) --- Here you could simulate simple opponent actions ---
        # For this example, opponents are not actively modeled.

        # Advance the betting round.
        self._progress_round()

        # If we've reached showdown, resolve the hand.
        if self.state.round == PokerRound.SHOWDOWN:
            reward = self._resolve_showdown()  # Evaluate hands and split pot.
            # If there are still hands left in the episode, start a new hand.
            if self.current_hand < self.num_hands:
                self._start_new_hand()
            else:
                self.done = True

        return self._get_obs(), reward, self.done, {}

    def _progress_round(self):
        """Advance the betting round (simulate dealing community cards)."""
        if self.state.round == PokerRound.PRE_FLOP:
            self.state.round = PokerRound.FLOP
            # Deal the flop (3 community cards).
            for _ in range(3):
                self.state.cards.append(self.deck.pop())
        elif self.state.round == PokerRound.FLOP:
            self.state.round = PokerRound.TURN
            self.state.cards.append(self.deck.pop())
        elif self.state.round == PokerRound.TURN:
            self.state.round = PokerRound.RIVER
            self.state.cards.append(self.deck.pop())
        elif self.state.round == PokerRound.RIVER:
            self.state.round = PokerRound.SHOWDOWN
        # (SHOWDOWN is handled in step())

    def _resolve_showdown(self) -> float:
        """
        Evaluate the showdown using the treys package.
        Active (non-folded) players’ hands are evaluated along with the community cards.
        The best hand(s) win the pot, which is split equally.
        
        Returns:
            A reward for the agent (player 0) computed as the net change in chips relative to the starting stack.
        """
        evaluator = Evaluator()
        active_players = [p for p in self.state.players if not p.folded]
        if not active_players:
            return -1.0  # If no players are active, penalize the agent.

        # Convert community cards to treys format.
        community = [TreysCard.new(self._treys_card_str(card)) for card in self.state.cards]
        scores = {}
        for p in active_players:
            hole = self.hands[p.id]
            hole_treys = [TreysCard.new(self._treys_card_str(card)) for card in hole]
            score = evaluator.evaluate(hole_treys, community)
            scores[p.id] = score

        best_score = min(scores.values())
        winners = [pid for pid, score in scores.items() if score == best_score]

        # Split the pot among winners.
        winnings = self.state.pot // len(winners)
        for p in active_players:
            if p.id in winners:
                p.stack += winnings

        # Compute the reward for the agent (player 0) as the difference relative to the starting stack.
        agent = self.state.players[0]
        reward = agent.stack - self.default_stack
        # Clear the pot for the next hand.
        self.state.pot = 0
        return reward

    def render(self, mode='human'):
        """Prints out the current state for debugging."""
        print(f"--- Hand: {self.current_hand} | Round: {self.state.round.value} ---")
        print(f"Pot: {self.state.pot} | Target Bet: {self.state.target_bet}")
        for p in self.state.players:
            print(f"Player {p.id} -> Stack: {p.stack}, Current Bet: {p.current_bet}, Folded: {p.folded}")
        print("Community Cards:")
        for card in self.state.cards:
            print(f"{card.rank.name} of {card.suit.name}")
        print("Recent History:")
        for entry in self.history[-5:]:
            print(entry)
        print("---------------------------")

    def close(self):
        """Any cleanup if needed."""
        pass

# --- Example Usage ---

if __name__ == '__main__':
    # Create the environment with custom parameters.
    env = PokerGymEnv(timeout_interval=3.0, small_blind=5, big_blind=10, num_hands=5, default_stack=500, max_players=4)
    obs = env.reset()
    env.render()

    total_reward = 0
    done = False

    # For demonstration, run a loop where we take random actions until the episode is done.
    while not done:
        action = env.action_space.sample()
        obs, reward, done, info = env.step(action)
        total_reward += reward
        env.render()

    print("Game Over. Total reward:", total_reward)
