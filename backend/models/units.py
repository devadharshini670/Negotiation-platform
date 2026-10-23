"""One place that decides how a scenario's values are written.

Currency symbols are written as a prefix ("$1,200"); a unit made of letters is
written as a suffix ("45 days"); "%" is attached ("4.5%")."""


def format_amount(v, unit='$', exact=False):
    if v is None:
        return '—'
    n = f'{v:,.0f}' if (not exact and abs(v - round(v)) < 0.005) else f'{v:,.2f}'
    if not unit:
        return n
    if unit == '%':
        return f'{n}%'
    return f'{n} {unit}' if unit[0].isalpha() else f'{unit}{n}'
