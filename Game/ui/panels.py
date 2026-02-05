
for elt in 'BONJOUR':
    if (ord(elt)+13)%91 < 65:
        print(chr((ord(elt)+13)%91+65))
    else:
        print(chr((ord(elt)+13)%91))

for elt in 'BONJOUR':
    print(chr((ord(elt)+13-65)%26+65))