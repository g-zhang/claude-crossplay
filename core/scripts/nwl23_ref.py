#!/usr/bin/env python3
"""
NWL23 reference word lists from "The Cheat Sheet" (Mike Baron & Seth Lipkin, 2024).
Used for:
  - Cross-word validation (2-letter words are the critical filter)
  - Premium-tile targeting (short high-value J/Q/X/Z words)
  - Bingo detection (TISANE/SATIRE/RETINA stems)
  - Vowel/consonant dump plays
"""

# === 2-LETTER WORDS (107 words) ===
# THE definitive cross-word filter. If a cross-word isn't in this list, the play is invalid.
TWO_LETTER = set("""
AA AB AD AE AG AH AI AL AM AN AR AS AT AW AX AY
BA BE BI BO BY
DA DE DO
ED EF EH EL EM EN ER ES ET EW EX
FA FE
GI GO
HA HE HI HM HO
ID IF IN IS IT
JO
KA KI
LA LI LO
MA ME MI MM MO MU MY
NA NE NO NU
OD OE OF OH OI OK OM ON OP OR OS OW OX OY
PA PE PI PO
QI
RE
SH SI SO
TA TE TI TO
UH UM UN UP US UT
WE WO
XI XU
YA YE YO
ZA
""".split())

# === SHORT J WORDS (2-4 letters) ===
SHORT_J = set("""
JO
AJI HAJ JAB JAG JAM JAR JAW JAY JEE JET JEU JIB JIG JIN
JOB JOE JOG JOT JOW JOY JUG JUN JUS JUT RAJ TAJ
AJAR AJEE AJIS DJIN DOJO FUJI GOJI HADJ HAJI HAJJ
JABS JACK JADE JAGG JAGS JAIL JAKE JAMB JAMS JANE JAPE JARL JARS
JATO JAUK JAUP JAVA JAWS JAYS JAZZ JEAN JEDI JEED JEEP JEER JEES
JEEZ JEFE JEHU JELL JEON JERK JESS JEST JETE JETS JEUX JIAO JIBB
JIBE JIBS JIFF JIGS JILL JILT JIMP JINK JINN JINS JINX JIRD JISM
JIVE JIVY JIZZ JOBS JOCK JOES JOEY JOGS JOHN JOIN JOKE JOKY JOLE
JOLT JOOK JOSH JOSS JOTA JOTS JOUK JOWL JOWS JOYS JUBA JUBE JUCO
JUDO JUDY JUGA JUGS JUJU JUKE JUKU JUMP JUNK JUPE JURA JURY JUST
JUTE JUTS KOJI MOJO PUJA RAJA SOJA SOJU YAJE
""".split())

# === SHORT Q WORDS (2-4 letters) ===
SHORT_Q = set("""
QI
QAT QIS QUA SUQ
AQUA CINQ QADI QAID QATS QOPH QUAD QUAG QUAI QUAY QUEY
QUID QUIN QUIP QUIT QUIZ QUOD SUQS
""".split())

# === SHORT X WORDS (2-4 letters) ===
# High-value plays: X=8pts. Target 2L/3L/2W/3W squares.
SHORT_X = set("""
AX EX OX XI XU
AXE BOX COX DEX DOX FAX FIX FOX GOX HEX KEX LAX LEX LOX LUX
MAX MIX MUX NIX OXO OXY PAX PIX POX PYX RAX REX SAX SEX SIX
SOX TAX TIX TUX VAX VEX VOX WAX XED XIS ZAX
APEX AXAL AXED AXEL AXES AXIL AXIS AXLE AXON BOXY BRUX CALX COAX
COXA CRUX DEXY DOUX DOXX DOXY EAUX EXAM EXEC EXED EXES EXIT EXON
EXPO FALX FAUX FIXT FLAX FLEX FLUX FOLX FOXY HOAX IBEX ILEX IXIA
JEUX JINX LUXE LYNX MAXI MINX MIXT MOXA MPOX NEXT NIXE NIXY ONYX
ORYX OXEN OXER OXES OXIC OXID OXIM PIXY PLEX POXY PREX ROUX SEXT
SEXY TAXA TAXI TEXT VAXX VEXT WAXY XYST
""".split())

