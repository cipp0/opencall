from opencall import SPATIAL, classify, find_deadline, funding, region

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
assert SPATIAL.search("a 64-channel Ambisonics dome") and SPATIAL.search("Binaural Klangkunst") and SPATIAL.search("Wave Field Synthesis")
assert not SPATIAL.search("a quiet atmosphere for visual artists")
assert not SPATIAL.search("The house is surrounded by forest")
assert classify("Ceramic Studio Residency", "installation and sound", "TransArtists", "Finland")["relevant"] == 0
assert classify("Residency 2027", "for painters and printmakers", "TransArtists", "Finland")["relevant"] == 0
assert classify("Residency 2027", "interaction design and HCI installations", "TransArtists", "Finland")["relevant"] == 1
assert classify("Lab", "a transmedia project", "On the Move", "Spain") == dict(funding="funded", region="Europa", spatial=0, relevant=1, rev=2)
print("ok")
