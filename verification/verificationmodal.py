import discord
from discord import ui

from verification import verification


class VerificationButton(ui.Button):
    def __init__(self, label, modal: ui.Modal):
        super().__init__(label=label)
        self.modal = modal
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(self.modal)


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
            view.add_item(VerificationButton("Code invullen", VerificationModal(student, self.verification_module)))
            await interaction.channel.send_message("Gelieve je mailbox te checken voor een verificatiecode. Druk vervolgens op de onderstaande knop.", view=view)
        else:
            await interaction.response.send_message("Volgens onze gegevens ben je geen student geneeskunde. Indien dit een vergissing is, contacteer dan zeker de beheerders of moderators. Zij helpen je graag verder op weg.")

class VerificationModal(ui.Modal, title='Verificatiecode studentenmail'):
    code = ui.TextInput(label='Verificatiecode')

    def __init__(self, student: verification.verificationuser.VerificationUser, verification_module):
        super().__init__()
        self.verification_module = verification_module
        self.student = student

    async def on_submit(self, interaction: discord.Interaction):
        # check of het juist is

        self.verification_module.cur.execute("SELECT code FROM verification_codes WHERE email = ?", (self.student.email,))
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
            await interaction.followup.send(f"Dank je wel! Je bent succesvol geverifieerd :)", ephemeral=True)
        else:
            await interaction.followup.send(f"De code die je hebt opgegeven is incorrect.", ephemeral=True)
