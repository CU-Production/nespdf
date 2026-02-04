with open("jsnes.min.js", "r", encoding="utf-8", errors="replace") as f:
    s = f.read()
# Pattern as in source: indexOf("NES\x1a") -> in file: indexOf("NES" + char(26) + ")
needle = '.indexOf("NES' + '\x1a' + '")'
found = needle in s
print("Pattern found:", found)
if found:
    i = s.index(needle)
    print("Context:", repr(s[i:i+60]))
else:
    # try finding "NES" and see what follows
    j = s.find('indexOf("NES')
    if j >= 0:
        print("Alt context:", repr(s[j:j+60]))
        for k in range(min(10, len(s)-j)):
            print(k, ord(s[j+k]) if j+k < len(s) else None)
