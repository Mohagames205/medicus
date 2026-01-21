import logging
import os
import sqlite3

import aiosqlite
import discord
import pytz
from discord.ext import commands
from dotenv import load_dotenv

import db.connection_manager
from misc import misc
from schedule.schedule import ScheduleModule
from verification.verification import VerificationModule

load_dotenv()

if os.getenv("PYTHONASYNCIODEBUG") == "1":
    logging.basicConfig(level=logging.DEBUG)

brussels_timezone = pytz.timezone('Europe/Brussels')

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.all()
client = commands.Bot(command_prefix='$', intents=intents)

tree = client.tree


embed_messages = {}

@client.event
async def setup_hook():
    client.con = await initialise_db()

@client.event
async def on_ready():
    await client.add_cog(VerificationModule(client, client.con))
    await client.add_cog(ScheduleModule(client, client.con))
    await client.add_cog(misc.MiscModule(client))

    await tree.sync()

    for guild in client.guilds:
        #tree.copy_global_to(guild=discord.Object(id=guild.id))
        await tree.sync(guild=discord.Object(id=guild.id))

    game = discord.Game("mootje.be")
    await client.change_presence(status=discord.Status.dnd, activity=game)

    await client.get_cog("verification").refresh_messages()

    logging.info("BOT IS READY")

@tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

async def initialise_db():
    con = await aiosqlite.connect("bot.db")
    con.row_factory = sqlite3.Row  # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
    cur = await con.cursor()

    await cur.execute(
        'CREATE TABLE IF NOT EXISTS subscribed_messages (id INTEGER PRIMARY KEY, channel_id INTEGER, message_id INTEGER, '
        'guild_id INTEGER, phase INTEGER);')

    await cur.execute(
        'CREATE TABLE IF NOT EXISTS calendars (id INTEGER PRIMARY KEY, link TEXT, phase INTEGER UNIQUE);')

    await cur.execute(
        'CREATE TABLE IF NOT EXISTS verification_codes (id INTEGER PRIMARY KEY, code INTEGER, email VARCHAR(255) UNIQUE)'
    )

    await cur.execute(
        'CREATE TABLE IF NOT EXISTS verified_users (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, email VARCHAR(255) UNIQUE)'
    )

    await cur.execute(
        'CREATE TABLE IF NOT EXISTS synced_verification_messages (id INTEGER PRIMARY KEY, guild_id INTEGER, channel_id '
        'INTEGER, message_id INTEGER)'
    )

    try:
        await cur.execute(
            'ALTER TABLE verification_codes ADD COLUMN generated_at TIMESTAMP')

        await cur.execute(
            "UPDATE verification_codes SET generated_at = datetime('now') WHERE generated_at IS NULL;")
    except Exception as e:
        print(e)


    await con.commit()

    cm = db.connection_manager.ConnectionManager(con)
    await cm.initialize_cursor()

    return con


client.run(os.getenv("TOKEN"))

