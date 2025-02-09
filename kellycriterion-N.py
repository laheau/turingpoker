#!/usr/bin/env python3
import asyncio
from typing import Tuple
import argparse
import treys
import time
import random

from tg.bot import Bot
import tg.types as pokerTypes
from tg.types import *

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

def card_name(card: pokerTypes.Card):
    val = str(card.rank)
    if card.rank == 1:
        val = 'A'
    if card.rank == 10:
        val = 'T'
    elif card.rank == 11:
        val = 'J'
    elif card.rank == 12:
        val = 'Q'
    elif card.rank == 13:
        val = 'K'
    return f"{val}{card.suit[0]}"

# Use kelly criterion to bet based on the win probability
class KellyCriterion(Bot):
    def act(self, state, hand):
        self.state = state
        
        prob = self.win_prob(state, hand)
        me = None
        for player in state.players:
            if player.id == self.username:
                me = player
            else:
                if (player.current_bet > 0 and PokerRound(state.round) == PokerRound.PRE_FLOP):
                    self.opponent_action(None, {"username": player.id})
        p = prob

        b = len(state.players)
    
        print("me", me)
        print(self.username, state.players)

        if (PokerRound(state.round) == PokerRound.PRE_FLOP):
            self.avg_opp_stack = sum(player.stack+player.current_bet for player in state.players if player.id != self.username) / (b - 1)
            print(me.stack, self.avg_opp_stack)

            self.edge = 1.0
            if me.stack < self.avg_opp_stack * 0.80: self.edge = 1.3
            elif me.stack > self.avg_opp_stack * 1.2: self.edge = 0.9

        round_adjust = 1
        print('round: ', state.round)
        match PokerRound(state.round):
            case PokerRound.PRE_FLOP:
                noise = random.uniform(-0.2, 0.3)
                round_adjust = 0.7+noise
            case PokerRound.FLOP:
                noise = random.uniform(-0.2, 0.3)
                round_adjust = 0.8+noise
            case PokerRound.TURN:
                noise = random.uniform(-0.2, 0.2)
                round_adjust = 0.9+noise
            case PokerRound.RIVER:
                noise = random.uniform(-0.2, 0.2)
                round_adjust = 1+noise
            case PokerRound.SHOWDOWN:
                noise = random.uniform(-0.2, 0.2)
                round_adjust = 1+noise
        
        raise_to = (p - (1-p)/b)*(me.stack) * round_adjust
        print(f'{self.username} Stack:', me.stack, raise_to, p, ''.join(map(card_name, hand)), ''.join(map(card_name, state.cards)))
        print(f'{self.username}: Adjustment', round_adjust, "Edge", self.edge, "Auto Call", self.auto_call)
        cost_to_play = min(state.target_bet-me.current_bet, me.stack)

        if (self.auto_call and p > 0.5):
            return {'type': 'call'}

        if raise_to > state.target_bet*self.edge:
            print('raise', raise_to-state.target_bet)
            self.last_action = ActionType.RAISE
            return {'type': 'raise', 'amount': raise_to-state.target_bet}
        elif raise_to >= cost_to_play or cost_to_play == 0:
            print('call')
            self.last_action = ActionType.CALL
            return {'type': 'call'}
        print('fold')
        self.last_action = ActionType.FOLD
        return {'type': 'fold'}

    def opponent_action(self, action, player_info):
        print(action, player_info)
        if (self.state == None): return
        opp = None
        for player in self.state.players:
            if (type(player_info) is dict and player.id == player_info.get("username")):
                opp = player
                break
            if  (type(player_info) is not dict and player.id == player_info.username):
                opp = player
                break
        
        if (self.avg_opp_stack == int(1e9)):
            self.avg_opp_stack = sum(player.stack+player.current_bet for player in self.state.players if player.id != self.username) / (len(self.state.players) - 1)

        self.auto_call = False
        print(self.delta_opp_bet, opp.current_bet, self.last_opp_bet, self.avg_opp_stack)
        self.delta_opp_bet = opp.current_bet-self.last_opp_bet
        self.last_opp_bet = opp.current_bet

        print(self.delta_opp_bet, 0.5*self.avg_opp_stack)
        if (self.delta_opp_bet > 0.5*self.avg_opp_stack):
            self.auto_call = True

        print(self.auto_call)

    def game_over(self, payouts):
        print('game over', payouts)
        self.last_opp_bet = 0
        self.delta_opp_bet = 0
        self.state = None
        self.auto_call = False
        self.avg_opp_stack = int(1e9)
        pass

    def start_game(self, my_id):
        self.my_id = my_id
        self.username = args.username
        self.last_opp_bet = 0
        self.delta_opp_bet = 0
        self.state = None
        self.auto_call = False
        self.avg_opp_stack = int(1e9)
        print('start game', my_id)
    
    def win_prob(self, state: pokerTypes.PokerSharedState, hand: Tuple[pokerTypes.Card, pokerTypes.Card]):
        out = 0
        hand = [
            treys.Card.new(card_name(hand[0])),
            treys.Card.new(card_name(hand[1]))]
        board = [treys.Card.new(card_name(card)) for card in state.cards]
        evaluator = treys.Evaluator()
        sims = int(7e3)
        for i in range(sims):
            deck = treys.Deck()
            deck.shuffle()
            for card in hand+board:
                deck.cards.remove(card)
            pred = board + deck.draw(5-len(board))
            score = evaluator.evaluate(hand, pred)
            other = 10**9

            for player in state.players:
                if player.id != self.my_id:
                    other = min(other, evaluator.evaluate(deck.draw(2), pred))
            if score < other:
                out += 1
        return out/sims


if __name__ == "__main__":
    bot = KellyCriterion(args.host, args.port, args.room, args.username)
    asyncio.run(bot.start())