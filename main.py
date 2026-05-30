import discord, asyncio, json, os
from typing import Any

with open("config.json") as f:
    config = json.load(f)

channel_id = config["channel-id"]
message_id = config["message-id"]
history_file = config["history-file"]
alternatives = config["alternatives"]
words = config["words"]
token = config["token"]
client = discord.Client()

if os.path.isfile(history_file):
    with open(history_file) as f:
        history: list[tuple[int, str, str]] = json.load(f)
else:
    history = []

# fetch recent history
async def fetch(channel: discord.TextChannel) -> None:
    limit = 100_000
    n_messages = 0
    old_ids = {x[0] for x in history}
    async for message in channel.history(limit=limit):
        name = message.author.name
        text = message.content.lower()
        msg_id = message.id
        if msg_id in old_ids:
            break
        history.append((msg_id, name, text))
        n_messages += 1
        if n_messages % 1000 == 0:
            print(f"{n_messages // 1000}%")
    print("fetched message history")

# get counts of each word for each user found
def count() -> dict[str, dict[str, int]]:
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
def percentages(data: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    return {name: {word: round(data[name][word] / data[name]["total"] * 100, 2) for word in words} for name in data}

# format nested dictionary as an ascii table
def table(data: dict[str, Any]) -> str:
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
    channel = client.get_channel(channel_id)
    if channel is None:
        print("Channel not found. Check ID.")
        return
    message = await channel.fetch_message(message_id)
    text = f"```{table(percentages(count()))}```"
    if message.content != text:
        await message.edit(content=text)

@client.event
async def on_ready() -> None:
    print(f"Logged in as {client.user}")
    channel = client.get_channel(channel_id)
    if channel is None:
        print("Channel not found. Check ID.")
        return
    await fetch(channel)
    await update()
    while True:
        with open(history_file, "w") as f:
            json.dump(history, f)
        await asyncio.sleep(60)

@client.event
async def on_message(message: discord.Message) -> None:
    if message.channel.id != channel_id:
        return
    history.append((message.id, message.author.name, message.content.lower()))
    await update()

client.run(token)
