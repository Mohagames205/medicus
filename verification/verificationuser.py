import json
import logging
import os
import random

import discord

import db.connection_manager
import verification.verification


# represents a user which may or may not be verified
class PartialStudent:

    def __init__(self, email: str, name: str = "", surname: str = ""):
        self.name = name
        self.surname = surname
        self.email = email

    def get_name(self):
        return self.name

    def get_surname(self):
        return self.surname

    def get_email(self):
        return self.email

    async def create_verification_code(self, user: discord.User):
        cm = db.connection_manager.ConnectionManager
        cursor = cm.cur
        conn = cm.con

        email = self.email

        code = random.randint(10000, 99999)
        await cursor.execute('INSERT OR REPLACE into verification_codes (`code`, `email`) values (?, ?)',
                             (code, email))
        await conn.commit()

        await verification.verification.VerificationModule.logger.on_code_creation(code, user, self)

        return code

    @staticmethod
    async def get_by_email(email: str):
        with open("assets/memberships.json") as file:
            memberships_raw = json.load(file)
            result = memberships_raw["results"]

            for user in result:
                if "emailAddress" in user["user"] and email.lower() == user["user"]["emailAddress"]:
                    user_details = user["user"]
                    return PartialStudent(user_details["emailAddress"], user_details["givenName"],
                                          user_details["familyName"])

            return None

    @staticmethod
    async def fetch_all():
        with open("assets/memberships.json") as file:
            partial_students = []
            memberships_raw = json.load(file)
            result = memberships_raw["results"]
            for user in result:
                    user_details = user["user"]
                    try:
                        partial_students.append(PartialStudent(user_details["emailAddress"], user_details["givenName"],
                                          user_details["familyName"]))
                    except:
                        logging.warning(user_details)

            return partial_students

    async def verify(self, member: discord.Member):
        role = member.guild.get_role(int(os.getenv('UNVERIFIED_ROLE_ID')))

        cur, con = PartialStudent.db()

        await member.remove_roles(role)
        await self.replace_verification_roles(member)

        if member.get_role(1196200228580237372):
            await member.remove_roles(member.get_role(1196200228580237372))

        await cur.execute('INSERT INTO verified_users (`user_id`, `email`) values(?, ?)',
                          (member.id, self.email))
        await cur.execute('DELETE FROM verification_codes WHERE `email` = ?',
                          (self.email,))
        await con.commit()

        await verification.verification.VerificationModule.logger.user_verified(member, self)

    async def replace_verification_roles(self, member: discord.Member):
        roles = member.roles
        replaceable_roles = verification.verification.VerificationModule.replaceable_roles

        for role in roles:
            if str(role.id) in list(replaceable_roles.keys()):
                real_role = member.guild.get_role(replaceable_roles[str(role.id)])
                if member.get_role(real_role.id) is None:
                    await member.add_roles(real_role)

    async def is_verified(self):
        return self.full() is not None

    async def full(self):
        cur, con = PartialStudent.db()

        await cur.execute('SELECT user_id FROM verified_users WHERE `email` = ?', (self.email,))
        result = await cur.fetchone()

        return Student(self.email, result[0], self.name, self.surname) if result else None

    # helper function to facilitate db access
    @staticmethod
    def db():
        cm = db.connection_manager.ConnectionManager
        cursor = cm.cur
        conn = cm.con

        return cursor, conn


# represents a verified user
class Student(PartialStudent):

    def __init__(self, email: str, discord_uid: int, name: str = "", surname: str = ""):
        super().__init__(email, name, surname)
        self.discord_uid = discord_uid

    def get_discord_uid(self):
        return self.discord_uid

    def get_firstname(self):
        return self.email.split('@')[0].split('.')[0]

    def get_lastname(self):
        return self.email.split('@')[0].split('.')[1]

    @staticmethod
    async def from_discord_uid(uid: int):
        cur, con = Student.db()

        await cur.execute('SELECT email FROM verified_users WHERE `user_id` = ?', (uid,))
        result = await cur.fetchone()

        return Student(result[0], uid) if result else None

    @staticmethod
    async def get_by_email(email: str):
        cur, con = Student.db()

        await cur.execute('SELECT user_id FROM verified_users WHERE `email` = ?', (email,))
        result = await cur.fetchone()

        return Student(email, result[0]) if result else None

    async def unverify(self):
        cur, con = Student.db()

        await cur.execute('DELETE FROM verified_users WHERE user_id = ?', (self.discord_uid,))
        await con.commit()

    @staticmethod
    async def fetch_all():
        cur, con = Student.db()
        await cur.execute('SELECT user_id, email FROM verified_users')
        result = await cur.fetchall()

        return [Student(email, user_id) for user_id, email in result]


    @staticmethod
    async def from_partial(partial: PartialStudent):
        return await partial.full()