# === SHORT Z WORDS (2-4 letters) ===
# Z=10pts, highest value tile.
SHORT_Z = set("""
ZA
ADZ AZO BIZ COZ CUZ FEZ FIZ REZ SEZ TIZ WIZ WUZ YEZ
ZAG ZAP ZAS ZAX ZED ZEE ZEK ZEN ZEP ZIG ZIN ZIP ZIT ZOA ZOO ZUZ ZZZ
ADZE AZAN AZON BAZZ BIZE BOZO BUZZ CAZH CHEZ COZY CZAR DAZE DITZ
DOZE DOZY FAZE FIZZ FOZY FRIZ FUTZ FUZE FUZZ GAZE GEEZ GRIZ HAZE
HAZY IZAR JAZZ JEEZ JIZZ LAZE LAZY LUTZ MAZE MAZY MEZE MOZO NAZI
OOZE OOZY ORZO OUZO OYEZ PHIZ PREZ PUTZ QUIZ RAZE RAZZ RITZ SIZE
SIZY SPAZ TIZZ TZAR WHIZ YUTZ YUZU ZAGS ZANY ZAPS ZARF ZEAL ZEBU
ZEDA ZEDS ZEES ZEIN ZEKS ZENS ZEPS ZERK ZERO ZEST ZETA ZIGS ZILL
ZINC ZINE ZING ZINS ZIPS ZITI ZITS ZIZZ ZOEA ZOIC ZONA ZONE ZONK
ZOOM ZOON ZOOS ZORI ZOUK ZUKE ZYME
""".split())

# === BINGO STEMS ===
# If rack contains 5+ of these letters, look for 7-tile plays (+40 bonus in Crossplay)
BINGO_STEMS = {
    "TISANE": set("TISANE"),
    "SATIRE": set("SATIRE"),
    "RETINA": set("RETINA"),
}

# === VOWEL DUMPS (2-4 letters) ===
# Use when stuck with too many vowels
VOWEL_DUMPS = set("""
AA AE AI OE OI
EAU
ACAI AEON AERO AGEE AGIO AGUE AIDE AJEE AKEE ALAE ALEE ALOE AMIA
AMIE ANOA AQUA AREA ARIA ARIE ASEA AURA AUTO AWEE BEAU CIAO EASE
EAUX EAVE EEEW EIDE EMEU EPEE ETUI EURO IDEA ILEA ILIA INIA IOTA
IXIA JIAO LIEU LUAU MEOU MOUE NAOI OBIA OBOE ODEA OGEE OHIA OLEA
OLEO OLIO OOZE OUTA OUZO OWIE PAUA QUAI RAIA ROUE TOEA UNAI UNAU
UREA UVEA ZOEA
""".split())

# === I DUMPS (4+ letters, multiple I's) ===
I_DUMPS = set("""
BIDI HILI IBIS ILIA IMID IMPI INIA INTI IRID IRIS IWIS IXIA KIWI
LIRI MIDI MINI MIRI NIDI NISI PIKI PILI TIKI TIPI TITI WIKI ZITI
BIKINI BIMINI IMIDIC IRIDIC IRITIC IRITIS
""".split())

# === U DUMPS (multiple U's) ===
U_DUMPS = set("""
ULU BUBU FUGU GURU JUJU JUKU KUDU KURU LUAU LULU MUMU PUDU PUPU
SULU TUTU UNAU URUS YUZU MUUMUU
""".split())

