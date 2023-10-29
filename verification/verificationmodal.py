import discord
from discord import ui

from verification import verification


class VerificationButton(ui.Button):
    def __init__(self, label, modal, verification_module):
        super().__init__(label=label, emoji="📥")
        self.modal = modal
        self.verification_module = verification_module

    async def callback(self, interaction: discord.Interaction):

        if await self.verification_module.is_verified(interaction.user.id):
            embed = discord.Embed(
                colour=discord.Color.red(),
                title="Reeds geverifieerd",
                description="Volgens onze gegevens ben je al geverifieerd in deze Discord-server. Dit incident is "
                            "gemeld."
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_modal(self.modal(self.verification_module))

        await self.verification_module.refresh_messages()


class InputCodeButton(ui.Button):
    def __init__(self, student, verification_module):
        super().__init__(label="Code invullen", emoji="🔐")
        self.student = student
        self.verification_module = verification_module

    async def callback(self, interaction: discord.Interaction):
        if await self.verification_module.is_verified(interaction.user.id):
            embed = discord.Embed(
                colour=discord.Color.red(),
                title="Reeds geverifieerd",
                description="Volgens onze gegevens ben je al geverifieerd in deze Discord-server. Dit incident is "
                            "gemeld."
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_modal(VerificationModal(self.student, self.verification_module))


class CollectNameModal(ui.Modal, title="Geef je voor- en achternaam"):
    firstname = ui.TextInput(label='Voornaam')
    familyname = ui.TextInput(label='Achternaam')

    def __init__(self, verification_module):
        super().__init__()
        self.verification_module = verification_module

    async def on_submit(self, interaction: discord.Interaction):

        student = await self.verification_module.get_student(self.firstname.value, self.familyname.value)
        if student is not None:

            code = self.verification_module.create_verification_code(student.email)
            print(code)
            self.verification_module.send_mail(student.email, code)

            view = ui.View()
            view.add_item(InputCodeButton(student, self.verification_module))
            await interaction.response.send_message(
                "Gelieve je studentenmail te checken voor een verificatiecode. Druk vervolgens op de onderstaande knop.",
                view=view, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Geen student bachelor geneeskunde",
                description="Je bent geen (bachelor) geneeskunde student aan de KU Leuven. Indien je denkt dat dit een vergissing is, neem dan contact op met een van de beheerders of moderators.",
                color=discord.Color.red()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)


class VerificationModal(ui.Modal, title='Verificatiecode studentenmail'):
    code = ui.TextInput(label='Verificatiecode')

    def __init__(self, student: verification.verificationuser.VerificationUser, verification_module):
        super().__init__()
        self.verification_module = verification_module
        self.student = student

    async def on_submit(self, interaction: discord.Interaction):
        self.verification_module.cur.execute("SELECT code FROM verification_codes WHERE email = ?",
                                             (self.student.email,))
        result = self.verification_module.cur.fetchone()

        inputted_code = int(self.code.value)
        sent_code = int(result["code"])

        await interaction.response.defer()

        if inputted_code == sent_code:
            await self.verification_module.verify_user(interaction.user, self.student)

            embed = discord.Embed(
                title="Succesvol geverifieerd",
                description="Je bent succesvol geverifieerd als student **Bachelor Geneeskunde** aan de **KU Leuven.**",
                color=discord.Color.from_rgb(82, 189, 236)
            )

            await interaction.user.send(embed=embed)
            await interaction.followup.send(
                f"Dank je wel {interaction.user.mention}! Je bent succesvol geverifieerd :). Ga naar <#1157399496372797480> om te chatten.",
                ephemeral=True)
        else:
            view = ui.View()
            view.add_item(InputCodeButton(self.student, self.verification_module))

            await interaction.followup.send(f"De code die je hebt opgegeven is incorrect. Probeer het opnieuw:",
                                            ephemeral=True, view=view)
