import argparse, asyncio, discord.ext.commands, json, os
from typing import Any

parser = argparse.ArgumentParser(description="Discord bot to count words used")
parser.add_argument("--config", default="config.json", help="json config file")
args = parser.parse_args()

with open(args.config) as f:
    config = json.load(f)

def get_config_option(channel: dict[str, Any], option: str) -> Any:
    if option in channel:
        return channel[option]
    if option in config:
        return config[option]
    return None

History = list[tuple[int, str, str]]

client = discord.ext.commands.Bot(command_prefix="!", self_bot=True)

for channel in config["channels"]:
    history_file = channel["history-file"]
    if os.path.isfile(history_file):
        with open(history_file) as f:
            channel["history"] = json.load(f)
    else:
        channel["history"] = []
    channel["initial-history"] = channel["history"].copy()

# fetch recent history
async def fetch(channel: discord.TextChannel, channel_config: dict[str, Any]) -> None:
    limit = get_config_option(channel_config, "limit")
    n_messages = 0
    percent = limit // 100
    old_ids = {msg_id for msg_id, _, _ in channel_config["initial-history"]}
    history = channel_config["history"]
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
            string += col + " " * (col_widths[i] + 3 - len(col))
        string += "\n"
    return string

# recount words and update or create message
async def update() -> None:
    for channel in config["channels"]:
        discord_channel = client.get_channel(channel["channel-id"])
        if discord_channel is None:
            print("Channel not found. Check ID.")
            return
        words = get_config_option(channel, "words")
        counts = count(channel["history"], words, get_config_option(channel, "alternatives"))
        text = f"```{table(percentages(counts, words), words)}```"
        # message-id is temporarily set to 0 to prevent bot from sending multiple messages
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
    for channel in config["channels"]:
        discord_channel = client.get_channel(channel["channel-id"])
        if discord_channel is None:
            print("Channel not found. Check ID.")
            return
        await fetch(discord_channel, channel)
    await update()
    while True:
        for channel in config["channels"]:
            with open(channel["history-file"], "w") as f:
                json.dump(channel["history"], f)
        await asyncio.sleep(60)

@client.event
async def on_message(message: discord.Message) -> None:
    await client.process_commands(message)
    for channel in config["channels"]:
        if message.channel.id != channel["channel-id"]:
            continue
        channel["history"].append((message.id, message.author.name, message.content.lower()))
        await update()

@client.command()
async def search(context: discord.ext.commands.Context, *search_terms: str) -> None:
    for channel in config["channels"]:
        if context.channel.id != channel["channel-id"]:
            continue
        results = ""
        count = 0
        for msg_id, author_name, content in channel["history"]:
            matches = True
            for search_term in search_terms:
                if search_term not in content:
                    matches = False
                    break
            if matches:
                try:
                    message = await context.channel.fetch_message(msg_id)
                    url = message.jump_url
                except:
                    url = "(deleted)"
                content = content[:100].replace("\n", "\n> ")
                results += f"{author_name}: {url}\n> {content}\n"
                count += 1
                if count >= 10:
                    break
        if results == "":
            results = "No results found"
        await context.send(results)

client.run(config["token"])
