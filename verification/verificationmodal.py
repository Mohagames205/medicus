import os

import discord
from discord import ui

import verification.verificationuser


class VerificationButton(ui.Button):
    def __init__(self, label, verification_module):
        super().__init__(label=label, emoji="📥")
        self.verification_module = verification_module

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CollectNameModal(self.verification_module))
        await self.verification_module.refresh_messages()


class InputCodeButton(ui.Button):
    def __init__(self, student, verification_module):
        super().__init__(label="Code invullen", emoji="🔐")
        self.student = student
        self.verification_module = verification_module

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VerificationModal(self.student, self.verification_module))


class CollectNameModal(ui.Modal, title="Geef je studentenmail"):
    studentmail = ui.TextInput(label="Studentenmail", placeholder="voornaam.achternaam@student.kuleuven.be")

    def __init__(self, verification_module):
        super().__init__()
        self.verification_module = verification_module

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        student = await verification.verificationuser.PartialStudent.get_by_email(self.studentmail.value)

        if student is not None:

            # fetches the full verified student object, which includes the discord uid
            verified_student = await student.full()

            if verified_student:
                await self.verification_module.logger.already_email_verified(interaction.user, verified_student)

                embed = discord.Embed(
                    title="Verificatie mislukt",
                    description="Je hebt reeds een account in deze server dat gekoppeld is aan de gegeven gegevens. We kunnen dit account dus niet verifiëren. Stuur een bericht in <#1167092094746239026> voor hulp.",
                    color=discord.Color.red()
                )

                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if await verification.verificationuser.Student.from_discord_uid(interaction.user.id):
                embed = discord.Embed(
                    colour=discord.Color.red(),
                    title="Reeds geverifieerd",
                    description="Volgens onze gegevens ben je al geverifieerd in deze Discord-server. Dit incident is "
                                "gemeld."
                )

                await interaction.response.send_message(embed=embed, ephemeral=True)

                await self.verification_module.logger.already_id_verified(interaction.user)
                return

            code = await student.create_verification_code(interaction.user)

            if os.getenv("ENVIRONMENT").lower() != "dev":
                self.verification_module.send_mail(student.email, code)

            view = ui.View(
                timeout=None
            )
            view.add_item(InputCodeButton(student, self.verification_module))
            await interaction.followup.send(
                "Gelieve je studentenmail te checken voor een verificatiecode. Druk vervolgens op de onderstaande knop.",
                view=view, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Geen student geneeskunde",
                description="Je bent geen geneeskunde student aan de KU Leuven. Indien je denkt dat dit een vergissing is, neem dan contact op met een van de bestuursleden.",
                color=discord.Color.red()
            )

            await self.verification_module.logger.no_student_found(interaction.user, self.studentmail.value)
            await interaction.followup.send(embed=embed, ephemeral=True)


class VerificationModal(ui.Modal, title='Verificatiecode studentenmail'):
    code = ui.TextInput(label='Verificatiecode')

    def __init__(self, student: verification.verificationuser.PartialStudent, verification_module):
        super().__init__()
        self.verification_module = verification_module
        self.student = student

    async def on_submit(self, interaction: discord.Interaction):
        await self.verification_module.cur.execute("SELECT code FROM verification_codes WHERE email = ?",
                                             (self.student.email,))
        result = await self.verification_module.cur.fetchone()

        inputted_code = int(self.code.value)
        sent_code = int(result["code"])

        await interaction.response.defer()

        if inputted_code == sent_code:
            await self.student.verify(interaction.user)
            self.verification_module.bot.dispatch("on_verified_join", member=interaction.user)

            embed = discord.Embed(
                title="Succesvol geverifieerd",
                description="Je bent succesvol geverifieerd als student **Geneeskunde** aan de **KU Leuven.**",
                color=discord.Color.from_rgb(82, 189, 236)
            )

            await interaction.user.send(embed=embed)
            await interaction.followup.send(
                f"Dank je wel {interaction.user.mention}! Je bent succesvol geverifieerd :). Ga naar <#1157399496372797480> om te chatten.",
                ephemeral=True)
        else:
            view = ui.View(
                timeout=None
            )
            view.add_item(InputCodeButton(self.student, self.verification_module))

            await interaction.followup.send(f"De code die je hebt opgegeven is incorrect. Probeer het opnieuw:",
                                            ephemeral=True, view=view)
