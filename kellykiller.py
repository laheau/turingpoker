#!/usr/bin/env python3
import asyncio
import itertools
import pickle
import random
from typing import Tuple
import argparse
import treys
import time

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

lookup_table = pickle.load(open('equity_table.pkl', 'rb'))

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
class KellyKriterion(Bot):

    def act(self, state, hand):
        hand = [
            treys.Card.new(card_name(hand[0])),
            treys.Card.new(card_name(hand[1]))]
        if state is not None and PokerRound(state.round) == PokerRound.PRE_FLOP:
            for p in state.players:
                if p.id != self.username:
                    self.opponent_first_bet = p.current_bet
                    self.opponent_stack_size = p.stack + p.current_bet
                    self.opponent_f = self.opponent_first_bet / self.opponent_stack_size
            # self.opponent_first_bet = player.current_bet
            self.opponent_p = (self.opponent_first_bet * self.opponent_f + 1) / (self.opponent_first_bet + 1)
            # print('opponent p', self.opponent_p)
            deck = treys.Deck()
            deck.cards = [card for card in deck.cards if card not in hand]
            # print('hands', hand)
            self.possible_hands = [list(hands) for hands in itertools.combinations(deck.cards, 2) if abs(self.opponent_p - lookup_table[tuple(sorted(hands))]) < 0.2]
            self.possible_hands = [x for x in self.possible_hands if x[0] not in hand and x[1] not in hand]

        if self.opponent_p is None:
            prob = self.win_prob(state, hand)
        else:
            prob = self.win_prob_first_round(state, hand)
        me = None
        for player in state.players:
            if player.id == self.username:
                me = player
                break
        p = prob

        b = len(state.players)
    
        # print(self.my_id, state.players)

        adjust = 1
    
        raise_to = (p - (1-p)/b)*(me.stack) * adjust
        cost_to_play = min(state.target_bet-me.current_bet, me.stack)
        
        if raise_to > state.target_bet:
            return {'type': 'raise', 'amount': raise_to-state.target_bet}
        elif raise_to >= cost_to_play or cost_to_play == 0:
            return {'type': 'call'}
        return {'type': 'fold'}

    def opponent_action(self, action, player, state):
        pass


    def game_over(self, payouts):
        #print('game over', payouts)
        pass

    def start_game(self, my_id):
        self.my_id = my_id
        self.username = args.username
        self.opponent_p = None
        print('start game', my_id)
    

    def win_prob_first_round(self, state: pokerTypes.PokerSharedState, hand: Tuple[pokerTypes.Card, pokerTypes.Card]):
        out = 0
    
        board = [treys.Card.new(card_name(card)) for card in state.cards]
        evaluator = treys.Evaluator()

        # print('possible hands len ', len(self.possible_hands))
        possible_hands = [hands for hands in self.possible_hands if hands[0] not in board and hands[1] not in board]
        # print('possible hands len ', len(possible_hands))
        # print('possible hands ', possible_hands)
        # print('my hand ', hand)
        for opponent_hand in possible_hands:
            deck = treys.Deck()
            deck.shuffle()
            for card in hand+board + opponent_hand:
                # print(card)
                deck.cards.remove(card)
            pred = board + deck.draw(5-len(board))
            score = evaluator.evaluate(hand, pred)
            other =  evaluator.evaluate(opponent_hand, pred)
            if score < other:
                out += 1
        return out/len(possible_hands) if len(possible_hands) > 0 else 1


    def win_prob(self, state: pokerTypes.PokerSharedState, hand: Tuple[pokerTypes.Card, pokerTypes.Card]):
        out = 0
        board = [treys.Card.new(card_name(card)) for card in state.cards]
        evaluator = treys.Evaluator()
        sims = int(3e3)
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
    bot = KellyKriterion(args.host, args.port, args.room, args.username)
    asyncio.run(bot.start())