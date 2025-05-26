import logging
import os

import discord
import git

from verification import verificationuser


class VerificationField:

    def __init__(self, name: str, value: str, inline: bool = False):
        self.name = name
        self.value = value
        self.inline = inline

    def __str__(self):
        return f"{self.name}: {self.value}"


class VerificationLogger:

    def __init__(self, channel: discord.TextChannel):
        self.logging_channel = channel

    async def enable(self):
        if os.getenv("ENVIRONMENT") != "dev":
            repo = git.Repo(search_parent_directories=True)
            sha = repo.head.object.hexsha
            await self.broadcast_info(f"Medicus is opgestart en runt op commit [{sha}[{repo.active_branch}]](https://github.com/mohagames205/medicus/commit/{sha})")

    async def send_embed(self, title: str, message: str, fields=None, color: discord.Color = discord.Color.blue(),
                         external_message: str = ""):
        if fields is None:
            fields = []

        embed = discord.Embed(
            title=title,
            description=message,
            color=color
        )

        for field in fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

        await self.logging_channel.send(content=external_message, embed=embed)

    async def broadcast_info(self, msg: str, fields=None, title: str = "Logger"):
        if fields is None:
            fields = []

        str_fields = ""
        for field in fields:
            str_fields += f"\n {str(field)}"

        logging.info(msg + str_fields)
        await self.send_embed(message=msg, fields=fields, title=title)

    async def user_verified(self, member: discord.Member, student: verificationuser.PartialStudent):

        fields = [
            VerificationField("Naam", student.name),
            VerificationField("Achternaam", student.surname),
            VerificationField("E-mail", student.email)
        ]

        channel = await member.guild.fetch_channel(int(os.getenv("WELCOME_CHANNEL")))
        if channel is not None:
            await channel.send(f'Welkom {member.mention} in de geneeskunde Discord server!! 🎊.')

        await self.broadcast_info(f"{member.mention}({member.name}) is geverifieerd als:", fields=fields,
                                  title="Nieuw lid geverifieerd")

    async def on_code_creation(self, code: int, user: discord.User, student: verificationuser.PartialStudent):
        fields = [
            VerificationField("Code", str(code)),
            VerificationField("Naam", f"{student.name} {student.surname}"),
            VerificationField("E-mail", student.email)
        ]

        await self.broadcast_info(title="Aanmaak code", msg=f"Een verificatiecode werd aangemaakt voor {user.mention}{user.name}", fields=fields)

    async def on_verified_user_join(self, member: discord.Member):
        await self.broadcast_info(title="Geverifieerde student gejoined",
                                  msg=f"{member.mention} was al eerder geverifieerd en heeft automatisch toegang "
                                      f"gekregen.")

    async def broadcast_warning(self, msg: str, fields=None, title: str = "❗ Waarschuwing"):
        if fields is None:
            fields = []

        str_fields = ""
        for field in fields:
            str_fields += f"\n {str(field)}"

        logging.info(msg + str_fields)
        await self.send_embed(external_message=f"<@&{os.getenv('MODERATOR_ROLE')}>", message=msg, fields=fields, title=title,
                              color=discord.Color.orange())

    async def already_id_verified(self, member: discord.Member):
        await self.broadcast_warning(title="Dubbele verificatie",
                                     msg=f"{member.mention} is al geverifieerd, maar probeert zich nogmaals te "
                                         f"verifiëren. Mogelijks is hier iets misgelopen?")

    async def already_email_verified(self, member: discord.Member, student: verificationuser.Student):

        fields = [
            VerificationField("Naam", f"{student.name} {student.surname}"),
            VerificationField("E-mail", student.email),
            VerificationField("Reeds geverifieerd account", f"<@{student.discord_uid}>")
        ]

        await self.broadcast_warning(title="Poging tot verificatie ALT",
                                     msg=f"{member.mention} probeert een ander account te verifiëren, maar is al "
                                         f"geverifieerd.",
                                     fields=fields)

    async def on_user_kick(self, cause: discord.Member, victim: discord.Member, unverified: bool):

        v_student = await verificationuser.Student.from_discord_uid(victim.id)

        fields = [
            VerificationField("Gekicked door", f"{cause.mention}({cause.name})"),
            VerificationField("Slachtoffer", f"{victim.mention}({victim.name})"),
            VerificationField("Gedeverifieerd?", "Ja" if unverified else "Neen")
        ]

        if v_student:
            fields.append(VerificationField("E-mail", v_student.email))

        await self.broadcast_info(title="Lid ge-kicked", msg="",
                                  fields=fields)

    async def on_ask_question(self, asker: discord.Member, question: str, message: discord.Message):

        fields = [
            VerificationField("Gesteld door", f"||{asker.mention}({asker.name})||"),
            VerificationField("Vraag", question),
            VerificationField("Bericht", message.jump_url)
        ]

        await self.broadcast_info(title="Anonieme vraag", msg="", fields=fields)

    async def no_student_found(self, member: discord.Member, email: str):

        fields = [
            VerificationField("E-mail", email),
        ]
        await self.broadcast_warning(title="Geen student gevonden",
                                     msg=f"{member.name}{member.mention} kon niet gevalideerd worden als student.")
