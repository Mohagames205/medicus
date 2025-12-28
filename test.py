import requests
from bs4 import BeautifulSoup
import re

def parse_kuleuven_course(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # ECTS-code uit extraheading
    ects_code_el = soup.find("span", class_="extraheading")
    ects_code = ects_code_el.text.strip(" ()") if ects_code_el else None

    # Studiepunten
    studiepunten = None
    spans = soup.find_all("span", class_="studiepunten")
    for span in spans:
        text = span.get_text(strip=True)
        if re.match(r"\d+(\.\d+)? studiepunten", text):
            if "6 studiepunten" in text:  # pas dit aan indien nodig
                studiepunten = text
                break

    # Titularissen
    titularis_spans = soup.find_all("span", class_="docent Titularis moretocome")
    titularissen = []
    for span in titularis_spans:
        a_tag = span.find("a")
        if a_tag:
            titularissen.append(a_tag.get_text(strip=True))

    # OLA’s
    olas = []
    for h3 in soup.find_all("h3", class_="mandatory"):
        a_tag = h3.find("a")
        print(h3)
        print(a_tag)
        if a_tag:
            text = a_tag.get_text(" ", strip=True)
            match = re.search(r"\((B-KUL-[A-Z0-9]+)\)", text)
            if match:
                code = match.group(1)
                naam = re.sub(r"\(B-KUL-[A-Z0-9]+\)", "", text).strip()
                olas.append({"code": code, "naam": naam})

    return {
        "ects_code": ects_code,
        "studiepunten": studiepunten,
        "titularissen": titularissen,
        "olas": olas
    }


# Voorbeeld
url = "https://www.onderwijsaanbod.kuleuven.be/syllabi/n/E0C15AN.htm"
data = parse_kuleuven_course(url)

import pprint
pprint.pprint(data)
