from terveyshamsteri.text import extract_votes


def test_one_count_per_line_with_names():
    text = ("Puheenjohtaja totesi,​ että suoritetaan äänestys:\n"
            "JAA 3 ääntä (Jami Toivonen, Heidi Sakari, Marja-Leena Alho)\n"
            "EI 2 ääntä (Kari Hannus ja Marjo Jaspa)\n"
            "TYHJÄÄ 1 ääni (Mirja Ylijoki)\n"
            "Puheenjohtaja totesi pohjaesityksen voittaneen.")
    [v] = extract_votes(text)
    assert v.counts == {"jaa": 3, "ei": 2, "tyhja": 1}
    assert v.names["ei"] == ["Kari Hannus", "Marjo Jaspa"]
    assert "suoritetaan äänestys" in v.context


def test_tagged_lines_and_colon_lists():
    text = ("Äänestys:\nJAA (Liedes/Ollanketo) 5 ääntä (Pirjo Sirviö, Asko Alasalmi, Tarja Ollanketo, Mika Rämet, Teijo Liedes)\n"
            "EI (hyvinvointialuejohtaja) 4 ääntä (Hemmo Heiskanen, Pekka Simonen, Mirja Vehkaperä, Liisa Kylmänen)\n\n"
            "Jaa 18 ääntä: Tero Suominen, Jere Hietala\nEi 39 ääntä: Tapani Eskola")
    a, b = extract_votes(text)
    assert a.counts == {"jaa": 5, "ei": 4} and len(a.names["jaa"]) == 5
    assert b.counts == {"jaa": 18, "ei": 39} and b.names["ei"] == ["Tapani Eskola"]


def test_counts_after_colon():
    [v] = extract_votes("Äänestyksessä annettiin ääniä seuraavasti:\nJAA-ääniä: 10\nEI-ääniä: 3")
    assert v.counts == {"jaa": 10, "ei": 3}


def test_winner_with_side_from_proposal():
    text = ("Suoritetussa äänestyksessä, jossa esittelijän pohjaehdotusta kannattavat äänestivät ”Jaa” ja "
            "Raililan lisäystä kannattavat äänestivät ”Ei”, Raililan lisäys voitti äänin 7 (Baumgartner, Honkasalo, "
            "Kujala, Munkberg, Oksanen, Railila, Lindqvist) – 6 (Edgren, Eskola Tapani, Eskola Vilhelmiina, Grönberg, Kahri, Lankia).")
    [v] = extract_votes(text)
    assert v.counts == {"jaa": 6, "ei": 7}
    assert v.names["ei"][0] == "Baumgartner" and v.names["jaa"][1] == "Eskola Tapani"


def test_jaa_won():
    [v] = extract_votes("Suoritetussa äänestyksessä ”Jaa” voitti äänin 54-5. Äänestystulos liitteenä 3.")
    assert v.counts == {"jaa": 54, "ei": 5}


def test_same_result_twice_is_two_votes():
    text = "Äänestyksessä JAA 53 ääntä, EI 4 ääntä.\n\nToisessa äänestyksessä JAA 53 ääntä, EI 4 ääntä."
    assert len(extract_votes(text)) == 2


def test_prose_is_not_a_vote():
    assert extract_votes("Ei ole tarvetta äänestää. Ja 12 jäsentä oli paikalla.") == []
    assert extract_votes("Pöytäkirjantarkastajat toimivat myös ääntenlaskijoina mahdollisten äänestysten sattuessa.") == []
