import asyncio
import random
import sqlite3

from discord.ext import commands
import discord
from discord import app_commands, ui
import json

from verification import verificationuser
from verification import verificationmodal
from verification.verification_logger import VerificationLogger
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class VerificationModule(commands.Cog):

    def __init__(self, bot: discord.ext.commands.Bot, con: sqlite3.Connection):
        self.replaceable_roles = self.fetch_replaceable_roles()
        self.__cog_name__ = "verification"
        self.bot = bot
        self.tree = bot.tree
        self.cur = con.cursor()
        self.con = con

        channel = bot.get_channel(int(os.getenv("REPORTS_CHANNEL")))
        self.verification_logger = VerificationLogger(channel)

    async def cog_load(self) -> None:
        await self.verification_logger.enable()

    def fetch_replaceable_roles(self):
        with open("assets/role_verification.json") as file:
            roles = json.load(file)
            return roles["roles"]

    def get_synced_messages(self):
        result = self.cur.execute(
            'SELECT *  FROM synced_verification_messages'
        ).fetchall()

        return result

    async def refresh_messages(self):
        for message in self.get_synced_messages():
            guild = self.bot.get_guild(message["guild_id"])
            channel = guild.get_channel(message["channel_id"])

            try:
                message = await channel.get_partial_message(message["message_id"]).fetch()
                view = discord.ui.View(
                    timeout=None
                )
                view.add_item(
                    verificationmodal.VerificationButton("Vraag code aan", verificationmodal.CollectNameModal,
                                                         self))
                await message.edit(view=view)
            except discord.errors.NotFound:
                print(f"Unregistering non existent message with ID: {message['message_id']}")
                await self.unregister_verification_channel(message["message_id"])
                continue

    # Tijdelijke hack, in de toekomst integreren we dit in een "VerifiedUser" class
    async def get_uid_by_email(self, email: str):
        self.cur.execute('SELECT user_id FROM verified_users WHERE `email` = ?', (email,))
        result = self.cur.fetchone()

        return result[0]

    @app_commands.command(name="setverificationchannel")
    async def set_verification_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Geneeskunde Verificatie",
            description="Om volledige toegang te krijgen tot deze groep, moet je jezelf eerst verifiëren. Druk op de "
                        "**onderstaande** knop om dit te doen:\n\n"
                        "1. **Druk** op de onderstaande knop\n"
                        "2. Je ontvangt een e-mail op je studentenmail met een **code**.\n"
                        "3. Druk vervolgens op de knop **'code ingeven'** en geef de code in.\n",
            color=discord.Color.blue()
        )

        view = discord.ui.View(
            timeout=None
        )
        view.add_item(
            verificationmodal.VerificationButton("Vraag code aan", verificationmodal.CollectNameModal, self))

        global_embed_msg = await interaction.channel.send(embed=embed, view=view)

        self.cur.execute(
            "INSERT INTO synced_verification_messages (`guild_id`, `channel_id`, `message_id`) values(?, ?, ?)",
            (global_embed_msg.guild.id, global_embed_msg.channel.id, global_embed_msg.id))
        self.con.commit()
        await interaction.followup.send("OK")

    async def unregister_verification_channel(self, message_id: int):
        self.cur.execute(
            "DELETE FROM synced_verification_messages WHERE message_id = ?", (message_id,))
        self.con.commit()

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
            if voornaam.lower() == student.name.lower() and achternaam.lower() == student.surname.lower():
                return student
        return None

    def send_mail(self, email, code):
        with open('assets/email.html') as file:
            html = file.read()

        message = Mail(
            from_email='medicus@mootje.be',
            to_emails=email,
            subject='Verificatie GNK Discord',
            html_content=html.replace("{{CODE}}", str(code)))
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
            voornaam.lower() == student.name.lower() and achternaam.lower() == student.surname.lower() for student
            in await self.get_students())

    async def create_verification_code(self, student: verificationuser.VerificationUser):

        email = student.email

        code = random.randint(10000, 99999)
        self.cur.execute('INSERT OR REPLACE into verification_codes (`code`, `email`) values (?, ?)', (code, email))
        self.con.commit()

        await self.verification_logger.on_code_creation(code, student)

        return code

    @app_commands.command()
    async def force_verify_user(self, int: discord.Interaction, user: discord.Member, name: str, surname: str):

        student = await self.get_student(name, surname)

        if student:
            await self.verify_user(user, student)

            embed = discord.Embed(
                title="Succesvol geverifieerd",
                description="Je bent succesvol geverifieerd als student **Bachelor Geneeskunde** aan de **KU Leuven.**",
                color=discord.Color.from_rgb(82, 189, 236)
            )

            await user.send(embed=embed)

            await int.response.send_message(f"{user.mention} is succesvol geverifieerd!")

    async def verify_user(self, member: discord.Member, student: verificationuser.VerificationUser):
        role = member.guild.get_role(int(os.getenv('UNVERIFIED_ROLE_ID')))

        try:
            await member.edit(nick=student.name)
        except Exception as er:
            print(er)

        await member.remove_roles(role)
        await self.replace_verification_roles(member)

        await self.verification_logger.user_verified(member, student)

        self.cur.execute('INSERT OR IGNORE INTO verified_users (`user_id`, `email`) values(?, ?)',
                         (member.id, student.email))
        self.con.commit()

    async def is_email_verified(self, email: str):
        self.cur.execute('SELECT COUNT(*) FROM verified_users WHERE `email` = ?', (email,))
        result = self.cur.fetchone()

        return result[0] > 0

    async def is_verified(self, user_id: int):
        self.cur.execute('SELECT COUNT(*) FROM verified_users WHERE `user_id` = ?', (user_id,))
        result = self.cur.fetchone()

        return result[0] > 0

    @commands.Cog.listener('on_member_join')
    async def on_verified_member_join(self, member: discord.Member):
        if not await self.is_verified(member.id):
            await member.add_roles(member.guild.get_role(int(os.getenv('UNVERIFIED_ROLE_ID'))))
            return

        await self.verification_logger.on_verified_user_join(member)

    async def replace_verification_roles(self, member: discord.Member):
        roles = member.roles

        for role in roles:
            if str(role.id) in list(self.replaceable_roles.keys()):
                real_role = member.guild.get_role(self.replaceable_roles[str(role.id)])
                if member.get_role(real_role.id) is None:
                    await member.add_roles(real_role)

                # await member.remove_roles(role)
                # don't remove the role, so when the user decides to change the role after onboarding, the bot can detect that and change the role for the user

    def get_sync_roles(self, roles_1, roles_2, member: discord.Member):
        role_diff = set(roles_2) - set(roles_1)
        subscribed_roles = [member.guild.get_role(self.replaceable_roles[str(role.id)]) for role in role_diff if
                            str(role.id) in list(self.replaceable_roles.keys())]
        subscribed_roles = [role for role in subscribed_roles if role is not None]

        return subscribed_roles

    @commands.Cog.listener('on_member_update')
    async def on_role_update(self, before: discord.Member, after: discord.Member):
        if await self.is_verified(after.id):

            if len(before.roles) < len(after.roles):
                roles = [role for role in self.get_sync_roles(before.roles, after.roles, after) if
                         after.get_role(role.id) is None]
                await after.add_roles(*roles)

            if len(before.roles) > len(after.roles):
                roles = [role for role in self.get_sync_roles(after.roles, before.roles, after) if
                         after.get_role(role.id)]
                await after.remove_roles(*roles)
