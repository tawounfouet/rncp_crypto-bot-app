"""Convention de signal partagée : label ("BUY"/"SELL"/"HOLD") <-> code numérique (1/-1/0).

Utilisée par des composants qui ne peuvent pas s'importer entre eux (models/ n'est pas
copié dans l'image backend, cf. Dockerfile) -- ce module vit dans utils/, partagé par les
deux, sur le même principe que utils/features/indicators.py.
"""

SIGNAL_TO_VALUE = {"BUY": 1, "HOLD": 0, "SELL": -1}
VALUE_TO_SIGNAL = {value: label for label, value in SIGNAL_TO_VALUE.items()}

# Convention de classes ML (cf. config.yaml > labels.classes) : les classifieurs
# sklearn/torch entrainent sur des ids entiers 0..N-1 (XGBoost l'exige). Id -> label.
CLASS_ID_TO_SIGNAL = {0: "SELL", 1: "HOLD", 2: "BUY"}
