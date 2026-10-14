from opencall import find_deadline, funding, region

assert funding("Honorarium of 7,000 EUR. There is a $25 application fee") == "funded"
assert funding("Paid by artist: Residency fee 300 euros per month") == "a pagamento"
assert funding("A budget is available to cover visa costs including application fees") == "funded"
assert funding("There is no application fee. Free entry.") == "non funded"
assert funding("Preisgeld: 3.000 €") == "funded"
assert find_deadline("Deadline: 25 Oct 2026") == "2026-10-25"
assert find_deadline("Einreichfrist bis 15.11.2026") == "2026-11-15"
assert find_deadline("deadline: November 3rd, 2026") == "2026-11-03"
assert region("Slovakia, Ukraine", "", "Mondo") == "Europa"
assert region("", "Konzerte in Graz", "Mondo") == "Austria"
assert region("USA", "", "Mondo") == "Mondo"
assert region("", "Labelförderung in Berlin", "Mondo") == "Europa"
print("ok")
