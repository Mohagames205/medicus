import asyncio
from datetime import datetime
import io

import aiohttp
import discord
from discord.ext import tasks, commands
import os
import sqlite3
import pytz
from arrow import Arrow
from ics import Calendar, Event
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
client = commands.Bot(command_prefix='$', intents=intents)
tree = client.tree

embed_messages = {}

con = sqlite3.connect("bot.db")
con.row_factory = sqlite3.Row  # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
cur = con.cursor()
cur.execute(
    'CREATE TABLE IF NOT EXISTS subscribed_messages (id INTEGER PRIMARY KEY, channel_id INTEGER, message_id INTEGER, guild_id INTEGER, phase INTEGER)')


# tijdelijke hack

tijd = {
    "jaar": 2023,
    "maand": 10,
    "dag": 10,
    "uur": 8,
    "minuut": 30
}

# sync the slash command to your server
@client.event
async def on_ready():
    for guild in client.guilds:
        tree.copy_global_to(guild=discord.Object(id=guild.id))
        await tree.sync(guild=discord.Object(id=guild.id))
    check_ical.start()
    print("ready")


async def get_file_content(url):
    response = await aiohttp.ClientSession().get(url)
    return discord.File(fp=io.BytesIO(await response.read()), filename="motivatie.mp3")


@client.hybrid_command(name="motivatie", description="Krijg motivatie van de enige echte motivator")
async def motivatie(ctx):
    file_content = await get_file_content(
        "https://cdn.discordapp.com/attachments/1122300299604918354/1123175156047695912/Messenger_Facebook.mp3?ex=65193460&is=6517e2e0&hm=7753692951a5f79a0a7e1419082bc1a60c8bb52a3edba854ef1d00b7a8c648f3&")
    await ctx.send("Als u een vraag niet weet, niet panikeren, maar altijd door doen, nooit opgeven")
    await ctx.channel.send(file=file_content)


@tree.command(name="setschedulechannel")
async def set_schedule_channel(int: discord.Interaction, fase: int):
    embed = discord.Embed(
        title="Huidig hoorcollege",
        description="Hier zie je informatie over het huidig hoorcollege.",
        color=discord.Color.blue()
    )

    global_embed_msg = await int.channel.send(embed=embed)
    await register_message(fase, global_embed_msg)

    await int.response.send_message("test")


async def get_event_at(time: Arrow):
    with open('cal.ics', 'r') as file:
        ics_text = file.read()

    cal = Calendar(ics_text)

    for event in cal.events:
        if event.begin <= time <= event.end:
            return event

    return Event("Geen hoorcollege")


async def update_embed(embed_message, ongoing_event: Event):
    embed = discord.Embed(
        title="Huidig hoorcollege",
        color=discord.Color.red()  # You can customize the color
    )

    embed.add_field(name="Hoorcollege", value=f"{ongoing_event.name}")

    if ongoing_event.name != 'Geen hoorcollege':
        embed.color = discord.Color.blue()
        embed.add_field(name="Locatie", value=f"{ongoing_event.location}", inline=False)
        embed.add_field(name="Start", value=f"{ongoing_event.begin}", inline=False)
        embed.add_field(name="Einde", value=f"{ongoing_event.end}", inline=False)
        embed.add_field(name="Duur", value=f"{ongoing_event.duration}", inline=False)
        embed.add_field(name="Beschrijving", value=f"{ongoing_event.description}", inline=False)

    await embed_message.edit(embed=embed)


@tree.command(name="overridetime")
async def override_time(interaction: discord.Interaction, jaar: int, maand: int, dag: int, uur: int, minuut: int):
    tijd["jaar"] = jaar
    tijd["maand"] = maand
    tijd["dag"] = dag
    tijd["uur"] = uur
    tijd["minuut"] = minuut

    await interaction.response.send_message("Time has been succesfully overriden")

@tasks.loop(seconds=10)
async def check_ical():
    for guild in client.guilds:

        for embed_message in await fetch_messages(guild):
            brussels_timezone = pytz.timezone('Europe/Brussels')

            print("going to update...")
            now = Arrow.fromdatetime(datetime(tijd["jaar"], tijd["maand"], tijd["dag"], tijd["uur"], tijd["minuut"]), tzinfo=brussels_timezone)
            await update_embed(embed_message, await get_event_at(now))


async def fetch_messages(guild: discord.Guild):
    cur.execute('SELECT * FROM subscribed_messages WHERE `guild_id` = ?', (guild.id,))
    results = cur.fetchall()

    # todo: implement phase specific schedule
    messages = []
    for result in results:
        guild = client.get_guild(result["guild_id"])
        channel = guild.get_channel(result["channel_id"])
        message = await channel.get_partial_message(result["message_id"]).fetch()
        messages.append(message)

    return messages


async def register_message(phase: int, message: discord.Message):
    cur.execute('INSERT INTO subscribed_messages (`phase`, `channel_id`, `message_id`, `guild_id`) values (?, ?, ?, ?)',
                (phase, message.channel.id, message.id, message.guild.id))
    con.commit()


client.run(os.getenv("token"))
