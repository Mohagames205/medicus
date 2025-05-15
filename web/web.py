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


class Web(commands.Cog):
    pass
