import asyncio
import random

from discord.ext import commands
import discord
from discord import app_commands
import json
from verification import verificationuser
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class VerificationModule(commands.Cog):
    def __init__(self, bot, cur):
        self.bot = bot
        self.tree = bot.tree
        self.cur = cur

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel is not None:
            await channel.send(f'WELKOM {member.mention} 🎊.')

    @app_commands.command(name="hello")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message("ewa")

    @app_commands.command(name="testverify")
    async def test_verification(self, int: discord.Interaction, voornaam: str, achternaam: str):
        await int.response.defer()
        if await self.is_student(voornaam, achternaam):
            await int.followup.send("Je bent inderdaad student! Check je mailbox om je identiteit te verifieren")
            await self.send_mail((await self.get_student(voornaam, achternaam)).email)
        else:
            await int.followup.send("Je bent geen student geneeskunde!")

    async def get_students(self):
        with open("assets/memberships.json") as file:
            memberships_raw = json.load(file)
            result = memberships_raw["results"]

            users = [verificationuser.VerificationUser(user["user"]["givenName"], user["user"]["familyName"],
                                                       user["user"]["emailAddress"])
                     if "emailAddress" in user["user"]
                     else verificationuser.VerificationUser(user["user"]["givenName"], user["user"]["familyName"], None)
                     for user in result]

            return users

    async def get_student(self, voornaam, achternaam):
        for student in await self.get_students():
            if voornaam.lower() == student.surname.lower() and achternaam.lower() == student.familyname.lower():
                return student

    async def send_mail(self, email):

        code = random.randint(1000, 9999)



        if email not in ["david.dawidian@student.kuleuven.be", "abdulsamed.sen@student.kuleuven.be",
                         "mohamed.elyousfi@student.kuleuven.be"]:
            return

        message = Mail(
            from_email='ikben@mootje.be',
            to_emails=email,
            subject='Verificatie GNK Discord',
            html_content=f'<strong>Hoi! Jouw persoonlijke code is: <u>{code}</u></strong>')
        try:
            sg = SendGridAPIClient("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")
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)

    async def is_student(self, voornaam, achternaam):
        for student in await self.get_students():
            if voornaam.lower() == student.surname.lower() and achternaam.lower() == student.familyname.lower():
                return True
