"""Мелочи, нужные и приложению, и окну настроек."""


def plural(n: int, one: str, few: str, many: str) -> str:
    """Русское согласование числительного: 1 слово, 2 слова, 5 слов.

    plural(n, 'слово', 'слова', 'слов')
    """
    m = abs(n) % 100
    if 11 <= m <= 14:      # 11..14 - всегда «слов», несмотря на последнюю цифру
        return many
    m %= 10
    if m == 1:
        return one
    if 2 <= m <= 4:
        return few
    return many
