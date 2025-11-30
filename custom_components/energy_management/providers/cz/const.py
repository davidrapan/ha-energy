from datetime import time
from decimal import Decimal
from zoneinfo import ZoneInfo

VAT = Decimal(".21")

TIMEZONE = ZoneInfo("Europe/Prague")

RATE = {
    2025: {
        "": Decimal("0.49500") + Decimal("0.17092") + Decimal("0.02830"),
        "cez": {
            "D01d": {
                "T1": Decimal("2.80318")
            },
            "D02d": {
                "T1": Decimal("2.09963")
            },
            "D25d": {
                "T1": Decimal("2.26711"),
                "T2": Decimal("0.20600"),
                "Name": "AKU8",
                "Type": {
                    "V1": ((time(hour = 0), time(hour = 6)), (time(hour = 19), time(hour = 21))),
                    "V2": ((time(hour = 0), time(hour = 5)), (time(hour = 18), time(hour = 20)), (time(hour = 23), time(hour = 23, minute = 59, second = 59))),
                    "V3": ((time(hour = 0), time(hour = 4)), (time(hour = 17), time(hour = 19)), (time(hour = 22), time(hour = 23, minute = 59, second = 59))),
                    "V4": ((time(hour = 0), time(hour = 6)), (time(hour = 22), time(hour = 23, minute = 59, second = 59))),
                    "V5": ((time(hour = 1), time(hour = 6)), (time(hour = 18), time(hour = 21))),
                    "V6": ((time(hour = 3), time(hour = 6)), (time(hour = 15), time(hour = 18)), (time(hour = 21), time(hour = 23)))
                }
            },
            "D26d": {
                "T1": Decimal("1.04600"),
                "T2": Decimal("0.20600"),
                "Name": "AKU8",
                "Type": {
                    "V1": ((time(hour = 0), time(hour = 6)), (time(hour = 19), time(hour = 21))),
                    "V2": ((time(hour = 0), time(hour = 5)), (time(hour = 18), time(hour = 20)), (time(hour = 23), time(hour = 23, minute = 59, second = 59))),
                    "V3": ((time(hour = 0), time(hour = 4)), (time(hour = 17), time(hour = 19)), (time(hour = 22), time(hour = 23, minute = 59, second = 59))),
                    "V4": ((time(hour = 0), time(hour = 6)), (time(hour = 22), time(hour = 23, minute = 59, second = 59))),
                    "V5": ((time(hour = 1), time(hour = 6)), (time(hour = 18), time(hour = 21))),
                    "V6": ((time(hour = 3), time(hour = 6)), (time(hour = 15), time(hour = 18)), (time(hour = 21), time(hour = 23)))
                }
            },
            "D27d": {
                "T1": Decimal("2.26711"),
                "T2": Decimal("0.20600"),
                "Name": "EMO",
                "Type": {
                    "V1": ((time(hour = 2), time(hour = 6)), (time(hour = 20), time(hour = 23, minute = 59, second = 59)))
                }
            },
            "D35d": {
                "T1": Decimal("0.72145"),
                "T2": Decimal("0.20600"),
                "Name": "AKU16",
                "Type": {
                    "V1": ((time(hour = 0), time(hour = 8)), (time(hour = 13), time(hour = 16)), (time(hour = 19), time(hour = 23, minute = 59, second = 59)))
                }
            },
            "D45d": {
                "T1": Decimal("0.72145"),
                "T2": Decimal("0.20600"),
                "Name": "PT",
                "Type": {
                    "V1": ((time(hour = 0), time(hour = 9)), (time(hour = 10), time(hour = 11)), (time(hour = 12), time(hour = 13)), (time(hour = 14), time(hour = 16)), (time(hour = 17), time(hour = 23, minute = 59, second = 59))),
                    "V2": ((time(hour = 0), time(hour = 6)), (time(hour = 7), time(hour = 9)), (time(hour = 10), time(hour = 13)), (time(hour = 14), time(hour = 16)), (time(hour = 17), time(hour = 23, minute = 59, second = 59))),
                    "V3": ((time(hour = 0), time(hour = 8)), (time(hour = 9), time(hour = 12)), (time(hour = 13), time(hour = 15)), (time(hour = 16), time(hour = 19)), (time(hour = 20), time(hour = 23, minute = 59, second = 59))),
                    "V4": ((time(hour = 0), time(hour = 10)), (time(hour = 11), time(hour = 12)), (time(hour = 13), time(hour = 14)), (time(hour = 15), time(hour = 17)), (time(hour = 18), time(hour = 23, minute = 59, second = 59)))
                }
            },
            "D56d": {
                "T1": Decimal("0.72145"),
                "T2": Decimal("0.20600"),
                "Name": "TČ",
                "Type": {
                    "V1": ((time(hour = 0), time(hour = 9)), (time(hour = 10), time(hour = 12)), (time(hour = 14), time(hour = 23, minute = 59, second = 59)))
                }
            },
            "D57d": {
                "T1": Decimal("0.72145"),
                "T2": Decimal("0.20600"),
                "Name": "EV",
                "Type": {
                    "V1": ((time(hour = 0), time(hour = 6)), (time(hour = 7), time(hour = 9)), (time(hour = 10), time(hour = 13)), (time(hour = 14), time(hour = 16)), (time(hour = 17), time(hour = 23, minute = 59, second = 59))),
                    "V2": ((time(hour = 0), time(hour = 8)), (time(hour = 9), time(hour = 12)), (time(hour = 13), time(hour = 15)), (time(hour = 16), time(hour = 19)), (time(hour = 20), time(hour = 23, minute = 59, second = 59))),
                    "V3": ((time(hour = 0), time(hour = 10)), (time(hour = 11), time(hour = 12)), (time(hour = 13), time(hour = 14)), (time(hour = 15), time(hour = 17)), (time(hour = 18), time(hour = 23, minute = 59, second = 59)))
                }
            },
            "D61d": {
                "T1": Decimal("3.28260"),
                "T2": Decimal("0.20600"),
                "Name": "VIK",
                "Type": {
                    "V1": ((), (), (), (), ((time(hour = 12), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 22))))
                }
            }
        },
        "egd": {
            "D01d": {
                "T1": Decimal("2.69479")
            },
            "D02d": {
                "T1": Decimal("2.17145")
            },
            "D25d": {
                "T1": Decimal("2.12308"),
                "T2": Decimal("0.22264")
            },
            "D26d": {
                "T1": Decimal("0.95821"),
                "T2": Decimal("0.22264")
            },
            "D27d": {
                "T1": Decimal("2.12308"),
                "T2": Decimal("0.22264")
            },
            "D35d": {
                "T1": Decimal("0.71876"),
                "T2": Decimal("0.22264")
            },
            "D45d": {
                "T1": Decimal("0.71876"),
                "T2": Decimal("0.22264")
            },
            "D56d": {
                "T1": Decimal("0.71876"),
                "T2": Decimal("0.22264")
            },
            "D57d": {
                "T1": Decimal("0.71876"),
                "T2": Decimal("0.22264")
            },
            "D61d": {
                "T1": Decimal("3.17899"),
                "T2": Decimal("0.22264")
            }
        },
        "pre": {
            "D01d": {
                "T1": Decimal("1.82339")
            },
            "D02d": {
                "T1": Decimal("1.40558")
            },
            "D25d": {
                "T1": Decimal("1.53998"),
                "T2": Decimal("0.11444")
            },
            "D26d": {
                "T1": Decimal("0.73991"),
                "T2": Decimal("0.11444")
            },
            "D27d": {
                "T1": Decimal("1.53998"),
                "T2": Decimal("0.11444")
            },
            "D35d": {
                "T1": Decimal("0.29685"),
                "T2": Decimal("0.11444")
            },
            "D45d": {
                "T1": Decimal("0.29685"),
                "T2": Decimal("0.11444")
            },
            "D56d": {
                "T1": Decimal("0.29685"),
                "T2": Decimal("0.11444")
            },
            "D57d": {
                "T1": Decimal("0.29685"),
                "T2": Decimal("0.11444")
            },
            "D61d": {
                "T1": Decimal("2.19927"),
                "T2": Decimal("0.11444")
            }
        }
    }
}

