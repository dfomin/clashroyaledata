from datetime import datetime, timedelta
from tqdm import tqdm

import aiohttp
import asyncio
from pymongo import MongoClient

from private import royale_token

client = MongoClient('mongodb://localhost:27017/')


class Player:
    def __init__(self, tag, name, trophies, best_trophies, war_day_wins):
        self.tag = tag
        self.name = name
        self.trophies = trophies
        self.best_trophies = best_trophies
        self.war_day_wins = war_day_wins
        self.cards = []

    @property
    def min_card_level(self):
        min_level = 13
        for card in self.cards:
            level = 13 - card["maxLevel"] + card["level"]
            if min_level > level:
                min_level = level
        return min_level

    @property
    def sum_level(self):
        s = 0
        for card in self.cards:
            s += card["level"] - card["maxLevel"]
        return s


async def load_player(session, player_tag: str) -> Player:
    player_tag = player_tag.replace("#", "")

    url = f"https://api.clashroyale.com/v1/players/%23{player_tag}"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        p = await response.json()
        player = Player(player_tag, p["name"], p["trophies"], p["bestTrophies"], p["warDayWins"])
        return player


async def main():
    db = client["clashroyale"]
    war_log = db["warlog"]
    war = next(war_log.find({}).sort("createdDate", -1))
    date = war["createdDate"]
    end_date = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
    start_date = end_date + timedelta(days=-1)

    battle_log = db["battlelog"]
    battles = battle_log.find({"type": "clanWarWarDay"})
    current_war_battles = []
    for battle in battles:
        date = battle["battleTime"]
        battle_time = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
        if start_date <= battle_time <= end_date:
            current_war_battles.append(battle)

    async with aiohttp.ClientSession() as session:
        players = []
        for battle in tqdm(current_war_battles):
            player = await load_player(session, battle["team"][0]["tag"])
            player.cards = battle["team"][0]["cards"]
            opponent = await load_player(session, battle["opponent"][0]["tag"])
            opponent.cards = battle["opponent"][0]["cards"]
            players.append((player, opponent))

        print_best(players, lambda x: x[1].trophies, True, "Opponent trophies")
        print_best(players, lambda x: x[1].best_trophies, True, "Opponent best trophies")
        print_best(players, lambda x: x[1].war_day_wins, True, "Opponent war day wins")
        print_best(players, lambda x: x[0].min_card_level, False, "Lowest card level")
        print_best(players, lambda x: x[0].sum_level, False, "Lowest sum of card levels")


def print_best(values, key, reverse, name):
    values = sorted(values, key=key, reverse=reverse)
    best = key(values[0])
    print(name)
    for value in values:
        if reverse:
            if key(value) < best:
                break
        else:
            if key(value) > best:
                break
        print(value[0].name, key(value))
    print()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
