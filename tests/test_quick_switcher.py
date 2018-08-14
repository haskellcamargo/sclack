from sclack.quick_switcher import remove_diacritic

def test_remove_diacritic():
    assert remove_diacritic("sábado") == "sabado"
