import json
import logging

import aiohttp
import aiosqlite
import discord
import pytz
from arrow import Arrow
from discord import app_commands
from discord.ext import tasks, commands
from ics import Calendar, Event

brussels_timezone = pytz.timezone('Europe/Brussels')


class CourseEvent:
    NO_EVENT = -1
    UPCOMING = 0
    CURRENT = 1

    def __init__(self, event: Event, status: int):
        self.event = event
        self.status = status


class ScheduleModule(commands.Cog):
    blacklist = json.load(open('assets/schedule_filter.json'))["filter"]

    def __init__(self, bot, con: aiosqlite.Connection):
        self.cur = None
        self.__cog_name__ = "scheduling"
        self.bot = bot
        self.tree = bot.tree
        self.con = con

    async def cog_load(self) -> None:
        self.cur = await self.con.cursor()
        self.check_ical.start()

    async def get_file_content(self, url):
        # thx https://github.com/Azure/azure-sdk-for-python/issues/13242#issuecomment-1239061801
        session = aiohttp.ClientSession()
        response = await session.get(url)

        content = await response.read()

        await session.close()
        return content.decode('utf-8')

    @app_commands.command(name="provideics")
    @commands.has_permissions(administrator=True)
    async def provide_ics(self, int: discord.Interaction, link: str, phase: int):
        await int.response.defer()
        await self.register_calendar(link, phase)
        await int.followup.send("ICS has been registered succesfully", ephemeral=True)

    @app_commands.command(name="setschedulechannel")
    async def set_schedule_channel(self, int: discord.Interaction, phase: int):
        embed = discord.Embed(
            title="Huidig hoorcollege",
            description="Inladen van ICS data",
            color=discord.Color.pink()
        )

        global_embed_msg = await int.channel.send(embed=embed)
        await self.register_message(phase, global_embed_msg)

        await int.response.send_message("Dit kanaal ontvangt vanaf nu uurrooster updates", ephemeral=True)

    async def get_event_at(self, time: Arrow, phase: int):
        calendar = await self.fetch_calendar(phase)

        if calendar is None:
            return CourseEvent(Event(name=f"Geen ICS geregistreerd voor fase {str(phase)}"), CourseEvent.NO_EVENT)

        file = await self.get_file_content(await self.fetch_calendar(phase))

        try:
            cal = Calendar(file)

            events = sorted(cal.events, key=lambda ev: ev.begin)

            for event in events:

                if event.name in self.blacklist:
                    continue

                event_begin = Arrow.fromdatetime(event.begin, tzinfo=brussels_timezone)
                event_end = Arrow.fromdatetime(event.end, tzinfo=brussels_timezone)

                if event_begin <= time <= event_end:
                    return CourseEvent(event, CourseEvent.CURRENT)

                elif event_end > time:
                    return CourseEvent(event, CourseEvent.UPCOMING)
        except:
            logging.warning("Something went wrong while parsing the calendar... trying again.")

        return CourseEvent(Event("Geen hoorcollege"), CourseEvent.NO_EVENT)

    async def update_embed(self, embed_message, course_event: CourseEvent):
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

        try:
            await embed_message.edit(embed=embed)
        except discord.errors.NotFound:
            logging.warning("Message does not exist...")

    @app_commands.command(name="anonymous", description="Stel je vraag anoniem")
    async def ask_anonymous(self, interaction: discord.Interaction, question: str):

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Anonieme vraag",
            description=f"{question}",
            colour=discord.Color.purple()
        )

        logging.info(f"{interaction.user.id} asked following question: {question}")
        await interaction.followup.send("Je vraag is succesvol gesteld in dit kanaal")
        await interaction.channel.send(embed=embed)

    @tasks.loop(seconds=30)
    async def check_ical(self):
        for guild in self.bot.guilds:

            for embed_message in await self.fetch_messages(guild):
                message = embed_message["message"]
                phase = embed_message["phase"]

                now = Arrow.now(tzinfo=brussels_timezone)

                logging.info(f"[{now}][Phase {phase}][{guild.id}][{message.channel.id}][{message.id}] Updating embed")

                event_now = await self.get_event_at(now, phase)
                await self.update_embed(message, event_now)

    @commands.Cog.listener('on_raw_message_delete')
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if await self.is_subscribed_message(payload.message_id):
            await self.unregister_message(payload.message_id)

    async def register_calendar(self, link: str, phase: int):
        await self.cur.execute('INSERT INTO calendars (`link`, `phase`) values (?, ?)',
                               (link, phase))
        await self.con.commit()

    async def fetch_calendar(self, phase: int):
        await self.cur.execute('SELECT * FROM calendars WHERE `phase` = ?', (phase,))
        result = await self.cur.fetchone()

        return result["link"] if result else None

    async def is_subscribed_message(self, message_id: int):
        await self.cur.execute('SELECT count(*) FROM subscribed_messages WHERE `message_id` = ?',
                               (message_id,))
        result = await self.cur.fetchone()

        return result[0] > 0

    async def fetch_messages(self, guild: discord.Guild):
        await self.cur.execute('SELECT * FROM subscribed_messages WHERE `guild_id` = ?', (guild.id,))
        results = await self.cur.fetchall()

        messages = []
        for result in results:
            guild = self.bot.get_guild(result["guild_id"])
            channel = guild.get_channel(result["channel_id"])

            try:
                message = await channel.get_partial_message(result["message_id"]).fetch()
            except discord.errors.NotFound:
                logging.warning(f"Unregistering non existent message with ID: {result['message_id']}")
                await self.unregister_message(result["message_id"])
                continue

            messages.append({"message": message, "phase": result["phase"]})

        return messages

    async def register_message(self, phase: int, message: discord.Message):
        await self.cur.execute(
            'INSERT INTO subscribed_messages (`phase`, `channel_id`, `message_id`, `guild_id`) values (?, ?, ?, ?)',
            (phase, message.channel.id, message.id, message.guild.id))
        await self.con.commit()

    async def unregister_message(self, message_id: int):
        await self.cur.execute('DELETE FROM subscribed_messages WHERE message_id = ?', (message_id,))
        await self.con.commit()
