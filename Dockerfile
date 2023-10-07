FROM python:3.9

LABEL Maintainer="mootje.be"

WORKDIR /home

COPY bot.py .env ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir aiohttp discord.py[voice] ics python-dotenv pytz

CMD [ "python", "./bot.py"]