# === HIGH PROBABILITY 7-LETTER BINGOS ===
HI_PROB_7 = set("""
ACONITE AEOLIAN AERADIO AEROSAT AGONIES AGONISE AILERON AIRDATE
AIRLINE ALEURON ALIENED ALIENER ALIENOR ALINERS ALUNITE AMNIOTE
ANEROID ANISEED ANISOLE ANODISE ARANEID ARENOSE ARENOUS ARIETTE
AROINTS ATELIER ATONERS AUDIENT AUDITEE DARIOLE DEARIES DELAINE
DELATOR DENARII DIATRON DILATER DINEROS DIORITE DONATES DOURINE
EARNEST EASTERN EDITION EDITORS ELATION ELOINER ELUTION ENATION
ENTERAL ENTIRES ENTOILS ENTRIES ERASION EROTICA ESTRIOL ETALONS
ETERNAL GENITOR GOATIER GODETIA IDEATES INDORSE INEDITA INOSITE
IODATES IONISER IRONIES IRONISE ISOLATE ISOLEAD LADRONE LEADIER
LENTOID LEOTARD LINEATE LOANERS LOITERS MORAINE NAILERS NEAREST
NEGATOR NEROLIS NEUROID NIOBATE NITERIE NOISIER NORITES OESTRIN
OLESTRA ONLIEST ORATION ORDINES ORIENTS OUTDARE OUTEARN OUTLIER
OUTLINE OUTREAD OUTRIDE RADIATE RADIOES RAINOUT RANDIES RATIONS
READIES READOUT REALISE REDTAIL REGINAE RELOANS RENAILS RETINES
RETINOL RETINUE REUNITE ROADIES ROASTED ROMAINE RONDEAU ROSEATE
ROSINED ROUTINE SANDIER SANTERO SARDINE SENARII SENATOR SORDINE
SORTIED SOUTANE STERANE STEROID STONIER STORIED STOURIE TAENIAE
TAENITE TALONED TELERAN TIARAED TOADIES TOENAIL TOILERS TOLANES
TORSADE TORULAE TRAILED TREASON TRIALED TRIENES TRIODES UNAIRED
URALITE URANIDE URINOSE UTERINE
""".split())

# === HELPER FUNCTIONS ===

def is_valid_2letter(word):
    """Check if a 2-letter word is valid in NWL23."""
    return word.upper() in TWO_LETTER

def validate_crosswords(crosswords):
    """Validate a list of cross-words. Returns (valid, invalid) lists."""
    valid, invalid = [], []
    for w in crosswords:
        w = w.upper()
        if len(w) == 2:
            (valid if w in TWO_LETTER else invalid).append(w)
        else:
            valid.append(w)  # Can't validate longer words here
    return valid, invalid

def check_bingo_potential(rack_letters):
    """Check if rack has bingo potential based on TISANE/SATIRE/RETINA stems."""
    rack = set(rack_letters.upper())
    results = []
    for stem_name, stem_letters in BINGO_STEMS.items():
        overlap = rack & stem_letters
        if len(overlap) >= 5:
            missing = stem_letters - rack
            results.append((stem_name, len(overlap), missing))
    return results

def get_premium_words(tile, max_len=4):
    """Get high-value short words containing a specific tile letter."""
    tile = tile.upper()
    lookup = {"J": SHORT_J, "Q": SHORT_Q, "X": SHORT_X, "Z": SHORT_Z}
    words = lookup.get(tile, set())
    return sorted([w for w in words if len(w) <= max_len])

def find_dump_words(rack_letters):
    """Find vowel/consonant dump words playable from rack."""
    rack = list(rack_letters.upper())
    dumps = []
    all_dumps = VOWEL_DUMPS | I_DUMPS | U_DUMPS
    for word in all_dumps:
        temp_rack = rack.copy()
        can_play = True
        for letter in word:
            if letter in temp_rack:
                temp_rack.remove(letter)
            elif "?" in temp_rack:  # blank
                temp_rack.remove("?")
            else:
                can_play = False
                break
        if can_play:
            dumps.append(word)
    return sorted(dumps, key=lambda w: (-len(w), w))


if __name__ == "__main__":
    print(f"2-letter words: {len(TWO_LETTER)}")
    print(f"Short J words: {len(SHORT_J)}")
    print(f"Short Q words: {len(SHORT_Q)}")
    print(f"Short X words: {len(SHORT_X)}")
    print(f"Short Z words: {len(SHORT_Z)}")
    print(f"Hi-prob 7s: {len(HI_PROB_7)}")
    print(f"Vowel dumps: {len(VOWEL_DUMPS)}")
    print(f"I dumps: {len(I_DUMPS)}")
    print(f"U dumps: {len(U_DUMPS)}")
    
    # Test
    print(f"\nValid 2-letter: EW={'✓' if is_valid_2letter('EW') else '✗'}")
    print(f"Valid 2-letter: EZ={'✓' if is_valid_2letter('EZ') else '✗'}")
    print(f"\nBingo check SATIRE: {check_bingo_potential('SATIRE')}")
    print(f"Bingo check XQQZZW: {check_bingo_potential('XQQZZW')}")
    print(f"\nShort X words (≤3): {get_premium_words('X', 3)}")
    print(f"\nDumps for AEIOU: {find_dump_words('AEIOU')}")
