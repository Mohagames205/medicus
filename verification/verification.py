import asyncio
import random
import sqlite3

from discord.ext import commands
import discord
from discord import app_commands, ui
import json
from verification import verificationuser
from verification import verificationmodal
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class VerificationModule(commands.Cog):
    def __init__(self, bot, con: sqlite3.Connection):
        self.bot = bot
        self.tree = bot.tree
        self.cur = con.cursor()
        self.con = con

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

        student = await self.get_student(voornaam, achternaam)
        if student is not None:
            await int.response.send_modal(verificationmodal.VerificationModal(student, self))
            # await (int.followup.original_response()).send_modal(Questionnaire())
            # await int.followup.send("Je bent inderdaad student! Check je mailbox om je identiteit te verifieren")
            # await self.send_mail((await self.get_student(voornaam, achternaam)).email)
        else:
            await int.response.send_message("Je bent geen student geneeskunde!")

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
        return None

    def send_mail(self, email, code):

        message = Mail(
            from_email='medicus@mootje.be',
            to_emails=email,
            subject='Verificatie GNK Discord',
            html_content=f'<strong>Hoi! Jouw persoonlijke code is: <u>{code}</u></strong>')
        try:
            sg = SendGridAPIClient(os.getenv("sendgrid_api"))
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)

    async def is_student(self, voornaam, achternaam):
        return any(
            voornaam.lower() == student.surname.lower() and achternaam.lower() == student.familyname.lower() for student
            in await self.get_students())

    def create_verification_code(self, email):
        code = random.randint(10000, 99999)
        self.cur.execute('INSERT OR REPLACE into verification_codes (`code`, `email`) values (?, ?)', (code, email))
        self.con.commit()
        return code

    async def verify_user(self, member: discord.Member, student: verificationuser.VerificationUser):
        role = member.guild.get_role(int(os.getenv('VERIFIED_ROLE_ID')))

        try:
            await member.edit(nick=student.surname)
        except Exception as er:
            print(er)

        await member.add_roles(role)
        self.cur.execute('INSERT OR IGNORE INTO verified_users (`user_id`) values(?)', (member.id,))
        self.con.commit()

    async def is_verified(self, user_id: int):
        self.cur.execute('SELECT COUNT(*) FROM verified_users WHERE `user_id` = ?', (user_id,))
        result = self.cur.fetchone()

        return result[0] > 0

    @commands.Cog.listener('on_member_join')
    async def on_verified_member_join(self, member: discord.Member):
        if member.get_role(int(os.getenv('VERIFIED_ROLE_ID'))) is None and await self.is_verified(member.id):
            role = member.guild.get_role(int(os.getenv('VERIFIED_ROLE_ID')))
            await member.add_roles(role)



