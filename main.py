import aiohttp
import asyncio

from datetime import datetime

import pymongo
from pymongo import MongoClient

from private import royale_token

client = MongoClient('mongodb://localhost:27017/')


def store_warlog(clan_tag: str, warlog: list) -> bool:
    db = client["clashroyale"]
    collection = db["warlog"]
    for war in warlog:
        war["tag"] = clan_tag
        try:
            collection.insert_one(war)
        except pymongo.errors.DuplicateKeyError:
            pass
    return True


def store_battle_log(player_tag: str, battle_log: list) -> bool:
    db = client["clashroyale"]
    collection = db["battlelog"]
    for battle in battle_log:
        battle["tag"] = player_tag
        try:
            collection.insert_one(battle)
        except pymongo.errors.DuplicateKeyError:
            pass
    return True


async def fetch_warlog(session, clan_tag: str) -> bool:
    url = "https://api.clashroyale.com/v1/clans/%23" + clan_tag + "/warlog"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        wars = await response.json()
        return store_warlog(clan_tag, wars["items"])


async def fetch_current_war(session, clan_tag: str):
    url = "https://api.clashroyale.com/v1/clans/%23" + clan_tag + "/currentwar"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        war = await response.json()
        now = datetime.utcnow()
        if war["state"] == "collectionDay":
            end_time = war["collectionEndTime"]
        elif war["state"] == "warDay":
            end_time = war["warEndTime"]
        time_left = datetime.strptime(end_time, "%Y%m%dT%H%M%S.%fZ") - now
        seconds_left = time_left.seconds
        if seconds_left <= 0:
            seconds_left = 60
        return seconds_left


async def fetch_player_battle_log(session, player_tag: str):
    url = "https://api.clashroyale.com/v1/players/%23" + player_tag + "/battlelog"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        battles = await response.json()
        clan_war_battles = filter(lambda x: x["type"] in ["clanWarCollectionDay", "clanWarWarDay"], battles)
        store_battle_log(player_tag, clan_war_battles)


async def fetch_clan_battle_log(session, clan_tag: str):
    url = "https://api.clashroyale.com/v1/clans/%23" + clan_tag

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        clan = await response.json()
        for member in clan["memberList"]:
            player_tag = member["tag"].replace("#", "")
            await fetch_player_battle_log(session, player_tag)


async def main():
    clan_tag = "2UJ2GJ"
    battle_log_cooldown = 60 * 60
    async with aiohttp.ClientSession() as session:
        while True:
            seconds_left = await fetch_current_war(session, clan_tag)
            if seconds_left < battle_log_cooldown:
                await asyncio.sleep(seconds_left)
                await fetch_warlog(session, clan_tag)
            else:
                await asyncio.sleep(battle_log_cooldown)
                await fetch_clan_battle_log(session, clan_tag)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
