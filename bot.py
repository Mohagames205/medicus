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


class CourseEvent:
    NO_EVENT = -1
    UPCOMING = 0
    CURRENT = 1

    def __init__(self, event: Event, status: int):
        self.event = event
        self.status = status


intents = discord.Intents.all()
client = commands.Bot(command_prefix='$', intents=intents)
tree = client.tree

embed_messages = {}

con = sqlite3.connect("bot.db")
con.row_factory = sqlite3.Row  # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
cur = con.cursor()
cur.execute(
    'CREATE TABLE IF NOT EXISTS subscribed_messages (id INTEGER PRIMARY KEY, channel_id INTEGER, message_id INTEGER, guild_id INTEGER, phase INTEGER);')

cur.execute(
    'CREATE TABLE IF NOT EXISTS calendars (id INTEGER PRIMARY KEY, link TEXT, phase INTEGER UNIQUE);')

# tijdelijke hack

tijd = {
    "jaar": 2023,
    "maand": 10,
    "dag": 10,
    "uur": 8,
    "minuut": 30,
    "override": False
}


# sync the slash command to your server
@client.event
async def on_ready():
    for guild in client.guilds:
        tree.copy_global_to(guild=discord.Object(id=guild.id))
        await tree.sync(guild=discord.Object(id=guild.id))
    check_ical.start()
    game = discord.Game("mootje.be")
    await client.change_presence(status=discord.Status.idle, activity=game)
    print("ready")


async def get_file_content(url):
    # thx https://github.com/Azure/azure-sdk-for-python/issues/13242#issuecomment-1239061801
    session = aiohttp.ClientSession()
    response = await session.get(url)

    content = await response.read()

    await session.close()
    return content.decode('utf-8')


@tree.command(name="providecal")
@commands.has_permissions(kick_members=True)
async def provice_ics(int: discord.Interaction, link: str, phase: int):
    await register_calendar(link, phase)
    await int.response.send_message("ICS has been registered succesfully", ephemeral=True)


@tree.command(name="setschedulechannel")
async def set_schedule_channel(int: discord.Interaction, phase: int):
    embed = discord.Embed(
        title="Huidig hoorcollege",
        description="Inladen van ICS data",
        color=discord.Color.pink()
    )

    global_embed_msg = await int.channel.send(embed=embed)
    await register_message(phase, global_embed_msg)

    await int.response.send_message("Dit kanaal ontvangt vanaf nu uurrooster updates", ephemeral=True)


async def get_event_at(time: Arrow, phase: int):
    calendar = await fetch_calendar(phase)

    if calendar is None:
        return CourseEvent(Event(name=f"Geen ICS geregistreerd voor fase {str(phase)}"), CourseEvent.NO_EVENT)

    file = await get_file_content(await fetch_calendar(phase))
    cal = Calendar(file)

    events = sorted(cal.events, key=lambda ev: ev.begin)

    ongoing_event = None
    next_event = None

    for event in events:
        if event.begin <= time <= event.end:
            ongoing_event = event

        elif event.begin > time:
            next_event = event
            break

    if ongoing_event:
        return CourseEvent(ongoing_event, CourseEvent.CURRENT)
    elif next_event:
        return CourseEvent(next_event, CourseEvent.UPCOMING)
    else:
        return CourseEvent(Event("Geen hoorcollege"), CourseEvent.NO_EVENT)


async def update_embed(embed_message, course_event: CourseEvent):
    ongoing_event = course_event.event
    duration_str = str(ongoing_event.duration)

    if course_event.status == CourseEvent.CURRENT:
        title = "🎯  |  Huidig hoorcollege"
        color = discord.Color.purple()
    elif course_event.status == CourseEvent.UPCOMING:
        title = "➡️  |  Toekomstig hoorcollege"
        color = discord.Color.green()
    else:
        title = "❌  |  Geen hoorcollege "
        color = discord.Color.red()

    embed = discord.Embed(
        title=title,
        color=color
    )

    embed.add_field(name="Hoorcollege", value=f"{ongoing_event.name}")

    if course_event.status != course_event.NO_EVENT:
        hours, minutes, _ = duration_str.split(":")
        formatted_duration = f"{hours}u{minutes}m"

        embed.add_field(name="Locatie", value=f"{ongoing_event.location}", inline=False)
        embed.add_field(name="Tijd",
                        value=f"{ongoing_event.begin.format('HH:mm', 'nl')} - {ongoing_event.end.format('HH:mm', 'nl')}  |  {ongoing_event.end.format('D MMMM YYYY', 'nl')}",
                        inline=False)
        embed.add_field(name="Duur", value=f"{formatted_duration}", inline=False)
        embed.add_field(name="Beschrijving", value=f"{ongoing_event.description}", inline=False)

    await embed_message.edit(embed=embed)


@tree.command(name="overridetime")
async def override_time(interaction: discord.Interaction, jaar: int, maand: int, dag: int, uur: int, minuut: int):
    tijd["jaar"] = jaar
    tijd["maand"] = maand
    tijd["dag"] = dag
    tijd["uur"] = uur
    tijd["minuut"] = minuut
    tijd["override"] = True

    await interaction.response.send_message("Time has been succesfully overriden")


@tree.command(name="clearoverride")
async def clear_override(interaction: discord.Interaction):
    tijd["override"] = False
    await interaction.response.send_message("Time has been succesfully reset")


@tasks.loop(seconds=30)
async def check_ical():
    print("fetching updates...")
    for guild in client.guilds:

        for embed_message in await fetch_messages(guild):
            message = embed_message["message"]
            phase = embed_message["phase"]

            brussels_timezone = pytz.timezone('Europe/Brussels')

            now = Arrow.now()

            if tijd["override"]:
                now = Arrow.fromdatetime(
                    datetime(tijd["jaar"], tijd["maand"], tijd["dag"], tijd["uur"], tijd["minuut"]),
                    tzinfo=brussels_timezone)
            await update_embed(message, await get_event_at(now, phase))


async def register_calendar(link: str, phase: int):
    cur.execute('INSERT INTO calendars (`link`, `phase`) values (?, ?)',
                (link, phase))
    con.commit()


async def fetch_calendar(phase: int):
    cur.execute('SELECT * FROM calendars WHERE `phase` = ?', (phase,))
    result = cur.fetchone()

    return result["link"] if result else None


async def fetch_messages(guild: discord.Guild):
    cur.execute('SELECT * FROM subscribed_messages WHERE `guild_id` = ?', (guild.id,))
    results = cur.fetchall()

    messages = []
    for result in results:
        guild = client.get_guild(result["guild_id"])
        channel = guild.get_channel(result["channel_id"])
        message = await channel.get_partial_message(result["message_id"]).fetch()

        messages.append({"message": message, "phase": result["phase"]})

    return messages


async def register_message(phase: int, message: discord.Message):
    cur.execute('INSERT INTO subscribed_messages (`phase`, `channel_id`, `message_id`, `guild_id`) values (?, ?, ?, ?)',
                (phase, message.channel.id, message.id, message.guild.id))
    con.commit()


client.run(os.getenv("token"))