TARIFF = {
    "AKU8V1": ((0, 6), (19, 21)),
    "AKU8V2": ((0, 5), (18, 20), (23, 24)),
    "AKU8V3": ((0, 4), (17, 19), (22, 24)),
    "AKU8V4": ((0, 6), (22, 24)),
    "AKU8V5": ((1, 6), (18, 21)),
    "AKU8V6": ((3, 6), (15, 18), (21, 23)),
    "EMOV1": ((2, 6), (20, 24)),
    "AKU16V1": ((0, 8), (13, 16), (19, 24)),
    "PTV1": ((0, 9), (10, 11), (12, 13), (14, 16), (17, 24)),
    "PTV2": ((0, 6), (7, 9), (10, 13), (14, 16), (17, 24)),
    "PTV3": ((0, 8), (9, 12), (13, 15), (16, 19), (20, 24)),
    "PTV4": ((0, 10), (11, 12), (13, 14), (15, 17), (18, 24)),
    "TČV1": ((0, 9), (10, 12), (14, 24)),
    "EVV1": ((0, 6), (7, 9), (10, 13), (14, 16), (17, 24)),
    "EVV2": ((0, 8), (9, 12), (13, 15), (16, 19), (20, 24)),
    "EVV3": ((0, 10), (11, 12), (13, 14), (15, 17), (18, 24)),
    "VIKV1": ((), (), (), (), ((12, 24)), ((0, 24)), ((0, 22))),
    "CHLV1": ((time(hour = 3), time(hour = 23))),
    "CHLV2": ((time(hour = 0), time(hour = 4)), (time(hour = 6), time(hour = 22))),
    "CHLV3": ((time(hour = 0), time(hour = 4, minute = 30)), (time(hour = 8, minute = 30), time(hour = 23, minute = 59, second = 59))),
    "CHLV4": ((time(hour = 0), time(hour = 14)), (time(hour = 18), time(hour = 23, minute = 59, second = 59))),
    "ZAV1": (((time(hour = 0), time(hour = 6)), (time(hour = 10), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 6)), (time(hour = 10), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 6)), (time(hour = 10), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 6)), (time(hour = 10), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 6)), (time(hour = 10), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 23, minute = 59, second = 59)))),
    "ZAV2": (((time(hour = 0), time(hour = 3)), (time(hour = 7), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 3)), (time(hour = 7), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 3)), (time(hour = 7), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 3)), (time(hour = 7), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 3)), (time(hour = 7), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 23, minute = 59, second = 59))), ((time(hour = 0), time(hour = 23, minute = 59, second = 59)))),
    "VYRV1": ((time(hour = 0), time(hour = 6)), (time(hour = 10), time(hour = 16)), (time(hour = 20), time(hour = 23, minute = 59, second = 59))),
    "VYRV2": ((time(hour = 0), time(hour = 7)), (time(hour = 15), time(hour = 23, minute = 59, second = 59))),
    "VYRV3": ((time(hour = 0), time(hour = 7)), (time(hour = 10), time(hour = 18)), (time(hour = 23), time(hour = 23, minute = 59, second = 59)))
}

URL_CEZ = "https://www.cezdistribuce.cz/webpublic/distHdo/adam/containers/{0}?&code={1}"
CEZ_TUPLES = (("CAS_ZAP_1", "CAS_VYP_1"), ("CAS_ZAP_2", "CAS_VYP_2"), ("CAS_ZAP_3", "CAS_VYP_3"), ("CAS_ZAP_4", "CAS_VYP_4"), ("CAS_ZAP_5", "CAS_VYP_5"), ("CAS_ZAP_6", "CAS_VYP_6"), ("CAS_ZAP_7", "CAS_VYP_7"), ("CAS_ZAP_8", "CAS_VYP_8"), ("CAS_ZAP_9", "CAS_VYP_9"), ("CAS_ZAP_10", "CAS_VYP_10"))

URL_EGD_REGION = "https://hdo.distribuce24.cz/region"
URL_EGD = "https://hdo.distribuce24.cz/casy"
