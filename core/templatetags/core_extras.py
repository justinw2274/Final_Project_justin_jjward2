from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key in templates"""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.simple_tag
def format_spread(game):
    """
    Format predicted spread with home team name in betting convention.

    Our model: positive = home favored (home wins by X)
    Betting: negative = favorite (must win by more than X)

    Examples:
    - Model +5 (home favored) -> "OKC -5.0" (OKC is favorite)
    - Model -3 (home underdog) -> "MIL +3.0" (MIL is underdog)
    """
    if not game or game.predicted_spread is None:
        return ""

    model_spread = float(game.predicted_spread)
    # Convert to betting convention (flip sign)
    betting_spread = -model_spread

    home_abbr = game.home_team.abbreviation if game.home_team else "HOME"

    if betting_spread >= 0:
        return f"{home_abbr} +{abs(betting_spread):.1f}"
    else:
        return f"{home_abbr} {betting_spread:.1f}"


@register.simple_tag
def format_vegas_spread(game):
    """
    Format Vegas spread with home team name.
    Vegas convention: negative = home favorite
    """
    if not game or game.vegas_spread is None:
        return ""

    vegas_spread = float(game.vegas_spread)
    home_abbr = game.home_team.abbreviation if game.home_team else "HOME"

    if vegas_spread >= 0:
        return f"{home_abbr} +{abs(vegas_spread):.1f}"
    else:
        return f"{home_abbr} {vegas_spread:.1f}"
