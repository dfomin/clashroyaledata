from datetime import datetime, timedelta

from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')

if __name__ == "__main__":
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
    players = []
    for battle in current_war_battles:
        player = battle["team"][0]
        opponent = battle["opponent"][0]
        level_sum = 0
        levels = []
        for card in player["cards"]:
            level = 13 - card["maxLevel"] + card["level"]
            level_sum += level
            levels.append(level)
        players.append((player["name"], level_sum, levels, opponent["startingTrophies"], opponent["tag"]))
    for value in sorted(players, key=lambda x: x[3]):
        print(value[0], value[3], value[4])
