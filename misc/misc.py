from discord import app_commands
from discord.ext import tasks, commands
import discord
from discord import app_commands
from discord.ext import commands

class MiscModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tree = bot.tree
        self.__cog_name__ = "misc"



