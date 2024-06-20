FROM python:3.9

LABEL Maintainer="mootje.be"

WORKDIR /home

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

CMD [ "python", "./bot.py"]