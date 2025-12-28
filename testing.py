from mailgun.client import Client
import os
from dotenv import load_dotenv
load_dotenv()

auth = ("api", os.environ["MAILGUN_API"])
client: Client = Client(auth=auth, api_url="https://api.eu.mailgun.net/")
domain: str = "gnkdiscord.be"

def post_message() -> None:
    # Messages
    # POST /<domain>/messages
    data = {
        "from": os.getenv("MESSAGES_FROM", "medicus@gnkdiscord.be"),
        "to": os.getenv("MESSAGES_TO", "mohamed.elyousfi@student.kuleuven.be"),
        "subject": "Hello from python!",
        "text": "Hello world!",
        "o:tag": "Python test",
    }

    req = client.messages.create(data=data, domain=domain)
    print(req)


post_message()