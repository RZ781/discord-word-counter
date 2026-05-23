import discord, asyncio, json
from typing import Any

with open("config.json") as f:
    config = json.load(f)

channel_id = config["channel-id"]
message_id = config["message-id"]
alternatives = config["alternatives"]
words = config["words"]
token = config["token"]
client = discord.Client()

# get counts of each word for each user found
async def count(channel: discord.TextChannel, history: list[tuple[int, str, str]]) -> dict[str, dict[str, int]]:
    # fetch recent history
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
    # calculate values
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

@client.event
async def on_ready() -> None:
    print(f"Logged in as {client.user}")
    channel = client.get_channel(channel_id)
    if channel is None:
        print("Channel not found. Check ID.")
        return
    with open("history.json") as f:
        history = json.load(f)
    message = await channel.fetch_message(message_id)
    text = "```" + table(percentages(await count(channel, history))) + "```"
    await message.edit(content=text)
    with open("history.json", "w") as f:
        json.dump(history, f)

client.run(token)
