FROM python:3.12

LABEL Maintainer="mootje.be"

WORKDIR /home

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

RUN git config --global --add safe.directory /home

CMD [ "python", "./bot.py"]