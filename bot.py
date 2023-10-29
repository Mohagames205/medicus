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
import logging

from schedule.schedule import ScheduleModule
from verification.verification import VerificationModule

brussels_timezone = pytz.timezone('Europe/Brussels')


load_dotenv()
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.all()
client = commands.Bot(command_prefix='$', intents=intents)
tree = client.tree

embed_messages = {}

con = sqlite3.connect("bot.db")
con.row_factory = sqlite3.Row  # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
cur = con.cursor()
cur.execute(
    'CREATE TABLE IF NOT EXISTS subscribed_messages (id INTEGER PRIMARY KEY, channel_id INTEGER, message_id INTEGER, '
    'guild_id INTEGER, phase INTEGER);')

cur.execute(
    'CREATE TABLE IF NOT EXISTS calendars (id INTEGER PRIMARY KEY, link TEXT, phase INTEGER UNIQUE);')

cur.execute(
    'CREATE TABLE IF NOT EXISTS verification_codes (id INTEGER PRIMARY KEY, code INTEGER, email VARCHAR(255) UNIQUE)'
)

cur.execute(
    'CREATE TABLE IF NOT EXISTS verified_users (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE)'
)

cur.execute(
    'CREATE TABLE IF NOT EXISTS synced_verification_messages (id INTEGER PRIMARY KEY, guild_id INTEGER, channel_id '
    'INTEGER, message_id INTEGER)'
)


@client.event
async def on_ready():
    await client.add_cog(VerificationModule(client, con))
    await client.add_cog(ScheduleModule(client, con))

    for guild in client.guilds:
        tree.copy_global_to(guild=discord.Object(id=guild.id))
        await tree.sync(guild=discord.Object(id=guild.id))

    game = discord.Game("mootje.be")
    await client.change_presence(status=discord.Status.idle, activity=game)

    await client.get_cog("verification").refresh_messages()

    logging.info("BOT IS READY")


client.run(os.getenv("token"))
