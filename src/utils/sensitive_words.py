SENSITIVE_WORDS = [
    "赌博", "毒品", "色情", "暴力", "恐怖主义",
    "枪支", "反动", "邪教", "传销", "诈骗",
]


def check_sensitive_words(text: str) -> list[str]:
    found = []
    text_lower = text.lower()
    for word in SENSITIVE_WORDS:
        if word in text_lower:
            found.append(word)
    return found
