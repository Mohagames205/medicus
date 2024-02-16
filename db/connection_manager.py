import aiosqlite


class ConnectionManager:

    con = None
    cur = None

    def __init__(self, con: aiosqlite.Connection):
        ConnectionManager.con = con

    async def initialize_cursor(self):
        ConnectionManager.cur = await self.con.cursor()


