def find_pattern(text, keyword):
    if keyword.lower() in text.lower():
        return "Found"
    else:
        return "Not Found"
