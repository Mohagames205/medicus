import logging
import os

import discord

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
            await self.broadcast_info("Verification logger has been enabled")

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

        await self.broadcast_info(f"{member.mention} is geverifieerd als:", fields=fields,
                                  title="Nieuw lid geverifieerd")

    async def on_code_creation(self, code: int, student: verificationuser.PartialStudent):
        fields = [
            VerificationField("Code", str(code)),
            VerificationField("Naam", f"{student.name} {student.surname}"),
            VerificationField("E-mail", student.email)
        ]

        await self.broadcast_info(title="Aanmaak code", msg="Een verificatiecode werd aangemaakt", fields=fields)

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
        await self.send_embed(external_message="<@&1157397256165658704->", message=msg, fields=fields, title=title,
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
            VerificationField("Gekicked door", cause.mention),
            VerificationField("Slachtoffer", f"{victim.mention}({victim.name})"),
            VerificationField("Gedeverifieerd?", "Ja" if unverified else "Neen")
        ]

        if v_student:
            fields.append(VerificationField("E-mail", v_student.email))

        await self.broadcast_info(title="Lid ge-kicked", msg="",
                                  fields=fields)
