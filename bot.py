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
from bubble import get_relations

load_dotenv()

intents = discord.Intents.all()
client = commands.Bot(command_prefix='$', intents=intents)
tree = client.tree

embed_messages = {}

con = sqlite3.connect("bot.db")
cur = con.cursor()


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


@tree.command(name="setschedule")
async def set_schedule_channel(int: discord.Interaction, fase: int):
    embed = discord.Embed(
        title="Huidig hoorcollege",
        description="Hier zie je informatie over het huidig hoorcollege.",
        color=discord.Color.blue()  # You can customize the color
    )

    # Add fields to the embed
    embed.add_field(name="Hoorcollege", value="Lorem ipsum")
    embed.add_field(name="Locatie", value="ABC", inline=False)
    embed.add_field(name="Duration", value="x", inline=False)
    embed.add_field(name="Start", value="1", inline=False)
    embed.add_field(name="Einde", value="", inline=False)

    global_embed_msg = await int.channel.send(embed=embed)

    embed_messages[fase] = global_embed_msg

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
        description="Hier zie je informatie over het huidig hoorcollege.",
        color=discord.Color.blue()  # You can customize the color
    )

    embed.add_field(name="Hoorcollege", value=f"{ongoing_event.name}")

    if ongoing_event != 'Geen hoorcollege':
        embed.add_field(name="Locatie", value=f"{ongoing_event.location}", inline=False)
        embed.add_field(name="Start", value=f"{ongoing_event.begin}", inline=False)
        embed.add_field(name="Einde", value=f"{ongoing_event.end}", inline=False)
        embed.add_field(name="Duur", value=f"{ongoing_event.duration}", inline=False)
        embed.add_field(name="Beschrijving", value=f"{ongoing_event.description}", inline=False)

    await embed_message.edit(embed=embed)

    print("updated embed with ")



@tasks.loop(seconds=10)
async def check_ical():
    for embed_message in embed_messages:
        brussels_timezone = pytz.timezone('Europe/Brussels')

        print("going to update...")
        now = Arrow.fromdatetime(datetime(2023, 10, 7, 8, 30), tzinfo=brussels_timezone)
        await update_embed(embed_messages[embed_message], await get_event_at(now))


client.run(os.getenv("token"))
