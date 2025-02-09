import gym
from gym import spaces
import numpy as np
import random
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from tg.types import *

# --- Gym Environment Implementation ---

class PokerGymEnv(gym.Env):
    metadata = {"render.modes": ["human"]}

    def __init__(self,
                 timeout_interval: float = 1.0,
                 small_blind: int = 5,
                 big_blind: int = 10,
                 num_rounds: int = 1000,
                 default_stack: int = 5000,
                 max_players: int = 2):
        super(PokerGymEnv, self).__init__()

        # Configurable parameters
        self.timeout_interval = timeout_interval
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.num_rounds = num_rounds
        self.default_stack = default_stack
        self.max_players = max_players

        # Set up poker configuration
        self.config = PokerConfig(
            dealer_position=0,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            max_players=self.max_players
        )

        # Define observation space.
        # For example, the observation includes:
        #  - the pot size,
        #  - current target bet,
        #  - current round (as an index),
        #  - each player's stack (padded to max_players),
        #  - and community cards (as integer codes; padded to 5 cards).
        self.observation_space = spaces.Dict({
            'pot': spaces.Discrete(10000),
            'target_bet': spaces.Discrete(10000),
            'round': spaces.Discrete(len(PokerRound)),
            'players_stack': spaces.Box(low=0, high=10000, shape=(self.max_players,), dtype=np.int32),
            'cards': spaces.MultiDiscrete([52] * 5)
        })

        # Define action space.
        # Actions are a dict with:
        #  - action_type: 0 (fold), 1 (call), or 2 (raise)
        #  - raise_amount: the additional amount (if raising)
        self.action_space = spaces.Dict({
            'action_type': spaces.Discrete(3),
            'raise_amount': spaces.Discrete(10000)  # Adjust maximum as needed
        })

        # Internal variables
        self.current_round = 0
        self.done = False

        # Initialize the game state and return the initial observation.
        self.reset()

    def reset(self):
        """Reset the environment to an initial state and returns an initial observation."""
        self.current_round = 0
        self.done = False

        # Create players. For simplicity, player 0 is the agent.
        players = []
        for i in range(self.max_players):
            players.append(PokerPlayer(id=str(i), stack=self.default_stack, folded=False, current_bet=0))

        # Create initial shared state
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

        # Initialize deck and shuffle it
        self.deck = self._init_deck()

        # Deal two cards to each player (store in a dict keyed by player id)
        self.hands = {}
        for p in players:
            self.hands[p.id] = (self.deck.pop(), self.deck.pop())

        return self._get_obs()

    def _init_deck(self) -> List[Card]:
        """Initialize and shuffle a deck of 52 cards."""
        deck = [Card(rank=rank, suit=suit) for suit in Suit for rank in Rank]
        random.shuffle(deck)
        return deck

    def _get_obs(self):
        """Convert the current game state to an observation."""
        # Get each player's stack; pad with zeros if fewer than max_players
        players_stack = np.array([p.stack for p in self.state.players], dtype=np.int32)
        if len(players_stack) < self.max_players:
            players_stack = np.pad(players_stack, (0, self.max_players - len(players_stack)), 'constant')

        # Represent community cards as integer codes (0-51).
        # Here we define a simple mapping: (rank-1)*4 + suit_index.
        suit_order = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3}

        def card_to_int(card: Card) -> int:
            return (card.rank - 1) * 4 + suit_order[card.suit]

        cards_obs = [card_to_int(card) for card in self.state.cards]
        # Pad to 5 cards (if there are fewer)
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

    def step(self, action: Dict) -> Tuple[dict, float, bool, dict]:
        """
        Execute one time step within the environment.
        For simplicity, we assume:
          - The agent is always player 0.
          - The opponents act via simple rules (or are skipped).
          - A full betting round is simulated.
        """
        if self.done:
            return self._get_obs(), 0.0, True, {}

        # Parse the action
        action_type = action.get('action_type')
        raise_amount = action.get('raise_amount', 0)

        # Retrieve agent state (player 0)
        agent = self.state.players[0]

        # If already folded, nothing to do.
        if agent.folded:
            reward = -1.0
            self.done = True
            return self._get_obs(), reward, self.done, {}

        if action_type == 0:  # Fold
            agent.folded = True
            reward = -1.0
        elif action_type == 1:  # Call
            call_amount = self.state.target_bet - agent.current_bet
            call_amount = min(call_amount, agent.stack)
            agent.stack -= call_amount
            agent.current_bet += call_amount
            self.state.pot += call_amount
            reward = 0.0
        elif action_type == 2:  # Raise
            call_amount = self.state.target_bet - agent.current_bet
            total_bet = call_amount + raise_amount
            if total_bet > agent.stack:
                total_bet = agent.stack  # all-in if not enough
            agent.stack -= total_bet
            agent.current_bet += total_bet
            self.state.pot += total_bet
            self.state.target_bet = agent.current_bet
            reward = 0.0
        else:
            # Invalid action type; treat as fold.
            agent.folded = True
            reward = -1.0

        # Progress the round (simulate dealing and opponent actions)
        self._progress_round()

        # End the game if the round limit is reached or only one player remains.
        if self.current_round >= self.num_rounds or sum(not p.folded for p in self.state.players) <= 1:
            self.done = True
            # Reward based on change in agent's stack (could be adjusted)
            reward = agent.stack - self.default_stack

        return self._get_obs(), reward, self.done, {}

    def _progress_round(self):
        """Advance the game round and simulate minimal opponent activity."""
        if self.state.round == PokerRound.PRE_FLOP:
            self.state.round = PokerRound.FLOP
            # Deal the flop: 3 community cards
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
            self._resolve_showdown()
            self.current_round += 1
        elif self.state.round == PokerRound.SHOWDOWN:
            # Start a new hand if not finished
            self.current_round += 1
            self.reset()

    def _resolve_showdown(self):
        """
        A placeholder for showdown resolution.
        Here, we simply assume that any player who has not folded splits the pot.
        A more sophisticated version would evaluate hand strengths.
        """
        active_players = [p for p in self.state.players if not p.folded]
        if active_players:
            winnings = self.state.pot // len(active_players)
            for p in active_players:
                p.stack += winnings
        self.state.pot = 0

    def render(self, mode='human'):
        """Render the current game state."""
        print(f"--- Round: {self.state.round.value} ---")
        print(f"Pot: {self.state.pot} | Target Bet: {self.state.target_bet}")
        for p in self.state.players:
            print(f"Player {p.id} -> Stack: {p.stack}, Current Bet: {p.current_bet}, Folded: {p.folded}")
        print("Community Cards:")
        for card in self.state.cards:
            print(f"{card.rank.name} of {card.suit.name}")
        print("---------------------------")

    def close(self):
        """Cleanup if needed."""
        pass

# --- Example Usage ---

if __name__ == '__main__':
    # Create the environment with custom parameters.
    env = PokerGymEnv(timeout_interval=3.0, small_blind=5, big_blind=10, num_rounds=50, default_stack=500, max_players=4)
    obs = env.reset()
    env.render()

    done = False
    total_reward = 0
    while not done:
        # For testing, sample a random action from the action space.
        action = env.action_space.sample()
        obs, reward, done, info = env.step(action)
        total_reward += reward
        env.render()

    print("Game Over. Total reward:", total_reward)
