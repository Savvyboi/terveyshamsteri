from terveyshamsteri.finances import derive, extract, norm

TAX = {
    "1": {"solutunniste": 1, "taso": 1, "tunnusluku": "Toimintakulut", "tehtava": "Talousarvio 202x", "sektori": None, "palvelu": None},
    "2": {"solutunniste": 2, "taso": 2, "tunnusluku": "   Henkilöstömenot", "tehtava": "Taloussuunnitelma\n202x+1", "sektori": None, "palvelu": None},
    "3": {"solutunniste": 3, "taso": 1, "tunnusluku": "TILIKAUDEN YLIJÄÄMÄ (ALIJÄÄMÄ)", "tehtava": "Talousarvio 202x", "sektori": None, "palvelu": None},
    # a service-class breakdown of the same line must not overwrite the total
    "4": {"solutunniste": 4, "taso": 1, "tunnusluku": "Toimintakulut", "tehtava": "Talousarvio 202x", "sektori": None, "palvelu": "Pelastustoimi"},
    "10": {"solutunniste": 10, "taso": 1, "tunnusluku": "Toimintakate", "sektori": "Ulkoiset", "palvelu": None},
    "11": {"solutunniste": 11, "taso": 1, "tunnusluku": "Toimintakate", "sektori": "Hyvinvointiyhtymät", "palvelu": None},
    "12": {"solutunniste": 12, "taso": 1, "tunnusluku": "5600-5699 Valtion rahoitus", "sektori": "Ulkoiset", "palvelu": None},
    "13": {"solutunniste": 13, "taso": 1, "tunnusluku": "6000-6999 Rahoitustuotot ja -kulut + (-)", "sektori": "Ulkoiset", "palvelu": None},
    "14": {"solutunniste": 14, "taso": 4, "tunnusluku": "Pitkäaikainen (korollinen vieras pääoma)", "sektori": "Ulkoiset", "palvelu": None},
    "15": {"solutunniste": 15, "taso": 4, "tunnusluku": "Lyhytaikainen (korollinen vieras pääoma)", "sektori": "Ulkoiset", "palvelu": None},
}


def v(code, value):
    return {"tunnusluku": code, "arvo": str(value)}


def test_norm():
    assert norm("   4000-4299 Henkilöstökulut") == "henkilöstökulut"
    assert norm("3710 Valmistus omaan käyttöön, tili") == "valmistus omaan käyttöön"
    assert norm("Taloussuunnitelma\n202x+1") == "taloussuunnitelma 202x+1"


def test_budget_columns():
    out = extract("HTAS", TAX, [v("1", 100), v("2", 60), v("3", -5), v("4", 7), v("99", 1)])
    assert out[0] == {"expenses": 100, "surplus": -5}
    assert out[1] == {"staff": 60}


def test_quarterly_uses_external_total_and_derives():
    out = extract("HHKNR", TAX, [v("10", -600), v("11", -3), v("12", 590), v("13", -2), v("14", 70), v("15", 30)])
    d = derive(out[None])
    assert d["operating_margin"] == -600
    assert d["annual_margin"] == -12
    assert d["loans"] == 100 and "loans_long" not in d
