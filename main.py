import aiohttp
import asyncio

from datetime import datetime

import pymongo
from pymongo import MongoClient

from data_analyzer import collection_day_results, war_day_results
from private import royale_token
from telegram_manager import TelegramManager

client = MongoClient('mongodb://localhost:27017/')


def store_warlog(clan_tag: str, warlog: list) -> bool:
    db = client["clashroyale"]
    collection = db["warlog"]
    is_new = False
    for war in warlog:
        war["tag"] = clan_tag
        try:
            collection.insert_one(war)
            is_new = True
        except pymongo.errors.DuplicateKeyError:
            pass
    return is_new


def store_battle_log(player_tag: str, battle_log: list) -> bool:
    db = client["clashroyale"]
    collection = db["battlelog"]
    is_new = False
    for battle in battle_log:
        battle["tag"] = player_tag
        try:
            collection.insert_one(battle)
            is_new = True
        except pymongo.errors.DuplicateKeyError:
            pass
    return is_new


async def fetch_warlog(session, clan_tag: str) -> bool:
    clan_tag = clan_tag.replace("#", "")

    url = "https://api.clashroyale.com/v1/clans/%23" + clan_tag + "/warlog"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        if response.status != 200:
            return False

        wars = await response.json()
        return store_warlog(clan_tag, wars["items"])


async def fetch_current_war(session, clan_tag: str):
    clan_tag = clan_tag.replace("#", "")

    url = "https://api.clashroyale.com/v1/clans/%23" + clan_tag + "/currentwar"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        if response.status != 200:
            return 60, None

        war = await response.json()
        now = datetime.utcnow()
        if war["state"] == "collectionDay":
            end_time = war["collectionEndTime"]
        elif war["state"] == "warDay":
            end_time = war["warEndTime"]
        else:
            print(war["state"])
            return 60, None
        time_left = datetime.strptime(end_time, "%Y%m%dT%H%M%S.%fZ") - now
        seconds_left = time_left.seconds
        if seconds_left <= 0:
            seconds_left = 60
        return seconds_left, war["state"]


async def fetch_player_battle_log(session, player_tag: str):
    player_tag = player_tag.replace("#", "")

    url = "https://api.clashroyale.com/v1/players/%23" + player_tag + "/battlelog"

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        if response.status != 200:
            return False

        battles = await response.json()
        clan_war_battles = filter(lambda x: x["type"] in ["clanWarCollectionDay", "clanWarWarDay"], battles)
        return store_battle_log(player_tag, clan_war_battles)


async def fetch_clan_battle_log(session, clan_tag: str):
    clan_tag = clan_tag.replace("#", "")

    url = "https://api.clashroyale.com/v1/clans/%23" + clan_tag

    params = dict(
        authorization=royale_token
    )

    async with session.get(url, params=params) as response:
        if response.status != 200:
            return False

        clan = await response.json()
        for member in clan["memberList"]:
            player_tag = member["tag"]
            await fetch_player_battle_log(session, player_tag)


async def main():
    clan_tag = "#2UJ2GJ"
    battle_log_cooldown = 30 * 60
    telegram_manager = TelegramManager()
    state = None
    async with aiohttp.ClientSession() as session:
        await fetch_clan_battle_log(session, clan_tag)

        while True:
            old_state = state
            seconds_left, state = await fetch_current_war(session, clan_tag)
            if state != old_state and state == "warDay" and old_state is not None:
                text = await collection_day_results(session, clan_tag)
                telegram_manager.message(text)

            if seconds_left < battle_log_cooldown:
                await asyncio.sleep(seconds_left + 60)
                is_new_war = await fetch_warlog(session, clan_tag)
                await fetch_clan_battle_log(session, clan_tag)

                if is_new_war:
                    text = await war_day_results(session, clan_tag)
                    telegram_manager.message(text)
            else:
                await asyncio.sleep(battle_log_cooldown)
                await fetch_clan_battle_log(session, clan_tag)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
