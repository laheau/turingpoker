import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np

from tg.bot import Bot

parser = argparse.ArgumentParser(
    prog='Template bot',
    description='A Turing Games poker bot that always checks or calls, no matter what the target bet is (it never folds and it never raises)')

parser.add_argument('--port', type=int, default=1999,
                    help='The port to connect to the server on')
parser.add_argument('--host', type=str, default='localhost',
                    help='The host to connect to the server on')
parser.add_argument('--room', type=str, default='my-new-room',
                    help='The room to connect to')
parser.add_argument('--username', type=str, default='bot',
                    help='The username for this bot (make sure it\'s unique)')

args = parser.parse_args()

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
        self.optimiser = torch.optim.Adam(self.model.parameters())

    def act(self, state, hand):
        pot = state.pot
        round = self.convert_round(state.round)
        common = [self.convert_card(c) for c in state.cards]
        us_hand = [self.convert_card(c) for c in hand]
        us_info, others_info = [], []
        for player in state.players:
            if player.id == self.actual:
                us_info = [player.current_bet, player.stack]
            else:
                others_info.append(0 if player.folded else player.current_bet)
                others_info.append(0 if player.folded else player.stack)

        hand_mask, common_mask = [0]*52, [0]*52
        for card in us_hand: hand_mask[card] = 1
        for card in common: common_mask[card] = 1

        info = us_info+others_info

        # model inference
        model_state = np.array(hand_mask+common_mask+[pot, round]+info)

        inf = self.model.forward(model_state)
        action = np.argmax(inf)

        if (action == 0): return {'type': 'fold'}
        elif (action == 1): return {'type': 'call'}

        raise_amount = us_info[1]*(action-1)*(rate/100)
        return {'type': 'raise', 'amount': raise_amount}

    def opponent_action(self, action, player):

        pass

    def game_over(self, payouts):
       

        loss_fn = nn.NLLLoss(reduction='none')
        self.actions = torch.tensor(self.actions)
        payout = payouts[self.username]
        if payout > 0:
            targets = F.onehot(torch.argmax(self.distributions), self.model.OUTPUT_SIZE)
        else:
            targets = torch.ones(len(self.actions), self.model.OUTPUT_SIZE)
            targets[torch.arange(len(self.actions)), self.actions] = 0
            targets = targets / (self.model.OUTPUT_SIZE - 1)

        
        loss = torch.dot(loss_fn(self.distributions, targets), torch.abs(payout))
        self.optimiser.zero_grad()
        loss.backward()
        self.optimiser.step()



            
    def start_game(self, my_id):
        self.my_id = my_id
        self.username = args.username
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
    

