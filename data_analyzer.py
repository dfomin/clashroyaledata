import json
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
    def mean_level(self):
        s = 0
        for card in self.cards:
            s += 13 - card["maxLevel"] + card["level"]
        return s / len(self.cards)


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


def filter_battles_by_clan(battles, clan_tag):
    filtered_battles = []
    for battle in battles:
        for player in battle["team"]:
            if player["clan"]["tag"] == clan_tag:
                filtered_battles.append(battle)
                break
    return filtered_battles


def filter_battles_by_date(battles, start_date, end_date):
    filtered_battles = []
    for battle in battles:
        date = battle["battleTime"]
        battle_time = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
        if start_date <= battle_time <= end_date:
            filtered_battles.append(battle)
    return filtered_battles


def load_collection_day_battles(start_date, end_date, battle_log, clan_tag):
    battles = battle_log.find({"type": "clanWarCollectionDay"})
    current_war_battles = filter_battles_by_date(battles, start_date, end_date)
    current_war_battles_by_clan = filter_battles_by_clan(current_war_battles, clan_tag)
    return current_war_battles_by_clan


def load_war_day_battles(start_date, end_date, battle_log, clan_tag):
    battles = battle_log.find({"type": "clanWarWarDay"})
    current_war_battles = filter_battles_by_date(battles, start_date, end_date)
    current_war_battles_by_clan = filter_battles_by_clan(current_war_battles, clan_tag)
    return current_war_battles_by_clan


async def load_opponents(battles):
    async with aiohttp.ClientSession() as session:
        players = []
        for battle in tqdm(battles):
            player = await load_player(session, battle["team"][0]["tag"])
            player.cards = battle["team"][0]["cards"]
            opponent = await load_player(session, battle["opponent"][0]["tag"])
            opponent.cards = battle["opponent"][0]["cards"]
            players.append((player, opponent))
        return players


async def collection_day_results(clan_tag: str):
    db = client["clashroyale"]
    war_log = db["warlog"]
    war = next(war_log.find({}).sort("createdDate", -1))
    date = war["createdDate"]
    end_date = datetime.now()
    start_date = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
    current_war_battles = load_collection_day_battles(start_date, end_date, db["battlelog"], clan_tag)

    players = await load_opponents(current_war_battles)

    print(find_best(players, lambda x: x[1].trophies, True, "Opponent trophies"))
    print(find_best(players, lambda x: x[1].best_trophies, True, "Opponent best trophies", 7000))
    print(find_best(players, lambda x: x[1].war_day_wins, True, "Opponent war day wins"))


async def war_day_results(clan_tag: str):
    db = client["clashroyale"]
    war_log = db["warlog"]
    war = next(war_log.find({}).sort("createdDate", -1))
    date = war["createdDate"]
    end_date = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
    start_date = end_date + timedelta(days=-1)
    current_war_battles = load_war_day_battles(start_date, end_date, db["battlelog"], clan_tag)

    players = await load_opponents(current_war_battles)

    print(find_best(players, lambda x: x[1].trophies, True, "Opponent trophies"))
    print(find_best(players, lambda x: x[1].best_trophies, True, "Opponent best trophies", 7000))
    print(find_best(players, lambda x: x[1].war_day_wins, True, "Opponent war day wins"))
    print(find_best(players, lambda x: x[0].min_card_level, False, "Lowest card level", 9))
    print(find_best(players, lambda x: x[0].mean_level, False, "Mean cards level"))


async def main():
    await collection_day_results("#2UJ2GJ")
    # await war_day_results("#2UJ2GJ")


def find_best(values, key, reverse, name, threshold=None):
    values = sorted(values, key=key, reverse=reverse)
    threshold = threshold or key(values[0])
    if (reverse and key(values[0]) < threshold) or (not reverse and key(values[0]) > threshold):
        threshold = key(values[0])
    result = f"{name}\n"
    for value in values:
        if reverse:
            if key(value) < threshold:
                break
        else:
            if key(value) > threshold:
                break
        result += f"{value[0].name} {key(value)}\n"
    return result


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
    client.close()
