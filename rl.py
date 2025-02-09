import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np

from tg.bot import Bot

device = torch.device(
    "cuda" if torch.cuda.is_available() else
    "mps" if torch.backends.mps.is_available() else
    "cpu"
)

def encode(state, hand):
    return None

class RL(Bot):
    def __init__(self, host, port, room, username, model):
        super().__init__(host, port, room, username)
        self.model = model

    def act(self, state, hand):
        me = None
        for player in state.players:
            if player.id == self.username:
                me = player
                break
        state = encode(state, hand)
        action_distribution = self.model(state)
        self.distributions.append(action_distribution)

        raise_to = (np.argmax(action_distribution) - 1) * me.stack
        cost_to_play = min(state.target_bet-me.current_bet, me.stack)

        if raise_to > state.target_bet:
            return {'type': 'raise', 'amount': raise_to-state.target_bet}
        elif raise_to >= cost_to_play or cost_to_play == 0:
            return {'type': 'call'}
        print('fold')
        return {'type': 'fold'}

    def opponent_action(self, action, player):

        pass

    def game_over(self, payouts):
        loss = 
        self.actions = torch.tensor(self.actions)
        payout = payouts[self.username]
        if payout > 0:
            target = F.onehot(torch.argmax(self.distributions), self.model.OUTPUT_SIZE)
        else:
            target = torch.ones(len(self.actions), self.model.OUTPUT_SIZE)
            target[torch.arange(len(self.actions)), self.actions] = 0
            target = target / (self.model.OUTPUT_SIZE - 1)

        

            
    def start_game(self, my_id, username):
        self.my_id = my_id
        self.username = username
        self.distributions = []
        print('start game', my_id)


class Agent(nn.Module):
    def __init__(self):
        super().__init__()
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(28*28, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, 100),
        )

    def forward(self, x):
        x = self.flatten(x)
        logits = self.linear_relu_stack(x)
        return logits
    

