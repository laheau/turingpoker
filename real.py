#!/usr/bin/env python3
import asyncio
import os
import random
from typing import Tuple
import argparse
import treys
import time
import numpy as np
import torch.nn.functional as F
from tg.bot import Bot
from tg.types import *
from models import *





parser = argparse.ArgumentParser(
    prog='Template bot',
    description='A Turing Games poker bot that always checks or calls, no matter what the target bet is (it never folds and it never raises)')

parser.add_argument('--port', type=int, default=1999,
                    help='The port to connect to the server on')
parser.add_argument('--host', type=str, default='localhost',
                    help='The host to connect to the server on')
parser.add_argument('--room', type=str, default=random.getrandbits(128),
                    help='The room to connect to')
parser.add_argument('--username', type=str, default='bot',
                    help='The username for this bot (make sure it\'s unique)')

args = parser.parse_args()

player_count = 2
rate = 5
raise_stages = int(100/rate)

class TemplateBot(Bot):
    def act(self, state, hand):
        # print('asked to act')
        # print('acting', state, hand, self.my_id)
        return {'type': 'call'}

    def opponent_action(self, action, player):
        #print('opponent action?', action, player)
        pass

    def game_over(self, payouts):
        # global cnt
        pass
        #print('game over', payouts)
        # cnt += 1
        # print(cnt)

    def start_game(self, my_id):
        self.my_id = my_id
        pass

class RLBot(Bot):
    def load(self, filename = None):
        self.model = ModelV1(52+52+2+2+2, 2+raise_stages, NN)
        if (filename): self.model.load_state(filename)
<<<<<<< HEAD

=======
        self.optimiser = torch.optim.Adam(self.model.parameters(), lr=0.0001)
>>>>>>> refs/remotes/origin/mcgill-tournament
    def convert_card(self, card):
        f = 0
        match Suit(card.suit):
            case Suit.HEARTS: f = 0
            case Suit.DIAMONDS: f = 1
            case Suit.CLUBS: f = 2
            case Suit.SPADES: f = 3
        return card.rank+(f*13)-1
    
    def convert_round(self, round):
        match PokerRound(round):
            case PokerRound.PRE_FLOP: return 0
            case PokerRound.FLOP: return 1
            case PokerRound.TURN: return 2
            case PokerRound.RIVER: return 3
            case PokerRound.SHOWDOWN: return 4
        return -1

    def act(self, state, hand):
        # print('act', state)
        pot = state.pot
        round = self.convert_round(state.round)
        common = [self.convert_card(c) for c in state.cards]
        us_hand = [self.convert_card(c) for c in hand]
        us_info, others_info = [], []
        for player in state.players:
            if player.current_bet == 0 and player.stack == 0:
                return {'type': 'fold'}
        
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
        model_state = torch.tensor(hand_mask+common_mask+[pot, round]+info, dtype=torch.float)

        inf = self.model.forward(model_state)
        self.distributions.append(inf)
        action = torch.argmax(inf)

        if (action == 0): return {'type': 'fold'}
        elif (action == 1): return {'type': 'call'}

        raise_amount = us_info[1]*(action-1)*(rate/100)
        return {'type': 'raise', 'amount': float(raise_amount)}

    def opponent_action(self, action, player):
        pass

    def game_over(self, payouts):
        print('game over', payouts)
        loss_fn = nn.KLDivLoss()
        if len(self.distributions) == 0: return
        self.distributions = torch.stack(self.distributions)
        actions = torch.argmax(self.distributions, dim=1)
        payout = getattr(payouts, self.actual)
        if payout > 0:
            targets = F.one_hot(actions, self.model.OUTPUT_SIZE)
        else:
            targets = torch.ones(len(actions), self.model.OUTPUT_SIZE)
            targets[torch.arange(len(actions)), actions] = 0
            targets = targets / (self.model.OUTPUT_SIZE - 1)

        loss = loss_fn(self.distributions, targets.unsqueeze(0).float())
        self.optimiser.zero_grad()
        loss.backward()
        self.optimiser.step()

    def start_game(self, my_id):
        self.my_id = my_id
        self.distributions = []
        print('start game', my_id)
    

# ...existing code...

async def run_bot(host, port, room, username, model_file):
    bot = RLBot(host, port, room, username)

    bot.actual = username

    if model_file and os.path.exists(f"{model_file}.pth"):
        bot.load(model_file)
    else:
        bot.load(None)

    await bot.start()
    torch.save(bot.model.state_dict(), f"{model_file}.pth")

async def run_bot_2(host, port, room, username):
    bot = TemplateBot(host, port, room, username)
    await bot.start()

if __name__ == "__main__":
    model_file = 'model'
    while True:
        room = random.getrandbits(128)
        print(f"https://ff1a4817.my-app-22r.pages.dev/games/{room}")
        async def main():
            bot1_task = asyncio.create_task(run_bot(args.host, args.port, room, "bot1", model_file))
            bot2_task = asyncio.create_task(run_bot_2(args.host, args.port, room, "bot2"))

            await asyncio.gather(bot1_task, bot2_task)
        
        asyncio.run(main())