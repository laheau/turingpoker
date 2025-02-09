#!/usr/bin/env python3
import asyncio
from typing import Tuple
import argparse
import treys
import time

from tg.bot import Bot
from tg.types import *
from models import ModelV1

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

player_count = 8

class RLBot(Bot):
    def convert_card(card):
        f = 0
        match Suit(card.suit):
            case HEARTS: f = 0
            case DIAMONDS: f = 1
            case CLUBS: f = 2
            case SPADES: f = 3
        return card.rank+(f*13)-1
    
    def convert_round(round):
        match PokerRound(round):
            case PRE_FLOP: return 0
            case FLOP: return 1
            case TURN: return 2
            case RIVER: return 3
            case SHOWDOWN: return 4
        return -1

    def act(self, state, hand):
        pot = state.pot
        round = convert_round(state.round)
        common = [convert_card(c) for c in state.cards]
        others_info = []
        us_info = []
        us_hand = [convert_card(c) for c in hand]
        for player in state.players:
            if player.id == self.actual:
                us_info = [player.current_bet, player.stack]
            else:
                others_info.append(player.current_bet)
                others_info.append(player.stack)

        hand_mask, common_mask = [0]*52, [0]*52
        for card in us_hand: hand_mask[card] = 1
        for card in common: common_mask[card] = 1

        info = us_info+others_info

        # model inference

        # return {'type': 'raise', 'amount': raise_to-state.target_bet}
        # return {'type': 'call'}
        return {'type': 'fold'}

    def opponent_action(self, action, player):
        pass

    def game_over(self, payouts):
        #print('game over', payouts)
        pass

    def start_game(self, my_id):
        self.my_id = my_id
        self.actual = args.username
        print('start game', my_id)
    

if __name__ == "__main__":
    bot = RLBot(args.host, args.port, args.room, args.username)
    asyncio.run(bot.start())