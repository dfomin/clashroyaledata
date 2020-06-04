from datetime import datetime, timedelta
from tqdm import tqdm

import aiohttp
import asyncio
from pymongo import MongoClient

from private import royale_token

client = MongoClient('mongodb://localhost:27017/')


MAX_TROPHIES = "Соперник(и) с наибольшим количеством кубков:"
MAX_BEST_TROPHIES = "Соперник(и) с наибольшим рекордом по кубкам:"
MAX_CLAN_WAR_WINS = "Соперник(и) с наибольшим количеством побед в кв:"
MIN_CARD_LEVEL = "Самая непрокачанная карта в колоде в кв:"
MIN_MEAN_CARDS_LEVEL = "Самая непрокачанная колода в кв:"


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
        if "name" not in p:
            return None
        player = Player(player_tag, p["name"], p["trophies"], p["bestTrophies"], p["warDayWins"])
        return player


async def fetch_current_war(session, clan_tag: str):
    clan_tag = clan_tag.replace("#", "")

    url = f"https://api.clashroyale.com/v1/clans/%23{clan_tag}/currentwar"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        if response.status != 200:
            return None

        war = await response.json()
        return war


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


def filter_battles_by_win(battles):
    filtered_battles = []
    for battle in battles:
        player_crowns = int(battle["team"][0]["crowns"])
        opponent_crowns = int(battle["opponent"][0]["crowns"])
        if player_crowns > opponent_crowns:
            filtered_battles.append(battle)
    return filtered_battles


def load_collection_day_battles(start_date, end_date, battle_log, clan_tag):
    battles = battle_log.find({"type": "clanWarCollectionDay"})
    current_war_battles = filter_battles_by_date(battles, start_date, end_date)
    current_war_battles_by_clan = filter_battles_by_clan(current_war_battles, clan_tag)
    # current_war_battles_by_clan = filter_battles_by_win(current_war_battles_by_clan)
    return current_war_battles_by_clan


def load_war_day_battles(start_date, end_date, battle_log, clan_tag):
    battles = battle_log.find({"type": "clanWarWarDay"})
    current_war_battles = filter_battles_by_date(battles, start_date, end_date)
    current_war_battles_by_clan = filter_battles_by_clan(current_war_battles, clan_tag)
    # current_war_battles_by_clan = filter_battles_by_win(current_war_battles_by_clan)
    return current_war_battles_by_clan


async def load_opponents(session, battles):
    players = []
    for battle in tqdm(battles):
        player = await load_player(session, battle["team"][0]["tag"])
        if player is None:
            continue
        player.trophies = battle["team"][0]["startingTrophies"]
        player.cards = battle["team"][0]["cards"]
        opponent = await load_player(session, battle["opponent"][0]["tag"])
        if opponent is None:
            continue
        opponent.trophies = battle["opponent"][0]["startingTrophies"]
        opponent.cards = battle["opponent"][0]["cards"]
        players.append((player, opponent))
    return players


async def collection_day_results(session, clan_tag: str):
    db = client["clashroyale"]
    war_log = db["warlog"]
    war = next(war_log.find({}).sort("createdDate", -1))
    date = war["createdDate"]
    end_date = datetime.utcnow()
    start_date = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
    current_war_battles = load_collection_day_battles(start_date, end_date, db["battlelog"], clan_tag)

    players = await load_opponents(session, current_war_battles)

    text = ""
    text += find_best(players, lambda x: x[1].trophies, True, MAX_TROPHIES)
    text += find_best(players, lambda x: x[1].best_trophies, True, MAX_BEST_TROPHIES, 7000)
    text += find_best(players, lambda x: x[1].war_day_wins, True, MAX_CLAN_WAR_WINS)
    return text


async def war_day_results(session, clan_tag: str):
    db = client["clashroyale"]
    war_log = db["warlog"]
    war = next(war_log.find({}).sort("createdDate", -1))
    date = war["createdDate"]
    end_date = datetime.strptime(date, "%Y%m%dT%H%M%S.%fZ")
    start_date = end_date + timedelta(days=-1)
    current_war_battles = load_war_day_battles(start_date, end_date, db["battlelog"], clan_tag)

    players = await load_opponents(session, current_war_battles)

    text = ""
    text += find_best(players, lambda x: x[1].trophies, True, MAX_TROPHIES)
    text += find_best(players, lambda x: x[1].best_trophies, True, MAX_BEST_TROPHIES, 7000)
    text += find_best(players, lambda x: x[1].war_day_wins, True, MAX_CLAN_WAR_WINS)
    text += find_best(players, lambda x: x[0].min_card_level, False, MIN_CARD_LEVEL, 9)
    text += find_best(players, lambda x: x[0].mean_level, False, MIN_MEAN_CARDS_LEVEL)
    return text


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
        if reverse:
            result += f"{value[0].name} против {value[1].name} ({key(value)})\n"
        else:
            result += f"{value[0].name}, уровень: {key(value)}\n"
    result += "\n"
    return result


async def main():
    clan_tag = "#2UJ2GJ"
    async with aiohttp.ClientSession() as session:
        current_war = await fetch_current_war(session, clan_tag)
        if current_war is not None:
            state = current_war["state"]
            if state == "collectionDay" or state == "notInWar":
                text = await war_day_results(session, clan_tag)
            elif state == "warDay":
                text = collection_day_results(session, clan_tag)
            else:
                text = "Current war is unavailable or unknown state."
            print(text)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
    client.close()
