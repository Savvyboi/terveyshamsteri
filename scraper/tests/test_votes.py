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


def test_comma_and_parenthesis_before_count():
    text = ("Puheenjohtajan äänestysesitys: Pohjaehdotus JAA, Kuoson muutosesitys EI.\n"
            "JAA, 4 ääntä\nEI (Kuoson muutosesitys, ei valita ketään), 17 ääntä\nTYHJÄ, 8")
    [v] = extract_votes(text)
    assert v.counts == {"jaa": 4, "ei": 17, "tyhja": 8}


def test_count_after_oli():
    [v] = extract_votes("Äänestyksessä annettiin yhteensä 12 ääntä, joista JAA ääniä oli 8 ja EI ääniä 4.")
    assert v.counts == {"jaa": 8, "ei": 4}


def test_swedish_personer_and_ledamoter():
    [v] = extract_votes("I omröstningen röstade 47 personer JA och 10 personer NEJ. 4 personer röstade blankt.")
    assert v.counts == {"jaa": 47, "ei": 10, "tyhja": 4}
    [v] = extract_votes("I omröstningen röstade 9 ledamöter JA (Ahlskog, Björkgren) och 2 personer NEJ (Huuki, Urpilainen).")
    assert v.counts == {"jaa": 9, "ei": 2}


def test_title_case_lines():
    [v] = extract_votes("Äänestyksessä annettiin 10 ääntä.\nJaa: 8\nEi: 2")
    assert v.counts == {"jaa": 8, "ei": 2}


def test_dash_means_zero():
    [v] = extract_votes("Äänestyksessä annettiin ääniä seuraavasti:\nJAA-ääniä: -\nEI-ääniä: 11")
    assert v.counts == {"jaa": 0, "ei": 11}


def test_space_around_hyphen():
    [v] = extract_votes("Suoritetussa äänestyksessä annettiin:\nJAA- ääniä 54\nEI -ääniä 15.")
    assert v.counts == {"jaa": 54, "ei": 15}


def test_number_words():
    [v] = extract_votes("Äänestyksessä annettiin seitsemän (7) Jaa-ääntä ja neljä (4) Ei-ääntä.")
    assert v.counts == {"jaa": 7, "ei": 4}
    [v] = extract_votes("Äänestyksessä annettiin kuusi jaa-ääntä ja viisi ei-ääntä.")
    assert v.counts == {"jaa": 6, "ei": 5}
    [v] = extract_votes("Äänestys:\nJaa: kahdeksan ääntä\nEi: kolme ääntä")
    assert v.counts == {"jaa": 8, "ei": 3}


def test_bare_label_winner():
    text = ("Äänestyksessä ponsiesityksen jättämistä vastaan äänestivät ”JAA” ja sitä kannattaneet äänestivät ”EI”. "
            "JAA voitti ää/nin 9 (Simola, Oksanen) -4 (Engård, Hällfors).")
    [v] = extract_votes(text)
    assert v.counts == {"jaa": 9, "ei": 4}


def test_number_words_in_prose_are_not_votes():
    assert extract_votes("Äänestyksessä yksi ei osallistunut. Kaksi jäsentä oli poissa.") == []
