from enum import StrEnum, auto


class PublicLinkType(StrEnum):
    file = auto()
    folder = auto()


class PublicLinkExpiration(StrEnum):
    exp_30d = '30d'
    exp_14d = '14d'
    exp_7d = '7d'
    exp_3d = '3d'
    exp_1d = '1d'
    exp_6h = '6h'
    exp_1h = '1h'
    never = 'never'
