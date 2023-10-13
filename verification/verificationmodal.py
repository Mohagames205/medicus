import discord
from discord import ui

from verification import verification


class VerificationModal(ui.Modal, title='Verificatiecode studentenmail'):
    code = ui.TextInput(label='Verificatiecode')

    def __init__(self, student: verification.verificationuser.VerificationUser, verification_module):
        super().__init__()
        self.email = student.email
        self.verification_module = verification_module
        self.student = student

        code = verification_module.create_verification_code(self.email)
        print(code)
        #verification_module.send_mail(self.email, code)

    async def on_submit(self, interaction: discord.Interaction):
        # check of het juist is

        self.verification_module.cur.execute("SELECT code FROM verification_codes WHERE email = ?", (self.email,))
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
