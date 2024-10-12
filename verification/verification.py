import asyncio
import datetime
import json
import logging
import os
import random
import time
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import db.connection_manager
from verification import verificationmodal
from verification import verificationuser
from verification.verification_logger import VerificationLogger


class VerificationView(discord.ui.View):

    def __init__(self, module):
        super().__init__(timeout=None)
        self.add_item(verificationmodal.VerificationButton("Vraag code aan",
                                                           module))


class VerificationModule(commands.Cog):
    logger = None
    replaceable_roles = None

    def __init__(self, bot: discord.ext.commands.Bot, con: aiosqlite.Connection):
        self.cur = None
        # still here for BC
        self.replaceable_roles = self.fetch_replaceable_roles()

        VerificationModule.replaceable_roles = self.fetch_replaceable_roles()
        self.__cog_name__ = "verification"
        self.bot = bot
        self.tree = bot.tree
        self.con = con

        channel = bot.get_channel(int(os.getenv("REPORTS_CHANNEL")))
        VerificationModule.logger = VerificationLogger(channel)

    async def cog_load(self) -> None:
        self.cur = await self.con.cursor()

        await VerificationModule.logger.enable()

    def fetch_replaceable_roles(self):
        with open("assets/role_verification.json") as file:
            roles = json.load(file)
            return roles["roles"]

    async def get_synced_messages(self):
        await self.cur.execute(
            'SELECT *  FROM synced_verification_messages'
        )

        result = await self.cur.fetchall()

        return result

    async def refresh_messages(self):
        for message in await self.get_synced_messages():
            guild = self.bot.get_guild(message["guild_id"])
            channel = guild.get_channel(message["channel_id"])

            try:
                message = await channel.get_partial_message(message["message_id"]).fetch()

                await message.edit(view=VerificationView(self))
            except discord.errors.NotFound:
                print(f"Unregistering non existent message with ID: {message['message_id']}")
                await self.unregister_verification_channel(message["message_id"])
                continue

    @app_commands.command(name="setverificationchannel")
    async def set_verification_channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Geneeskunde Verificatie",
            description="Om volledige toegang te krijgen tot deze groep, moet je jezelf eerst verifiëren. Druk op de "
                        "**onderstaande** knop om dit te doen:\n\n"
                        "1. **Druk** op de onderstaande knop\n"
                        "2. Je ontvangt een e-mail op je studentenmail met een **code**.\n"
                        "3. Druk vervolgens op de knop **'code ingeven'** en geef de code in.\n\n"
                        "⚠ De code durft soms eens in de spambox te vallen. Check dus zeker je spambox!",
            color=discord.Color.blue()
        )

        global_embed_msg = await interaction.channel.send(embed=embed, view=VerificationView(self))

        await self.cur.execute(
            "INSERT INTO synced_verification_messages (`guild_id`, `channel_id`, `message_id`) values(?, ?, ?)",
            (global_embed_msg.guild.id, global_embed_msg.channel.id, global_embed_msg.id))
        await self.con.commit()
        await interaction.followup.send("OK")

    async def unregister_verification_channel(self, message_id: int):
        await self.cur.execute(
            "DELETE FROM synced_verification_messages WHERE message_id = ?", (message_id,))
        await self.con.commit()

    def send_mail(self, email, code):
        with open('assets/email.html') as file:
            html = file.read()

        message = Mail(
            from_email='medicus@mootje.be',
            to_emails=email,
            subject='Verificatie GNK Discord',
            html_content=html.replace("{{CODE}}", str(code)))
        try:
            sg = SendGridAPIClient(os.getenv("SENDGRID_API"))
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)

    @app_commands.command()
    async def force_verify_user(self, int: discord.Interaction, member: discord.Member, email: str, voornaam: str = "",
                                achternaam: str = ""):
        await int.response.defer()

        student = verificationuser.PartialStudent(email, voornaam, achternaam)

        if student:
            await student.verify(member)

            embed = discord.Embed(
                title="Succesvol geverifieerd",
                description="Je bent succesvol geverifieerd als student **Geneeskunde** aan de **KU Leuven.**",
                color=discord.Color.from_rgb(82, 189, 236),
            )

            await member.send(embed=embed)
            await int.followup.send(f"{member.mention} is succesvol geverifieerd!")

    @app_commands.command()
    async def unverify_email(self, interaction: discord.Interaction, email: str):
        await interaction.response.defer()

        student = await verificationuser.Student.get_by_email(email)

        if not student:
            await interaction.followup.send(f'Er bestaat geen gebruiker met **email** {email}.')
            return

        await student.unverify()

        # check if the user account still exists
        member = interaction.guild.get_member(student.discord_uid)
        if not member:
            await interaction.followup.send(
                f'De verificatiestatus van dit e-mailadres is ingetrokken, maar de Discord gebruiker geassocieerd met dit e-mailadres bestaat niet meer.')
            return

        replaceable_roles = VerificationModule.replaceable_roles
        roles_to_remove = [member.guild.get_role(replaceable_roles[str(role.id)]) for role in member.roles if
                           str(role.id) in list(replaceable_roles.keys())]
        await member.remove_roles(*roles_to_remove)
        await member.add_roles(member.guild.get_role(int(os.getenv('UNVERIFIED_ROLE_ID'))))

        await interaction.followup.send(f'De gebruiker met email {email} is succes gedeverifieerd.')

    @app_commands.command()
    async def force_unverify_user(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()

        student = await verificationuser.Student.from_discord_uid(member.id)
        if student:
            await student.unverify()

            replaceable_roles = VerificationModule.replaceable_roles

            roles_to_remove = [member.guild.get_role(replaceable_roles[str(role.id)]) for role in member.roles if
                               str(role.id) in list(replaceable_roles.keys())]
            await member.remove_roles(*roles_to_remove)

            await member.add_roles(member.guild.get_role(int(os.getenv('UNVERIFIED_ROLE_ID'))))

            await interaction.followup.send(f"{member.mention} is succesvol gedeverifieerd!")
        else:
            await interaction.followup.send(f"A sahbe, {member.mention} is niet eens geverifieerd. Rwina!")

    async def is_verified(self, user_id: int):
        await self.cur.execute('SELECT COUNT(*) FROM verified_users WHERE `user_id` = ?', (user_id,))
        result = await self.cur.fetchone()

        return result[0] > 0

    @app_commands.command()
    async def whois(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()

        student = await verificationuser.Student.from_discord_uid(member.id)

        if student:
            pt_student = await verificationuser.PartialStudent.get_by_email(student.email)

            embed = discord.Embed(
                title="Whois",
                description=f"Meer informatie over {member.mention}",
                color=discord.Color.blue()
            )

            embed.add_field(name="Naam",
                            value=f"{pt_student.name} {pt_student.surname}" if pt_student else "Geen studentendata gevonden",
                            inline=False)
            embed.add_field(name="Email", value=f"{student.email}", inline=False)

            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send("Deze persoon is waarschijnlijk niet geverifieerd.")

    @app_commands.command()
    async def lookup(self, interaction: discord.Interaction, email: str):
        await interaction.response.defer()

        cm = db.connection_manager.ConnectionManager
        cur = cm.cur
        conn = cm.con

        await cur.execute('SELECT user_id FROM verified_users WHERE `email` = ?', (email,))
        result = await cur.fetchone()

        if not result:
            await interaction.followup.send("Deze persoon zit niet in de server of is niet geverifieerd.")

        embed = discord.Embed(
            title="Reverse Lookup",
            description=f"Meer informatie over `{email}`",
            color=discord.Color.blue()
        )

        embed.add_field(name="Discord",
                        value=f"<@{result['user_id']}>",
                        inline=False)

        await interaction.followup.send(embed=embed)
        return

    @app_commands.command()
    async def kick(self, int: discord.Interaction, member: discord.Member, reason: str = "", unverify: bool = False):

        await int.response.defer()

        student = await verificationuser.Student.from_discord_uid(member.id)

        if unverify and student:
            await student.unverify()

        await VerificationModule.logger.on_user_kick(int.user, member, unverify)

        await int.followup.send(
            f"{member.mention} is gekicked door {int.user.mention} omwille van: ```{reason if reason != '' else 'Geen reden opgegeven'}```")

        embed = discord.Embed(
            title="Je bent gekicked",
            description="Je bent gekicked uit de Geneeskunde discord-groep. Indien je vragen of opmerkingen hebt, "
                        "contacteer je het best <@326311622194888704>.",
            color=discord.Color.red()
        )

        embed.add_field(name="Reden", value=reason if reason != '' else 'Geen reden opgegeven')

        await member.send(embed=embed)

        await member.kick(reason=reason)

    @commands.Cog.listener('on_member_join')
    async def on_verified_member_join(self, member: discord.Member):
        student = await verificationuser.Student.from_discord_uid(member.id)
        if student is None:
            await member.add_roles(member.guild.get_role(int(os.getenv('UNVERIFIED_ROLE_ID'))))
            return

        await VerificationModule.logger.on_verified_user_join(member)

    def get_sync_roles(self, roles_1, roles_2, member: discord.Member):
        role_diff = set(roles_2) - set(roles_1)
        subscribed_roles = [member.guild.get_role(self.replaceable_roles[str(role.id)]) for role in role_diff if
                            str(role.id) in list(self.replaceable_roles.keys())]
        subscribed_roles = [role for role in subscribed_roles if role is not None]

        return subscribed_roles

    @app_commands.command()
    async def sync_roles(self, interaction: discord.Interaction):
        await interaction.response.defer()

        for member in interaction.guild.members:
            student = await verificationuser.Student.from_discord_uid(member.id)

            if not student:
                continue

            roles = member.roles

            roles_to_add = [member.guild.get_role(self.replaceable_roles[str(role.id)]) for role in roles if
                            str(role.id) in list(self.replaceable_roles.keys()) and not member.get_role(
                                self.replaceable_roles[str(role.id)])]

            roles_to_remove = [role for role in roles if
                               role.id in list(self.replaceable_roles.values()) and not member.get_role(
                                   int({str(v): k for k, v in self.replaceable_roles.items()}[str(role.id)]))]

            if roles_to_add: await interaction.channel.send(
                f"Rollen toe te voegen bij {member.mention}" + ", ".join([role.name for role in roles_to_add]))

            await member.add_roles(*roles_to_add)

            if roles_to_remove: await interaction.channel.send(
                f"Rollen te verwijderen bij {member.mention}" + ", ".join([role.name for role in roles_to_remove]))

            await member.remove_roles(*roles_to_remove)

        await interaction.followup.send("DONE")

    @commands.Cog.listener('on_member_update')
    async def on_role_update(self, before: discord.Member, after: discord.Member):
        student = await verificationuser.Student.from_discord_uid(after.id)
        if student:
            before_roles = set(before.roles)
            after_roles = set(after.roles)

            added_roles = after_roles - before_roles
            removed_roles = before_roles - after_roles

            if added_roles:
                sync_roles_to_add = [role for role in self.get_sync_roles(before.roles, after.roles, after)
                                     if after.get_role(role.id) is None]

                roles = [role for role in self.get_sync_roles(before.roles, after.roles, after) if
                         after.get_role(role.id) is None]
                await after.add_roles(*roles)

                if sync_roles_to_add:
                    await after.add_roles(*sync_roles_to_add)

            if removed_roles:
                sync_roles_to_remove = [role for role in self.get_sync_roles(after.roles, before.roles, after)
                                        if after.get_role(role.id)]
                if sync_roles_to_remove:
                    await after.remove_roles(*sync_roles_to_remove)

            print(f"Added roles: {sync_roles_to_add if added_roles else 'None'}")
            print(f"Removed roles: {sync_roles_to_remove if removed_roles else 'None'}")
            print("Role update processed successfully.")

    @app_commands.command(name="generatepool")
    async def generate_pool(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="anonymous", description="Stel je vraag anoniem")
    async def ask_anonymous(self, interaction: discord.Interaction, question: str):

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Anonieme vraag",
            description=f"{question}",
            colour=discord.Color.purple()
        )

        message = await interaction.channel.send(embed=embed)
        await interaction.followup.send("Je vraag is succesvol gesteld in dit kanaal")
        await VerificationModule.logger.on_ask_question(interaction.user, question, message)

    @app_commands.command(name="whisper", description="Stel je vraag anoniem")
    async def whisper(self, interaction: discord.Interaction, member: discord.Member, message: str):

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title=f"⚠ Bericht van moderator",
            description=f"{message}",
            colour=discord.Color.blue(),
        )

        embed.set_footer(text=f"GNK discord")

        message = await member.send(content=f"U heeft een bericht ontvangen van {interaction.user.mention}",
                                    embed=embed)
        await interaction.followup.send("Je bericht is succesvol verzonden!")

    @commands.Cog.listener('verified_join')
    async def on_verified_join(self, member: discord.Member):
        channel = await member.guild.fetch_channel(int(os.getenv("WELCOME_CHANNEL")))
        if channel is not None:
            await channel.send(f'Welkom {member.mention}!! 🎊.')
