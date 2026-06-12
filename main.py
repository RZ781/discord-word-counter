import argparse, asyncio, discord, json, os
from typing import Any

parser = argparse.ArgumentParser(description="Discord bot to count words used")
parser.add_argument("--config", default="config.json", help="json config file")
args = parser.parse_args()

with open(args.config) as f:
    config = json.load(f)

def get_config_option(channel: int, option: str) -> Any:
    if option in config["channels"][channel]:
        return config["channels"][channel][option]
    if option in config:
        return config[option]
    return None

token = config["token"]
client = discord.Client()
histories: list[list[tuple[int, str, str]]] = []

for channel in config["channels"]:
    history_file = channel["history-file"]
    if os.path.isfile(history_file):
        with open(history_file) as f:
            histories.append(json.load(f))
    else:
        histories.append([])

# fetch recent history
async def fetch(channel: discord.TextChannel, history: list[tuple[int, str, str]], limit: int) -> None:
    n_messages = 0
    percent = limit // 100
    old_ids = {x[0] for x in history}
    async for message in channel.history(limit=limit):
        name = message.author.name
        text = message.content.lower()
        msg_id = message.id
        if msg_id in old_ids:
            break
        history.append((msg_id, name, text))
        n_messages += 1
        if n_messages % percent == 0:
            print(f"{n_messages // percent}%")
    print("fetched message history in", channel.name)

# get counts of each word for each user found
def count(history: list[tuple[int, str, str]], words: list[str], alternatives: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    counts = {}
    for _, name, text in history:
        if name not in counts:
            counts[name] = {"total": 0}
            for word in words:
                counts[name][word] = 0
        counts[name]["total"] += 1
        for word in words:
            forms = [word]
            if word in alternatives:
                forms += alternatives[word]
            for form in forms:
                if form in text:
                    counts[name][word] += 1
                    break
    return counts

# convert counts of words to percentages
def percentages(data: dict[str, dict[str, int]], words: list[str]) -> dict[str, dict[str, float]]:
    return {name: {word: round(data[name][word] / data[name]["total"] * 100, 2) for word in words} for name in data}

# format nested dictionary as an ascii table
def table(data: dict[str, Any], words: list[str]) -> str:
    array = [[""] + list(words)] + [[name] + [str(data[name][word]) for word in words] for name in data]
    col_widths = []
    for i in range(len(words) + 1):
        col_widths.append(max([len(row[i]) for row in array]))
    string = ""
    for row in array:
        for i, col in enumerate(row):
            string += col + " " * (col_widths[i]+3-len(col))
        string += "\n"
    return string

# recount words and update message
async def update() -> None:
    for i, channel in enumerate(config["channels"]):
        discord_channel = client.get_channel(channel["channel-id"])
        if discord_channel is None:
            print("Channel not found. Check ID.")
            return
        words = get_config_option(i, "words")
        counts = count(histories[i], words, get_config_option(i, "alternatives"))
        text = f"```{table(percentages(counts, words), words)}```"
        while channel["message-id"] == 0:
            await asyncio.sleep(0)
        if channel["message-id"] is None:
            channel["message-id"] = 0
            message = await discord_channel.send(text)
            channel["message-id"] = message.id
        else:
            message = await discord_channel.fetch_message(channel["message-id"])
            if message.content != text:
                await message.edit(content=text)

@client.event
async def on_ready() -> None:
    print(f"Logged in as {client.user}")
    for i, channel in enumerate(config["channels"]):
        discord_channel = client.get_channel(channel["channel-id"])
        if discord_channel is None:
            print("Channel not found. Check ID.")
            return
        await fetch(discord_channel, histories[i], get_config_option(i, "limit"))
    await update()
    while True:
        for i, channel in enumerate(config["channels"]):
            with open(channel["history-file"], "w") as f:
                json.dump(histories[i], f)
        await asyncio.sleep(60)

@client.event
async def on_message(message: discord.Message) -> None:
    for i, channel in enumerate(config["channels"]):
        if message.channel.id != channel["channel-id"]:
            continue
        histories[i].append((message.id, message.author.name, message.content.lower()))
        await update()

client.run(token)
