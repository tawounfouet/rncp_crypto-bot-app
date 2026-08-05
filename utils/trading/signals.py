"""Convention de signal partagée : label ("BUY"/"SELL"/"HOLD") <-> code numérique (1/-1/0).

Utilisée par des composants qui ne peuvent pas s'importer entre eux (models/ n'est pas
copié dans l'image backend, cf. Dockerfile) -- ce module vit dans utils/, partagé par les
deux, sur le même principe que utils/features/indicators.py.
"""

SIGNAL_TO_VALUE = {"BUY": 1, "HOLD": 0, "SELL": -1}
VALUE_TO_SIGNAL = {value: label for label, value in SIGNAL_TO_VALUE.items()}
